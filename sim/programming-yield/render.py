#!/usr/bin/env python3
"""sim/programming-yield render.py -- pure Markdown record renderer and
read-table helpers.

Turns saved `klt sim` reports (loaded by model.load_run) into the per-run
record under records/: the provenance header and success criteria, the
execution job list, the programmed-read table, the per-sizing yield tables,
the worst-corner table, the sampler check and the access-path current
distribution. Imports one-way from model.py (loaded via harness.modload
under its fixed unique name, reusing the copy the CLI facade already
loaded); nothing in model.py imports this module.
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
# the library exists once per process whether this module is reached through
# the CLI or alone.
M = sys.modules.get("sim_py_model") or load_module(THIS_DIR / "model.py", "sim_py_model")

IBSWEEP = (1e-5, 1e-4, 1e-3, 1e-2)      # I_bound levels the current table reports fractions below


def sci(x) -> str:
    return NF.sci(x, nan_placeholder=True)


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def parse_record_figs(rid: str) -> dict[str, float]:
    """I_sneak_max and worst-corner I_prog_min out of the #62 record (not retyped)."""
    txt = (SIM_DIR / "cell-breakdown-model" / "records" / f"{rid}.md").read_text()
    sn = re.search(r"headline, st: I_sneak_max = ([0-9.eE+-]+) A", txt)
    pm = re.search(r"worst over all 45 resolved corners: \*\*([0-9.eE+-]+) A\*\*", txt)
    out = {}
    if sn:
        out["i_sneak_max"] = float(sn.group(1))
    if pm:
        out["i_prog_min_wc"] = float(pm.group(1))
    return out


def stored_bd_record(cand) -> str | None:
    """The #62 static-bench record of this candidate (the one with an I_prog_min section)."""
    for rp in sorted((SIM_DIR / "cell-breakdown-model" / "records").glob("*.md")):
        t = rp.read_text()
        if f"**I_prog_min (Candidate {cand.n})**" in t:
            return rp.stem
    return None


def read_tables(readtab: dict | None) -> dict[str, dict[str, dict[int, float]]]:
    """sizing -> corner-id -> {z: |I_read|}"""
    out: dict[str, dict[str, dict[int, float]]] = {}
    if not readtab:
        return out
    for c in readtab["corners"]:
        cid = C.corner_id(c["process"], int(round(c["temperature_c"])),
                          C.fmt_node_supply("bl", (c.get("supply_v") or {}).get("vbl", 0.0)))
        for m in c["measurements"]:
            mm = re.match(r"i_(min|2x)_z([pm])(\d)$", m["name"].lower())
            if mm and m["value"] is not None and c["status"] == "pass":
                z = int(mm.group(3)) * (1 if mm.group(2) == "p" else -1)
                out.setdefault(mm.group(1), {}).setdefault(cid, {})[z] = abs(m["value"])
    return out


def worst_table(per_corner: dict[str, dict[int, float]]) -> dict[int, float]:
    """Pointwise minimum over the read corners: the worst-case read at each z."""
    z_all = sorted({z for t in per_corner.values() for z in t})
    return {z: min(t[z] for t in per_corner.values() if z in t) for z in z_all}


# ---------------------------------------------------------------------------
# Record sections (render_record runs them in order; each appends lines)
# ---------------------------------------------------------------------------


