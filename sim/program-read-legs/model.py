#!/usr/bin/env python3
"""sim/program-read-legs model.py -- the experiment's shared library.

Campaign constants (PVT corner axes, fleet sharding bounds, Monte Carlo
points), the ``klt sim`` request builders (corner and Monte Carlo
variants), the bench definitions built on benches.py, the per-corner /
per-sample data shaping (``meas_table`` / ``mc_table``) and the analysis
and statistics helpers (exclusion / ballast / margin analyses,
Clopper-Pearson lower bound, percentiles, mean/sigma). The CLI entry point
is run_experiment.py, which loads this module (and render.py) via
harness.modload and re-exports this surface, so consumers keep loading
run_experiment.py as the library. render.py imports one-way from this
module; nothing here imports render.py or the CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(THIS_DIR))

import benches as B  # noqa: E402

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
# The batch fleet kills a whole job at JOB_CEILING_S and reports batch_job_timeout
# for every unit in it, and klt checks a request's conservative fully-serial bound
# (units_per_job * options.timeout_s + overhead) against that ceiling on every
# submission. Sharding the unit count across remote.hosts keeps the bound under
# the ceiling: floor((3600 - 120) / 300) = 11 units per job, which is klt's own
# max_units_per_job for this driver (integrated-transition's 16 is tied to that
# driver's cheaper per-unit cost, not this one).
JOB_CEILING_S = 3600
JOB_OVERHEAD_S = 120
PER_UNIT_TIMEOUT_S = 300
MAX_UNITS_PER_SHARD = (JOB_CEILING_S - JOB_OVERHEAD_S) // PER_UNIT_TIMEOUT_S
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
    units = len(bundles) * len(temps) * len(vdd)
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
        "options": {"keep_artifacts": True, "timeout_s": PER_UNIT_TIMEOUT_S, "stage_model_inputs": True},
        "batch": dict(BATCH_OPTS),
        # shard across fleet hosts so the declared job bound stays under the ceiling
        "remote": {"hosts": max(1, -(-units // MAX_UNITS_PER_SHARD))},
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
    # MC units are monte_carlo.n, not the one-corner cross-product the delegated
    # request was built with: re-shard for the real unit count.
    req["remote"] = {"hosts": max(1, -(-n // MAX_UNITS_PER_SHARD))}
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


# ---------------------------------------------------------------------------
# Monte Carlo (mismatch) variant: statistics and per-sample data shaping
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
