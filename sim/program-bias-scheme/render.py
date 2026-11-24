#!/usr/bin/env python3
"""sim/program-bias-scheme render.py -- the Markdown record renderers.

Turns saved-report results (shaped by model.collect / model.fill /
model.load_saved) into the append-only record bodies under records/: the
shared record header, the per-corner and per-level terminal-pair extreme
tables, the BL-driven re-tabulation (render_retab) and the PL-driven /
gate-well-drive record with its verdict table (render_pl). Imports one-way
from model.py (loaded via harness.modload under the fixed unique name,
reusing the copy the CLI facade already loaded); nothing in model.py
imports this module.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import evidence_store as ES  # noqa: E402
from harness import numfmt as NF  # noqa: E402
from harness.modload import load_module  # noqa: E402

# model.py is loaded under the fixed unique name run_experiment.py uses, so
# the library exists once per process whether this module is reached through
# the CLI or alone.
M = sys.modules.get("sim_pbs_model") or load_module(THIS_DIR / "model.py", "sim_pbs_model")

# The model surface the (verbatim-moved) renderers below read by their
# pre-split bare names.
CB = M.CB
CHAR = M.CHAR
EXISTING_PROGC = M.EXISTING_PROGC
GWD_DRIVE = M.GWD_DRIVE
GWD_BENCHES = M.GWD_BENCHES
BENCHES = M.BENCHES
BENCH_DESC = M.BENCH_DESC
ACCESS_PAIRS = M.ACCESS_PAIRS
PAIR_LABEL = M.PAIR_LABEL
off_level = M.off_level


def sci(x) -> str:
    return NF.sci(x, digits=3)


# ---------------------------------------------------------------------------
# Record rendering (shared by the retabulation and the new scheme)
# ---------------------------------------------------------------------------


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


def render_retab(pdk, cand, rid: str, params: dict, note: str | None, src: str | None = None) -> str | None:
    """Re-tabulate the existing BL-driven evidence into one record body.

    Refuses to mint an empty record: when no ``progc_*`` reports can be
    found for ``src`` (disk or artifact store) it prints the reason and
    returns None, and the caller must not write — write_once is append-only,
    so a record with no result sections whose Links line cites the source
    anyway could never be corrected in place.
    """
    src = src or EXISTING_PROGC[cand.n]
    src_corn = CB.THIS_DIR / "corners" / src
    src_base = ES.run_dir_for_reading("cell-breakdown-model", src, REPO_ROOT, src_corn)
    src_reports = (f"`sim/cell-breakdown-model/corners/{src}/`" if src_base == src_corn
                   else f"manifest `manifests/artifacts/cell-breakdown-model-{src}.manifest.json`")
    res = CB.results_from_reports(cand, src, params, benches=("progc_st", "progc_b1m", "progc_b1l"),
                                  base_dir=src_base)
    if not res:
        print(f"ERROR: no saved progc_* reports for {src} (disk or artifact store)", file=sys.stderr)
        return None
    rating = CB.ACCESS_RATING_V[cand.n]
    L: list[str] = []
    a = L.append
    common_header(a, cand, rid, params,
                  "BL-driven program leg (the scheme #62/#74 used), re-tabulated per PVT corner from the existing "
                  "fleet evidence. NO NEW SIMULATION: the numbers are the `mx_*`/`mn_*` measurements already in "
                  f"the `{src}` run's `progc_*/report.json` ({src_reports}).", note)
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
    a(f"  - Source records and raw reports: `sim/cell-breakdown-model/records/{src}.md`, raw `progc_*` "
      f"reports in {src_reports}")
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
    a(f"  - Requests, bodies, klt reports, per-corner decks and logs: artifact store manifest "
      f"`manifests/artifacts/program-bias-scheme-{rid}.manifest.json`, entries `<bench>/…`")
    a(f"  - Netlist snapshot: `sim/program-bias-scheme/netlist-snapshots/{rid}.spice`")
    a("  - BL-driven counterpart (same levels, same cell): `sim/cell-breakdown-model/records/"
      f"{EXISTING_PROGC[cand.n]}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host)")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("")
    return "\n".join(L)