def _header(a: list[str], rid: str, cand, dirty, note: str | None, params: dict, vbd: float) -> None:
    P_ = a.append
    P_(f"# Record {rid}")
    P_("")
    P_(f"- **Record ID**: {rid}")
    P_(f"- **Claim**: issue #66 -- programming yield of Candidate {cand.n} / Region {cand.region}, "
       "success fraction vs pulse condition (`spec/split-axis-plan.md` section 4), per access-sizing "
       "sub-configuration and PVT corner. Substantiates T1 item 6 (Monte Carlo evidence) only in the "
       "conditional form stated in the banner below.")
    P_(f"- **Netlist provenance**: schematic (design/netlists/{cand.netlist} wrapped by design/breakdown/"
       f"cell_candidates_bd.spice), {'dirty' if dirty else 'clean'} tree at run time")
    if note:
        P_(f"- **Run note**: {note}")
    P_("")
    P_("> **PROVENANCE BANNER -- READ FIRST.** Every number below is **conditional on the ASSUMED "
       "breakdown statistics** of `design/breakdown/breakdown_params.spice` (critical field, "
       "field-acceleration, Weibull shape, completion time, filament median and spread are all labelled "
       "`assumed`; only the oxide thicknesses are `literature`; nothing is `measured`). These yields are "
       "**not a prediction of gf180 silicon**. They show how the *design axes* move a yield curve under "
       "that stated model, and they exercise the harness; they cannot replace measured breakdown data "
       "from `measurements/`.")
    P_("")
    P_("- **Model parameters** (sha256 of `design/breakdown/breakdown_params.spice`: "
       f"`{M.BM.sha256(M.BD_DIR / 'breakdown_params.spice')}`):")
    P_("")
    P_("  | Parameter | Value | Unit | Provenance |")
    P_("  |---|---|---|---|")
    for k in (f"c{cand.n}_bd_tox", "bd_ebd", "bd_tref", "bd_gam", "bd_beta", "bd_tcomp", "bd_rf_med", "bd_rf_sig"):
        pr = params[k]
        P_(f"  | `{k}` | {sci(pr['value'])} | {pr.get('unit', '')} | {pr['provenance']} |")
    P_("")
    P_(f"  Derived: V_bd(t_ref) = **{vbd:.3f} V** (assumed, not a gf180 number). Pulse polarity "
       f"{'positive' if cand.polarity == 'n' else 'negative'} (as the #62 trigger bench).")
    P_("")


def _criteria(a: list[str], cand, groups, ibound: float) -> tuple[set, bool]:
    """The per-sample success criteria; returns (kinds, read_defined)."""
    P_ = a.append
    P_("- **Success criterion** (per sample; a sample is exactly one of ok / fail / inconclusive):")
    P_(f"  1. the breakdown state is **latched** at the end of the transient: `st >= {M.LATCHED}` "
       f"(`st <= {M.INTACT}` is *not programmed* = fail; anything in between is a half-formed filament "
       "and is **inconclusive**, not counted either way);")
    kinds = {x.ikind for g in groups.values() for smp in g.samples.values() for x in smp if x.ok}
    if kinds == {"flat-top"}:
        what = ("the **steady post-event current**, |i(VBL)| at the end of the pulse flat top (20 ns before the "
                "falling edge). The whole-pulse maximum is not used for this candidate: the stock capacitor's "
                "charging current alone reaches several mA and is identical for programmed and unprogrammed "
                "samples, so it says nothing about the programming current (README \"Current criterion\")")
    else:
        what = ("the **peak access-path current** over the pulse, max |i(VBL)| (this record predates the "
                "flat-top measurement; for this candidate the filament current dominates the charging "
                "current, so the value is the programming current)")
    P_(f"  2. {what}, is `<= {sci(ibound)} A`. "
       "This bound is an **ASSUMED campaign parameter, not a ratified one**: `spec/architecture.md` "
       "section 2 leaves `I_target_max` open and the cell model has no ballast resistor, so the current "
       "limit here is the access device alone. The current distribution is tabulated so any other "
       "bound can be applied to the saved data;")
    if cand.n == 3:
        P_("  3. **read decision: NOT EVALUATED for Candidate 3.** The #62 records show no `I_ref` window "
           "at the inherited placeholder read bias (I_prog_min below I_sneak_max; follow-up #75), so "
           "\"post-pulse read decision correct\" has no defined threshold. The Candidate 3 yields below "
           "are therefore **upper bounds** on a full read-decision yield (latch and current bound only).")
        read_defined = False
    else:
        read_defined = True
        P_("  3. the **post-pulse read decision is correct at the worst-case read corner**: the programmed "
           "cell's read current `I_read(z)` at that sample's filament draw `z` is `>= I_ref`, where "
           "`I_read(z)` is the pointwise minimum over the read corners "
           f"({M.READ_PROCESS}, {', '.join(f'{t:g}' for t in M.READ_TEMPS)} degC, BL = {M.READ_RAIL} V) of the "
           "programmed-read table below, interpolated log-linearly in z, and "
           "`I_ref = sqrt(I_sneak_max * I_prog_min,wc)` from the #62 record. **`I_ref` is a campaign "
           "choice** (geometric mean of the window, which `spec/architecture.md` section 4 does not "
           "ratify), not a spec value. The decision uses the programmed side only; the unprogrammed side "
           "is the #62 `I_sneak_max`, which the model makes independent of the pulse.")
    P_("")
    return kinds, read_defined


