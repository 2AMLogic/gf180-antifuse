#!/usr/bin/env python3
"""sim/program-bias-scheme -- program bias schemes against the ratified
access-device ratings, per candidate and per PVT corner (issue #90).

Two things, both reusing sim/cell-breakdown-model as a library (deck
helpers, breakdown wrapper, candidate definitions, corner grid, klt runner),
so the stimulus levels, the 45-corner grid and the assumed breakdown
parameters are identical by construction:

  --retabulate   Re-tabulate the EXISTING fleet evidence of the BL-driven
                 program leg (cell-breakdown-model `progc_*` benches, records
                 20261014-0017{17,20,23}-86afd07) as one row per PVT corner
                 with every access-device terminal-pair extreme. Runs no
                 simulation.
  (default)      Run the PL-driven scheme on the batch fleet:
                   plb_<v>   VPP pulse -> ballast -> PL; BL = 0 V through an
                             ammeter; WL, VB static at the #62 "on" bias.
                   plu_st    the same PL pulse on an UNSELECTED stock cell:
                             WL at its OFF level, BL = 0 V; CN floats.
                 with <v> = st (stock cell), b1m / b1l (element enabled,
                 median / low Weibull quantile). Each bench is one `klt sim`
                 request (3 moscap corners x 3 T x 5 levels = 45 corners),
                 submitted to the batch fleet; never run as a local grid.

    python3 sim/program-bias-scheme/run_experiment.py --retabulate
    python3 sim/program-bias-scheme/run_experiment.py --candidates 1,2,3
    python3 sim/program-bias-scheme/run_experiment.py --smoke 2:plb_b1m   # ONE local corner

All results are conditional on the ASSUMED breakdown parameters in
design/breakdown/breakdown_params.spice (V_bd 8.0 / 15.2 / 7.9 V). Nothing
here relaxes or edits a ratified spec.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
CB_DIR = SIM_DIR / "cell-breakdown-model"

sys.path.insert(0, str(SIM_DIR))
from harness import evidence_store as ES  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402


CB = load_module(CB_DIR / "run_experiment.py", "sim_cb_lib")
CHAR = CB.CHAR

# Existing BL-driven fleet records (cell-breakdown-model, C-infinity edges,
# "progc" = BL-driven program leg), per candidate.
EXISTING_PROGC = {1: "20261014-001717-86afd07", 2: "20261014-001720-86afd07", 3: "20261014-001723-86afd07"}

LEGACY_BENCHES = ("plb_st", "plb_b1m", "plb_b1l", "plu_st")
# Candidate 3 gate/well-drive benches (#129): the PL-driven leg of `plb`, with the access device's
# gate (WL) and n-well tie (VB) levels set per scheme instead of the #62 "on" bias. Static levels
# [V], Candidate 3 only (PMOS access, rating 6 V); the pulse is the same signed PL level.
GWD_DRIVE = {
    "gwa": {"wl": -3.3, "vb": 0.0, "desc": "WL -3.3 V (the #62 on level), n-well tie lowered from +3.3 V to 0 V (the BL return level)"},
    "gwb": {"wl": -6.0, "vb": 0.0, "desc": "WL -6.0 V (stronger gate drive), n-well tie 0 V (the BL return level)"},
}
GWD_VARIANTS = ("st", "b1m", "b1l")
GWD_BENCHES = tuple(f"{s}_{v}" for s in GWD_DRIVE for v in GWD_VARIANTS)
BENCHES = LEGACY_BENCHES + GWD_BENCHES
BENCH_DESC = {
    "plb_st": "PL-driven through ballast, selected cell, stock cell (no breakdown element)",
    "plb_b1m": "PL-driven through ballast, selected cell, element enabled, median quantile (ubd=0.5)",
    "plb_b1l": f"PL-driven through ballast, selected cell, element enabled, low quantile (ubd={CB.UBD_LOW})",
    "plu_st": "PL pulse on an UNSELECTED stock cell (WL at OFF level, BL = 0 V, CN floating)",
}
_VAR_DESC = {"st": "stock cell (no breakdown element)", "b1m": "element enabled, median quantile (ubd=0.5)",
             "b1l": f"element enabled, low quantile (ubd={CB.UBD_LOW})"}
for _s, _d in GWD_DRIVE.items():
    for _v in GWD_VARIANTS:
        BENCH_DESC[f"{_s}_{_v}"] = f"gate/well drive `{_s}` ({_d['desc']}), {_VAR_DESC[_v]}"
ACCESS_PAIRS = CB.ACCESS_PAIRS
PAIR_LABEL = {k: f"{k}: {CB.TERMINAL_PAIRS[k][0].upper()}-{CB.TERMINAL_PAIRS[k][1].upper()}" for k in CB.TERMINAL_PAIRS}
TRIGC_KEY = "trigc_st"   # corner-id/level convention shared with the PL-driven #74 benches


def off_level(cand) -> float:
    """WL level that holds the access device OFF with BL = 0 V: the bulk
    level (0 V for the NMOS candidates, the n-well tie for the PMOS one)."""
    return cand.vb


# ---------------------------------------------------------------------------
# Deck bodies
# ---------------------------------------------------------------------------


C_PL_SHUNT = 100e-15   # PLACEHOLDER plate-line shunt capacitance [F]


def body_pl(pdk, cand, defaults, body_dir: Path, lib_root: str, bench: str, params: dict):
    scheme, var = bench.split("_", 1)
    out = [CB.body_header(pdk, body_dir, f"Candidate {cand.n} {bench} (tran, #90)", cand, "trigger", lib_root)]
    out.append(f".param t1={CB.fmt(CB.TRIG_T1)} tr={CB.fmt(CB.TRIG_TR)} tw={CB.fmt(CB.TRIG_TW)}")
    out += CB.edge_lines("cinf")
    out.append("VAMP AMP 0 DC 0")                      # klt's supply axis sets this (signed level)
    out.append("BVPP VPP 0 V = 'v(amp)*v(sh)'")
    out.append(f"RBAL VPP PLM {CB.fmt(CB.prog_rballast(cand, params))}")
    out.append("VPLM PLM PL DC 0")                     # ammeter: program (return-side) current
    out.append("VBL BL 0 DC 0")                        # bit line at the 0 V return, through an ammeter
    if scheme in GWD_DRIVE:
        if cand.n != 3:
            raise ValueError(f"bench {bench} is defined for Candidate 3 only")
        wl, vb = GWD_DRIVE[scheme]["wl"], GWD_DRIVE[scheme]["vb"]
    else:
        wl = cand.moscap_wl_on if scheme == "plb" else off_level(cand)
        vb = cand.vb
    out.append(f"VWL WL 0 DC {CB.fmt(wl)}")
    out.append(f"VVB VB 0 DC {CB.fmt(vb)}")
    # Plate-line (pad / routing) shunt capacitance. Without it the ballasted PL node is a
    # high-impedance node that stalls the `uic` start of the moscap macro (timestep collapse at
    # -40 C and at the slow corner on the fleet; found in #90). 100 fF is a PLACEHOLDER.
    out.append(f"CPL PL 0 {CB.fmt(C_PL_SHUNT)}")
    geo = CB.geometry(cand, defaults, "min", "min")
    out.append(f"XDUT BL WL PL VB {CB.conv_dut(cand, var, geo)}")
    cn = CB.conv_cn(var)
    node = {"cn": cn, "pl": "pl", "wl": "wl", "bl": "bl", "vb": "vb"}
    ms: list[dict] = []
    for k, (p, n, _) in CB.TERMINAL_PAIRS.items():
        out.append(f"BD{k.upper()} D{k.upper()} 0 V = 'v({node[p]})-v({node[n]})'")
        ms.append({"name": f"mx_{k}", "spice": f".meas tran mx_{k} MAX v(d{k})", "unit": "V"})
        ms.append({"name": f"mn_{k}", "spice": f".meas tran mn_{k} MIN v(d{k})", "unit": "V"})
    ms.append(CB.meas("tran", "vox_mid", "v(dox)", CB.TRIG_TMID, "V"))
    ms.append(CB.meas("tran", "vcn_mid", f"v({cn})", CB.TRIG_TMID, "V"))
    ms.append(CB.meas("tran", "vcn_end", f"v({cn})", CB.TRIG_TMEAS, "V"))
    ms.append(CB.meas("tran", "ipl_mid", "i(vplm)", CB.TRIG_TMID, "A"))
    ms.append({"name": "ipl_mx", "spice": ".meas tran ipl_mx MAX i(vplm)", "unit": "A"})
    ms.append({"name": "ipl_mn", "spice": ".meas tran ipl_mn MIN i(vplm)", "unit": "A"})
    if var.startswith("b1"):
        ms.append(CB.meas("tran", "st", "v(xdut.xbd.st)", CB.TRIG_TMEAS, "1"))
        ms.append(CB.meas("tran", "st_mid", "v(xdut.xbd.st)", CB.TRIG_TMID, "1"))
    return "\n".join(out) + "\n", ms


def make_request(bench: str, cand, pdk, ms: list[dict], params: dict) -> dict:
    # the PL-driven #74 request (signed level on VAMP, 45 corners, tran uic)
    req = CB.make_request(TRIGC_KEY, cand, pdk, ms, params)
    return req


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def collect(bench: str, report: dict | None, err: str, bdir: Path, cand, params: dict):
    if report is None or "corners" not in report:
        msg = err if report is None or "error" not in report else json.dumps(report["error"])
        return CB.BenchResult(bench=bench, status="submit-error", remote=None, error=msg)
    env = report.get("environment", {})
    res = CB.BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"), klt_env=env)
    fill(res, report, bdir, cand, params, write=True)
    return res


def fill(res, report: dict, bdir: Path, cand, params: dict, write: bool) -> None:
    for c in report["corners"]:
        cid = CB.corner_key(TRIGC_KEY, c, cand, params)
        res.corner_status[cid] = c["status"]
        res.values[cid] = {m["name"].lower(): m["value"] for m in c["measurements"]}
        if write:
            art = c.get("artifacts") or {}
            for kind, suffix in (("log", ".log"), ("deck", ".cir")):
                src = art.get(kind)
                if src and Path(src).is_file():
                    R.write_once(bdir / f"{cid}{suffix}", Path(src).read_text(errors="replace"))
        log = bdir / f"{cid}.log"
        res.outcome[cid] = CB.classify_failure(c["status"], c.get("diagnostics") or [],
                                               log.read_text(errors="replace") if log.is_file() else None,
                                               res.values[cid])


def load_saved(cand, rid: str, params: dict) -> dict:
    out = {}
    for bench in BENCHES:
        bdir = THIS_DIR / "corners" / rid / bench
        if (bdir / "report.json").is_file():
            report = json.loads((bdir / "report.json").read_text())
            env = report.get("environment", {})
            res = CB.BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"),
                                 klt_env=env)
            fill(res, report, bdir, cand, params, write=False)
            out[bench] = res
        elif (bdir / "submit-error.txt").is_file():
            out[bench] = CB.BenchResult(bench=bench, status="submit-error", remote=None,
                                        error=(bdir / "submit-error.txt").read_text())
    return out


# ---------------------------------------------------------------------------
# Rendering (shared by the retabulation and the new scheme)
# ---------------------------------------------------------------------------


def sci(x) -> str:
    return "n/a" if x is None else f"{x:.3e}"


def corner_sort(cid: str):
    proc = cid.split("_")[1] if cid.startswith("moscap_") else cid
    return (CB.corner_level(cid), proc, CB.corner_temp(cid))


def per_corner_table(a, cand, params, res, stim: str, rating: float, with_current: str | None) -> None:
    """One row per PVT corner: largest |V| of every access-device pair over
    the WHOLE transient; bold = over the ratified rating."""
    head = ["Level", "Corner", "st end"] + [PAIR_LABEL[k] for k in ACCESS_PAIRS] + ["over rating"]
    if with_current:
        head.append(f"I peak [A] ({with_current})")
    a("    | " + " | ".join(head) + " |")
    a("    |" + "---|" * len(head))
    for cid in sorted(res.values, key=corner_sort):
        v, o = res.values[cid], res.outcome[cid]
        lvl = CB.level_label(cand, params, stim, CB.corner_level(cid))
        if o["kind"] != "pass":
            a(f"    | {lvl} | `{cid}` | {o['kind']} |" + " |" * (len(head) - 3))
            continue
        cells, over = [], 0
        for k in ACCESS_PAIRS:
            x = CB.abs_extreme(v, k)
            if x is None:
                cells.append("n/a")
            elif x > rating:
                over += 1
                cells.append(f"**{x:.2f}**")
            else:
                cells.append(f"{x:.2f}")
        st = v.get("st")
        row = [lvl, f"`{cid}`", "n/a" if st is None else f"{st:.0f}"] + cells + [f"{over} pair(s)"]
        if with_current:
            ip = max(abs(v.get(f"{with_current}_mx") or 0.0), abs(v.get(f"{with_current}_mn") or 0.0))
            row.append(sci(ip))
        a("    | " + " | ".join(row) + " |")
    a("")


def level_summary(a, cand, params, res, stim: str, rating: float) -> None:
    """Per level: how many of the 9 PVT corners programmed, and the worst
    corner's extreme of each pair (per level, never across levels)."""
    head = ["rated"] + [f"{f:g}x" for f in CB.TRIG_FRACTIONS]
    a("    | Level | VPP/PL [V] | corners ok | programmed (st=1) | " +
      " | ".join(f"max {PAIR_LABEL[k]}" for k in ACCESS_PAIRS) + " | pairs over rating (any corner) |")
    a("    |" + "---|" * (5 + len(ACCESS_PAIRS)))
    for h in head:
        cids = [c for c in res.values if CB.level_label(cand, params, stim, CB.corner_level(c)) == h]
        ok = [c for c in cids if res.outcome[c]["kind"] == "pass"]
        prog = sum(1 for c in ok if (res.values[c].get("st") or 0) > 0.5) if any(
            "st" in res.values[c] for c in ok) else None
        cells, over = [], 0
        for k in ACCESS_PAIRS:
            xs = [CB.abs_extreme(res.values[c], k) for c in ok]
            xs = [x for x in xs if x is not None]
            if not xs:
                cells.append("n/a")
                continue
            m = max(xs)
            if m > rating:
                over += 1
                cells.append(f"**{m:.2f}**")
            else:
                cells.append(f"{m:.2f}")
        lv = abs(CB.corner_level(cids[0])) if cids else float("nan")
        a(f"    | {h} | {lv:.2f} | {len(ok)}/{len(cids)} | " + ("n/a" if prog is None else f"{prog}/{len(ok)}") +
          " | " + " | ".join(cells) + f" | {over} |")
    a("")


