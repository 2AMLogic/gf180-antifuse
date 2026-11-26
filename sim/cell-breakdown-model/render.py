#!/usr/bin/env python3
"""sim/cell-breakdown-model render.py -- pure Markdown record renderers.

The #62/#75 record renderers (the #74 convergence record is in render_conv.py) and record-comparison helpers. Imports
one-way from model.py (loaded via harness.modload under its fixed unique
name, reusing the copy the CLI facade already loaded); nothing in model.py
imports this module.
"""

from __future__ import annotations

import math
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

# model.py is loaded under the fixed unique name run_experiment.py uses, so
# the library exists once per process (one BenchResult identity, one V_bd
# override global) whether this module is reached through the CLI or alone.
M = sys.modules.get("sim_cb_model") or load_module(THIS_DIR / "model.py", "sim_cb_model")

# The #74 convergence-record renderer lives in render_conv.py (loaded once under a fixed unique
# name); its public names are re-exported here so they stay reachable through this module and
# the run_experiment.py facade.
_CONV = sys.modules.get("sim_cb_render_conv") or load_module(THIS_DIR / "render_conv.py", "sim_cb_render_conv")
ORIGINAL_TRIGGER_RECORDS = _CONV.ORIGINAL_TRIGGER_RECORDS
CELL_QUANTITIES = _CONV.CELL_QUANTITIES
conv_ok = _CONV.conv_ok
render_conv_record = _CONV.render_conv_record
render_conv_matrix = _CONV.render_conv_matrix
render_control = _CONV.render_control
control_role = _CONV.control_role
render_attribution = _CONV.render_attribution
render_opstart = _CONV.render_opstart
render_conv_trigger = _CONV.render_conv_trigger
compare_decks = _CONV.compare_decks
render_conv_regression = _CONV.render_conv_regression
render_device_limits = _CONV.render_device_limits
render_prog_current = _CONV.render_prog_current


def stored_record_id(cand) -> str | None:
    hits = []
    for p in sorted((M.CHAR_DIR / "records").glob("*.md")):
        # only records with committed raw per-corner logs can serve as the (a2) reproduction baseline; the
        # klt-campaign records (issue #99 re-pin) carry reports, not .log files
        if (M.CHAR_DIR / "corners" / p.stem).is_dir() and re.search(rf"Candidate {cand.n}\b", p.read_text()):
            hits.append(p.stem)
    return hits[-1] if hits else None


def stored_value(rid: str, sizing: str, geom: str, cid: str, name: str) -> float | None:
    p = M.CHAR_DIR / "corners" / rid / f"access-{sizing}_cap-{geom}" / f"{cid}.log"
    if not p.is_file():
        return None
    return NF.parse_scalar(p.read_text(), name)


def stored_headline(rid: str) -> dict:
    text = (M.CHAR_DIR / "records" / f"{rid}.md").read_text()
    out = {}
    m = re.search(r"I_sneak_max = ([0-9.eE+-]+) A", text)
    out["i_sneak_max"] = float(m.group(1)) if m else None
    m = re.search(r"R_on = ([0-9.eE+-]+) ohm", text)
    out["r_on"] = float(m.group(1)) if m else None
    return out


SIZING_GEOM = [(s, g) for s in ("min", "2x") for g in ("min", "2x")]


def inertness(results: dict[str, M.BenchResult]) -> list[dict]:
    """Within one solve: does every regression quantity agree across the
    three variants? Exact equality of the printed values is required."""
    rows = []
    for bench in ("access_op", "access_ac", "cap_op", "cap_ac"):
        r = results.get(bench)
        if r is None or not r.values:
            continue
        for v in ("b0", "b1"):
            n = exact = ok = 0
            worst, worst_at, q = 0.0, "", ""
            for cid, vals in r.values.items():
                for name, x in vals.items():
                    m = re.match(rf"^(ioff|ron|ilk|cval)_{v}_(.*)$", name)
                    if not m:
                        continue
                    q = m.group(1)
                    ref = vals.get(f"{q}_st_{m.group(2)}")
                    if ref is None or x is None:
                        continue
                    n += 1
                    exact += x == ref
                    ok += M.within_tol(q, x, ref)
                    d = M.rel_dev(x, ref)
                    if d > worst:
                        worst, worst_at = d, f"{cid} {name}"
            rows.append({"bench": bench, "quantity": q, "variant": v, "n": n, "exact": exact, "ok": ok,
                         "worst_rel": worst, "worst_at": worst_at})
    return rows