def _sampling(a: list[str], groups, n: int) -> None:
    P_ = a.append
    P_(f"- **Sample sizing**: n = {n} Monte Carlo samples per (sub-configuration, pulse condition, PVT "
       f"corner) cell. The 95 % Wilson interval half-width is at most {1.96 * math.sqrt(0.25 / n):.3f} "
       f"(p = 0.5, n = {n}) and narrower toward the ends; pooling the {len(C.MOSCAP_CORNERS)} x "
       f"{len(C.TEMPS_C)} PVT corners of a condition multiplies the sample by up to "
       f"{len(C.MOSCAP_CORNERS) * len(C.TEMPS_C)}. Chosen from that half-width, not from a yield target. "
       "A cell that needs a tighter interval is re-run with a larger n as a new record.")
    P_(f"- **Sampler**: `klt sim` `monte_carlo` {{n={n}, vary=\"{M.MC_VARY}\"}}; the draws are "
       f"`ubd = aunif(0.5, 0.5)` clamped to [{M.UB_FLOOR:g}, 1 - {M.UB_FLOOR:g}] (uniform Weibull quantile) and "
       "`zrf = agauss(0, 1, 1)` (standard-normal filament draw), evaluated once per run from the "
       "`.options seed=` klt writes, with a distinct `monte_carlo.seed` per process corner "
       f"(base {M.MC_SEED} + 1000 x process index). The draws are a function of (seed, temperature index, "
       "sample index), so the PVT corners of a condition are independent samples while the two access "
       "sizings and the five pulse conditions reuse the same draws at the same (process, temperature, "
       "sample) -- a paired design, README \"Draw reuse\".")
    P_("")
    P_("- **Corner matrix run**: " + str(sorted({k[1] for g in groups.values() for k in g.samples})) +
       " x temperatures " + str(sorted({k[2] for g in groups.values() for k in g.samples})) + " degC x pulse "
       "conditions below x access sizing " + ", ".join(M.SIZINGS) + f" (capacitor geometry fixed at `{M.GEOM}`). "
       "Programming transient only; the read-side PVT is the table below.")
    P_("- **Not run, and why**: the capacitor-geometry axis (`2x`). `af_breakdown` has **no area "
       "dependence** (its kinetics see tox only), so a larger capacitor changes the breakdown statistics "
       "of this model by construction -- it is *not resolvable* here and a run would only add the stock "
       "capacitor's different divider. The model must gain area scaling (Poisson-area Weibull) before "
       "that split axis can be read from a yield curve; running it now would manufacture a null result.")
    P_("")


def _execution(a: list[str], groups) -> None:
    P_ = a.append
    P_("- **Execution**: engine ngspice on the batch fleet; every request names `\"backend\": \"batch\"`; "
       "no local grid was run. Jobs:")
    listed: set = set()
    for (sz, tag), g in sorted(groups.items()):
        for j in g.jobs:
            r = j.get("remote") or {}
            key = (sz, r.get("job_id") or id(j))
            if key in listed:
                continue                  # first-run layout: one job covers several conditions
            listed.add(key)
            P_(f"  - access `{sz}`, `{tag}`: klt status `{j.get('status') or 'submit-error'}`, "
               f"job `{r.get('job_id', 'n/a')}`, runner klt {r.get('runner_klt_version', 'n/a')} "
               f"({r.get('runner_compatibility', 'n/a')}), {r.get('elapsed_seconds', 'n/a')} s"
               + (f" -- ERROR: {esc(j['error'][:300])}" if j.get("error") else ""))
    P_("")