def common_header(a, cand, rid: str, params: dict, claim: str, note: str | None, issue: int = 90) -> None:
    rating = CB.ACCESS_RATING_V[cand.n]
    vbd = CB.vbd_ref(cand, params)
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    a(f"- **Claim**: issue #{issue} -- Candidate {cand.n} / Region {cand.region}: {claim} Terminal-pair extremes are "
      f"logged per PVT corner against the ratified {rating:g} V rating of "
      f"`{CHAR.CANDIDATES[cand.n - 1].access_model}` (`spec/cell-candidates.md`). "
      + (f"V_BD SENSITIVITY POINT (not a parameter update, see the sensitivity bullet below): V_bd(t_ref) = "
         f"**{vbd:.2f} V** from the primary-sourced BVox, every other breakdown parameter still ASSUMED."
         if CB.VBD_EBD_OVERRIDE is not None else
         f"CONDITIONAL ON THE ASSUMED breakdown parameters: V_bd(t_ref) = bd_ebd x c{cand.n}_bd_tox = "
         f"**{vbd:.2f} V** (assumed, not a gf180 number; `design/breakdown/breakdown_params.spice`, unchanged)."))
    if note:
        a(f"- **Run note**: {note}")
    a(f"- **Corner matrix**: {', '.join(CB.C.MOSCAP_CORNERS)} (MOS typical) x {', '.join(str(t) for t in CB.C.TEMPS_C)} "
      f"degC x 5 stress levels (the capacitor's rated {cand.cap_rated_v:g} V and "
      + ", ".join(f"{f:g}" for f in CB.TRIG_FRACTIONS) + " x V_bd) = 45 corners per bench; process-minimum geometry; "
      f"pulse edges {CB.TRIG_TR*1e9:g} ns (C-infinity), flat {CB.TRIG_TW*1e6:g} us from {CB.TRIG_T1*1e6:g} us; "
      f"`tran {CB.fmt(CB.TRIG_TSTEP)} {CB.fmt(CB.TRIG_TSTOP)} uic`; one cell per deck. Rows below are per "
      "corner; level summaries take the worst corner WITHIN one level only.")