def reproduction(results: dict[str, M.BenchResult], rid: str) -> list[dict]:
    """Default-tolerance benches vs the committed raw logs of `rid`."""
    rows = []
    spec = [
        ("access_op", "ioff", {"lo": "ioff_lo", "mid": "ioff_mid", "hi": "ioff_hi"}),
        ("access_ac", "ron", {None: "ron"}),
        ("cap_op", "ilk", {k: f"ilk_{k}" for k in range(1, 6)}),
        ("cap_ac", "cval", {k: f"cval_{k}" for k in range(1, 6)}),
    ]
    for bench, q, suffixes in spec:
        r = results.get(bench)
        if r is None or not r.values:
            continue
        for v in M.REGRESSION_VARIANTS:
            n = ok = exact = missing = 0
            worst, worst_at = 0.0, ""
            for cid, vals in r.values.items():
                for s, g in SIZING_GEOM:
                    for suf, stored_name in suffixes.items():
                        name = f"{q}_{v}_{M.sg_tag(s, g)}" + (f"_{suf}" if suf is not None else "")
                        x = vals.get(name)
                        ref = stored_value(rid, s, g, cid, stored_name)
                        if x is None or ref is None:
                            missing += 1
                            continue
                        n += 1
                        rel = M.rel_dev(x, ref)
                        ok += M.within_tol(q, x, ref)
                        exact += x == ref
                        if rel > worst:
                            worst, worst_at = rel, f"{cid} {name}"
            rows.append({"bench": bench, "quantity": q, "variant": v, "n": n, "ok": ok, "exact": exact,
                         "missing": missing, "worst_rel": worst, "worst_at": worst_at})
    return rows


def headline(results: dict[str, M.BenchResult], variant: str) -> dict:
    fh_c, fh_t, fh_dv = C.FAST_HOT_HIGH
    sc_c, sc_t, sc_dv = C.SLOW_COLD_LOW
    fh = C.corner_id(fh_c, fh_t, C.fmt_node_supply("bl", M.CHAR.V_READ_NOM * (1 + fh_dv)))
    sc = C.corner_id(sc_c, sc_t, C.fmt_node_supply("bl", M.CHAR.V_READ_NOM * (1 + sc_dv)))
    out = {"fh": fh, "sc": sc, "i_off": None, "i_sneak_max": None, "r_on": None}
    op = results.get("access_op")
    if op and fh in op.values:
        vals = [x for n, x in op.values[fh].items() if n.startswith(f"ioff_{variant}_") and x is not None]
        if vals:
            out["i_off"] = max(vals)
            out["i_sneak_max"] = (M.CHAR.N_GRID - 1) * max(vals)
    ac = results.get("access_ac")
    if ac and sc in ac.values:
        vals = [x for n, x in ac.values[sc].items() if n.startswith(f"ron_{variant}_") and x is not None]
        if vals:
            out["r_on"] = max(vals)
    return out


def iread_table(results: dict[str, M.BenchResult]) -> list[dict]:
    op = results.get("access_op")
    rows = []
    if not op:
        return rows
    for cid, vals in op.values.items():
        med = [x for n, x in vals.items() if n.startswith("iread_pm_") and x is not None]
        wc = {n: x for n, x in vals.items() if n.startswith("iread_pw_") and x is not None}
        if not wc:
            rows.append({"cid": cid, "med_min": None, "wc_min": None, "wc_at": "", "status": op.corner_status.get(cid)})
            continue
        at = min(wc, key=wc.get)
        rows.append({"cid": cid, "med_min": min(med) if med else None, "wc_min": wc[at],
                     "wc_at": at.replace("iread_pw_", ""), "status": op.corner_status.get(cid)})
    return rows


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------


sci = NF.sci


