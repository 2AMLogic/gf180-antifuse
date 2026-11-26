#!/usr/bin/env python3
"""sim/cell-breakdown-model render_conv.py -- the issue #74 convergence-record renderer.

Moved out of render.py unchanged: render_conv_record and its helpers (control
comparison, corner attribution, device-limit and program-current tables).
Imports one-way from model.py (the copy already in sys.modules, as render.py
does); nothing here imports render.py. render.py re-exports every public name
so callers reaching them through the renderer or the runner facade are unaffected.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness import numfmt as NF  # noqa: E402
from harness.modload import load_module  # noqa: E402

M = sys.modules.get("sim_cb_model") or load_module(THIS_DIR / "model.py", "sim_cb_model")

sci = NF.sci


# --- issue #74 convergence record -------------------------------------------

# The #62 trigger records whose non-converged corners #74 is about; the
# control bench of a #74 run is compared corner by corner against them.
ORIGINAL_TRIGGER_RECORDS = {1: "20261009-023645-6eff628", 2: "20261009-023648-6eff628", 3: "20261009-023651-6eff628"}


def conv_ok(res: M.BenchResult | None, cid: str) -> bool | None:
    if res is None or cid not in res.outcome:
        return None
    return res.outcome[cid]["kind"] == "pass"


def render_conv_record(pdk, cand, rid: str, results: dict[str, M.BenchResult], params: dict,
                       dirty: bool | None, note: str | None = None) -> str:
    L: list[str] = []
    a = L.append
    vbd = M.vbd_ref(cand, params)
    rating = M.ACCESS_RATING_V[cand.n]
    orig_rid = ORIGINAL_TRIGGER_RECORDS.get(cand.n)
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    stims = [s_ for s_ in M.CONV_STIMULI if any(f"{s_}_{v}" in results for v in M.CONV_VARIANTS)]
    a(f"- **Claim**: issue #74 -- does the breakdown-event transient of Candidate {cand.n} / Region {cand.region} "
      "converge at every corner of the full #62 trigger PVT grid on the fleet engine? Benches in this run: "
      + ("the #62 two-instance trigger bench re-run unchanged (control); " if M.CONTROL_BENCH in results else "")
      + "; ".join(f"`{s_}` = {M.CONV_STIMULI[s_]}" for s_ in stims)
      + ". Every single-instance stimulus is run as stock / element-disabled / element-enabled decks "
      "that differ only in the cell line; any non-convergence is attributed by that comparison. Trigger "
      "threshold, latch, program current and access-device terminal voltages (against the ratified "
      f"{rating:g} V rating of `{M.CHAR.CANDIDATES[cand.n - 1].access_model}`) are logged, CONDITIONAL ON THE "
      "ASSUMED breakdown parameters.")
    if dirty is None:
        state = f"; working-tree state at run time not captured, exact decks frozen in the artifact store, manifest `manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`)"
    else:
        state = ", dirty tree at run time)" if dirty else ")"
    a(f"- **Netlist provenance**: schematic (design/netlists/{cand.netlist} wrapped by "
      "design/breakdown/cell_candidates_bd.spice" + state)
    if note:
        a(f"- **Run note**: {note}")
    a("- **Model parameters**: `design/breakdown/breakdown_params.spice` unchanged by #74 (sha256 "
      f"`{M.sha256(M.BD_DIR / 'breakdown_params.spice')}`); element `design/breakdown/af_breakdown.spice` sha256 "
      f"`{M.sha256(M.BD_DIR / 'af_breakdown.spice')}`. Derived V_bd(t_ref) = bd_ebd x c{cand.n}_bd_tox = "
      f"**{vbd:.2f} V** (assumed, not a gf180 number).")
    a("- **Corner matrix run** (each bench one `klt sim` request on the batch fleet; same grid as the #62 "
      f"trigger records): {', '.join(C.MOSCAP_CORNERS)} (MOS typical) x {', '.join(str(t) for t in C.TEMPS_C)} "
      f"degC x 5 stress levels = 45 corners per single-instance bench; the control is 90 corners "
      "(2 instances x 5 levels). Process-minimum (netlist-default) geometry. Levels: the capacitor's rated "
      f"voltage ({cand.cap_rated_v:g} V) and " + ", ".join(f"{f:g}" for f in M.TRIG_FRACTIONS) +
      f" x V_bd. Pulse: edges {M.TRIG_TR*1e9:g} ns (shape per bench, `edge_lines()`), flat {M.TRIG_TW*1e6:g} us from t = "
      f"{M.TRIG_T1*1e6:g} us; `tran {M.fmt(M.TRIG_TSTEP)} {M.fmt(M.TRIG_TSTOP)} uic`; default ngspice tolerances, "
      f"gmin = {M.fmt(M.CHAR.GMIN)}; per-corner timeout 300 s.")
    a("  - PL-driven (`trig1`, `trigc`): PL driven to the signed level, BL = 0 V, WL = "
      f"{cand.moscap_wl_on:g} V, VB = {cand.vb:g} V (the #62 stimulus, one cell).")
    a(f"  - BL-driven (`prog`, `progc`): VPP pulse (positive level) -> ballast {M.prog_rballast(cand, params)/1e3:.4g} kOhm (PLACEHOLDER: "
      f"V_bd / {M.PROG_ILIM_PLACEHOLDER*1e6:g} uA; `I_target_max` is unresolved in `spec/architecture.md` 2) -> BL; "
      f"PL = 0 V return; WL = {cand.moscap_wl_on:g} V + VPP(t)"
      + (f"; n-well VB = {cand.vb:g} V + VPP(t)" if cand.polarity == "p" else f"; VB = {cand.vb:g} V (p-substrate tie)")
      + ". Gate (and well) drive riding on VPP is a bench choice: the gate-drive and well levels are "
      "unresolved in `spec/supply-domains-decision.md` rows 8, 9, 15.")
    envs = [r.klt_env for r in results.values() if r.klt_env]
    if envs:
        e0 = envs[0]
        rm = e0.get("remote") or {}
        a(f"- **Execution**: engine ngspice {e0.get('engine_version')} on the batch fleet (runner klt "
          f"{rm.get('runner_klt_version')}, submitting client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}`); models_lib sha256 "
          f"`{e0.get('models_lib_sha256')}`.")
    a("- **Result**:")
    render_conv_matrix(a, cand, params, results)
    render_control(a, cand, params, results, orig_rid)
    render_attribution(a, rid, results)
    render_opstart(a, rid, results)
    for stim in M.CONV_STIMULI:
        render_conv_trigger(a, cand, params, results, stim)
    if any(b in results for b in M.CONV_BENCHES):
        render_conv_regression(a, results)
        render_device_limits(a, cand, params, results)
        render_prog_current(a, cand, params, results)
    a("- **Links**:")
    a("  - Model: `design/breakdown/` (unchanged by this run)")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Requests, bodies, klt reports, per-corner decks and logs: artifact store manifest "
      f"`manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`, entries `<bench>/…`")
    if orig_rid:
        a(f"  - Original trigger record: `sim/cell-breakdown-model/records/{orig_rid}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host); fleet-side hashes in each `report.json`")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a(f"- **Supersedes**: (none -- the #62 trigger record `{orig_rid}` stays as evidence; this record adds "
      "the #74 convergence campaign)")
    a("")
    return "\n".join(L)


def render_conv_matrix(a, cand, params, results) -> None:
    a("  - **(1) Convergence, every attempted corner counted** (`pass` = klt pass AND every measurement has a "
      "value; failures by kind: `timeout` = 300 s per-corner limit, `timestep` = ngspice \"timestep too "
      "small\", `missing` = ran to the end but a measurement has no value):")
    a("")
    a("    | Bench | Stimulus / variant | Attempted | Pass | Timeout | Timestep | Missing | Other | klt | Job |")
    a("    |---|---|---|---|---|---|---|---|---|---|")
    for b in (M.CONTROL_BENCH,) + M.CONV_BENCHES + (M.OPSTART_BENCH,):
        r = results.get(b)
        if r is None:
            continue
        if b == M.OPSTART_BENCH:
            desc = "stock cell, trigc deck, rated level, operating-point start (no `uic`)"
        else:
            desc = "control: #62 two-instance bench, unchanged" if b == M.CONTROL_BENCH else \
            f"{b.split('_')[0]} / {M.CONV_VARIANTS[M.conv_split(b)[1]]}"
        job = (r.remote or {}).get("job_id", "?") if r.remote else ("submit-error" if r.error else "?")
        t = M.tally([o["kind"] for o in r.outcome.values()])
        a(f"    | `{b}` | {desc} | {t['attempted']} | {t['pass']} | {t['timeout']} | {t['timestep']} | "
          f"{t['missing-measurement']} | {t['error']} | `{r.status}` | `{job}` |")
        if r.error:
            a(f"    | | ERROR: {r.error[:300]!r} | | | | | | | | |")
    a("")
    a("    Per stress level (pass / attempted), each level over 3 moscap corners x 3 temperatures:")
    a("")
    head = ["rated"] + [f"{f:g}x" for f in M.TRIG_FRACTIONS]
    a("    | Bench | " + " | ".join(head) + " |")
    a("    |---|" + "---|" * len(head))
    for b in (M.CONTROL_BENCH,) + M.CONV_BENCHES:
        r = results.get(b)
        if r is None or not r.outcome:
            continue
        stim = "trig1" if b == M.CONTROL_BENCH else M.conv_split(b)[0]  # control: same levels as trig1
        cnt = {h: [0, 0] for h in head}
        for cid, o in r.outcome.items():
            h = M.level_label(cand, params, stim, M.corner_level(cid))
            cnt[h][1] += 1
            cnt[h][0] += o["kind"] == "pass"
        a(f"    | `{b}` | " + " | ".join(f"{cnt[h][0]}/{cnt[h][1]}" for h in head) + " |")
    a("")


def render_control(a, cand, params, results, orig_rid) -> None:
    r = results.get(M.CONTROL_BENCH)
    if r is None or not orig_rid:
        return
    orig = M.results_from_reports(cand, orig_rid, params, benches=(M.CONTROL_BENCH,)).get(M.CONTROL_BENCH)
    if orig is None:
        return
    now_bad = {c for c, o in r.outcome.items() if o["kind"] != "pass"}
    old_bad = {c for c, o in orig.outcome.items() if o["kind"] != "pass"}
    a(f"  - **(2) Control reproduction** -- the #62 two-instance deck, re-submitted unchanged, vs record "
      f"`{orig_rid}`: {len(now_bad)}/{len(r.outcome)} not converged now, {len(old_bad)}/{len(orig.outcome)} "
      f"then; same corners: **{'yes' if now_bad == old_bad else 'no'}**"
      + ("" if now_bad == old_bad else
         f" (only now: {', '.join(f'`{c}`' for c in sorted(now_bad - old_bad)) or 'none'}; only then: "
         f"{', '.join(f'`{c}`' for c in sorted(old_bad - now_bad)) or 'none'})") + ".")
    where: dict[str, int] = {}
    for c in sorted(now_bad):
        o = r.outcome[c]
        k = o["kind"] if o["kind"] != "timestep" else f"timestep in {o['node']} ({control_role(c, o['node'])})"
        where[k] = where.get(k, 0) + 1
    if where:
        a("    Where ngspice reported the failure: " + "; ".join(f"{k}: {n}" for k, n in sorted(where.items())) + ".")


def control_role(cid: str, node: str) -> str:
    """In the two-instance control deck: was the failing node in the stressed
    cell, the idle one, or a testbench source?"""
    m = re.match(r"^(?:e\.)?x([ab])\.", node)
    if not m:
        return "testbench source"
    stressed = "a" if "_pla" in cid else "b"
    return "stressed instance" if m.group(1) == stressed else "idle instance"


def render_attribution(a, rid, results) -> None:
    if not any(b in results for b in M.CONV_BENCHES):
        return
    a("  - **(3) Attribution of non-converged single-instance corners** (stock / disabled / enabled decks of "
      "the same stimulus at the same corner; the committed `.cir` is the minimal reproducer, one cell, one "
      "corner):")
    any_bad = False
    for stim in M.CONV_STIMULI:
        rs = {v: results.get(f"{stim}_{v}") for v in M.CONV_VARIANTS}
        cids = sorted(set().union(*[set(r.outcome) for r in rs.values() if r]))
        for cid in cids:
            ok = {v: conv_ok(rs[v], cid) for v in M.CONV_VARIANTS}
            if all(x is not False for x in ok.values()):
                continue
            any_bad = True
            fails = []
            for v, x in ok.items():
                if x is False:
                    o = rs[v].outcome[cid]
                    det = o["kind"] + (f" at t = {o['time']:.4e} s in `{o['node']}` ({o['where']})"
                                       if o["kind"] == "timestep" else "")
                    fails.append(f"{v}: {det}; reproducer manifest entry `{stim}_{v}/{cid}.cir`")
            a(f"    - `{stim}` `{cid}`: **{M.attribute_corner(ok)}** -- " + "; ".join(fails))
    if not any_bad:
        a("    - none: every corner of every single-instance bench converged.")


def render_opstart(a, rid, results) -> None:
    r = results.get(M.OPSTART_BENCH)
    if r is None:
        return
    t = M.tally([o["kind"] for o in r.outcome.values()])
    job = (r.remote or {}).get("job_id", "?") if r.remote else "?"
    a(f"  - **(3b) Operating-point start, stock cell** (`{M.OPSTART_BENCH}`: the `trigc_st` deck at the rated level, "
      "`tran` WITHOUT `uic`, job "
      f"`{job}`): {t['pass']}/{t['attempted']} converged (timeout {t['timeout']}, timestep {t['timestep']}, "
      f"missing {t['missing-measurement']}, other {t['error']}). No breakdown element is in this deck, so any "
      "failure here is **stock-cell**; reproducer manifest entries "
      f"`{M.OPSTART_BENCH}/<corner>.cir` (run manifest `manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`):")
    for cid in sorted(r.outcome, key=lambda c: (c.split("_")[1], M.corner_temp(c))):
        o = r.outcome[cid]
        a(f"    - `{cid}`: {o['kind']}" + (f" at t = {o['time']:.4e} s in `{o['node']}`" if o["kind"] == "timestep" else ""))


def render_conv_trigger(a, cand, params, results, stim) -> None:
    b0 = results.get(f"{stim}_b0")
    rows = []
    for var, ubd in (("b1m", 0.5), ("b1l", M.UBD_LOW)):
        r = results.get(f"{stim}_{var}")
        if r is None:
            continue
        for cid in sorted(r.values, key=lambda c: (c.split("_")[1], M.corner_temp(c), abs(M.corner_level(c)))):
            vals = r.values[cid]
            vox = (b0.values.get(cid) or {}).get("vox_mid") if b0 else None
            d_lo = d_hi = pred = None
            if vox is not None:
                d_lo, d_hi = M.damage_prediction(cand, params, vox, ubd)
                pred = M.predict_state(d_lo, d_hi)
            rows.append((var, cid, vox, d_lo, pred, vals, r.outcome[cid]["kind"]))
    if not rows:
        return
    title = (f"(4) Trigger/latch, `{stim}`: "
             + ("PL-driven, one cell per deck" if M.STIM_DRIVE[stim] == "pl" else "BL-driven program leg")
             + (", raised-cosine edges" if M.STIM_EDGE[stim] == "rc" else ", C-infinity edges"))
    a(f"  - **{title}** -- predicted state from the E-model applied to the DISABLED deck's mid-pulse oxide "
      "voltage at the same corner (damage over the flat top >= 2: must break down; flat top plus edges <= 0.5: "
      "must not; in between: threshold boundary, not scored). `st` read at "
      f"{M.TRIG_TMID*1e6:g} us (mid-pulse) and {M.TRIG_TMEAS*1e6:g} us (after the pulse: latch):")
    a("")
    a("    | Variant | Corner | Level | V(CN,PL) disabled [V] | D_pred (flat) | predicted | st mid | st end | D end | outcome |")
    a("    |---|---|---|---|---|---|---|---|---|---|")
    n_conv = n_scored = n_ok = n_bound = n_nopred = 0
    for var, cid, vox, d_lo, pred, vals, kind in rows:
        st = vals.get("st")
        conv = kind == "pass"
        n_conv += conv
        if conv and pred is not None and st is not None:
            n_scored += 1
            n_ok += int(M.latched_as_predicted(st, pred))
        n_bound += pred is None and vox is not None
        n_nopred += vox is None
        ptxt = "no prediction" if vox is None else ("boundary" if pred is None else str(pred))
        a(f"    | {var} | `{cid}` | {M.level_label(cand, params, stim, M.corner_level(cid))} | "
          f"{'n/a' if vox is None else f'{vox:.4f}'} | {sci(d_lo)} | {ptxt} | "
          f"{sci(vals.get('st_mid'))} | {sci(st)} | {sci(vals.get('dmg'))} | {kind} |")
    a("")
    a(f"    **Converged {n_conv}/{len(rows)}; outcome as predicted (and fully latched, st = 0 or 1) at "
      f"{n_ok}/{n_scored} scored corners; {n_bound} at the threshold boundary and {n_nopred} without a "
      "prediction because the disabled deck did not converge there (neither scored).**")


CELL_QUANTITIES = tuple(f"{p}_{k}" for k in M.TERMINAL_PAIRS for p in ("mx", "mn")) + \
    ("vox_mid", "vcn_mid", "vbl_mid", "vpl_mid", "vcn_end", "ibl_mid", "ibl_mx", "ibl_mn")


def compare_decks(ra: M.BenchResult | None, rb: M.BenchResult | None, cids=None) -> dict:
    """Exact-equality count and worst relative deviation of every cell
    quantity between two decks, over corners where both converged."""
    out = {"n": 0, "exact": 0, "worst": 0.0, "at": "", "corners": 0}
    if ra is None or rb is None:
        return out
    for cid in sorted(set(ra.values) & set(rb.values)):
        if cids is not None and cid not in cids:
            continue
        if ra.outcome[cid]["kind"] != "pass" or rb.outcome[cid]["kind"] != "pass":
            continue
        out["corners"] += 1
        for q in CELL_QUANTITIES:
            x, y = rb.values[cid].get(q), ra.values[cid].get(q)
            if x is None or y is None:
                continue
            out["n"] += 1
            out["exact"] += x == y
            d = M.rel_dev(x, y) if abs(y) > 1e-9 else abs(x - y)
            if d > out["worst"]:
                out["worst"], out["at"] = d, f"{cid} {q}"
    return out


def render_conv_regression(a, results) -> None:
    a("  - **(5) Element inertness in transient** -- every logged cell quantity (terminal-difference extremes, "
      "mid-pulse and end voltages, BL current), same corner, decks differing only in the cell line. "
      "Relative deviation (absolute below 1 nV/nA):")
    for stim in M.CONV_STIMULI:
        st = results.get(f"{stim}_st")
        if st is None:
            continue
        c = compare_decks(st, results.get(f"{stim}_b0"))
        a(f"    - `{stim}` disabled (`b0`) vs stock: {c['exact']}/{c['n']} exactly equal over {c['corners']} "
          f"corners; worst deviation {c['worst']:.2e}" + (f" at `{c['at']}`" if c["at"] else ""))
        for v in ("b1m", "b1l"):
            r = results.get(f"{stim}_{v}")
            if r is None:
                continue
            intact = {cid for cid, vals in r.values.items() if vals.get("st") == 0.0}
            c = compare_decks(st, r, intact)
            a(f"    - `{stim}` enabled (`{v}`) vs stock where the enabled cell stayed intact (st = 0 exactly): "
              f"{c['exact']}/{c['n']} exactly equal over {c['corners']} corners; worst deviation {c['worst']:.2e}"
              + (f" at `{c['at']}`" if c["at"] else ""))


def render_device_limits(a, cand, params, results) -> None:
    rating = M.ACCESS_RATING_V[cand.n]
    a(f"  - **(6) Terminal voltages vs ratings** -- largest |V| of each pair over the WHOLE transient, worst "
      f"PVT corner per stress level (converged corners only). Access-device rating {rating:g} V "
      f"(`{M.CHAR.CANDIDATES[cand.n - 1].access_model}`); **bold** = exceeds it. The capacitor column is the "
      f"stressed oxide (rated {cand.cap_rated_v:g} V; exceeding it is the point of the bench):")
    head = ["rated"] + [f"{f:g}x" for f in M.TRIG_FRACTIONS]
    for stim in M.CONV_STIMULI:
        for var in ("st", "b1m", "b1l"):
            r = results.get(f"{stim}_{var}")
            if r is None or not r.values:
                continue
            a("")
            a(f"    `{stim}_{var}`:")
            a("")
            a("    | Level | " + " | ".join(f"{k}: {M.TERMINAL_PAIRS[k][0].upper()}-{M.TERMINAL_PAIRS[k][1].upper()}"
                                         for k in M.TERMINAL_PAIRS) + " | over rating |")
            a("    |---|" + "---|" * (len(M.TERMINAL_PAIRS) + 1))
            for h in head:
                cells, over = [], 0
                cids = [c for c in r.values if M.level_label(cand, params, stim, M.corner_level(c)) == h
                        and r.outcome[c]["kind"] == "pass"]
                for k in M.TERMINAL_PAIRS:
                    best, at = None, ""
                    for c in cids:
                        x = M.abs_extreme(r.values[c], k)
                        if x is not None and (best is None or x > best):
                            best, at = x, c
                    if best is None:
                        cells.append("n/a")
                        continue
                    if k in M.ACCESS_PAIRS and best > rating:
                        over += 1
                        cells.append(f"**{best:.2f}**")
                    else:
                        cells.append(f"{best:.2f}")
                a(f"    | {h} ({len(cids)} corners) | " + " | ".join(cells) + f" | {over} pair(s) |")
    a("")


def render_prog_current(a, cand, params, results) -> None:
    rb = M.prog_rballast(cand, params)
    a(f"  - **(7) Program current, BL-driven leg** -- I(BL) at mid-pulse and its peak over the transient; the "
      f"ballast alone allows VPP / {rb/1e3:.4g} kOhm:")
    a("")
    a("    | Variant | Corner | VPP [V] | ballast-only limit [A] | I(BL) mid [A] | I(BL) peak [A] | st end | outcome |")
    a("    |---|---|---|---|---|---|---|---|")
    for var in ("b1m", "b1l"):
        r = results.get(f"prog_{var}")
        if r is None:
            continue
        for cid in sorted(r.values, key=lambda c: (c.split("_")[1], M.corner_temp(c), M.corner_level(c))):
            v = r.values[cid]
            vpp = M.corner_level(cid)
            a(f"    | {var} | `{cid}` | {vpp:.2f} | {sci(vpp / rb)} | {sci(v.get('ibl_mid'))} | "
              f"{sci(v.get('ibl_mx'))} | {sci(v.get('st'))} | {r.outcome[cid]['kind']} |")
    a("")