def render_retab(pdk, cand, rid: str, params: dict, note: str | None, src: str | None = None) -> str:
    src = src or EXISTING_PROGC[cand.n]
    res = CB.results_from_reports(cand, src, params, benches=("progc_st", "progc_b1m", "progc_b1l"))
    rating = CB.ACCESS_RATING_V[cand.n]
    L: list[str] = []
    a = L.append
    common_header(a, cand, rid, params,
                  "BL-driven program leg (the scheme #62/#74 used), re-tabulated per PVT corner from the existing "
                  "fleet evidence. NO NEW SIMULATION: the numbers are the `mx_*`/`mn_*` measurements already in "
                  f"`sim/cell-breakdown-model/corners/{src}/progc_*/report.json`.", note)
    a("- **Scheme (BL-driven)**: VPP pulse -> ideal ballast "
      f"{CB.prog_rballast(cand, params)/1e3:.4g} kOhm (PLACEHOLDER, V_bd / 500 uA) -> BL; PL = 0 V; "
      f"WL = {cand.moscap_wl_on:g} V + VPP(t)"
      + (f"; n-well VB = {cand.vb:g} V + VPP(t)" if cand.polarity == "p" else f"; VB = {cand.vb:g} V (p-substrate tie)")
      + ". The gate/well riding on VPP is a bench choice (`spec/supply-domains-decision.md` rows 8, 9, 15 are open).")
    a(f"- **Source evidence**: `sim/cell-breakdown-model/records/{src}.md`, benches `progc_st`, `progc_b1m`, `progc_b1l`.")
    a("- **Result**:")
    for b in ("progc_b1m", "progc_b1l", "progc_st"):
        r = res.get(b)
        if r is None:
            continue
        t = CB.tally([o["kind"] for o in r.outcome.values()])
        a("")
        a(f"  - `{b}` ({CB.CONV_VARIANTS[CB.conv_split(b)[1]]}); {t['pass']}/{t['attempted']} corners converged.")
        a("")
        level_summary(a, cand, params, r, "progc", rating)
        per_corner_table(a, cand, params, r, "progc", rating, "ibl" if b != "progc_st" else "ibl")
    a("- **Links**:")
    a(f"  - Source records and raw reports: `sim/cell-breakdown-model/records/{src}.md`, "
      f"`sim/cell-breakdown-model/corners/{src}/`")
    a("- **Method**: the table is produced by `sim/program-bias-scheme/run_experiment.py --retabulate`; "
      "no simulation was run for this record.")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("")
    return "\n".join(L)