def render_record(pdk, cand, rid: str, results: dict[str, M.BenchResult], params: dict,
                  dirty: bool | None, stored_rid: str | None, note: str | None = None) -> str:
    L: list[str] = []
    a = L.append
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    a("- **Claim**: issue #62 -- behavioral breakdown-augmented model for Candidate "
      f"{cand.n} / Region {cand.region} (`spec/cell-candidates.md` \"Post-breakdown model behavior\" gap; "
      "`spec/architecture.md#4-sense-scheme` `I_ref < I_prog_min`). (a) With the breakdown element disabled, "
      "or enabled but unprogrammed, the cell reproduces `sim/cell-device-characterization` "
      f"record `{stored_rid}`; (b) programmed-cell read current and `I_prog_min` per PVT corner under the "
      "ASSUMED parameters of `design/breakdown/breakdown_params.spice`; (c) the trigger/latch mechanism.")
    if dirty is None:
        state = (f"; working-tree state at run time not captured -- the run executed commit "
                 f"`{rid.rsplit('-', 1)[-1]}` (record id), and the exact decks are frozen in the artifact "
                 f"store, manifest `manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`)")
    else:
        state = ", dirty tree at run time)" if dirty else ")"
    prov = f"schematic (design/netlists/{cand.netlist} wrapped by design/breakdown/cell_candidates_bd.spice" + state
    a(f"- **Netlist provenance**: {prov}")
    if note:
        a(f"- **Run note**: {note}")
    a("- **Model parameters** (sha256 of `design/breakdown/breakdown_params.spice`: "
      f"`{M.sha256(M.BD_DIR / 'breakdown_params.spice')}`):")
    a("")
    a("  | Parameter | Value | Unit | Provenance |")
    a("  |---|---|---|---|")
    for name, p in params.items():
        if name.startswith("c") and "_bd_tox" in name and not name.startswith(f"c{cand.n}_"):
            continue
        a(f"  | `{name}` | {p['value']:.4g} | {p['unit']} | {p['provenance']} |")
    a("")
    a(f"  Derived: V_bd(t_ref) = bd_ebd x c{cand.n}_bd_tox = **{M.vbd_ref(cand, params):.2f} V** (assumed, "
      "not a gf180 number); worst-case filament rf = bd_rf_med x exp(bd_zrf_wc x bd_rf_sig) = "
      f"{params['bd_rf_med']['value'] * math.exp(params['bd_zrf_wc']['value'] * params['bd_rf_sig']['value']):.4g} ohm.")
    a("- **Corner matrix run** (each bench one `klt sim` request; job ids below):")
    a(f"  - access benches: MOS process {', '.join(C.MOS_CORNERS)} (moscap_typical) x "
      f"{', '.join(str(t) for t in C.TEMPS_C)} degC x read rail {M.CHAR.V_READ_NOM*0.9:.2f}/{M.CHAR.V_READ_NOM:.2f}/"
      f"{M.CHAR.V_READ_NOM*1.1:.2f} V = 45 corners; x 4 (access-sizing x capacitor-geometry) sub-configurations "
      "as instances in the same deck")
    a(f"  - capacitor benches: {', '.join(C.MOSCAP_CORNERS)} (MOS typical) x 3 temperatures = 9 corners (`nosupply`), "
      "x 4 sub-configurations x 5 capacitor biases as instances")
    a(f"  - trigger bench: {', '.join(C.MOSCAP_CORNERS)} x 3 temperatures x 10 stress points "
      "(2 instances x 5 levels, one stressed per corner) = 90 corners, process-minimum (netlist-default) geometry")
    a("  - geometry/sizing levels are the committed netlists' placeholder defaults and their x2 widths, "
      "NOT `spec/split-axis-plan.md`'s ratified levels (same caveat as the characterization records)")
    envs = [r.klt_env for r in results.values() if r.klt_env]
    if envs:
        e0 = envs[0]
        rm = e0.get("remote") or {}
        a(f"- **Execution**: engine ngspice {e0.get('engine_version')} on the batch fleet "
          f"(runner klt {rm.get('runner_klt_version')}, submitting client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}` -- requests use only runner-supported "
          "features, README \"Fleet klt version\"); models_lib sha256 "
          f"`{e0.get('models_lib_sha256')}`. ngspice {e0.get('engine_version')} prints `.meas` results to 6 "
          "significant digits; the committed characterization logs carry 7, so exact digit matches against "
          "them are not expected and relative deviations of order 1e-6 are print precision.")
    a("- **Result**:")
    a("  - **Bench status**:")
    for b in M.BENCHES:
        r = results.get(b)
        if r is None:
            a(f"    - `{b}`: not run")
            continue
        job = (r.remote or {}).get("job_id", "local") if r.remote is not None else "local"
        nerr = sum(1 for s in r.corner_status.values() if s != "pass")
        a(f"    - `{b}`: klt status `{r.status}`, {len(r.corner_status)} corners, {nerr} not `pass`, job `{job}`"
          + (f" -- ERROR: {r.error[:400]}" if r.error else ""))
    a("  - **(a1) Element inertness, same deck** -- each regression quantity of the disabled (`b0`) and the "
      "enabled-unprogrammed (`b1`) wrapper vs the stock cell instance at the same bias in the same solve. "
      f"Criterion (README \"Regression criterion\"): well-conditioned {'/'.join(M.WELL_CONDITIONED)} within "
      f"reltol = {M.DEFAULT_RELTOL:g}; gmin-floor {'/'.join(M.GMIN_FLOOR)} within reltol*|ref| + abstol "
      f"({M.DEFAULT_ABSTOL:g} A), ngspice's own convergence bound for currents below abstol. Exact-match counts "
      "and the worst relative deviation are reported regardless:")
    if not inertness(results):
        a("    - (no regression bench in this run)")
    for row in inertness(results):
        a(f"    - `{row['bench']}` {row['quantity']} [{row['variant']}]: {row['ok']}/{row['n']} within criterion, "
          f"{row['exact']}/{row['n']} exactly equal; worst relative difference {row['worst_rel']:.2e}"
          + (f" at `{row['worst_at']}`" if row["worst_at"] else ""))
    if stored_rid and ("access_op" in results or "access_ac" in results or "cap_op" in results or "cap_ac" in results):
        a(f"  - **(a2) Reproduction of committed record `{stored_rid}`** (default tolerances, as that record ran) -- "
          "per corner and sub-configuration vs its raw logs; same class-based criterion as (a1):")
        for row in reproduction(results, stored_rid):
            a(f"    - `{row['bench']}` {row['quantity']} [{row['variant']}: {M.VARIANTS[row['variant']]}]: "
              f"{row['ok']}/{row['n']} within criterion, {row['exact']}/{row['n']} exactly equal, "
              f"worst relative deviation {row['worst_rel']:.2e}"
              + (f" at `{row['worst_at']}`" if row["worst_at"] else "")
              + (f", {row['missing']} not comparable" if row["missing"] else ""))
        sh = stored_headline(stored_rid)
        for v in M.REGRESSION_VARIANTS:
            h = headline(results, v)
            a(f"    - headline, {v}: I_sneak_max = {sci(h['i_sneak_max'])} A at `{h['fh']}` (record: "
              f"{sci(sh['i_sneak_max'])}); R_on = {sci(h['r_on'])} ohm at `{h['sc']}` (record: {sci(sh['r_on'])})")
    rows = iread_table(results)
    if rows:
        render_iread(a, rows, results, cand)
    tr = results.get("trigger")
    if tr and tr.values:
        render_trigger(a, tr, cand, params)
    render_links(a, rid, stored_rid, pdk)
    return "\n".join(L)



