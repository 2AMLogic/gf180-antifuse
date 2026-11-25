#!/usr/bin/env python3
"""sim/integrated-transition render.py -- the Markdown and CSV record renderers.

Pure text assembly (``render_record``, ``render_measurement_md``, ``csv_rows``
and the table builders they share) is kept apart from the disk writes in
``write_records``. Each of the seven Markdown table blocks is built once per
record (``build_blocks``) and reused by the record and the per-region
measurement view. The CLI driver, ``klt sim`` orchestration and slice grading
stay in run_bench.py, which re-exports this surface.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402

B = A.B
G = B.G


REGION = {"I": "Region I (Candidate 1)", "II": "Region II (Candidate 2)", "III": "Region III (Candidate 3)"}
BANDS = [b[0] for b in G.BANDS]


CHECKS = [
    ("armed_sense", "armed: sense node moved < 10 % VDD (both bands)"),
    ("armed_rdata", "armed: RDATA unchanged within 10 % VDD (both bands)"),
    ("armed_legs_off", "armed: PON and RON stay < 10 % VDD (both bands)"),
    ("armed_iread", f"armed: mean current into read leg < {A.I_ARM_FRAC:g} x I_ref over the last 100 ns of arm (both bands)"),
    ("exclusion", "PON and RON never both > 10 % VDD (both bands)"),
    ("pulse_read_off", "pulse: RON stays < 10 % VDD (selected band)"),
    ("pulse_sense", "pulse: sense node and RDATA move < 10 % VDD (selected band)"),
    ("decision", "read: final RDATA decision correct and stable by the end of the grid"),
    ("no_false_high", "read: unprogrammed side never drives RDATA high (no glitch)"),
    ("unselected_off", f"unselected select lines within {A.V_OFF_TOL:g} V of their OFF level"),
]


def fe(x, n=3):
    return "n/a" if x is None else f"{x:.{n}g}"


def group(rows, keyf):
    g = defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    return g


def worst(rs, f, big=True):
    r = max(rs, key=f) if big else min(rs, key=f)
    return f(r), r["tag"]


def sub(r):
    return (r["band"], r["cap"], r["acc"])



def table_armed(rows):
    out = ["| Region | Cap level | Access level | points | sense exc max (V): selected / idle band | RDATA exc max (V): sel / idle | "
           "mean I into read leg, last 100 ns of arm, max (A): sel / idle | PON,RON max (V) | both-ON max (V) | points failing any armed check |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for k, rs in sorted(group(rows, sub).items(), key=lambda kv: (BANDS.index(kv[0][0]), kv[0][1], kv[0][2])):
        def mx(f):
            return max((f(r) for r in rs), default=0.0)
        bad = sum(1 for r in rs if not all(r["chk"][c] for c in ("armed_sense", "armed_rdata", "armed_legs_off", "armed_iread", "exclusion")))
        out.append(f"| {REGION[k[0]]} | {k[1]} | {k[2]} | {len(rs)} | {fe(mx(lambda r: r['arm_sense_sel']))} / "
                   f"{fe(mx(lambda r: r.get('arm_sense_idle', 0.0)))} | {fe(mx(lambda r: r['arm_rdata_sel']))} / "
                   f"{fe(mx(lambda r: r.get('arm_rdata_idle', 0.0)))} | {fe(mx(lambda r: r['arm_iread_sel']))} / "
                   f"{fe(mx(lambda r: r.get('arm_iread_idle', 0.0)))} | "
                   f"{fe(mx(lambda r: max(r['arm_legon_sel'], r.get('arm_legon_idle', 0.0))))} | "
                   f"{fe(mx(lambda r: max(r['both_sel'], r.get('both_idle', 0.0))))} | {bad} |")
    return out


def table_pulse(rows):
    out = ["| Region | Cap level | Access level | filament | points | RON max (V) | sense exc max (V) | RDATA exc max (V) | "
           "program-leg DC current on the pulse flat top, max |avg| (A) | read-leg current on the pulse flat top, max |avg| (A) | points failing a pulse check |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    keyf = lambda r: (*sub(r), "unprogrammed" if r["var"] == "unprog" else "assumed R_prog")
    for k, rs in sorted(group(rows, keyf).items(), key=lambda kv: (BANDS.index(kv[0][0]), *kv[0][1:])):
        bad = sum(1 for r in rs if not (r["chk"]["pulse_read_off"] and r["chk"]["pulse_sense"]))
        out.append(f"| {REGION[k[0]]} | {k[1]} | {k[2]} | {k[3]} | {len(rs)} | {fe(max(r['pul_ron'] for r in rs))} | "
                   f"{fe(max(r['pul_sense'] for r in rs))} | {fe(max(r['pul_rdata'] for r in rs))} | "
                   f"{fe(max(abs(r['pul_ipg']) for r in rs))} | {fe(max(abs(r['pul_ird']) for r in rs))} | {bad} |")
    return out


def table_transition(rows):
    out = ["| Region | Cap level | Access level | scenario | filament | points | decision correct and stable | glitch (unprog RDATA high) | "
           "decision-stable delay worst (us after READ_EN) | analog-settled delay worst (us) | V(BLG) at end min..max (V) |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    keyf = lambda r: (*sub(r), r["scen"], r["var"])
    order = list(B.SCENARIOS)
    for k, rs in sorted(group(rows, keyf).items(), key=lambda kv: (BANDS.index(kv[0][0]), kv[0][1], kv[0][2], order.index(kv[0][3]), kv[0][4])):
        ok = sum(1 for r in rs if r["chk"]["decision"])
        gl = sum(1 for r in rs if not r["chk"]["no_false_high"])
        td = [r["t_dec"] for r in rs if r["t_dec"] is not None]
        ts = [r["t_settle"] for r in rs if r["t_settle"] is not None]
        def delay(v):
            if not v:
                return f"never ({len(rs)} of {len(rs)})"
            return fe(max(v)) + (f" ({len(rs) - len(v)} never)" if len(v) < len(rs) else "")
        out.append(f"| {REGION[k[0]]} | {k[1]} | {k[2]} | {k[3]} | {k[4]} | {len(rs)} | {ok}/{len(rs)} | {gl} | {delay(td)} | "
                   f"{delay(ts)} | {fe(min(r['blg_final'] for r in rs))}..{fe(max(r['blg_final'] for r in rs))} |")
    return out


def table_lines(rows):
    out = ["| Region | points | worst unselected-line deviation from OFF level (V) | line | corner | points over tolerance |", "|---|---|---|---|---|---|"]
    for b in BANDS:
        rs = [r for r in rows if r["band"] == b]
        if not rs:
            continue
        v, tag = worst(rs, lambda r: r["off_dev"])
        line = next(r["off_line"] for r in rs if r["off_dev"] == v)
        out.append(f"| {REGION[b]} (selected) | {len(rs)} | {fe(v)} | {line} | {tag} | {sum(1 for r in rs if not r['chk']['unselected_off'])} |")
    return out


def stress_status(a):
    if a["limit"] is None:
        return "unchecked"
    return "within" if a["over"] == 0 else f"EXCEEDS ({a['over']} of {a['n']})"


def table_stress(stress, cell_filter):
    out = ["| Device region | Role | Class vs selected cell | Model | Terminal pair | Peak (V) | Supported limit (V) | Margin (V) | Status | Limit source / reason | Worst corner |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    pn = {"gs": "gate-source", "gd": "gate-drain", "ds": "drain-source", "t12": "terminal 1-2 (capacitor G-B / resistor ends)"}
    for k in sorted(stress, key=lambda k: (BANDS.index(k[0]), k[1], k[2], k[3], k[4])):
        if cell_filter(k) is False:
            continue
        a = stress[k]
        lim = a["limit"]
        out.append(f"| {REGION[k[0]]} | {k[1]} | {k[2]} | `{k[3]}` | {pn[k[4]]} | {a['peak']:.3f} | {fe(lim)} | "
                   f"{'n/a' if lim is None else f'{lim - a['peak']:.3f}'} | {stress_status(a)} | {a['source']} | {a['where']} |")
    return out


def summary_lines(rows):
    out = ["| Region | points | " + " | ".join(c for c, _ in CHECKS) + " |", "|---|---|" + "---|" * len(CHECKS)]
    for b in BANDS:
        rs = [r for r in rows if r["band"] == b]
        if rs:
            out.append(f"| {REGION[b]} | {len(rs)} | " + " | ".join(f"{sum(1 for r in rs if r['chk'][c])}/{len(rs)}" for c, _ in CHECKS) + " |")
    out += ["", "Check definitions (this bench's own acceptance numbers, not spec values):", ""]
    out += [f"- `{c}`: {t}" for c, t in CHECKS]
    return out


CSV_COLS = ["slice", "process", "temp_c", "scale", "band", "cell_r", "cell_c", "cap", "acc", "scenario", "filament",
            "arm_sense_sel_v", "arm_sense_idle_v", "arm_rdata_sel_v", "arm_iread_sel_a", "arm_legon_v", "both_v",
            "pul_ron_v", "pul_sense_v", "pul_rdata_v", "pul_ipg_avg_a", "pul_ird_avg_a", "rd_ipg_avg_a", "rd_ird_avg_a", "dec_ok", "t_dec_us", "t_settle_us",
            "false_high", "rd_sense_max_v", "blg_pulse_max_v", "blg_final_v", "off_dev_v", "off_line"] + [c for c, _ in CHECKS]


def csv_rows(rows):
    out = [",".join(CSV_COLS)]
    for r in sorted(rows, key=lambda r: r["tag"]):
        vals = [r["slice"], r["process"], r["temp"], r["scale"], r["band"], r["cell"][0], r["cell"][1], r["cap"], r["acc"],
                r["scen"], r["var"], r["arm_sense_sel"], r.get("arm_sense_idle", ""), r["arm_rdata_sel"], r["arm_iread_sel"],
                max(r["arm_legon_sel"], r.get("arm_legon_idle", 0.0)), max(r["both_sel"], r.get("both_idle", 0.0)),
                r["pul_ron"], r["pul_sense"], r["pul_rdata"], r["pul_ipg"], r["pul_ird"], r["rd_ipg"], r["rd_ird"], int(r["dec_ok"]),
                "" if r["t_dec"] is None else r["t_dec"], "" if r["t_settle"] is None else r["t_settle"],
                int(r["false_high"]), r["rd_sense_max"], r["blg_pulse_max"], r["blg_final"], r["off_dev"], r["off_line"] or ""]
        vals += [int(r["chk"][c]) for c, _ in CHECKS]
        out.append(",".join(str(v) for v in vals))
    return out


ASSUMPTIONS = f"""\
- **Control waveforms are bench-assumed, not designed.** The digital controller (`spec/architecture.md` section 5) is not
  built; its outputs are behavioural B sources with C-infinity edges (20 ns). Sequence: power-up ramp ({B.PWR_RAMP} us) and
  settle; external VPP ramp from VDD to V_PK at {B.T_VPP0} us over `tvr`; ARM (row select, then column select after
  `tcsl`) at {B.T_ARM} us; PROG_EN of the selected band at {B.SCENARIOS['base']['tpe']} us for 1.0 us; completion at
  {B.SCENARIOS['base']['tpf']} us; READ_EN at `tren`. **The assumed controller timing is the scenario table below;
  no sample delay is assumed**: the read decision is reported at ten fixed sample times
  ({', '.join(f'{t:g}' for t in B.SAMPLES)} us) and the smallest grid delay after READ_EN at which it is correct and stays
  correct is the measured settling. The grid resolves settling only to the grid spacing.