def _read_table(a: list[str], cand, readtab, rerr: str | None, read_defined: bool) -> dict[str, float | None]:
    """The programmed-read table section; returns the per-sizing z_crit."""
    P_ = a.append
    tabs = read_tables(readtab)
    iref = None
    figs: dict[str, float] = {}
    zcrit: dict[str, float | None] = {}
    if read_defined:
        bdrid = stored_bd_record(cand)
        figs = parse_record_figs(bdrid) if bdrid else {}
        P_(f"- **Programmed-read table** (read side; request `readtab`, source of `I_read(z)`); "
           f"#62 record `{bdrid}`: I_sneak_max = {sci(figs.get('i_sneak_max'))} A, worst-corner "
           f"I_prog_min = {sci(figs.get('i_prog_min_wc'))} A:")
        if "i_sneak_max" in figs and "i_prog_min_wc" in figs:
            iref = math.sqrt(figs["i_sneak_max"] * figs["i_prog_min_wc"])
        P_(f"  - **I_ref (campaign choice) = {sci(iref)} A**")
        if rerr:
            P_(f"  - read table submit ERROR: {esc(rerr[:300])}")
        P_("")
        P_("  | Sizing | " + " | ".join(f"z={z:+d}" for z in M.Z_GRID) + " | z_crit |")
        P_("  |---|" + "---|" * (len(M.Z_GRID) + 1))
        for sz in M.SIZINGS:
            wt = worst_table(tabs.get(sz, {})) if tabs.get(sz) else {}
            zcrit[sz] = M.zcrit_from_table(wt, iref) if iref and wt else None
            P_(f"  | `{sz}` (min over read corners) | " + " | ".join(sci(wt.get(z)) for z in M.Z_GRID)
               + f" | {('%.2f' % zcrit[sz]) if zcrit[sz] is not None else 'n/a'} |")
        P_("")
        P_("  `z_crit` is the filament draw above which the read falls under `I_ref`; the assumed "
           "filament median/spread put it at "
           + ("; ".join(f"`{sz}`: P(z <= z_crit) = {0.5 * (1 + math.erf(zcrit[sz] / math.sqrt(2))):.4f}"
                        for sz in M.SIZINGS if zcrit.get(sz) is not None) or "n/a") + ".")
        P_("")
    return zcrit