def gwd_verdict(a, cand, params, results: dict, rating: float, n: int) -> None:
    """Per stress level and gate/well scheme: how many attempted corners keep ALL six access-device
    pairs within the rating, over the whole transient. A non-converged corner is in the denominator
    and never counts as in rating. Levels are never merged."""
    a(f"  - **({n}) Verdict: does any gate/well scheme keep all six pairs within {rating:g} V?** A corner is "
      "\"in rating\" when it converged and every pair's largest |V| over the whole transient is <= the rating. "
      "Cells are in-rating corners / attempted corners (non-converged corners stay in the denominator); "
      "the last column names the scheme/variant benches that hold at EVERY attempted corner of that level.")
    a("")
    benches = [b for b in GWD_BENCHES if b in results and results[b].values]
    a("    | Level | " + " | ".join(f"`{b}`" for b in benches) + " | all-corners-in-rating benches |")
    a("    |" + "---|" * (len(benches) + 2))
    anywhere = False
    for h in ["rated"] + [f"{f:g}x" for f in CB.TRIG_FRACTIONS]:
        cells, holds = [], []
        for b in benches:
            r = results[b]
            cids = [c for c in r.values if CB.level_label(cand, params, "trigc", CB.corner_level(c)) == h]
            ok = 0
            for c in cids:
                if r.outcome[c]["kind"] != "pass":
                    continue
                xs = [CB.abs_extreme(r.values[c], k) for k in ACCESS_PAIRS]
                if all(x is not None and x <= rating for x in xs):
                    ok += 1
            cells.append(f"{ok}/{len(cids)}")
            if cids and ok == len(cids):
                holds.append(f"`{b}`")
        anywhere = anywhere or bool(holds)
        a(f"    | {h} | " + " | ".join(cells) + " | " + (", ".join(holds) if holds else "**none**") + " |")
    a("")
    a("    " + ("At least one scheme keeps every pair in rating at some level (rows above)." if anywhere else
                "**Result: no gate/well scheme tried keeps all six pairs in rating at any stress level.**"))
    a("")
    a("    Reading note: the `_st` benches have no breakdown element, so they show only the stress of the pulse on "
      "an intact cell; a program event is represented by the `_b1m` / `_b1l` benches (element enabled), which are "
      "the rows to compare per level. Conditional on the assumed V_bd; #130 supersedes with sourced values.")
    a("")


