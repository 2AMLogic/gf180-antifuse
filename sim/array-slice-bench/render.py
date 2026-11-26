#!/usr/bin/env python3
"""sim/array-slice-bench render.py -- the Markdown/CSV record renderers.

Slice-mode rendering (the per-slice sections, the structural orientation
table, the slice record and its per-region measurement view) and the
full-band record body, per-region measurement view and per-corner CSV --
the full-band tables themselves live in fullband.py and are passed in as
``F``, because fullband.py imports the shared constants and the number
formatter from here (render never imports fullband.py, keeping the import
graph one-way: fullband -> {model, render}, render -> model).

Imports one-way from model.py, loaded via harness.modload under the fixed
unique name the CLI facade uses (never a bare ``import``, which under
``python3 -I`` has no script dir on sys.path and would collide in
sys.modules with other experiments' sibling modules). ``repo`` is a
parameter everywhere a netlist or the git tree is read (same contract as
model.py: the CLI passes its own ``REPO`` at call time).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "design"))
from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402
import gen_array as G  # noqa: E402
import make_bench as B  # noqa: E402

# model.py is loaded under the fixed unique name run_bench.py uses, so the
# library exists once per process whether this module is reached through
# the CLI, through fullband.py, or alone.
M = sys.modules.get("sim_asb_model") or load_module(THIS_DIR / "model.py", "sim_asb_model")

ETA_MIN = M.ETA_MIN
RETURN_MIN = M.RETURN_MIN
BL_MIN = M.BL_MIN
PL_MAX = M.PL_MAX
ISO_MAX = M.ISO_MAX
R_FIL = M.R_FIL
region_tables = M.region_tables

REGION_NAME = {"I": "Region I (Candidate 1)", "II": "Region II (Candidate 2)", "III": "Region III (Candidate 3)"}


def fmt_e(x):
    return f"{x:.3g}"


# ---------------------------------------------------------------------------
# Slice mode
# ---------------------------------------------------------------------------


def slice_section(sl, report, per, report_shas, write=True):
    r0, r1, c0, c1 = G.SLICES[sl]
    reach, iso, errors = region_tables(sl, per)
    env = report.get("environment", {})
    jobs = report.get("jobs") or [env.get("remote") or {}]
    out = [f"### {sl} (rows {r0}-{r1}, cols {c0}-{c1})", ""]
    out.append(f"- corners run: {report['corner_count']} "
               f"(pass {report['passed']}, fail {report['failed']}, error {report['errored']}, "
               f"inconclusive {report['inconclusive']}); {errors} not gradable")
    out.append(f"- engine: {env.get('engine')} {env.get('engine_version')}")
    out.append("- batch jobs (one per process corner): " + (
        ", ".join(f"`{j.get('job_id')}` ({j.get('provider')}, {j.get('instance_type')}, {j.get('lifecycle')})" for j in jobs)
        if any(jobs) else "none reported (local run)"))
    out.append(f"- pdk: {report.get('provenance', {}).get('pdk')}")
    missing = sorted(k for k, v in report_shas.items() if not v)
    if missing:
        out.append(f"- sha256 of the full, un-elided text: none attestable ({', '.join(missing)}: the input "
                   f"report is already coverage-elided); no sidecar written")
    elif write:
        shas = ", ".join(f"{k}: `{v}`" for k, v in sorted(report_shas.items()))
        out.append(f"- per-report sha256 of the full, un-elided text ({shas}); each is committed "
                   f"beside its report as `{sl}_<process>.report.json.sha256`")
    else:
        shas = ", ".join(f"{k}: `{v}`" for k, v in sorted(report_shas.items()))
        out.append(f"- per-report sha256 of the full, un-elided text ({shas}); not committed (--no-write)")
    out.append("")
    out.append("**Selected cell reaches the BL/PL program path** (per region, per capacitor-geometry x "
               "access-sizing sub-combination; worst case over every corner and every selected cell of that "
               "sub-combination). eta = selected-cell access-path current / (V_BLG / R_FIL).")
    out.append("")
    out.append("| Region | Cap level | Access level | selections x corners | eta min (worst corner) | "
               "I(PLG)/I(BLG) min | V(BL)/V(BLG) min | V(PL)/V(BLG) max | not meeting criteria |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for key in sorted(reach, key=lambda k: (G.BANDS and [b[0] for b in G.BANDS].index(k[0]), k[2], k[3])):
        lab, cand, cap, acc = key
        t = reach[key]
        out.append(f"| {REGION_NAME[lab]} | {cap} | {acc} | {t['n']} | {fmt_e(t['eta'][0])} ({t['eta'][1]}) | "
                   f"{fmt_e(t['ret'][0])} | {fmt_e(t['bl'][0])} | {fmt_e(t['pl'][0])} | {t['bad']} |")
    out.append("")
    out.append("**Unselected cells isolated** (per region; worst unselected-cell access-path current relative to "
               "the region's own ideal V_BLG/R_FIL; classes are relative to the selected cell: `same_col` = BL "
               "powered, word line off; `same_row` = word line on, column pass-gate off; `other`; `bus` = a "
               "powered global bit-line bus of a band that holds no selected cell).")
    out.append("")
    out.append("| Region | Class | corner x selection instances | worst ratio (corner) | over threshold |")
    out.append("|---|---|---|---|---|")
    for (lab, cls) in sorted(iso, key=lambda k: ([b[0] for b in G.BANDS].index(k[0]), k[1])):
        u = iso[(lab, cls)]
        out.append(f"| {REGION_NAME[lab]} | {cls} | {u['n']} | {fmt_e(u['worst'][0])} ({u['worst'][1]}) | {u['bad']} |")
    out.append("")
    return out, reach, iso, errors


def orientation_section(repo: Path = REPO_ROOT):
    """Structural proof of the drain-to-BL (Candidate 2) / source-to-BL
    (Candidate 3) orientation, read from the derived netlists."""
    out = []
    nl = repo / "design" / "netlists"
    for cand, model, pin in ((1, "nfet_06v0", "d"), (2, "nfet_10v0_asym", "d"), (3, "pfet_06v0", "s")):
        text = (nl / f"cell_candidate{cand}.spice").read_text()
        m = re.search(r"^XM1 (\S+) (\S+) (\S+) (\S+) (\S+)", text, re.M)
        d, g, s, b, mod = m.groups()
        bl_on = {"d": d, "s": s}[pin]
        ok = bl_on == "BL" and mod == model
        out.append(f"| Candidate {cand} | `{model}` | `XM1 {d} {g} {s} {b}` (d g s b) | BL on {'drain' if pin == 'd' else 'source'} | "
                   f"{'confirmed' if ok else 'VIOLATED'} |")
    return out


def write_records(record_id, sections, clean, now, repo: Path = REPO_ROOT):
    sha = R.git_out(repo, "rev-parse", "HEAD")
    rec = [f"# Record {record_id}", "",
           "- **Record ID**: " + record_id,
           "- **Claim**: `spec/architecture.md` §1.1/§1.3 (two-tier addressing: a cell is selected only when both "
           "its row and column pass-gates are enabled; every other row/column pass-gate is held OFF) and §3 "
           "(unselected access devices do not conduct), as captured by `design/gen_array.py` -> "
           "`design/netlists/slice_*.spice`; `spec/cell-candidates.md` (Candidate 2 `nfet_10v0_asym` drain faces BL).",
           f"- **Netlist provenance**: schematic (`design/netlists/`, derived by xschem from `design/array/`, "
           f"`design/mux/`, `design/cells/`); git HEAD `{sha[:12]}`; working tree "
           f"{'clean' if clean else 'NOT clean (uncommitted changes at run time)'}.",
           "- **Corner matrix run**: process {typical, ff, ss, fs, sf} (MOS and moscap sections from the request, the "
           "matching 10 V LDMOS section from the netlist; one `klt sim` request per process corner, see "
           "`testbench/*.request.json`) x temperature {-40, 27, 125} C x supply {-10%, nominal, "
           "+10%} (scaling VDDL, every VDDH, every BLG stand-in level together) x all 16 selectable cells of the "
           "slice. This is the full CLAUDE.md PVT matrix; no subset.",
           "- **Result**: see per-slice sections below. Per region, per sub-combination; nothing is averaged "
           "across regions or sub-combinations.",
           "- **Links**: testbench `sim/array-slice-bench/testbench/`; raw klt reports in the artifact "
           f"store, manifest `manifests/artifacts/array-slice-bench-{record_id}.manifest.json`.",
           f"- **Timestamp / author**: {now:%Y-%m-%dT%H:%M:%SZ} / Claude Sonnet 5.5 (Loom builder, issue #64)",
           "- **Supersedes**: (none)", "",
           "## Acceptance thresholds used (this record's own; not spec numbers)", "",
           f"eta >= {ETA_MIN}; |I(PLG)|/|I(BLG)| in [{RETURN_MIN}, {1/RETURN_MIN:.3f}]; V(BL)/V(BLG) >= {BL_MIN}; "
           f"V(PL)/V(BLG) <= {PL_MAX}; unselected-cell and idle-bus current <= {ISO_MAX:g} of the ideal "
           f"V_BLG/R_FIL, with R_FIL = {R_FIL:g} ohm a **bench-only filament stand-in** (see make_bench.py: it "
           "makes conduction observable at DC; it is not a post-breakdown model). The BLG levels, VDDH rails "
           "and VDDL are bench placeholders, not programming conditions.", "",
           "## Access-device orientation (structural)", "",
           "| Candidate | Access device | Derived netlist line | Required | Status |", "|---|---|---|---|---|",
           *orientation_section(repo), "",
           "## Results", ""]
    for s in sections:
        rec += s
    return "\n".join(rec) + "\n"


def slice_measurement_view(record_id, sections) -> str:
    """The per-region measurement view of a slice record (header + sections)."""
    return (f"# Array slice bench - per-region results ({record_id})\n\n"
            "**Pre-silicon simulation, not a silicon measurement.** This is the per-region view of "
            f"`sim/array-slice-bench/records/{record_id}.md` (the evidence record, which carries the corner matrix, "
            "provenance and thresholds). Regions are never averaged together.\n\n"
            + "\n".join("\n".join(s) for s in sections))


# ---------------------------------------------------------------------------
# Full-band leakage mode (issue #70)
# ---------------------------------------------------------------------------


def _jobs_line(reps: dict) -> list[str]:
    out = []
    for key in sorted(reps):
        j = (reps[key].get("environment") or {}).get("remote") or {}
        out.append(f"`{j.get('job_id')}` ({key}; {j.get('provider')}, {j.get('instance_type')}, {j.get('lifecycle')}, "
                   f"exit {j.get('exit_code')})" if j else f"none reported ({key}; local run)")
    return out


def fullband_record_body(F, record_id, sha, clean, now, pg, nat, sel, floor_n, sel_bad, jobs) -> str:
    """The full-band record body (everything except the file writes). ``F`` is
    fullband.py, passed in by the driver exactly as the pre-split code thread
    it, so this module never imports fullband.py."""
    eqn = [
        "I_leak,total = I_node,pgoff + I_cell,max          (each term once)",
        "I_node,pgoff = -i(Vbl_<band>) with every column OFF and every BL_c clamped to 0 V",
        "             = sum_c i(Vcl_<c>)  [channel leakage into OFF columns]  +  I_other  [BLG-node junction/bulk]",
        "I_cell,max   = 31 x I_off from sim/cell-device-characterization/records (carried, not re-measured here)",
        "margin       = I_ref - I_leak,total   and   I_ref / I_leak,total",
    ]
    body = [f"# Record {record_id}", "",
            f"- **Record ID**: {record_id}",
            "- **Claim**: `spec/architecture.md` §3 (the selected bit-line budget includes the aggregate OFF-state "
            "leakage) and §4 (`I_ref > I_sneak_max`, fast/hot leakage analysed apart from slow/cold selected-path "
            "conduction), per region (`spec/split-axis-plan.md`: 11 / 11 / 10 columns). Closes the addressing-stage "
            "term that the #65 margin benches did not carry.",
            f"- **Netlist provenance**: schematic (`design/netlists/band_{{i,ii,iii}}.spice`, generated by "
            f"`design/gen_array.py`, netlisted with `klt netlist`); git HEAD `{sha[:12]}`; working tree "
            f"{'clean' if clean else 'NOT clean (uncommitted changes at run time)'}.",
            "- **Corner matrix run**: process {typical, ff, ss, fs, sf} (one `klt sim` request per variant, band and "
            "process corner) x temperature {-40, 27, 125} C x supply {-10 %, nominal, +10 %} (scales VDDL and the band "
            "VDDH) x read level (per region, below) x read-level scale {0.9, 1.0, 1.1} (the VCLAMP +-10 % tracking "
            "points, approximated as a scaling of the level; `sel` runs level scale 1.0 only). Full CLAUDE.md PVT "
            "matrix; no subset.",
            "- **Result**: see the per-region tables below; nothing is averaged across regions or read levels.",
            f"- **Links**: raw klt reports in the artifact store, manifest "
            f"`manifests/artifacts/array-slice-bench-{record_id}.manifest.json`; per-corner CSV "
            f"`measurements/array-slice-bench/{record_id}.csv`; per-region view "
            f"`measurements/array-slice-bench/{record_id}.md`.",
            f"- **Timestamp / author**: {now:%Y-%m-%dT%H:%M:%SZ} / Claude Sonnet 5.5 (Loom builder, issue #70)",
            "- **Supersedes**: (none)", "",
            "## Assumed / placeholder inputs (all of them)", "",
            "- **Sense-node attachment: ASSUMED.** The read leg is not connected to the array on `main` "
            "(`design/README.md`). The bench places the sense node on the band's `BLG` bus (shared by all of the "
            "band's column pass-gates). Every unselected `BL_c` is either clamped to 0 V (`pgoff`, the leakage worst "
            "case) or floating (`nat`, the natural DC steady state); idle-band buses do not exist in a one-band "
            "slice, so no idle-band term is claimed. All columns are OFF (n, not n-1: a read has one column ON, so "
            "this is the conservative count). Attachment is #73's to design.",
            f"- **Read levels**: bracket the bit-line voltages in `sim/program-read-legs/records/{B.READ_RECORD}.md` "
            "(\"BL at worst\" rows), not corner-matched; table below. Program-path placeholder stimulus (BLG 3.0/3.5 V) "
            "is **not** used for the margin budget.",
            "- **Cell term** `31 x I_off` is the committed record's value, a gmin-floor upper bound evaluated at BL "
            "0.9-1.1 V (ff/125C/high). It was **not** re-evaluated at the 3.77-3.98 V unprogrammed sense levels; "
            "this record does not claim the cell term at those levels.",
            "- **Programmed side**: carried from #65 with its ASSUMED R_prog; Region III programmed side is unproven (#75). "
            "Leakage is drawn out of the sense node in the same direction as the programmed-cell read current, so it "
            "cannot reduce the programmed-side margin - the #65 figures are carried unchanged.",
            f"- **Simulator floor**: estimated as gmin ({F.GMIN:g} S) x V_BLG x columns; a pass-gate-at-node reading "
            f"below {F.FLOOR_FACTOR:g}x that is flagged floor-dominated (upper bound only). {floor_n} of {len(pg)} "
            "graded points are flagged.",
            "- **Settling is not evidenced**: the stock moscap model does not run in transient (README); selected-path "
            "conduction is a DC check only.", "",
            "## Sign convention and budget equation", "",
            "Leakage is positive when drawn **out of** the summation node `BLG_<band>`; ngspice `i(V)` of a supplying "
            "source is negative, so `I_node = -i(Vbl)`; `i(Vcl_c)` (BL_c clamp, + terminal on BL_c) is positive for "
            "current entering BL_c from the OFF pass-gate.", "", "```", *eqn, "```", "",
            "## Summary (recomputed from the graded points)", "", *F.summary_lines(pg, sel), "",
            "## Read-level provenance", "", *F.provenance_rows(), "",
            "## Leakage budget, worst corner per region and read level", "", *F.budget_table(pg), "",
            "## Per-region PVT table (worst supply / level scale per process x temperature)", "", *F.pvt_table(pg), "",
            "## Which pass-gate leaks (per-column spread at each region's worst point)", "", *F.attribution_table(pg), "",
            "## Natural DC steady state vs clamped worst case", "", *F.nat_table(nat, pg), "",
            f"## Selected-path conduction at the read level (thresholds: eta >= {F.ETA_MIN}, V(BL)/V(BLG) >= {F.BL_MIN}, "
            f"return in [{F.RETURN_MIN}, {1 / F.RETURN_MIN:.3f}]; {sel_bad} of {len(sel)} points below)", "",
            *F.sel_table(sel), "",
            "## Programmed / unprogrammed side margins carried from #65", "",
            f"Parsed from `sim/program-read-legs/records/{B.READ_RECORD}.md`; R_prog is ASSUMED there.", "",
            *F.programmed_side_from_65(), "",
            "## Fleet jobs (out-of-band verification)", "", *jobs, ""]
    return "\n".join(body)


def fullband_measurement_view(F, record_id, pg, sel) -> str:
    return (f"# Full-band leakage - per-region results ({record_id})\n\n"
            "**Pre-silicon simulation, not a silicon measurement.** Per-region view of "
            f"`sim/array-slice-bench/records/{record_id}.md` (assumptions, corner matrix, provenance). "
            "Regions are never averaged together.\n\n## Leakage budget\n\n" + "\n".join(F.budget_table(pg)) +
            "\n\n## Per-region PVT table\n\n" + "\n".join(F.pvt_table(pg)) +
            "\n\n## Selected-path conduction\n\n" + "\n".join(F.sel_table(sel)) + "\n")


def fullband_csv(pg) -> str:
    csv = ["band,process,temp_c,level,level_scale,supply_scale,vblg_v,i_ref_a,pg_channel_a,pg_other_a,pg_node_a,"
           "cell_a,total_a,headroom_a,ratio,floor_a,floor_dominated"]
    for r in sorted(pg, key=lambda r: (r["band"], r["level"], r["i_ref"], r["process"], r["temp"], r["scale"],
                                       r["level_scale"])):
        csv.append(",".join(str(x) for x in (r["band"], r["process"], r["temp"], r["level"], r["level_scale"],
                                             r["scale"], r["vbl"], r["i_ref"], r["pg_channel"], r["pg_other"],
                                             r["pg_node"], r["cell"], r["total"], r["headroom"], r["ratio"],
                                             r["floor"], r["floor_dominated"])))
    return "\n".join(csv) + "\n"