def _yield_tables(a: list[str], cand, groups, params: dict, vbd: float, conds, read_defined: bool,
                  zcrit: dict[str, float | None], ibound: float) -> None:
    P_ = a.append
    P_("- **Result** -- success fraction vs pulse condition. One block per access sizing; rows are "
       "(condition, PVT corner). `succ/n` counts ok samples over **all** n drawn; `err` are inconclusive "
       "samples (klt error / non-converged / half-formed), so `yield` is a **lower bound** (errors counted "
       "as not-ok) and `yield_hi` counts them as ok. `yield, no I bound` drops criterion 2 (the unratified current "
       "bound) and keeps latch and read. CI is the 95 % Wilson interval on `succ/n`. "
       "`analytic` is the closed-form constant-field Weibull prediction, a sampler cross-check only.")
    P_("")
    for sz in M.SIZINGS:
        P_(f"### Candidate {cand.n} / Region {cand.region}, access sizing `{sz}`")
        P_("")
        P_("| Condition | V_pulse [V] | tw [us] | Corner | n | succ | err | yield | CI95 | yield_hi | yield, no I bound | analytic |")
        P_("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cnd in conds:
            g = groups.get((sz, cnd["tag"]))
            if not g or not g.samples:
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | (no data) | | | | | | | | |")
                continue
            pooled = {"n": 0, "succ": 0, "err": 0}
            for key in sorted(k for k in g.samples if k[0] == cnd["frac"]):
                smp = g.samples[key]
                cl = [M.classify(x, zcrit.get(sz), read_defined, ibound) for x in smp]
                ok, er = cl.count("ok"), cl.count("inconclusive")
                lo, hi = M.wilson(ok, len(smp))
                cid = C.corner_id(key[1], key[2], "nosupply").replace("_nosupply", "")
                nb = [M.classify(x, zcrit.get(sz), read_defined, float("inf")) for x in smp].count("ok")
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | `{cid}` | {len(smp)} | "
                   f"{ok} | {er} | {ok / len(smp):.3f} | [{lo:.3f}, {hi:.3f}] | {(ok + er) / len(smp):.3f} | "
                   f"{nb / len(smp):.3f} | {M.analytic_yield(cand, params, cnd['frac'], cnd['tw']):.3f} |")
                pooled["n"] += len(smp); pooled["succ"] += ok; pooled["err"] += er; pooled["nb"] = pooled.get("nb", 0) + nb
            if pooled["n"]:
                lo, hi = M.wilson(pooled["succ"], pooled["n"])
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | **all PVT pooled** | "
                   f"{pooled['n']} | {pooled['succ']} | {pooled['err']} | **{pooled['succ'] / pooled['n']:.3f}** | "
                   f"[{lo:.3f}, {hi:.3f}] | {(pooled['succ'] + pooled['err']) / pooled['n']:.3f} | "
                   f"{pooled['nb'] / pooled['n']:.3f} | {M.analytic_yield(cand, params, cnd['frac'], cnd['tw']):.3f} |")
        P_("")


def _worst_corner(a: list[str], groups, conds, read_defined: bool, zcrit: dict[str, float | None],
                  ibound: float) -> None:
    P_ = a.append
    P_("- **Worst PVT corner per condition** (lowest yield among the corners of a cell; the "
       "yield-vs-condition claim for design purposes is this, not the pooled row):")
    P_("")
    P_("  | Sizing | Condition | Worst corner | yield | CI95 |")
    P_("  |---|---|---|---|---|")
    for sz in M.SIZINGS:
        for cnd in conds:
            g = groups.get((sz, cnd["tag"]))
            if not g:
                continue
            best = None
            for key, smp in g.samples.items():
                if key[0] != cnd["frac"]:
                    continue
                cl = [M.classify(x, zcrit.get(sz), read_defined, ibound) for x in smp]
                y = cl.count("ok") / len(smp)
                if best is None or y < best[0]:
                    best = (y, key, cl.count("ok"), len(smp))
            if best:
                lo, hi = M.wilson(best[2], best[3])
                cid = C.corner_id(best[1][1], best[1][2], "nosupply").replace("_nosupply", "")
                P_(f"  | `{sz}` | `{cnd['tag']}` | `{cid}` | {best[0]:.3f} | [{lo:.3f}, {hi:.3f}] |")
    P_("")


def _sampler_check(a: list[str], groups) -> None:
    P_ = a.append
    seen: set = set()
    ub, zr = [], []
    total = 0
    for g in groups.values():
        for smp in g.samples.values():
            for x in smp:
                if x.ok:
                    total += 1
                    k = (round(x.ubd, 6), round(x.zrf, 6))
                    if k not in seen:
                        seen.add(k); ub.append(x.ubd); zr.append(x.zrf)
    if ub:
        mu, sd = sum(ub) / len(ub), math.sqrt(sum((x - sum(ub) / len(ub)) ** 2 for x in ub) / len(ub))
        zm, zs = sum(zr) / len(zr), math.sqrt(sum((x - sum(zr) / len(zr)) ** 2 for x in zr) / len(zr))
        P_(f"- **Sampler check** ({total} usable samples, {len(ub)} distinct (ubd, zrf) draws; the rest are "
           "deliberate repeats, see README \"Draw reuse\"), statistics over the distinct draws: "
           f"`ubd` mean {mu:.4f} (uniform: 0.5000, s.e. {math.sqrt(1 / 12 / len(ub)):.4f}), sd {sd:.4f} "
           f"(uniform: 0.2887), min {min(ub):.4f}, max {max(ub):.4f}; `zrf` mean {zm:+.4f} "
           f"(s.e. {1 / math.sqrt(len(zr)):.4f}), sd {zs:.4f} (target 1).")
        P_("")