- **Scenarios** (timing keys, us): {'; '.join(f"`{n}` " + ", ".join(f"{k}={v:g}" for k, v in d.items()) for n, d in B.SCENARIOS.items())}.
  `tvr` is the external VPP ramp time, `tcsl` the column-select lag behind the row select, `tpe`/`tpf` the PROG_EN rise and
  fall, `tren` the READ_EN rise (a `tren` before `tpf` overlaps the enables and tests the interlock), `tdis` the
  select release ({B.NEVER:g} = never). `timeout` arms and releases without a pulse, then reads at once.
- **Placeholder levels, not programming conditions.** V_PK = {B.V_PK:g} V (x0.9/1.0/1.1 with the supply axis), VDDH per
  band {B.RAILS} V (x scale), VCLAMP {B.VCLAMP:g} V, I_ref {B.I_REF:g} A, VDD = VDDL = {B.VDD:g} V. No claim is made about the
  programming voltage or yield of any region.
- **Filament:** none for `unprog`; for `prog_lo` / `prog_hi` an ASSUMED linear conductance across the SELECTED cell's capacitor
  ({1 / B.GFIL['prog_lo']:g} / {1 / B.GFIL['prog_hi']:g} ohm), present for the whole run, including before the pulse. It is not a
  breakdown model (none is used): the pulse does not program the cell, so these rows test the read transition on an already
  programmed cell. Region III programmed reads are known-unproven (#75).
- **Floating bus:** each band's BLG bus has a {B.R_BLEED:g} ohm bleed to VSS so a floating bus has a defined DC start. The bus
  level when no leg drives it is set by coupling, leakage and that bleed; the bench reports it, it does not assert it.
- **Level-shifter rail VDDH is constant** at its per-band placeholder through the whole run (it does not step between the
  program and read levels), which is the stressful case for the read-phase gate drive.
- **Power-up under `uic`.** The transient starts from zero node voltages (the stock moscap macro does not start from
  an operating point at every corner; `sim/cell-breakdown-model/README.md`). Nothing is measured before
  {B.T_PWR} us; the supplies are not a power-up-sequencing study.
- **Slice, not array.** Four rows by four columns around a region boundary; one program leg and one read leg per
  band on that band's BLG bus. A full array adds bus capacitance and 31x the OFF-state leakage terms
  (`sim/array-slice-bench/` full-band mode); this bench does not carry them.
- **Substitutions (disclosed):** none of the netlists is replaced. Not probed because every terminal is bounded by VDD/VSS by
  construction: the legs' interlock gates, the program leg's PONB inverter, the sense inverters, and the level shifters'
  3.3 V input inverters. The legs' `leg_interlock` is the real committed netlist.
- **Stress limits.** Only limits stated in a committed record are compared (`limits.py`). `spec/cell-candidates.md` gives one
  rating per device family and names no terminal pair; it is applied to gate-source and gate-drain only. Every other pair,
  `ppolyf_u_2k_6p0` (rating OPEN, `spec/leg-design-record.md` section 3), and the selected cell's own capacitor are
  **unchecked**: their peak is reported, never judged.
"""

STATEMENT = """\
## What this record does and does not establish

**Supported by these simulations (pre-silicon, assumed stimulus):** whether the two legs, the array's addressing stage and
the cells, as drawn in the committed netlists, keep the sense input and RDATA still while armed and while a pulse is
applied; whether the legs ever drive the bus together; how far the unselected select lines move; the sense node's settling
after a pulse for an unprogrammed cell and for a cell with an assumed filament; and each probed gate-referenced terminal
pair's peak against the stated device rating.

**Not established, and not claimed:**

- Any breakdown, programming yield or stress-to-failure behaviour: no calibrated breakdown model is used here.
- Long-term disturb, retention or reliability of an unselected cell. The unselected-cell exposure table reports the
  voltage an unselected cell's capacitor and access device reach in this simulation. Staying under a device *rating* is
  not evidence about wear-out: no time-dependent or calibrated oxide behaviour is simulated or cited.
- Silicon safety of any bias point. Pairs without a stated limit (drain-source, junction, `ppolyf_u_2k_6p0`, the selected
  cell's capacitor) are **unchecked**.
- Controller behaviour. The enable timing is an assumption; a real controller must meet or beat the settling reported.
"""


def jobs_lines(comps_by_slice):
    out = []
    for sl, comps in comps_by_slice.items():
        for (proc, tier), comp in comps.items():
            rem = comp.get("remote") or {}
            s = comp.get("summary") or {}
            jobs = rem.get("fleet") or [rem]
            ids = ", ".join(f"`{j.get('job_id')}`" for j in jobs)
            out.append(f"- `{sl}` / `{proc}` / tier {tier}: {s.get('corner_count')} units (pass {s.get('passed')}, fail {s.get('failed')}, "
                       f"error {s.get('errored')}, inconclusive {s.get('inconclusive')}); {len(jobs)} job(s) {ids} "
                       f"({jobs[0].get('provider')}, {jobs[0].get('instance_type')}, {jobs[0].get('lifecycle')}, runner klt "
                       f"{jobs[0].get('runner_klt_version')}); engine {comp.get('engine')}")
    return out



def build_blocks(all_rows, stress):
    """The seven Markdown table blocks (lists of lines), each built once per record."""
    unsel = lambda k: k[1] == "cell" and k[2] != "selected"
    return {
        "summary": summary_lines(all_rows),
        "armed": table_armed(all_rows),
        "pulse": table_pulse(all_rows),
        "transition": table_transition(all_rows),
        "lines": table_lines(all_rows),
        "stress": table_stress(stress, lambda k: True),
        "unsel": table_stress(stress, lambda k: unsel(k)),
    }


def render_record(record_id, blocks, n_units, n_rows, ungradable, clean, now, sha, comps_by_slice):
    """Text of records/<record-id>.md (pure; ``sha`` is the git HEAD at run time)."""
    head = [
        f"# Record {record_id}", "",
        f"- **Record ID**: {record_id}",
        "- **Claim**: `spec/architecture.md` section 1.2 (read leg disabled for the entire armed state and during a pulse; at most one "
        "leg on the shared bit line), section 3 (actively driven unselected lines; unselected cells isolated), and "
        "`spec/supply-domains-decision.md` (domain crossing: the read path is not exposed to a program-voltage transient), checked "
        "electrically on the assembled slice. Issue #73.",
        f"- **Netlist provenance**: schematic (`design/netlists/slice_*.spice`, `program_leg.spice`, `read_leg.spice`, "
        f"`leg_interlock.spice`, cells, pass-gates, level shifters), included from the working tree at git HEAD `{sha[:12]}`; "
        f"working tree {'clean' if clean else 'NOT clean (uncommitted changes at run time)'}.",
        f"- **Corner matrix run**: process {{typical, ff, ss, fs, sf}} (MOS, moscap and poly-resistor sections from the request; the "
        f"matching 10 V LDMOS section from the netlist) x temperature {{-40, 27, 125}} C x supply scale {{0.9, 1.0, 1.1}} "
        f"(VDD, VDDH, VCLAMP and V_PK scale together) x selected cell x scenario/filament point list, in two tiers: "
        f"**tier A**, the full 45-corner PVT grid for the base case (immediate read), unprogrammed and with the assumed "
        f"10 kohm filament, on 4 selected cells per region (all four capacitor x access sub-combinations); **tier B**, the "
        f"other scenarios and the 100 kohm filament on 2 cells per region (rows 0 and 3, opposite on both axes) at a REDUCED "
        f"set of 7 PVT corners: ss at -40 and 125 C with scale 0.9, ff at -40 and 125 C with scale 1.1, and typical, fs, sf at 27 C "
        f"with scale 1.0. The subset is used because a fleet unit costs about 12 s (README.md, 'Cost and the two tiers'); "
        f"the worst corners of each scenario are the cold/slow/low-supply and hot/fast/high-supply extremes and the two skewed "
        f"corners. **{n_units} units**, two slices, twenty `klt sim` requests (two tiers, below).",
        f"- **Result**: per-region tables below; `measurements/integrated-transition/{record_id}.md` and `.csv`.",
        f"- **Links**: testbench `sim/integrated-transition/testbench/`; raw measurements in the artifact "
        f"store, manifest `manifests/artifacts/integrated-transition-{record_id}.manifest.json`; "
        f"runner `run_bench.py`, grading `analyze.py`, limits `limits.py`.",
        f"- **Timestamp / author**: {now:%Y-%m-%dT%H:%M:%SZ} / Claude Sonnet 5.5 (Loom builder, issue #73)",
        "- **Supersedes**: (none)", "",
        "## Assumed / placeholder inputs and disclosed substitutions (all of them)", "", ASSUMPTIONS,
        f"## Coverage", "", f"- units returned: {n_units}; graded points: {n_rows}; **not gradable: {ungradable}** "
        "(never counted as passes; each is listed in the run log). Fleet job ids are listed at the end of this record.", "",
        "## Verdict per criterion (points meeting the criterion / graded points, per region)", "", *blocks["summary"], "",
        "## Armed isolation and leg exclusion", "", *blocks["armed"], "",
        "## Pulse-phase isolation of the read leg", "", *blocks["pulse"], "",
        "## Program-to-read transition (per region, sub-combination, scenario, filament)", "", *blocks["transition"], "",
        "## Unselected select-line bias", "", *blocks["lines"], "",
        "## Device terminal stress against supported limits", "", *blocks["stress"], "",
        "## Unselected-cell exposure (cells only, class relative to the selected cell)", "",
        *blocks["unsel"], "",
        STATEMENT, "## Fleet jobs (out-of-band verification)", "", *jobs_lines(comps_by_slice), ""]
    return "\n".join(head)


def render_measurement_md(record_id, blocks):
    """Text of measurements/integrated-transition/<record-id>.md (pure)."""
    return (
        f"# Integrated program-to-read transition - per-region results ({record_id})\n\n"
        "**Pre-silicon simulation with assumed controller timing, not a silicon measurement.** Per-region view of "
        f"`sim/integrated-transition/records/{record_id}.md` (assumptions, corner matrix, provenance). Regions and "
        "capacitor x access sub-combinations are never averaged together. The per-point rows are in the `.csv` next to this "
        "file.\n\n## Verdict per criterion\n\n" + "\n".join(blocks["summary"]) +
        "\n\n## Armed isolation and leg exclusion\n\n" + "\n".join(blocks["armed"]) +
        "\n\n## Pulse-phase isolation\n\n" + "\n".join(blocks["pulse"]) +
        "\n\n## Program-to-read transition\n\n" + "\n".join(blocks["transition"]) +
        "\n\n## Unselected select-line bias\n\n" + "\n".join(blocks["lines"]) +
        "\n\n## Device terminal stress\n\n" + "\n".join(blocks["stress"]) +
        "\n\n## Unselected-cell exposure\n\n" + "\n".join(blocks["unsel"]) + "\n\n" + STATEMENT)


def write_records(record_id, all_rows, stress, comps_by_slice, ungradable, clean, now, sha, repo=REPO, here=HERE):
    """Render once and write records/<id>.md, measurements/.../<id>.md and .csv."""
    n_units = sum(len(c["points"]) for cs in comps_by_slice.values() for c in cs.values())
    blocks = build_blocks(all_rows, stress)
    rec = here / "records" / f"{record_id}.md"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(render_record(record_id, blocks, n_units, len(all_rows), ungradable, clean, now, sha, comps_by_slice))
    meas = repo / "measurements" / "integrated-transition"
    meas.mkdir(parents=True, exist_ok=True)
    (meas / f"{record_id}.csv").write_text("\n".join(csv_rows(all_rows)) + "\n")
    (meas / f"{record_id}.md").write_text(render_measurement_md(record_id, blocks))
    print(f"wrote {rec.relative_to(repo)}, measurements/integrated-transition/{record_id}.{{md,csv}}")
    return rec