def render_bias_record(pdk, cand, rid: str, results: dict[str, M.BenchResult], params: dict,
                       dirty: bool | None, note: str | None = None) -> str:
    """Record for the Candidate 3 read-bias study (#75). Every scenario is
    reported -- feasible or not -- so the choice in
    spec/candidate3-read-bias-decision.md can be audited against all alternatives."""
    L: list[str] = []
    a = L.append
    r = results[M.BIAS_BENCH]
    lo, mid, hi = M.CHAR.off_levels(cand)
    stats = {sc.name: M.bias_stats(r.values, r.corner_status, sc) for sc in M.BIAS_SCENARIOS}
    volt = {sc.name: M.bias_voltages(r.values, sc, (lo, mid, hi)) for sc in M.BIAS_SCENARIOS}
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    a("- **Claim**: issue #75 -- Candidate 3 / Region III read bias. At the #62 placeholder bias (WL on = 0 V, "
      "n-well 3.3 V) the programmed cell reads below `I_sneak_max`, so `spec/architecture.md#4-sense-scheme`'s "
      "`I_sneak_max < I_ref < I_prog_min` has no solution. This record compares seven alternative read-bias "
      "arrangements plus two well-offset sensitivities, each with the programmed and the unprogrammed cell "
      "simulated at the SAME bias and the leakage bound recomputed at that bias, over the full PVT matrix. "
      "Decision: `spec/candidate3-read-bias-decision.md`. Candidates 1 and 2 are not touched by this bench "
      "(their records are the #62 ones).")
    state = ("; working-tree state at run time not captured" if dirty is None
             else (", dirty tree at run time)" if dirty else ")"))
    a(f"- **Netlist provenance**: schematic (design/netlists/{cand.netlist} wrapped by "
      "design/breakdown/cell_candidates_bd.spice" + state)
    if note:
        a(f"- **Run note**: {note}")
    a("- **Model parameters**: assumed breakdown/filament parameters of `design/breakdown/breakdown_params.spice` "
      f"(sha256 `{M.sha256(M.BD_DIR / 'breakdown_params.spice')}`); filament rf_med = "
      f"{params['bd_rf_med']['value']:.4g} ohm, worst case rf_wc = "
      f"{params['bd_rf_med']['value'] * math.exp(params['bd_zrf_wc']['value'] * params['bd_rf_sig']['value']):.4g} ohm "
      f"(+{params['bd_zrf_wc']['value']:g} sigma). ALL programmed-cell currents below are CONDITIONAL on these "
      "assumed filament resistances; none is a gf180 measurement.")
    a(f"- **Corner matrix run** (one `klt sim` request, one deck, all scenarios as instances): MOS process "
      f"{', '.join(C.MOS_CORNERS)} x {', '.join(str(t) for t in C.TEMPS_C)} degC x read-rail corner "
      f"{M.CHAR.V_READ_NOM*0.9:.2f}/{M.CHAR.V_READ_NOM:.2f}/{M.CHAR.V_READ_NOM*1.1:.2f} V (scaled by each scenario's "
      f"rail factor) = 45 corners; 4 access-sizing x capacitor-geometry sub-configurations per scenario. "
      f"Geometry levels are the committed netlist's placeholder defaults and x2, NOT the ratified split-axis levels. "
      f"Unselected-WL OFF levels {lo:g}/{mid:g}/{hi:g} V in every scenario.")
    if r.klt_env:
        e0 = r.klt_env
        rm = e0.get("remote") or {}
        a(f"- **Execution**: ngspice {e0.get('engine_version')} on the batch fleet (job "
          f"`{rm.get('job_id')}`, runner klt {rm.get('runner_klt_version')}, client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}`); models_lib sha256 `{e0.get('models_lib_sha256')}`.")
    nerr = sum(1 for x in r.corner_status.values() if x != "pass")
    a(f"- **Bench status**: klt `{r.status}`, {len(r.corner_status)} corners, {nerr} not `pass`"
      + (f" -- ERROR: {r.error[:400]}" if r.error else ""))
    a("- **Method**:")
    a("  - `I_off` = max over {unprogrammed, programmed(median filament)} cells x 3 OFF levels x 4 sub-configs "
      "of the BL current with WL at an OFF level and PL = 0. The programmed-OFF case is the worst sneak case "
      "(CN pulled to PL, full V_DS across the OFF device) and is new relative to #62's unprogrammed-only `I_off`.")
    a(f"  - `I_sneak_max` = (N-1) x `I_off`, N = {M.CHAR.N_GRID} (`spec/split-axis-plan.md`). Currents below "
      f"abstol ({M.DEFAULT_ABSTOL:g} A) are not resolved by ngspice, and `gmin` = {M.CHAR.GMIN:g} S dominates them; the "
      "**solver-floor-limited bound** `I_sneak,f` = (N-1) x max(`I_off`, abstol) is therefore the number the "
      "verdict uses. Model leakage below abstol is UNRESOLVED: the raw values are exactly 0.0 A or +-k x 2^-54 "
      "(machine-epsilon residue of both signs), i.e. solver roundoff, not model output, and `abs()` in the "
      "derivation hides the sign. The bound is a resolution floor, not a bound on physical leakage and not a "
      "prediction.")
    a("  - `I_zero,f` = `I_sneak,f` + max(selected-unprogrammed current, abstol): the current an UNPROGRAMMED "
      "selected cell reads together with the N-1 unselected cells. `I_prog` = worst-filament (rf_wc) programmed "
      "read current, minimum over sub-configs. A bias is **feasible** iff, with no failed corner, "
      "min over all corners of `I_prog` > max over all corners of `I_zero,f` (a single common `I_ref` exists; "
      "the window is the ratio). The per-corner pass count (same-corner comparison) is also given.")
    a("")
    a("- **Result** (all scenarios; per-corner values in the per-scenario tables):")
    a("")
    a("  | Scenario | rail x | WL on [V] | n-well | failed corners | min I_prog [A] (corner) | max I_sneak_max [A] | max I_zero,f [A] | corners with I_prog > I_zero,f | window (I_prog min / I_zero,f max) | feasible |")
    a("  |---|---|---|---|---|---|---|---|---|---|---|")
    for sc in M.BIAS_SCENARIOS:
        st = stats[sc.name]
        vb = f"{sc.vb_v:g} V fixed" if sc.vb_mode == "fixed" else f"BL {sc.vb_v:+g} V"
        if "prog_min" in st:
            a(f"  | `{sc.name}` | {sc.rail_scale:g} | {sc.wl_on:g} | {vb} | {len(st['failed'])} | "
              f"{sci(st['prog_min'])} (`{st['prog_min_at']}`) | {sci(st['sneak_max'])} | {sci(st['zero_f_max'])} | "
              f"{st['per_corner_ok']}/{len(st['rows'])} | {st['window']:.3g} | **{'yes' if st['common_iref'] else 'NO'}** |")
        else:
            a(f"  | `{sc.name}` | {sc.rail_scale:g} | {sc.wl_on:g} | {vb} | {len(st['failed'])} | n/a | n/a | n/a | 0/0 | n/a | **NO** |")
    a("")
    a("- **Junction polarity and oxide checks** (worst over corners, from the measured BL/n-well/CN voltages of the "
      f"programmed cells; limits: pfet_06v0 {M.PFET06_RATING_V:g} V, cap_pmos_03v3 {M.CAP_RATING_C3_V:g} V; a p+/n-well "
      f"junction is called reverse/zero-biased if its forward bias stays under {M.JUNCTION_FWD_LIMIT_V:g} V -- an "
      "ASSUMED screening limit, not a PDK number):")
    a("")
    a("  | Scenario | n-well minus BL, min [V] | n-well minus CN, min [V] | gate-to-well max [V] | gate-to-BL max [V] | cell oxide V (BL-PL) max [V] | junctions ok | gate ok | cap ok |")
    a("  |---|---|---|---|---|---|---|---|---|")
    for sc in M.BIAS_SCENARIOS:
        v = volt[sc.name]
        if not v:
            a(f"  | `{sc.name}` | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        a(f"  | `{sc.name}` | {v['src_well_min']:+.3f} | {v['drn_well_min']:+.3f} | {v['gate_well_max']:.2f} | "
          f"{v['gate_bl_max']:.2f} | {v['cap_v_max']:.2f} | {'yes' if v['fwd_ok'] else 'NO'} | "
          f"{'yes' if v['gate_ok'] else 'NO'} | {'yes' if v['cap_ok'] else 'NO'} |")
    a("")
    for sc in M.BIAS_SCENARIOS:
        st = stats[sc.name]
        a(f"- **`{sc.name}`** -- {sc.note}")
        if st["failed"]:
            a(f"  - **FAILED / unresolved corners ({len(st['failed'])})**: "
              + "; ".join(f"`{c}` (klt `{s_}`, {d})" for c, s_, d in st["failed"]))
        if not st["rows"]:
            a("  - no resolved corner")
            continue
        a(f"  - Per sub-configuration (access sizing s1/s2 x capacitor geometry g1/g2; splits are not averaged): "
          + "; ".join(f"{sg}: min I_prog {sci(d['prog'][0])} (`{d['prog'][1]}`), max I_off {sci(d['off'][0])}, "
                      f"max I_sel-unprog {sci(d['un'][0])}" for sg, d in sorted(st["by_sg"].items())))
        if st["per_corner_bad"]:
            a(f"  - corners where I_prog <= I_zero,f: {', '.join('`'+c+'`' for c in st['per_corner_bad'])}")
        if sc.name == M.CHOSEN_C3_SCENARIO:
            a("")
            a("    | Corner | I_prog rf_wc, worst sub-config [A] | I_prog rf_med [A] | I_off (unprog/prog max) [A] | I_sneak_max [A] | I_zero,f [A] | I_prog / I_zero,f |")
            a("    |---|---|---|---|---|---|---|")
            for cid, row in st["rows"].items():
                a(f"    | `{cid}` | {sci(row['i_prog'])} ({row['i_prog_at']}) | {sci(row['i_prog_med'])} | "
                  f"{sci(row['i_off'])} | {sci(row['i_sneak'])} | {sci(row['i_zero_f'])} | {row['i_prog']/row['i_zero_f']:.3g} |")
            a("")
    chosen = stats[M.CHOSEN_C3_SCENARIO]
    a(f"- **Chosen scenario (as adopted in the decision record)**: `{M.CHOSEN_C3_SCENARIO}`; feasible = "
      f"**{chosen['common_iref']}**" + (f", window {chosen['window']:.3g}" if "window" in chosen else "")
      + (f"; failed corners: {len(chosen['failed'])}" if chosen["failed"] else "") + ".")
    a("- **Caveats**: conditional behavioral simulation, not silicon. Junction leakage, GIDL and well-to-substrate "
      "terms beyond the PDK model are not characterized; read disturb is NOT established (the oxide voltage is "
      "listed, the E-model parameters are assumed). Region III only; the program-leg overstress question is #90.")
    a("- **Links**:")
    a("  - Decision record: `spec/candidate3-read-bias-decision.md`")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Request, body, klt report, per-corner decks and logs: artifact store manifest "
      f"`manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`, entries `{M.BIAS_BENCH}/…`")
    a("  - Failure being fixed (placeholder bias): `sim/cell-breakdown-model/records/20261009-020416-66efd11.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host)")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("- **Supersedes**: (none -- appends; `20261009-020416-66efd11` stays as the placeholder-bias record)")
    a("")
    return "\n".join(L)