def _current(a: list[str], groups, kinds: set) -> None:
    P_ = a.append
    P_(f"- **Access-path current of latched samples** ({'flat-top end' if kinds == {'flat-top'} else 'max over the pulse'}; "
       "the data behind criterion 2):")
    P_("")
    P_("  | Sizing | latched samples | median [A] | p95 [A] | max [A] | frac <= " +
       " | frac <= ".join(sci(b) for b in IBSWEEP) + " |")
    P_("  |---|---|---|---|---|" + "---|" * len(IBSWEEP))
    for sz in M.SIZINGS:
        ip = [x.ipk for (s_, _), g in groups.items() if s_ == sz for smp in g.samples.values() for x in smp
              if x.ok and x.st >= M.LATCHED]
        if ip:
            P_(f"  | `{sz}` | {len(ip)} | {sci(M.quantile(ip, .5))} | {sci(M.quantile(ip, .95))} | {sci(max(ip))} | " +
               " | ".join(f"{sum(1 for v in ip if v <= b) / len(ip):.3f}" for b in IBSWEEP) + " |")
    P_("")


def _trailer(a: list[str], rid: str, supersedes: str | None) -> None:
    P_ = a.append
    P_("- **What this does not show**: (i) any silicon yield; (ii) the capacitor-area axis (model has none); "
       "(iii) temperature or process dependence of breakdown itself (the model has none, so PVT enters "
       "only through the stock capacitor/access device); (iv) ballast sizing (no ballast in the cell "
       "model; the current bound is an assumed placeholder); (v) the program-path bias scheme (not "
       "ratified; the pulse is applied on PL with BL = 0 and the access device on, as in the #62 trigger "
       "bench); (vi) any difference between candidates beyond oxide thickness and the access device: the "
       "model gives all three the same kinetics and the same seeded draws, so candidates with equal relative "
       "pulse and comparable access devices reproduce each other's latch counts (e.g. Candidates 1 and 3 here). "
       "A cross-candidate yield comparison is a statement about this assumed model, not about the oxides.")
    P_("")
    P_("- **Links**:")
    P_(f"  - frozen netlist snapshot: `sim/programming-yield/netlist-snapshots/{rid}.spice`")
    P_(f"  - requests, decks and klt reports: artifact store manifest "
       f"`manifests/artifacts/programming-yield-{rid}.manifest.json`")
    P_(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} / Claude (loom sweep, issue #66)")
    P_(f"- **Supersedes**: {supersedes or '(none)'}")


def render_record(pdk, cand, rid: str, groups, readtab, rerr, params: dict, dirty, ibound: float,
                  n: int, note: str | None, supersedes: str | None = None) -> str:
    a: list[str] = []
    vbd = M.vbd_ref(cand, params)
    conds = M.conditions()
    _header(a, rid, cand, dirty, note, params, vbd)
    kinds, read_defined = _criteria(a, cand, groups, ibound)
    _sampling(a, groups, n)
    _execution(a, groups)
    zcrit = _read_table(a, cand, readtab, rerr, read_defined)
    _yield_tables(a, cand, groups, params, vbd, conds, read_defined, zcrit, ibound)
    _worst_corner(a, groups, conds, read_defined, zcrit, ibound)
    _sampler_check(a, groups)
    _current(a, groups, kinds)
    _trailer(a, rid, supersedes)
    return "\n".join(a) + "\n"
