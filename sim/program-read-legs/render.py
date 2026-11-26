#!/usr/bin/env python3
"""sim/program-read-legs render.py -- pure Markdown record renderer.

Turns ``klt sim`` responses (shaped by model.meas_table / model.mc_table
and analysed by the model.analyze_* helpers) into the record sections and
the full records under records/: the bench section tables (exclusion,
ballast, margin), the Monte Carlo mismatch tables and both record headers.
Imports one-way from model.py (loaded via harness.modload under the fixed
unique name, reusing the copy the CLI facade already loaded); nothing in
model.py imports this module.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import numfmt as NF  # noqa: E402
from harness.modload import load_module  # noqa: E402

# model.py is loaded under the fixed unique name run_experiment.py uses, so
# the library exists once per process whether this module is reached through
# the CLI or alone.
M = sys.modules.get("sim_prl_model") or load_module(THIS_DIR / "model.py", "sim_prl_model")

# The model surface the (verbatim-moved) renderers below read by its
# pre-split bare names.
B = M.B
I_DRIVE = M.I_DRIVE
MC_CONF = M.MC_CONF
MC_SEED = M.MC_SEED
MC_POINTS = M.MC_POINTS
cp_lower = M.cp_lower


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
# Monte Carlo (mismatch) record sections and record
# ---------------------------------------------------------------------------

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
          f"  - Full klt reports (per-sample measurements, seeds, diagnostics): artifact store manifest "
          f"`manifests/artifacts/program-read-legs-{record_id}.manifest.json` (per-sample ngspice logs are not kept)",
          f"- **Timestamp / author**: {now}, agent-builder",
          "- **Supersedes**: (none -- adds mismatch statistics to the corner-only record "
          "`records/20261015-151616-d3df921.md`, which is unchanged)", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Corner-record
# ---------------------------------------------------------------------------

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
          f"  - Full klt reports (per-corner measurements) and raw logs: artifact store manifest "
          f"`manifests/artifacts/program-read-legs-{record_id}.manifest.json`",
          f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}`",
          f"- **Timestamp / author**: {now}, agent-builder",
          "- **Supersedes**: (none -- first record for this claim)", ""]
    return "\n".join(L)