def render_iread(a, rows, results, cand) -> None:
    a("  - **(b) Programmed-cell read current** (BL = read rail, WL fully on, PL = 0, state forced programmed; "
      "minimum over the 4 sub-configurations at each corner). `rf_med` = median filament, `rf_wc` = "
      "+bd_zrf_wc sigma filament. CONDITIONAL ON THE ASSUMED FILAMENT PARAMETERS:")
    a("")
    a("    | Corner | I_read (rf_med) [A] | I_read (rf_wc) [A] | worst sub-config | klt |")
    a("    |---|---|---|---|---|")
    for row in rows:
        a(f"    | `{row['cid']}` | {sci(row['med_min'])} | {sci(row['wc_min'])} | {row['wc_at']} | {row['status']} |")
    a("")
    h1 = headline(results, "b1")
    sc_row = next((r for r in rows if r["cid"] == h1["sc"]), None)
    valid = [r for r in rows if r["wc_min"] is not None]
    glob = min(valid, key=lambda r: r["wc_min"]) if valid else None
    a(f"  - **I_prog_min (Candidate {cand.n})**, worst-case filament (rf_wc), worst sub-configuration:")
    a(f"    - at the corner `spec/architecture.md` Section 4 names for the selected cell (`{h1['sc']}`): "
      f"**{sci(sc_row['wc_min'] if sc_row else None)} A**")
    a(f"    - worst over all {len(valid)} resolved corners: **{sci(glob['wc_min'] if glob else None)} A** at "
      f"`{glob['cid'] if glob else 'n/a'}`" + (" -- a different corner than Section 4 names" if glob and sc_row
                                                  and glob["cid"] != sc_row["cid"] else ""))
    if h1["i_sneak_max"] is not None and glob is not None:
        ratio = glob["wc_min"] / h1["i_sneak_max"]
        if ratio > 1:
            a(f"    - against this run's unprogrammed-model `I_sneak_max` = {sci(h1['i_sneak_max'])} A (`{h1['fh']}`, "
              "gmin-floor upper bound): the `I_sneak_max < I_ref < I_prog_min` window spans a factor of "
              f"**{ratio:.3g}** (worst-corner I_prog_min). This sizes nothing -- it is conditional on the assumed "
              "filament distribution and the placeholder read/WL biases.")
        else:
            a(f"    - against this run's unprogrammed-model `I_sneak_max` = {sci(h1['i_sneak_max'])} A (`{h1['fh']}`): "
              f"the worst-corner I_prog_min is **below** it (ratio {ratio:.3g}). **No `I_ref` satisfies "
              "`I_sneak_max < I_ref < I_prog_min` at these placeholder read/WL biases, so a usable I_prog_min "
              "cannot be derived for this candidate until its read bias is set** -- see the run note.")