def render_pl(pdk, cand, rid: str, params: dict, results: dict, note: str | None) -> str:
    rating = CB.ACCESS_RATING_V[cand.n]
    L: list[str] = []
    a = L.append
    gwd = any(b in results for b in GWD_BENCHES)
    common_header(a, cand, rid, params,
                  ("Candidate 3 gate/well-drive program bench (PL-driven leg, WL and n-well tie varied per scheme), "
                   "evaluated on the batch fleet; the verdict table states per stress level whether any scheme keeps "
                   "all six pairs in rating." if gwd else
                   "PL-driven program scheme with a return-side ballast (the alternative to the BL-driven leg), "
                   "evaluated on the batch fleet; `plu_st` shows the unselected-cell consequence."),
                  note, issue=129 if gwd else 90)
    a(f"- **Scheme (PL-driven, `plb`)**: VPP pulse (signed level, same magnitudes as the BL-driven bench) -> "
      f"ballast {CB.prog_rballast(cand, params)/1e3:.4g} kOhm (same PLACEHOLDER as the BL-driven bench: V_bd / "
      f"500 uA; ideal resistor) -> PL; BL = 0 V through an ammeter; WL static at {cand.moscap_wl_on:g} V (the #62 "
      f"\"on\" bias); VB static at {cand.vb:g} V. The access device therefore carries only the program current times "
      "its on-resistance, not VPP.")
    drv = [(k, v) for k, v in GWD_DRIVE.items() if any(b.startswith(k + "_") for b in results)]
    for k, v in drv:
        a(f"- **Gate/well drive (`{k}`, Candidate 3 only)**: same PL pulse, ballast and BL = 0 V as `plb`, with static "
          f"WL = {v['wl']:g} V and n-well VB = {v['vb']:g} V instead of the #62 \"on\" bias "
          f"({cand.moscap_wl_on:g} V / {cand.vb:g} V). {v['desc']}.")
    a(f"- **Unselected-cell scheme (`plu`)**: the same PL pulse, stock cell, WL at its OFF level "
      f"({off_level(cand):g} V), BL = 0 V; CN is floating (no DC path but gmin), so it is set by capacitive "
      "coupling from PL.")
    envs = [r.klt_env for r in results.values() if r.klt_env]
    if envs:
        e0 = envs[0]
        rm = e0.get("remote") or {}
        a(f"- **Execution**: engine ngspice {e0.get('engine_version')} on the batch fleet (runner klt "
          f"{rm.get('runner_klt_version')}, submitting client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}`); models_lib sha256 "
          f"`{e0.get('models_lib_sha256')}`.")
    a("- **Result**:")
    a("")
    a("  - **(1) Convergence, every attempted corner counted**:")
    a("")
    a("    | Bench | Description | Attempted | Pass | Timeout | Timestep | Missing | Other | klt | Job |")
    a("    |---|---|---|---|---|---|---|---|---|---|")
    for b in BENCHES:
        r = results.get(b)
        if r is None:
            continue
        t = CB.tally([o["kind"] for o in r.outcome.values()])
        job = (r.remote or {}).get("job_id", "?") if r.remote else ("submit-error" if r.error else "?")
        a(f"    | `{b}` | {BENCH_DESC[b]} | {t['attempted']} | {t['pass']} | {t['timeout']} | {t['timestep']} | "
          f"{t['missing-measurement']} | {t['error']} | `{r.status}` | `{job}` |")
        if r.error:
            a(f"    | | ERROR: {r.error[:300]!r} | | | | | | | |")
    a("")
    n = 2
    for b in ("plb_b1m", "plb_b1l", "plb_st", "plu_st") + GWD_BENCHES:
        r = results.get(b)
        if r is None or not r.values:
            continue
        a(f"  - **({n}) `{b}`** -- {BENCH_DESC[b]}. Per level (worst PVT corner within each level; bold = over the "
          f"{rating:g} V rating):")
        a("")
        level_summary(a, cand, params, r, "trigc", rating)
        a(f"    Per PVT corner (largest |V| of each pair over the whole transient; `st end` = breakdown state at "
          "19.9 us; I peak = ballast/program current):")
        a("")
        per_corner_table(a, cand, params, r, "trigc", rating, "ipl")
        n += 1
    if any(b in results for b in GWD_BENCHES):
        gwd_verdict(a, cand, params, results, rating, n)
    a("- **Links**:")
    a(f"  - Requests, bodies, klt reports, per-corner decks and logs: `sim/program-bias-scheme/corners/{rid}/<bench>/`")
    a(f"  - Netlist snapshot: `sim/program-bias-scheme/netlist-snapshots/{rid}.spice`")
    a("  - BL-driven counterpart (same levels, same cell): `sim/cell-breakdown-model/records/"
      f"{EXISTING_PROGC[cand.n]}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host)")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def smoke(pdk, cand, bench: str, params: dict, idx: int = 3) -> int:
    """ONE corner of ONE bench, locally -- a debug probe, not evidence."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}-{bench}"
    work.mkdir(parents=True)
    body, ms = body_pl(pdk, cand, defaults, work, str(pdk.variant_dir), bench, params)
    (work / "body.spice").write_text(body)
    req = make_request(bench, cand, pdk, ms, params)
    corners = req["corners"]
    corners["process"] = corners["process"][:1]
    corners["temperature_c"] = [27.0]
    vals = corners["supply_v"]["vamp"]
    corners["supply_v"] = {"vamp": [vals[idx]]}        # default index 3 = 1.0 x V_bd
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    report, err = CB.run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke {bench}: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    print(f"smoke c{cand.n} {bench}: {c['corner_id']} status={c['status']}; work dir {work}")
    for m in c["measurements"]:
        print(f"   {m['name']} = {m['value']}")
    return 0 if c["status"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=",".join(LEGACY_BENCHES),
                    help="comma list; the Candidate 3 gate/well benches (" + ",".join(GWD_BENCHES) +
                         ") are opt-in: --candidates 3 --benches " + ",".join(GWD_BENCHES))
    ap.add_argument("--retabulate", action="store_true", help="re-tabulate existing BL-driven evidence (no sim)")
    ap.add_argument("--retab-src", default=None, metavar="RECORD_ID",
                    help="with --retabulate and ONE candidate: re-tabulate this cell-breakdown-model record's "
                         "progc_* reports (a #130 sensitivity run) instead of the #62/#74 original")
    ap.add_argument("--smoke", default=None, metavar="N:BENCH[:LEVEL_INDEX]", help="ONE local corner (debug probe, no record)")
    ap.add_argument("--resume", default=None, metavar="RECORD_ID",
                    help="finish an interrupted batch run of ONE candidate: benches with a saved report.json are "
                         "reloaded, the rest are submitted into the same corners/RECORD_ID/ (no new record id)")
    ap.add_argument("--render", default=None, metavar="RECORD_ID",
                    help="(re)write records/RECORD_ID.md from saved reports of ONE candidate; no simulation")
    ap.add_argument("--note", default=None)
    ap.add_argument("--vbd-case", choices=tuple(CB.SOURCED_VBD), default=None,
                    help="V_bd sensitivity point (#130): per-candidate override of bd_ebd to the sourced BVox "
                         "typ/floor value; the shared parameter file is not changed")
    ap.add_argument("--klt", default="klt")
    args = ap.parse_args(argv)
    CB.KLT_CMD[:] = args.klt.split()
    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if not shutil.which(CB.KLT_CMD[0]):
        print(f"ERROR: {CB.KLT_CMD[0]} not on PATH", file=sys.stderr)
        return 3
    base_params, perr = CB.CHECK.parse_params((CB.BD_DIR / "breakdown_params.spice").read_text())
    if perr:
        print("ERROR: breakdown_params.spice fails provenance checks", file=sys.stderr)
        return 3
    params = base_params
    by_n = {c.n: c for c in CHAR.CANDIDATES}
    wanted = [int(x) for x in args.candidates.split(",") if x.strip()]

    if args.smoke:
        n, bench, *ix = args.smoke.split(":")
        return smoke(pdk, by_n[int(n)], bench, CB.apply_vbd_case(base_params, args.vbd_case, int(n)),
                     int(ix[0]) if ix else 3)
    if args.render:
        cand = by_n[wanted[0]]
        params = CB.apply_vbd_case(base_params, args.vbd_case, cand.n)
        res = load_saved(cand, args.render, params)
        R.write_once(THIS_DIR / "records" / f"{args.render}.md",
                     CB.tag_record(render_pl(pdk, cand, args.render, params, res, args.note),
                                   CB.sensitivity_block(args.vbd_case, cand.n, params)))
        return 0
    if args.retabulate:
        if args.retab_src and len(wanted) != 1:
            print("ERROR: --retab-src applies to exactly one candidate", file=sys.stderr)
            return 2
        for n in wanted:
            cand = by_n[n]
            params = CB.apply_vbd_case(base_params, args.vbd_case, n)
            if args.vbd_case and not args.retab_src:
                print("ERROR: --vbd-case with --retabulate needs --retab-src (the sensitivity run's record id)",
                      file=sys.stderr)
                return 2
            rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
            R.write_once(THIS_DIR / "records" / f"{rid}.md",
                         CB.tag_record(render_retab(pdk, cand, rid, params, args.note, args.retab_src),
                                       CB.sensitivity_block(args.vbd_case, n, params)))
            print(f"Candidate {n}: records/{rid}.md (re-tabulation, no simulation)")
            time.sleep(1.1)
        return 0

    benches = [b for b in args.benches.split(",") if b.strip()]
    unknown = [b for b in benches if b not in BENCHES]
    if unknown:
        print(f"ERROR: unknown bench(es) {unknown}", file=sys.stderr)
        return 2
    if any(b in GWD_BENCHES for b in benches) and wanted != [3]:
        print("ERROR: the gate/well-drive benches are defined for Candidate 3 only (--candidates 3)", file=sys.stderr)
        return 2
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand = by_n[n]
        params = CB.apply_vbd_case(base_params, args.vbd_case, n)
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = args.resume or R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n} (Region {cand.region}) record {rid}" + (" (resumed)" if args.resume else ""))
        if not args.resume:
            R.write_once(THIS_DIR / "corners" / rid / "run-provenance.json",
                         json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty}) + "\n")
        results = load_saved(cand, rid, params) if args.resume else {}
        for bench in benches:
            if bench in results:
                continue
            bdir = THIS_DIR / "corners" / rid / bench
            if args.resume and bdir.exists():
                shutil.rmtree(bdir)   # interrupted submit: no report.json, nothing to preserve but the request
            bdir.mkdir(parents=True, exist_ok=False)
            body, ms = body_pl(pdk, cand, defaults, bdir, CB.fleet_lib_root(pdk), bench, params)
            R.write_once(bdir / "body.spice", body)
            req = make_request(bench, cand, pdk, ms, params)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = CB.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
            if report is not None:
                R.write_once(bdir / "report.json", json.dumps(report, indent=2) + "\n")
            res = collect(bench, report, err, bdir, cand, params)
            if res.error:
                R.write_once(bdir / "submit-error.txt", res.error + "\n")
            results[bench] = res
            job = (res.remote or {}).get("job_id") if res.remote else None
            print(f"   {bench}: {res.status} ({len(res.corner_status)} corners, {time.time()-t0:.0f}s, job {job})"
                  + (f" ERROR {res.error[:300]}" if res.error else ""), flush=True)
            if res.status not in ("pass", "pass_partial"):
                rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", CB.snapshot(cand))
        R.write_once(THIS_DIR / "records" / f"{rid}.md", CB.tag_record(render_pl(pdk, cand, rid, params, results, args.note),
                                   CB.sensitivity_block(args.vbd_case, n, params)))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("program-bias-scheme", rid, THIS_DIR / "corners" / rid, REPO_ROOT)
        time.sleep(1.1)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
