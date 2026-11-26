#!/usr/bin/env python3
"""Generate the run3 chip-level reference netlist and pad table (issue #275).

One source of truth for the 36-instance table and the 8-point geometry table;
writes two committed artifacts next to this script:

  run3_top.spice   chip-level SPICE reference netlist, self-contained
                   (per-geometry cell subcircuits + the top ``run3_top``
                   subckt), in the klt lvs reference.form = "subckt-call"
                   shape with top = "run3_top".
  pad_table.json   machine-readable pad table: 48 logical slots L01-L48
                   (pad id, signal, direction, slot type, voltage class).

``--check`` byte-compares both against the committed files on sha256, like
``layout/bitcell_gen.py``. Stdlib only: no klt, no network, no third-party
package. Deterministic: two runs are byte-identical.

Geometry basis (README.md states it in exactly one place): capacitor W/L at
the ratified levels of spec/capacitor-geometry-decision.md; access W/L at the
drawn XM1 literals of layout/cell_*/lvs_reference.spice. The capacitor half
knowingly disagrees with all seven committed cells until #296 lands;
design/check-geometry-basis.py owns that divergence record, not this issue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# --- instance table: the single source (issue #275 AC1) ---------------------
#
# Groups of spec/run3-test-chip-floorplan.md "Cells and instance counts":
# shared BL and WL per group, private PL per instance. Each group spans both
# capacitor levels; instances per (geometry) level are the record's 4 (C1) or
# 5 (C2, C3). Pad ids L01-L36 follow the record's pad table exactly.

GROUPS = [
    # (group label, candidate, access level, instances per capacitor level)
    ("C1-Amin", "C1", "Amin", 4),
    ("C1-A2x", "C1", "A2x", 4),
    ("C2-Amin", "C2", "Amin", 5),
    ("C3-Amin", "C3", "Amin", 5),
]
CAP_LEVELS = ("Gmin", "G2x")


def cell_name(cand: str, acc: str, cap: str) -> str:
    """Layout cell name of a geometry point, per the committed
    layout/cell_* naming convention: the all-Minimum point is the bare
    ``cell_candidate<N>``; every other point carries both levels."""
    base = f"cell_candidate{cand[1]}"
    if acc == "Amin" and cap == "Gmin":
        return base
    return f"{base}_{acc}_{cap}"


def build_instances() -> list[dict]:
    """36 instance rows in pad order: pad id, instance name, PL net (= pad
    signal name), group, candidate, access level, capacitor level."""
    insts: list[dict] = []
    pad = 0
    for group, cand, acc, per_level in GROUPS:
        for cap in CAP_LEVELS:
            for i in range(1, per_level + 1):
                pad += 1
                insts.append({
                    "pad": f"L{pad:02d}",
                    "name": f"Xinst_{cand}_{acc}_{cap}_{i}",
                    "signal": f"PL_{cand}_{acc}_{cap}_{i}",
                    "group": group,
                    "candidate": cand,
                    "access": acc,
                    "capacitor": cap,
                })
    assert pad == 36, pad
    return insts


# --- geometry table: 8 points, each half keyed to the source that binds it --
#
# Capacitor W/L: ratified levels, spec/capacitor-geometry-decision.md
# "Decision" table (region map of spec/split-axis-plan.md: I = C1,
# II = C2, III = C3). C2 moves in BOTH dimensions: its drawn
# c_length=0.56u violates PL.2_MV independently of width.
CAP_RATIFIED = {
    # candidate -> (device, {cap level: (W, L) in um, as emitted})
    "C1": ("cap_nmos_03v3", {"Gmin": ("1.0", "0.28"), "G2x": ("2.0", "0.28")}),
    "C2": ("cap_nmos_06v0", {"Gmin": ("1.0", "0.70"), "G2x": ("2.0", "0.70")}),
    "C3": ("cap_pmos_03v3", {"Gmin": ("1.0", "0.28"), "G2x": ("2.0", "0.28")}),
}

# Access W/L: drawn XM1 literals, copied from the committed
# layout/cell_*/lvs_reference.spice files (issue #275 Verified correction 7).
# The access-device sizing axis is unratified (spec/capacitor-geometry-decision.md:
# "the access-device sizing axis is untouched"), so the drawn literals are the
# only committed physical basis.
ACCESS_DRAWN = {
    # candidate -> access level -> (device, L, W, nf), as drawn and as emitted
    "C1": {"Amin": ("nfet_06v0", "0.70", "0.42", "1"),
           "A2x": ("nfet_06v0", "0.70", "0.84", "1")},
    "C2": {"Amin": ("nfet_10v0_asym", "0.60", "8", "2")},
    "C3": {"Amin": ("pfet_06v0", "0.55", "0.42", "1")},
}

# XM1 node order per candidate: nfet candidates take BL WL CN VB; Candidate 3's
# pfet draws CN WL BL VB (as in every committed lvs_reference.spice).
XM1_NODES = {"C1": "BL WL CN VB", "C2": "BL WL CN VB", "C3": "CN WL BL VB"}

# --- pad-table derivation ---------------------------------------------------
#
# spec/program-bias-scheme-proposed-decision.md is PROPOSED, not ratified, and
# recommends the PL-driven program leg, so the HV pad class rides the PL pads.
# If the operator ratifies BL-driven instead, the floorplan record's wiring
# section says the HV terminal moves to BL and the private/shared roles of BL
# and PL swap: pad counts are unchanged, the slot types are not ("HV on
# bidirectional, standard on analog" -- for the HV-pad sibling to confirm).
# Flipping this one constant moves both derived fields in
# terminal_pad_fields(); nothing else in the generator changes.
HV_TERMINAL = "PL"


def terminal_pad_fields(kind: str) -> tuple[str, str]:
    """(voltage_class, slot_type) of a program-terminal pad (PL or BL kind).

    Applies the record's rule "HV on bidirectional, standard on analog" to
    whichever terminal carries the program pulse."""
    if kind == HV_TERMINAL:
        return "HV", "bidir"
    return "standard", "analog"


# Fixed per-kind pad data (record pad table; not touched by the HV swap).
NON_TERMINAL_FIELDS = {
    # kind -> (direction, slot_type, voltage_class)
    "WL": ("input", "input-only", "standard"),
    "VBW": ("bidir", "bidir", "standard"),
}
UNUSED_PADS = [
    # (pad id, unused index, slot_type) -- the only pad rows whose slot type
    # is row data
    ("L46", 1, "input-only"),
    ("L47", 2, "input-only"),
    ("L48", 3, "bidir"),
]

# C1/C2 bodies tie on-die to the substrate; C3's n-well tie is a pad
# (VBW_C3), per the floorplan record's wiring section. The substrate net name
# is the generator's PLACEHOLDER, not a ratified name:
# spec/supply-domains-decision.md rows 2/13/14 leave it open (OI-2, OI-6).
SUBSTRATE_NET = "VSS_ANALOG"
VBW_NET = "VBW_C3"


def build_pads() -> list[dict]:
    """48 pad rows in slot order L01-L48."""
    pads: list[dict] = []
    # L01-L36: the 36 private PL pads, one per instance, in pad order.
    for inst in build_instances():
        cls, slot = terminal_pad_fields("PL")
        pads.append({"pad": inst["pad"], "signal": inst["signal"],
                     "direction": "bidir", "slot_type": slot,
                     "voltage_class": cls})
    # L37-L40: the four groups' shared BL nets, in group order; L41-L44: WL.
    group_nets = []
    for _, cand, acc, _ in GROUPS:
        sub = "A2x" if acc == "A2x" else "Amin"
        group_nets.append(f"BL_C1_{sub}" if cand == "C1" else f"BL_{cand}_Amin")
    for net in group_nets:
        cls, slot = terminal_pad_fields("BL")
        pads.append({"pad": f"L{len(pads) + 1:02d}", "signal": net,
                     "direction": "analog", "slot_type": slot,
                     "voltage_class": cls})
    for net in (n.replace("BL_", "WL_") for n in group_nets):
        d, slot, cls = NON_TERMINAL_FIELDS["WL"]
        pads.append({"pad": f"L{len(pads) + 1:02d}", "signal": net,
                     "direction": d, "slot_type": slot, "voltage_class": cls})

    d, slot, cls = NON_TERMINAL_FIELDS["VBW"]
    pads.append({"pad": f"L{len(pads) + 1:02d}", "signal": VBW_NET,
                 "direction": d, "slot_type": slot, "voltage_class": cls})
    for pad_id, idx, slot in UNUSED_PADS:
        pads.append({"pad": pad_id, "signal": f"UNUSED_{idx}",
                     "direction": "none", "slot_type": slot,
                     "voltage_class": "n/a"})
    assert len(pads) == 48, len(pads)
    return pads


def emit_pad_table() -> str:
    doc = {
        "schema": "run3-pad-table/1",
        "source_record": "spec/run3-test-chip-floorplan.md",
        "record_status": "Proposed for operator ratification",
        "hv_terminal": HV_TERMINAL,
        "pads": build_pads(),
    }
    return json.dumps(doc, indent=2) + "\n"


def _cell_subckt(cand: str, acc: str, cap: str) -> str:
    name = cell_name(cand, acc, cap)
    dev, l, w, nf = ACCESS_DRAWN[cand][acc]
    cap_dev, levels = CAP_RATIFIED[cand]
    cw, cl = levels[cap]
    lines = [f".subckt {name} BL WL PL VB"]
    lines.append(f"* access: drawn XM1 literal (layout/{name}/lvs_reference.spice)")
    lines.append(f"XM1 {XM1_NODES[cand]} {dev} L={l}u W={w}u nf={nf} m=1")
    lines.append(f"* capacitor: ratified {cap} level"
                 f" (spec/capacitor-geometry-decision.md)")
    lines.append(f"XC1 CN PL {cap_dev} c_width={cw}u c_length={cl}u m=1")
    lines.append(".ends")
    return "\n".join(lines)


def _geometry_points() -> list[tuple[str, str, str]]:
    pts: list[tuple[str, str, str]] = []
    for _, cand, acc, _ in GROUPS:
        for cap in CAP_LEVELS:
            if (cand, acc, cap) not in pts:
                pts.append((cand, acc, cap))
    return pts


def format_instance_lines(insts: list[dict]) -> list[str]:
    """SPICE group comments and instance calls for an ordered slice of
    build_instances() rows."""
    lines: list[str] = []
    last_group = None
    for inst in insts:
        cand = inst["candidate"]
        sub = "A2x" if inst["access"] == "A2x" else "Amin"
        bl = f"BL_C1_{sub}" if cand == "C1" else f"BL_{cand}_Amin"
        wl = bl.replace("BL_", "WL_")
        vb = VBW_NET if cand == "C3" else SUBSTRATE_NET
        if inst["group"] != last_group:
            lines.append(f"* Group {inst['group']}: shared {bl} / {wl},"
                         f" private PL per instance, bodies to {vb}.")
            last_group = inst["group"]
        cell = cell_name(cand, inst["access"], inst["capacitor"])
        lines.append(f"{inst['name']} {bl} {wl} {inst['signal']} {vb} {cell}")
    return lines


def emit_netlist() -> str:
    insts = build_instances()
    points = _geometry_points()
    out: list[str] = [
        "* run3_top -- chip-level reference netlist for the run3 test chip",
        "* (issue #275, part of #203).",
        "* Generated by layout/run3_top/generate_run3_top.py -- DO NOT EDIT.",
        "* Regenerate and verify: python3 -I layout/run3_top/generate_run3_top.py --check",
        "*",
        "* Geometry basis (README.md states it in exactly one place): capacitor",
        "* W/L at the ratified levels of spec/capacitor-geometry-decision.md;",
        "* access W/L at the drawn XM1 literals of layout/cell_*/lvs_reference.spice.",
        "* The capacitor half knowingly disagrees with all seven committed cells",
        "* until #296 lands; design/check-geometry-basis.py owns that divergence",
        "* record, scripts/check_run3_pad_table.py re-checks each half against its",
        "* binding source.",
        "*",
        f"* The substrate net {SUBSTRATE_NET} is the generator's placeholder for the",
        "* C1/C2 p-substrate tie; it is NOT a ratified name",
        "* (spec/supply-domains-decision.md rows 2/13/14, OI-2/OI-6). C3's n-well",
        f"* tie is the {VBW_NET} pad net.",
        "*",
        '* Written to the klt lvs reference.form = "subckt-call" shape',
        '* (top = "run3_top"); whether klt resolves this hierarchical form is',
        "* first exercised at chip assembly (#211). It is not asserted here that",
        "* the netlist passes klt lvs.",
        "",
    ]
    out.append("* ---- per-geometry cell subcircuits (8 points) ----")
    out.append("")
    for cand, acc, cap in points:
        out.append(_cell_subckt(cand, acc, cap))
        out.append("")
    out.append("* ---- top: 36 instances, 45 signal ports ----")
    out.append("")
    ports = [p["signal"] for p in build_pads()[:45]]
    out.append(".subckt run3_top " + " ".join(ports))
    out.extend(format_instance_lines(insts))
    out.append(".ends")
    out.append("")
    return "\n".join(out)


ARTIFACTS = (("run3_top.spice", emit_netlist),
             ("pad_table.json", emit_pad_table))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="byte-compare against the committed files, write nothing")
    args = ap.parse_args()
    bad = False
    for fname, emit in ARTIFACTS:
        text = emit()
        committed = HERE / fname
        if args.check:
            if not committed.is_file():
                print(f"missing {committed}")
                bad = True
                continue
            a, b = sha(text), sha(committed.read_text())
            if a != b:
                print(f"DRIFT: {fname}: regenerated sha256 {a} != committed {b}")
                bad = True
            else:
                print(f"OK: {fname} sha256 {b}")
        else:
            committed.write_text(text)
            print(f"wrote {committed} sha256 {sha(text)}")
    if bad:
        sys.exit("regeneration drifted; run without --check to rewrite")


if __name__ == "__main__":
    main()