def render_trigger(a, tr: M.BenchResult, cand, params: dict) -> None:
    if tr.values:
        lv = M.trigger_levels(cand, params)
        a("  - **(c) Trigger/latch** -- PL stressed with a raised-cosine pulse "
          f"({M.TRIG_TW*1e6:g} us flat, {M.TRIG_TR*1e9:g} ns edges) with the access device on and BL = 0; state "
          f"`st` and damage `D` read at {M.TRIG_TMEAS*1e6:g} us, i.e. after the pulse has ended (a latched state "
          "must still read 1). Instance a: median Weibull quantile; instance b: ubd = "
          f"{M.UBD_LOW}. Model-mechanism check only, NOT a program-path claim:")
        a("")
        a("    | Corner | V(PL) [V] | inst | predicted st | st | D | V(CN,PL) mid-pulse [V] | klt |")
        a("    |---|---|---|---|---|---|---|---|")
        n_conv = n_ok = 0
        for cid in sorted(tr.values):
            vals = tr.values[cid]
            inst = "a" if "_pla" in cid else "b"
            vpl = cid.rsplit("_", 1)[1][3:-1].replace("p", ".")  # pla8p00v -> 8.00
            pred = trigger_prediction(cand, params, float(vpl), inst)
            st = vals.get(f"st_{inst}")
            if st is not None and tr.corner_status.get(cid) == "pass":
                n_conv += 1
                n_ok += int((st > 0.5) == bool(pred))
            a(f"    | `{cid}` | {vpl} | {inst} | {pred} | {sci(st)} | {sci(vals.get(f'dmg_{inst}'))} "
              f"| {M.vox(vals, inst)} | {tr.corner_status.get(cid)} |")
        a("")
        a(f"    **Converged corners: {n_conv}/{len(tr.corner_status)}; outcome as predicted at {n_ok}/{n_conv}.** "
          "Prediction (from the parameters alone): intact at the rated voltage and at 0.9 x V_bd; at 0.95 x V_bd "
          f"intact for the median instance a (D ~ 0.32) but broken down for instance b (ubd = {M.UBD_LOW}); broken "
          "down and latched at 1.0 and 1.1 x V_bd. Non-converged corners carry no state reading and are not "
          "counted either way (README \"Transient start\"; follow-up #74).")
        a(f"    Stress points: rated voltage {abs(lv[0]):.2f} V, then "
          + ", ".join(f"{f:g} x V_bd" for f in M.TRIG_FRACTIONS) + f" (V_bd = {M.vbd_ref(cand, params):.2f} V).")


