#!/usr/bin/env python3
"""sim/program-read-legs -- program-leg / read-leg benches and margin tables.

Run through the shared entry point:

    python3 sim/run_corners.py program-read-legs [--benches ...] [--probe]

Unlike sim/cell-device-characterization (which drives ngspice itself), this
experiment expresses every grid as a ``klt sim`` request (corners axes), so a
multi-corner sweep goes to whichever backend ``KLT_SIM_BACKEND`` / ``--backend``
selects -- the Spot batch fleet on the dispatch hosts. This script never loops
over ngspice itself. ``--probe`` runs ONE typical corner on the ``local``
backend, as a debug aid only; its output is not evidence and is not recorded.

Benches (see README.md):
    exclusion        PROG_EN/READ_EN states x VPP x bit-line level, both legs
                     on one bit line
    ballast          program leg alone, BL held at an assumed compliance voltage
    margin1/2/3      read decision per candidate/region, unprogrammed and
                     programmed sides, access sizing min/2x

Stdlib only (klt is the only external tool; set KLT to override its path).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(THIS_DIR))

import benches as B  # noqa: E402
from harness import evidence_store as ES  # noqa: E402
from harness import klt as K  # noqa: E402
from harness import numfmt as NF  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402

WORK = THIS_DIR / ".work"          # git-ignored scratch (host-specific paths)
REL_NETLISTS = "../../../design/netlists"   # from .work/ or testbench/

TEMPS = (-40, 27, 125)
# (corner name, MOS section, moscap section, res section)
PROCESS = (
    ("typical", "typical", "moscap_typical", "res_typical"),
    ("ff", "ff", "moscap_ff", "res_ff"),
    ("ss", "ss", "moscap_ss", "res_ss"),
    ("fs", "fs", "moscap_typical", "res_typical"),
    ("sf", "sf", "moscap_typical", "res_typical"),
)
KLT_TIMEOUT_S = 3 * 3600
# klt-side capacity patience, complementary to K.BACKOFF: capacity_wait_s
# makes klt wait *before* refusing a launch (batch_no_capacity / the fleet's
# shared concurrency cap); K.BACKOFF resubmits the same request *after* a
# refusal that still happens. 1800 s matches the sibling driver
# (sim/cell-breakdown-model's BATCH_OPTS); the fleet rule's floor is 600 s.
# runner_version_check is deliberately not copied: it works around a runner
# image skew this driver does not have.
BATCH_OPTS = {"capacity_wait_s": 1800}


def process_bundles(candidate_has_smbb: bool, preamble: str, design_section: str = "design") -> list[dict]:
    out = []
    for name, mos, moscap, res in PROCESS:
        sections: list = [{"lib": preamble, "section": design_section}, mos]
        if candidate_has_smbb:
            sections.append({"lib": "libs.tech/ngspice/smbb000149.ngspice", "section": mos})
        sections += [moscap, res]
        out.append({"name": name, "sections": sections})
    return out


def make_request(netlist_name: str, measurements: list[dict], smbb: bool, preamble: str,
                 temps=TEMPS, processes=None, vdd_points=None) -> dict:
    vdd = list(vdd_points or B.VDD_POINTS)
    clamp = [round(B.VCLAMP_NOM * v / B.VDD_NOM, 4) for v in vdd]
    bundles = process_bundles(smbb, preamble)
    if processes is not None:
        bundles = [b for b in bundles if b["name"] in processes]
    return {
        "netlist": netlist_name,
        "models": {"pdk": "gf180mcuD", "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": bundles,
            "supply_v": {"VDD": [round(v, 4) for v in vdd], "VCLAMP": clamp},
            "temperature_c": list(temps),
        },
        "analysis": {"kind": "op", "args": ""},
        "measurements": measurements,
        "options": {"keep_artifacts": True, "timeout_s": 300, "stage_model_inputs": True},
        "batch": dict(BATCH_OPTS),
    }


# Monte Carlo corner points (one request each, so the sweep is these points and
# not a cross product): (label, process bundle, temperature C, VDD V).
MC_POINTS = (
    ("typ", "typical", 27, 3.30),
    ("slow_cold", "ss", -40, 2.97),     # slow/cold selected cell, low supply
    ("fast_hot", "ff", 125, 3.63),      # fast/hot selected cell, high supply
)
MC_N = 200          # samples per corner point (per instance: each bench holds >= 4 independent draws)
MC_SEED = 20261016
MC_CONF = 0.95      # one-sided confidence for the decision-yield bound


def make_mc_request(netlist_name: str, measurements: list[dict], smbb: bool, preamble: str,
                    point: tuple, n: int = MC_N, seed: int = MC_SEED) -> dict:
    """A klt `monte_carlo` request (vary=mismatch) at ONE named PVT point."""
    _label, proc, temp, vdd = point
    req = make_request(netlist_name, measurements, smbb, preamble, temps=(temp,),
                       processes=(proc,), vdd_points=(vdd,))
    for b in req["corners"]["process"]:
        b["sections"][0] = {"lib": preamble, "section": "design_mm"}
    req["monte_carlo"] = {"n": n, "seed": seed, "vary": "mismatch"}
    return req


def mc_bench_defs() -> dict:
    """name -> (netlist text, measurements, needs smbb, candidate or None)."""
    defs = {}
    n, m = B.offset_bench(REL_NETLISTS)
    defs["offset"] = (n, m, False, None)
    for k in (1, 2, 3):
        n, m = B.margin_bench(k, REL_NETLISTS)
        defs[f"margin{k}"] = (n, m, k == 2, k)
    n, m = B.margin_bench(3, REL_NETLISTS, iref=B.I_REF_LOW)
    defs["margin3_lowiref"] = (n, m, False, 3)
    return defs


def bench_defs() -> dict:
    """name -> (netlist text, measurements, needs smbb, candidate or None)."""
    defs = {}
    n, m = B.exclusion_bench(REL_NETLISTS)
    defs["exclusion"] = (n, m, False, None)
    n, m = B.ballast_bench(REL_NETLISTS)
    defs["ballast"] = (n, m, False, None)
    for k in (1, 2, 3):
        n, m = B.margin_bench(k, REL_NETLISTS)
        defs[f"margin{k}"] = (n, m, k == 2, k)
    n, m = B.margin_bench(3, REL_NETLISTS, iref=B.I_REF_LOW)
    defs["margin3_lowiref"] = (n, m, False, 3)
    return defs


def bench_iref(name: str) -> float:
    return B.I_REF_LOW if name.endswith("lowiref") else B.I_REF


def corner_label(c: dict) -> str:
    """repo corner-id: <process>_<temp>c_<supply>, supply = vdd<volts>v."""
    vdd = c["supply_v"]["VDD"]
    return f"{c['process']}_{int(c['temperature_c'])}c_vdd{vdd:.2f}v".replace(".", "p")


# ---------------------------------------------------------------------------
# klt invocation
# ---------------------------------------------------------------------------

def run_klt(request_path: Path, outdir: Path, backend: str | None) -> tuple[dict | None, str]:
    env = dict(os.environ)
    env.setdefault("PDK_ROOT", str(Path.home() / ".ciel"))
    return K.run_klt(request_path, outdir, backend, klt_cmd=[os.environ.get("KLT", "klt")],
                     timeout_s=KLT_TIMEOUT_S, env=env, retry=K.BACKOFF)


def meas_table(response: dict) -> dict[str, dict[str, float | None]]:
    """corner label -> {measurement name -> value}."""
    out = {}
    for c in response["corners"]:
        out[corner_label(c)] = {m["name"]: m.get("value") for m in c["measurements"]}
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

I_DRIVE = 1e-6  # A: a leg "drives"/"sinks" the bit line above this


def analyze_exclusion(tab: dict) -> dict:
    cases = B.exclusion_cases()
    rows, bad = [], []
    worst = {"off_leak": (0.0, None), "on_prog_min": (1e9, None), "on_read_min": (1e9, None)}
    for lab, v in tab.items():
        ok_corner = True
        for st, vpp, bl in cases:
            t = B.case_tag(st, vpp, bl)
            ip, ir = v.get(f"ipg_{t}"), v.get(f"ird_{t}")
            if ip is None or ir is None:
                ok_corner = False
                bad.append((lab, t, "no value"))
                continue
            p_on, r_on = abs(ip) > I_DRIVE, abs(ir) > I_DRIVE
            if bl == "0":
                want = (st == (1, 0), st == (0, 1))     # (program drives, read drives)
            else:
                want = (False, False)
            if (p_on, r_on) != want or (p_on and r_on):
                ok_corner = False
                bad.append((lab, t, f"prog={ip:.3e} read={ir:.3e}"))
            if not want[0]:
                if abs(ip) > worst["off_leak"][0]:
                    worst["off_leak"] = (abs(ip), (lab, t, "program leg"))
            else:
                if abs(ip) < worst["on_prog_min"][0]:
                    worst["on_prog_min"] = (abs(ip), (lab, t, "program leg"))
            if not want[1]:
                if abs(ir) > worst["off_leak"][0]:
                    worst["off_leak"] = (abs(ir), (lab, t, "read leg"))
            else:
                if abs(ir) < worst["on_read_min"][0]:
                    worst["on_read_min"] = (abs(ir), (lab, t, "read leg"))
        rows.append((lab, ok_corner))
    return {"rows": rows, "bad": bad, "worst": worst, "ncases": len(cases)}


def analyze_ballast(tab: dict) -> dict:
    out = {}
    for vpp in B.VPP_STEPS:
        tcomp = f"vpp{vpp:.1f}_comp".replace(".", "p")
        tshort = f"vpp{vpp:.1f}_short".replace(".", "p")
        per_corner = {}
        for lab, v in tab.items():
            ic, vrt, vbl = v.get(f"ipg_{tcomp}"), v.get(f"vrbtop_{tcomp}"), v.get(f"vbl_{tcomp}")
            ish = v.get(f"ipg_{tshort}")
            if None in (ic, vrt, vbl, ish) or ic == 0:
                continue
            per_corner[lab] = dict(i_comp=ic, i_short=ish, rb=(vrt - vbl) / ic, rsw=(vpp - vrt) / ic)
        out[vpp] = per_corner
    return out


def analyze_margin(tab: dict, iref: float) -> dict:
    res = {}
    for lab, v in tab.items():
        vdd = v.get("vddm_U_min")
        row = {}
        for side, _ in B.SIDES:
            for sz, _m in B.SIZINGS:
                t = f"{side}_{sz}"
                i = v.get(f"ird_{t}")
                rd = v.get(f"vrdata_{t}")
                if i is None or rd is None or vdd is None:
                    row[t] = None
                    continue
                if side == "U":
                    margin = iref / max(abs(i), 1e-18)
                    correct = rd < vdd / 2
                else:
                    margin = abs(i) / iref
                    correct = rd > vdd / 2
                row[t] = dict(i=i, margin=margin, ok=correct, vbl=v.get(f"vbl_{t}"), rdata=rd)
        res[lab] = row
    return res


def sci(x) -> str:
    return NF.sci(x, digits=3)


# ---------------------------------------------------------------------------
# Record rendering
# ---------------------------------------------------------------------------

def render_exclusion(a: dict) -> str:
    n_ok = sum(1 for _, ok in a["rows"] if ok)
    L = [f"- Corners where every state/VPP/BL case matched the expected exclusive-drive pattern: "
         f"**{n_ok}/{len(a['rows'])}** ({a['ncases']} cases per corner; a leg \"drives\" above "
         f"{I_DRIVE:.0e} A).",
         f"- Largest current through a leg that should be OFF: **{sci(a['worst']['off_leak'][0])} A** "
         f"at {a['worst']['off_leak'][1]}.",
         f"- Smallest current through a leg that should be ON (BL at 0 V): program "
         f"**{sci(a['worst']['on_prog_min'][0])} A** at {a['worst']['on_prog_min'][1]}; read "
         f"**{sci(a['worst']['on_read_min'][0])} A** at {a['worst']['on_read_min'][1]}."]
    if a["bad"]:
        L.append("- **Violations / unresolved cases**:")
        for lab, t, msg in a["bad"][:40]:
            L.append(f"  - `{lab}` `{t}`: {msg}")
        if len(a["bad"]) > 40:
            L.append(f"  - ... {len(a['bad']) - 40} more")
    else:
        L.append("- No violations: in no corner, state, VPP or bit-line level did both legs drive the "
                 "bit line, and (PROG_EN, READ_EN) = (1, 1) left both legs OFF.")
    return "\n".join(L)


def render_ballast(a: dict) -> str:
    L = []
    need = {}
    for vpp, pc in a.items():
        if not pc:
            L.append(f"- VPP = {vpp:.1f} V: no resolved corners.")
            continue
        rb_min_lab = min(pc, key=lambda k: pc[k]["rb"])
        rb_max_lab = max(pc, key=lambda k: pc[k]["rb"])
        i_max_lab = max(pc, key=lambda k: pc[k]["i_comp"])
        sh_lab = max(pc, key=lambda k: pc[k]["i_short"])
        req = (vpp - B.V_COMPLIANCE_ASSUMED) / B.I_TARGET_MAX_ASSUMED
        need[vpp] = req
        L.append(
            f"| {vpp:.1f} | {req:.0f} | {pc[rb_min_lab]['rb']:.0f} (`{rb_min_lab}`) | "
            f"{pc[rb_max_lab]['rb']:.0f} (`{rb_max_lab}`) | {pc[i_max_lab]['rsw']:.0f} | "
            f"{pc[i_max_lab]['i_comp']*1e3:.3f} (`{i_max_lab}`) | "
            f"{pc[sh_lab]['i_short']*1e3:.3f} (`{sh_lab}`) | "
            f"{'yes' if pc[rb_min_lab]['rb'] >= req else 'NO'} |")
    head = ("| VPP (V) | required R_ballast >= (VPP - V_comp)/I_target_max (ohm) | R_ballast min over PVT (ohm) | "
            "R_ballast max over PVT (ohm) | R_switch at max-current corner (ohm) | "
            "max I at BL = V_comp (mA) | max I with BL shorted to 0 V (mA) | inequality met at min R? |\n"
            "|---|---|---|---|---|---|---|---|")
    return head + "\n" + "\n".join(x for x in L if x.startswith("|"))


def render_margin(cand: int, a: dict) -> str:
    c = B.CANDIDATES[cand]
    out = []
    keys = [f"{s}_{z}" for s, _ in B.SIDES for z, _m in B.SIZINGS]
    names = {"U": "unprogrammed", "Plo": f"programmed, R_prog={B.R_PROG_ASSUMED['lo']/1e3:.0f}k (ASSUMED)",
             "Phi": f"programmed, R_prog={B.R_PROG_ASSUMED['hi']/1e3:.0f}k (ASSUMED)"}
    # worst-case summary
    out.append("| side | access sizing | worst margin (x) | at corner | I_read at worst (A) | "
               "BL at worst (V) | decisions correct |\n|---|---|---|---|---|---|---|")
    for side, _ in B.SIDES:
        for sz, _m in B.SIZINGS:
            t = f"{side}_{sz}"
            vals = {lab: r[t] for lab, r in a.items() if r.get(t)}
            if not vals:
                out.append(f"| {names[side]} | {sz} | n/a | n/a | n/a | n/a | n/a |")
                continue
            wl = min(vals, key=lambda k: vals[k]["margin"])
            okc = sum(1 for x in vals.values() if x["ok"])
            out.append(f"| {names[side]} | {sz} | {vals[wl]['margin']:.3g} | `{wl}` | {sci(vals[wl]['i'])} | "
                       f"{vals[wl]['vbl']:.3f} | {okc}/{len(vals)} |")
    out.append("")
    out.append("Per-corner table (margin ratio; `!` marks a wrong RDATA decision at that point):\n")
    out.append("| corner | " + " | ".join(f"{s}/{z}" for s, _ in B.SIDES for z, _m in B.SIZINGS) + " |")
    out.append("|---|" + "---|" * len(keys))
    for lab in sorted(a):
        cells = []
        for t in keys:
            x = a[lab].get(t)
            cells.append("n/a" if x is None else f"{x['margin']:.3g}{'' if x['ok'] else '!'}")
        out.append(f"| `{lab}` | " + " | ".join(cells) + " |")
    return "\n".join(out)


def env_summary(resp: dict) -> str:
    env = resp.get("environment", {})
    remote = env.get("remote")
    return f"engine {env.get('engine')} {env.get('engine_version')}; remote={json.dumps(remote) if remote else 'none'}"


# ---------------------------------------------------------------------------
# Monte Carlo (mismatch) variant: statistics, request fan-out, record
# ---------------------------------------------------------------------------

def mc_table(response: dict) -> dict[str, dict[str, float | None]]:
    """sample label -> {measurement name -> value} (one request = one PVT point)."""
    out = {}
    for c in response["corners"]:
        idx = (c.get("monte_carlo") or {}).get("sample_index", len(out))
        out[f"s{idx:04d}"] = {m["name"]: m.get("value") for m in c["measurements"]}
    return out


def cp_lower(k: int, n: int, conf: float = MC_CONF) -> float:
    """One-sided Clopper-Pearson lower bound on a success probability: the p with
    P(X >= k | n, p) = 1 - conf (bisection; stdlib only)."""
    if n == 0 or k == 0:
        return 0.0
    if k == n:
        return (1.0 - conf) ** (1.0 / n)
    from math import comb
    alpha = 1.0 - conf

    def tail(p: float) -> float:        # P(X >= k)
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))

    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if tail(mid) > alpha:
            hi = mid
        else:
            lo = mid
    return lo


def pctl(vals: list[float], q: float) -> float:
    v = sorted(vals)
    if not v:
        return float("nan")
    pos = q / 100 * (len(v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def mean_sigma(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    m = sum(vals) / n
    return m, (sum((x - m) ** 2 for x in vals) / (n - 1)) ** 0.5 if n > 1 else 0.0


def analyze_mc_margin(tab: dict, iref: float) -> dict:
    """side_sizing -> decision count, yield bound and margin-ratio spread, over samples."""
    rows = analyze_margin(tab, iref)
    out = {}
    for side, _ in B.SIDES:
        for sz, _m in B.SIZINGS:
            t = f"{side}_{sz}"
            xs = [r[t] for r in rows.values() if r.get(t)]
            if not xs:
                out[t] = None
                continue
            k = sum(1 for x in xs if x["ok"])
            marg = [x["margin"] for x in xs]
            mu, sd = mean_sigma([x["i"] for x in xs])
            out[t] = dict(n=len(xs), k=k, lb=cp_lower(k, len(xs)), mmin=min(marg),
                          p1=pctl(marg, 1), med=pctl(marg, 50), i_mu=mu, i_sd=sd)
    return out


def analyze_mc_offset(tab: dict) -> dict:
    vals = [v[f"isense_o{k}"] for v in tab.values() for k in range(B.OFFSET_INSTANCES)
            if v.get(f"isense_o{k}") is not None]
    mu, sd = mean_sigma(vals)
    return dict(n=len(vals), mu=mu, sd=sd, lo=min(vals), hi=max(vals),
                absmax=max(abs(x) for x in vals), p1=pctl(vals, 1), p99=pctl(vals, 99))


def render_mc_offset(per_point: dict) -> str:
    L = ["| corner point | draws | mean (A) | sigma (A) | sigma / I_ref | min (A) | max (A) | mean +- 3 sigma / I_ref |",
         "|---|---|---|---|---|---|---|---|"]
    for label, a in per_point.items():
        if a is None:
            L.append(f"| {label} | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        L.append(f"| {label} | {a['n']} | {sci(a['mu'])} | {sci(a['sd'])} | {a['sd']/B.I_REF:.1%} | "
                 f"{sci(a['lo'])} | {sci(a['hi'])} | "
                 f"{(a['mu']-3*a['sd'])/B.I_REF:+.1%} .. {(a['mu']+3*a['sd'])/B.I_REF:+.1%} |")
    return "\n".join(L)


def render_mc_margin(cand: int, per_point: dict) -> str:
    names = {"U": "unprogrammed", "Plo": f"programmed, R_prog={B.R_PROG_ASSUMED['lo']/1e3:.0f}k (ASSUMED)",
             "Phi": f"programmed, R_prog={B.R_PROG_ASSUMED['hi']/1e3:.0f}k (ASSUMED)"}
    L = [f"| corner point | side | access sizing | samples | correct | yield (point) | "
         f"{MC_CONF:.0%} lower bound | margin x: min / 1% / median | I_read mean +- sigma (A) |",
         "|---|---|---|---|---|---|---|---|---|"]
    for label, a in per_point.items():
        for side, _ in B.SIDES:
            for sz, _m in B.SIZINGS:
                x = (a or {}).get(f"{side}_{sz}")
                if x is None:
                    L.append(f"| {label} | {names[side]} | {sz} | n/a | n/a | n/a | n/a | n/a | n/a |")
                    continue
                L.append(f"| {label} | {names[side]} | {sz} | {x['n']} | {x['k']} | {x['k']/x['n']:.1%} | "
                         f"{x['lb']:.1%} | {x['mmin']:.3g} / {x['p1']:.3g} / {x['med']:.3g} | "
                         f"{sci(x['i_mu'])} +- {sci(x['i_sd'])} |")
    return "\n".join(L)


def run_mc(args, pdk, preamble: Path) -> int:
    from concurrent.futures import ThreadPoolExecutor
    wanted = [b.strip() for b in args.benches.split(",") if b.strip()]
    defs = mc_bench_defs()
    unknown = [b for b in wanted if b not in defs]
    if unknown:
        print(f"ERROR: unknown MC benches {unknown}; known: {sorted(defs)}", file=sys.stderr)
        return 2
    backend = "local" if args.probe else args.backend
    n_samples = 1 if args.probe else args.mc_n
    points = MC_POINTS[:1] if args.probe else MC_POINTS
    dirty = R.git_is_dirty(REPO_ROOT)
    record_id = R.allocate_record_id(THIS_DIR, REPO_ROOT)
    snap_dir = THIS_DIR / "netlist-snapshots" / record_id
    corner_dir = THIS_DIR / "corners" / record_id

    jobs = []
    for name in wanted:
        text, meas, smbb, _cand = defs[name]
        netlist_path = WORK / f"{name}.sp"
        netlist_path.write_text(text.replace(f".include {B.PDK_DESIGN}\n", ""))
        for pt in points:
            req = make_mc_request(f"{name}.sp", meas, smbb, str(preamble), pt, n=n_samples)
            req_path = WORK / f"{name}.{pt[0]}.mc.request.json"
            req_path.write_text(json.dumps(req, indent=1))
            out = (WORK / "probe" / f"mc_{name}_{pt[0]}") if args.probe else (corner_dir / f"{name}.{pt[0]}")
            out.mkdir(parents=True, exist_ok=True)
            jobs.append((name, pt, req_path, out))

    def submit(job):
        name, pt, req_path, out = job
        t0 = time.time()
        # Fleet-refusal retry is the harness's (K.BACKOFF, passed by run_klt above);
        # nothing else is retried, and a batch submit is never replayed locally.
        resp, err = run_klt(req_path, out, backend)
        print(f"== {name}/{pt[0]}: {time.time() - t0:.0f}s status="
              f"{(resp or {}).get('status')} units={(resp or {}).get('corner_count')} "
              f"pass={(resp or {}).get('passed')} err={(resp or {}).get('errored')}", flush=True)
        return job, resp, err

    # Submissions only go through klt (batch fleet via KLT_SIM_BACKEND); the thread pool just
    # overlaps the waits. No local ngspice grid is ever started here (--probe is one unit).
    with ThreadPoolExecutor(max_workers=1 if args.probe else 4) as ex:
        results = list(ex.map(submit, jobs))

    responses: dict[tuple, dict] = {}
    failures: dict[tuple, str] = {}
    for (name, pt, req_path, out), resp, err in results:
        key = (name, pt[0])
        if resp is None or "corners" not in resp:
            failures[key] = (err or "no response").strip()[-1500:]
        elif not resp.get("passed"):
            remote = resp.get("environment", {}).get("remote") or {}
            failures[key] = (f"no sample resolved; diagnostics={resp.get('diagnostic_counts', {}).get('by_code', {})}; "
                             f"job={remote.get('job_id')}")
        else:
            responses[key] = resp
    for key, msg in failures.items():
        print(f"   FAILED {key}: {msg[:300]}", file=sys.stderr)
    if args.probe:
        for key, resp in responses.items():
            print(key, json.dumps(list(mc_table(resp).items())[:1])[:800])
        return 1 if failures else 0
    if not responses:
        shutil.rmtree(corner_dir, ignore_errors=True)
        print("ERROR: no MC request resolved; no record written. Failures:\n  "
              + "\n  ".join(f"{k}: {v}" for k, v in failures.items()), file=sys.stderr)
        return 1

    snap_dir.mkdir(parents=True, exist_ok=True)
    for (name, pt, req_path, out) in jobs:
        key = (name, pt[0])
        if key not in responses:
            continue
        if not (snap_dir / f"{name}.sp").exists():
            R.write_once(snap_dir / f"{name}.sp", (WORK / f"{name}.sp").read_text())
        req_norm = json.loads(req_path.read_text())
        for b in req_norm["corners"]["process"]:
            for sec in b["sections"]:
                if isinstance(sec, dict) and sec["lib"].endswith("preamble.lib"):
                    sec["lib"] = "sim/program-read-legs/models/preamble.lib"
        R.write_once(snap_dir / f"{name}.{pt[0]}.mc.request.json", json.dumps(req_norm, indent=1) + "\n")
        text, full_sha = R.klt_report_payload(responses[key], indent=1)
        R.write_once(corner_dir / f"{name}.{pt[0]}.report.json", text)
        R.write_once(corner_dir / f"{name}.{pt[0]}.report.json.sha256", full_sha + "\n")
        for stale in [*out.rglob("corner.cir"), *out.rglob("ngspice.log")]:
            stale.unlink()      # per-sample decks/logs: the report keeps values, seeds and diagnostics

    sections, unevidenced, remotes = [], [], {}
    for name in wanted:
        per_point = {}
        for pt in points:
            key = (name, pt[0])
            label = f"{pt[0]} ({pt[1]}, {pt[2]} C, VDD {pt[3]:.2f} V)"
            resp = responses.get(key)
            if resp is None:
                per_point[label] = None
                unevidenced.append(f"{name}/{pt[0]}: klt sim did not return a report ({failures.get(key, 'not run')[:200]})")
                continue
            remotes[f"{name}/{pt[0]}"] = (resp.get("environment", {}).get("remote") or {}).get("job_id")
            tab = mc_table(resp)
            short = [lab for lab, v in tab.items() if any(x is None for x in v.values())]
            if short or len(tab) != args.mc_n:
                unevidenced.append(f"{name}/{pt[0]}: {len(tab)} of {args.mc_n} samples returned, "
                                   f"{len(short)} with a missing measurement")
            tab = {k: v for k, v in tab.items() if k not in short}
            if name == "offset":
                per_point[label] = analyze_mc_offset(tab) if tab else None
            else:
                per_point[label] = analyze_mc_margin(tab, bench_iref(name)) if tab else None
        if name == "offset":
            sections.append(("Sense-mirror current offset vs I_ref", render_mc_offset(per_point)))
        else:
            k = defs[name][3]
            c = B.CANDIDATES[k]
            sections.append((f"Read decision under mismatch, Candidate {k} (Region {c['region']}), "
                             f"I_ref = {bench_iref(name):.0e} A", render_mc_margin(k, per_point)))
    rec = render_mc_record(record_id, pdk, dirty, args.mc_n, sections, unevidenced, failures, remotes)
    R.write_once(THIS_DIR / "records" / f"{record_id}.md", rec)
    print(f"record: sim/program-read-legs/records/{record_id}.md")
    rc = 1 if (failures or unevidenced) else 0
    rc |= ES.publish_for_runner("program-read-legs", record_id, THIS_DIR / "corners" / record_id, REPO_ROOT)
    return rc


def render_mc_record(record_id, pdk, dirty, n, sections, unevidenced, failures, remotes) -> str:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pts = "; ".join(f"`{p[0]}` = {p[1]} / {p[2]} C / VDD {p[3]:.2f} V (VCLAMP tracking)" for p in MC_POINTS)
    L = [f"# Record {record_id}", "",
         f"- **Record ID**: {record_id}",
         "- **Claim**: `spec/architecture.md` 4 (read decision), the part the corner-only records cannot "
         "bound: random mismatch of the sense mirror against `I_ref`. Per candidate/region, "
         "unprogrammed and programmed sides in separate rows, never averaged. Regions I/II/III = "
         "Candidates 1/2/3 (`spec/split-axis-plan.md`).",
         f"- **Netlist provenance**: `design/netlists/{{leg_interlock,program_leg,read_leg,cell_candidate1..3}}.spice`, "
         f"{'DIRTY' if dirty else 'clean'} working tree at run time. Frozen bench netlists and the normalised "
         f"`klt sim` requests: `sim/program-read-legs/netlist-snapshots/{record_id}/`.",
         f"- **Method**: one `klt sim` request per bench per corner point, each with `monte_carlo = "
         f"{{n: {n}, seed: {MC_SEED}, vary: \"mismatch\"}}` on the batch backend (no hand-launched ngspice). "
         f"Corner points: {pts}. The slow/cold and fast/hot points are the selected-cell extremes; the "
         "recorded `I_sneak_max` floor is applied at every point (as in the corner-only record). "
         "`sw_stat_mismatch = 1` is set by the `design_mm` section of `models/preamble.lib` "
         "(PDK default 0); `sw_stat_global` stays 0, so only intra-die mismatch is sampled, on top of "
         "the named corner.",
         "- **What is sampled**: the PDK's per-instance MOS mismatch (`delvto`, `mulu0`, Pelgrom-scaled) on "
         "**every** MOS in the bench, because the PDK exposes one global switch, not a per-instance one. "
         "That covers the sense mirror (`MPI`/`MPO`/`MNI`/`MNO`), the clamp and read switch, the latch "
         "inverters and the access device of the selected cell. The offset bench contains the read leg "
         "only. Poly-resistor and MIM mismatch are not sampled by this PDK deck; the assumed filament "
         "resistor is therefore a fixed value.",
         "- **Statistics**: the decision yield is the fraction of samples whose `RDATA` is correct; the "
         f"stated bound is the one-sided {MC_CONF:.0%} Clopper-Pearson lower bound. With N = {n} and all "
         f"samples correct the bound is {cp_lower(n, n):.1%}; a yield above that cannot be claimed from this N. "
         "Each sample of a margin bench holds six independent read legs (3 sides x 2 access sizings), so "
         "every row has N independent draws; the offset bench holds "
         f"{B.OFFSET_INSTANCES} independent legs per sample. Seeds are derived by klt from the stated seed "
         "(reproducible).",
         "- **Mirror offset definition**: read leg alone, bit line sunk at exactly `I_ref`, `SENSE` forced to "
         "VDD/2; the current through the forcing source is `I(MPO) - I(MNO)`, zero for a matched mirror. "
         "The decision threshold is `I_ref` plus this offset.",
         "- **Assumed / placeholder inputs**: programmed-state resistance 10 kohm and 100 kohm **ASSUMED** "
         "(no breakdown model; `sim/cell-breakdown-model/` not used here), so every programmed-side row is "
         "**conditional on the assumed R_prog**. `I_ref` and `VCLAMP` are bench-supplied. Access sizing "
         "\"min\" is the committed netlist default `wacc`, not the ratified split-axis level.",
         f"- **Region III**: Candidate 3's read path is unproven (tracked in #75); its programmed-side rows are "
         "reported as measured and are **not** a pass.",
         f"- **PDK**: `{pdk.variant}`, open_pdks `{pdk.revision}`.",
         f"- **Fleet job ids** (`environment.remote.job_id` per request): "
         + (", ".join(f"`{k}` {v}" for k, v in sorted(remotes.items())) or "none recorded"),
         "- **Result**:", ""]
    for title, body in sections:
        L += [f"### {title}", "", body, ""]
    if unevidenced or failures:
        L += ["### Not evidenced by this record", ""]
        L += [f"- {u}" for u in unevidenced]
        L += [""]
    L += ["- **Links**:",
          "  - Benches: `sim/program-read-legs/benches.py` (`margin_bench`, `offset_bench`); runner `run_experiment.py --mc`",
          f"  - Frozen netlists / requests: `sim/program-read-legs/netlist-snapshots/{record_id}/`",
          f"  - Full klt reports (per-sample measurements, seeds, diagnostics): `sim/program-read-legs/corners/{record_id}/` (per-sample ngspice logs are not kept)",
          f"- **Timestamp / author**: {now}, agent-builder",
          "- **Supersedes**: (none -- adds mismatch statistics to the corner-only record "
          "`records/20261015-151616-d3df921.md`, which is unchanged)", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benches", default="exclusion,ballast,margin1,margin2,margin3,margin3_lowiref")
    ap.add_argument("--backend", default=None, help="klt sim backend (default: $KLT_SIM_BACKEND, then request/local)")
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="ONE typical corner on the local backend; debug only, nothing recorded")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--mc", action="store_true",
                    help="mismatch Monte Carlo variant (klt `monte_carlo`, vary=mismatch) of the margin "
                         "benches + the mirror-offset bench; default benches then become "
                         "offset,margin1,margin2,margin3,margin3_lowiref")
    ap.add_argument("--mc-n", type=int, default=MC_N, help="samples per corner point (default %(default)s)")
    args = ap.parse_args(argv)
    if args.mc and args.benches == ap.get_default("benches"):
        args.benches = "offset,margin1,margin2,margin3,margin3_lowiref"

    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if shutil.which(os.environ.get("KLT", "klt")) is None:
        print("ERROR: klt not found on PATH (set KLT to override).", file=sys.stderr)
        return 3
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK OK.")
        return 0

    WORK.mkdir(exist_ok=True)
    # Host-specific preamble: design.ngspice include with the resolved absolute path.
    preamble = WORK / "preamble.lib"
    preamble.write_text(
        (THIS_DIR / "models" / "preamble.lib").read_text().replace(
            "$PDK_ROOT/gf180mcuD", str(pdk.variant_dir)))

    if args.mc:
        return run_mc(args, pdk, preamble)

    wanted = [b.strip() for b in args.benches.split(",") if b.strip()]
    defs = bench_defs()
    unknown = [b for b in wanted if b not in defs]
    if unknown:
        print(f"ERROR: unknown benches {unknown}; known: {sorted(defs)}", file=sys.stderr)
        return 2

    backend = "local" if args.probe else args.backend
    dirty = R.git_is_dirty(REPO_ROOT)
    record_id = R.allocate_record_id(THIS_DIR, REPO_ROOT)
    responses: dict[str, dict] = {}
    failures: dict[str, str] = {}
    snap_dir = THIS_DIR / "netlist-snapshots" / record_id
    corner_dir = THIS_DIR / "corners" / record_id

    for name in wanted:
        text, meas, smbb, _cand = defs[name]
        netlist_path = WORK / f"{name}.sp"
        netlist_path.write_text(text.replace(f".include {B.PDK_DESIGN}\n", ""))
        if args.probe:
            req = make_request(f"{name}.sp", meas, smbb, str(preamble), temps=(27,),
                               processes=("typical",), vdd_points=(B.VDD_NOM,))
        else:
            req = make_request(f"{name}.sp", meas, smbb, str(preamble))
        req_path = WORK / f"{name}.request.json"
        req_path.write_text(json.dumps(req, indent=1))
        out = (WORK / "probe" / name) if args.probe else (corner_dir / name)
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        print(f"== {name}: klt sim ({len(req['corners']['process']) * len(req['corners']['temperature_c']) * len(req['corners']['supply_v']['VDD'])} corners, backend={backend or 'env/default'}) ==", flush=True)
        resp, err = run_klt(req_path, out, backend)
        print(f"   {time.time() - t0:.0f}s", flush=True)
        if resp is None or "corners" not in resp:
            failures[name] = err.strip()[-1500:] if err else "no response"
            print(f"   FAILED: {failures[name][:300]}", file=sys.stderr)
            continue
        print(f"   status={resp.get('status')} corners={resp.get('corner_count')} "
              f"pass={resp.get('passed')} err={resp.get('errored')}")
        if not resp.get("passed"):
            # Nothing resolved (e.g. the batch submit was rejected): that is a
            # failed submit to report, not evidence to commit. Do NOT fall back
            # to a local grid (host rule): fix the backend and re-run.
            codes = resp.get("diagnostic_counts", {}).get("by_code", {})
            remote = resp.get("environment", {}).get("remote") or {}
            failures[name] = (f"no corner resolved; diagnostics={codes}; "
                              f"job={remote.get('job_id')} runner_compat={remote.get('runner_compatibility')} "
                              f"runner_klt={remote.get('runner_klt_version')} client_klt={remote.get('client_klt_version')}")
            print(f"   FAILED: {failures[name]}", file=sys.stderr)
            shutil.rmtree(out, ignore_errors=True)
            continue
        responses[name] = resp
        if args.probe:
            tab = meas_table(resp)
            for lab, v in tab.items():
                print(lab, json.dumps(v, indent=0)[:1500])
            continue
        # Evidence: frozen netlist + normalised request + full klt response; drop
        # the generated per-corner decks (host paths) and raw vectors.
        snap_dir.mkdir(parents=True, exist_ok=True)
        R.write_once(snap_dir / f"{name}.sp", netlist_path.read_text())
        req_norm = json.loads(req_path.read_text())
        for b in req_norm["corners"]["process"]:
            for s in b["sections"]:
                if isinstance(s, dict) and s["lib"].endswith("preamble.lib"):
                    s["lib"] = "sim/program-read-legs/models/preamble.lib"
        R.write_once(snap_dir / f"{name}.request.json", json.dumps(req_norm, indent=1) + "\n")
        text, full_sha = R.klt_report_payload(resp, indent=1)
        R.write_once(corner_dir / f"{name}.report.json", text)
        R.write_once(corner_dir / f"{name}.report.json.sha256", full_sha + "\n")
        for deck in out.rglob("corner.cir"):
            deck.unlink()

    if args.probe:
        return 1 if failures else 0

    if not responses:
        shutil.rmtree(corner_dir, ignore_errors=True)
        print("ERROR: no bench produced a resolved report; no record written. "
              "Failures:\n  " + "\n  ".join(f"{k}: {v}" for k, v in failures.items()), file=sys.stderr)
        return 1

    # --- tables -----------------------------------------------------------
    sections = []
    unevidenced = []
    for name in wanted:
        if name not in responses:
            unevidenced.append(f"{name}: klt sim did not return a report ({failures.get(name, 'not run')[:200]})")
            continue
        resp = responses[name]
        tab = meas_table(resp)
        unresolved = [lab for lab, v in tab.items() if any(x is None for x in v.values())]
        note = (f"corners requested {resp.get('corner_count')}, passed {resp.get('passed')}, "
                f"errored {resp.get('errored')}, unresolved (some measurement missing): {len(unresolved)}; "
                f"{env_summary(resp)}")
        if name == "exclusion":
            sections.append(("Mutual exclusion", note, render_exclusion(analyze_exclusion(tab))))
        elif name == "ballast":
            sections.append(("Program leg ballast / compliance", note, render_ballast(analyze_ballast(tab))))
        else:
            k = defs[name][3]
            c = B.CANDIDATES[k]
            ir = bench_iref(name)
            sections.append((f"Read margin, Candidate {k} (Region {c['region']}), I_ref = {ir:.0e} A", note,
                             render_margin(k, analyze_margin(tab, ir))))
        if unresolved:
            unevidenced.append(f"{name}: {len(unresolved)} corner(s) with unresolved measurements: "
                               + ", ".join(unresolved[:6]))
    rec = render_record(record_id, pdk, dirty, wanted, sections, unevidenced, failures)
    R.write_once(THIS_DIR / "records" / f"{record_id}.md", rec)
    print(f"record: sim/program-read-legs/records/{record_id}.md")
    rc = 1 if (failures or unevidenced) else 0
    rc |= ES.publish_for_runner("program-read-legs", record_id, THIS_DIR / "corners" / record_id, REPO_ROOT)
    return rc


def render_record(record_id, pdk, dirty, wanted, sections, unevidenced, failures) -> str:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    L = [f"# Record {record_id}", "",
         f"- **Record ID**: {record_id}",
         "- **Claim**: `spec/architecture.md` 1.2 (PROG_EN/READ_EN mutual exclusion at the shared bit line), "
         "2 (ballast sizing inequality), 4 (read decision vs corner, unprogrammed and programmed sides "
         "separately). Regions I/II/III = Candidates 1/2/3 (`spec/split-axis-plan.md`).",
         f"- **Netlist provenance**: schematic (`design/netlists/{{leg_interlock,program_leg,read_leg,cell_candidate1..3}}.spice`), "
         f"{'DIRTY' if dirty else 'clean'} working tree at run time. Frozen bench netlists and the normalised "
         f"klt requests are in `sim/program-read-legs/netlist-snapshots/{record_id}/`.",
         "- **Corner matrix run** (every bench): process = typical, ff, ss, fs, sf (MOS section; moscap and "
         "poly-resistor sections follow ff/ss, typical for fs/sf); temperature = -40, 27, 125 C; supply = "
         f"VDD {B.VDD_POINTS[0]:.2f} / {B.VDD_POINTS[1]:.2f} / {B.VDD_POINTS[2]:.2f} V (nominal +-10%) with the "
         f"clamp bias VCLAMP tracking at {B.VCLAMP_NOM:.2f} V +-10%; 45 corners per bench. Corner ids follow "
         "`<process>_<temp>c_vdd<volts>v`. Split axes reported separately, never averaged: candidate/region "
         "(three benches), access-device sizing (min = committed-netlist default `wacc`, 2x), side "
         "(unprogrammed / programmed).",
         "- **Assumed / placeholder inputs (all of them)**:",
         f"  - Programmed-state resistance **R_prog = {B.R_PROG_ASSUMED['lo']/1e3:.0f} kohm and "
         f"{B.R_PROG_ASSUMED['hi']/1e3:.0f} kohm, ASSUMED** -- no breakdown-augmented cell model exists "
         "(`spec/cell-candidates.md`); the filament is modelled as a resistor across the capacitor. "
         "Every programmed-side number below is conditional on it. `I_prog_min` does not exist, so "
         "`I_ref < I_prog_min` is **unchecked**.",
         f"  - Unprogrammed side: bit line loaded by the recorded `I_sneak_max` of each candidate "
         f"(`sim/cell-device-characterization/records/`, evaluated there at ff/125C/high supply, a gmin-floor "
         f"upper bound) applied at EVERY corner, i.e. the worst-case sneak floor is combined with every "
         f"selected-cell corner (conservative; spec 4 asks for these two corners on different devices).",
         f"  - `I_ref = {B.I_REF:.0e} A` (and {B.I_REF_LOW:.0e} A for a second Candidate 3 bench) bench-supplied (ideal source into the I_ref mirror); `VCLAMP`, "
         f"`VPP` ({', '.join(f'{v:.1f}' for v in B.VPP_STEPS)} V illustrative; {B.VPP_IDLE:.1f} V while the program leg is OFF) "
         "are bench rails. Program-pulse VPP per region is unresolved in the spec.",
         f"  - Ballast inequality inputs: `V_compliance = {B.V_COMPLIANCE_ASSUMED:.1f} V` and "
         f"`I_target_max = {B.I_TARGET_MAX_ASSUMED*1e3:.1f} mA`, both **ASSUMED** (`spec/architecture.md` 2 leaves "
         "I_target_max open).",
         "  - Access/capacitor geometry are the committed netlists' placeholder defaults (design/README.md), "
         "not the ratified split-axis levels. Capacitor geometry is not a margin axis here (the intact "
         "capacitor blocks DC; the programmed state is a resistor across it).",
         "  - Statistics: process corners only. No Monte Carlo / mismatch: the sense mirror's offset spread "
         "is NOT evidenced here.",
         "- **Result**:", ""]
    for title, note, body in sections:
        L += [f"### {title}", "", f"_{note}_", "", body, ""]
    if unevidenced or failures:
        L += ["### Not evidenced by this record", ""]
        L += [f"- {u}" for u in unevidenced]
        L += [""]
    L += ["- **Links**:",
          "  - Benches: `sim/program-read-legs/benches.py` (generator), runner `sim/program-read-legs/run_experiment.py`",
          f"  - Frozen netlists / requests: `sim/program-read-legs/netlist-snapshots/{record_id}/`",
          f"  - Full klt reports (per-corner measurements) and raw logs: `sim/program-read-legs/corners/{record_id}/`",
          f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}`",
          f"- **Timestamp / author**: {now}, agent-builder",
          "- **Supersedes**: (none -- first record for this claim)", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