def trigger_prediction(cand, params: dict, vpl: float, inst: str) -> int:
    """Expected latched state (0/1) at the end of the trigger bench, from the
    stress level alone (index into trigger_levels)."""
    lv = [abs(v) for v in M.trigger_levels(cand, params)]
    i = min(range(len(lv)), key=lambda k: abs(lv[k] - abs(vpl)))
    f = (None,) + M.TRIG_FRACTIONS
    if i == 0 or f[i] < 0.95:
        return 0
    if f[i] == 0.95:
        return 0 if inst == "a" else 1
    return 1


def render_links(a, rid: str, stored_rid: str | None, pdk) -> None:
    a("- **Links**:")
    a("  - Model: `design/breakdown/` (element, wrappers, parameters, `check_params.py`)")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Requests, generated bodies, klt reports, per-corner decks and logs: artifact store manifest "
      f"`manifests/artifacts/cell-breakdown-model-{rid}.manifest.json`, entries `<bench>/…`")
    a(f"  - Regression reference: `sim/cell-device-characterization/records/{stored_rid}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host); fleet-side engine/model hashes in each `report.json` `environment`")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("- **Supersedes**: (none -- first record for this claim/region)")
    a("")


def render_any(pdk, cand, rid: str, results: dict[str, M.BenchResult], params: dict, dirty, note) -> str:
    """A run that includes any #74 bench gets the convergence record; a bias_op-only run (#75) its own."""
    if set(results) == {M.BIAS_BENCH}:
        return render_bias_record(pdk, cand, rid, results, params, dirty, note)
    if any(b in M.CONV_BENCHES or b == M.OPSTART_BENCH for b in results):
        return render_conv_record(pdk, cand, rid, results, params, dirty, note)
    return render_record(pdk, cand, rid, results, params, dirty, stored_record_id(cand), note)
