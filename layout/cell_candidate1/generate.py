#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell (spec/cell-candidates.md).

Cell: thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`)
in series with a 6.0 V NMOS access device (`nfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring), `klt draw` (two metal1 straps) and
`klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum of spec/split-axis-plan.md sections 2-3
(capacitor geometry = Minimum, access sizing = Minimum). The capacitor is
drawn at the ratified Minimum level, W = 1.0 um at L = 0.28 um
(`spec/capacitor-geometry-decision.md`: the PDK runset's 1 um `DF.1c`
"Min. COMP Width for MOSCAP" floor). The access width stays at the 0.42 um
generator floor (a contact-fit floor above the process minimum; the
schematic's default wacc is 0.30 um -- the access axis is out of scope here,
see README).

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um
  cap    : thin-oxide NMOS gate over COMP, W = 1.0 um, L = 0.28 um,
           source and drain shorted (moscap) on net CN

Straps and marker come from `candidate1_points.straps(1.0, 0.42)` -- the same
derivation the candidate-1 split cells use: CN inside both tap rings'
metal1 exit-gap windows (>= 0.23 um metal1.space.1 clearance), VB over both
tap-ring pads, MOS_CAP_MK grown with the capacitor island.

Ports (text labels on Metal1): BL (access drain), WL (access gate),
PL (cap gate/plate), VB (both tap rings, strapped).

Usage:  generate.py            write cell_candidate1.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)
import candidate1_points as pts  # noqa: E402  shared strap derivation (layout/candidate1_points.py)

HERE = os.path.dirname(os.path.abspath(__file__))
L_ACC = 0.70       # um, 6 V device minimum drawn length (schematic lacc)
DX = 4.2           # um, access-block x offset (keeps Pplus spacing >= 0.4);
                   # == pts.DX, kept local as before.

if __name__ == "__main__":
    bg.main(
        HERE, gds_name="cell_candidate1.gds", cell="cell_candidate1",
        flavor="nfet", w_cap_um=1.0, l_cap_um=bg.L_CAP, w_acc_um=bg.W_MIN,
        l_acc=L_ACC, cap_gap_side="E", acc_gap_side="W",
        straps=pts.straps(1.0, bg.W_MIN),
        origins_um={"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_D"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
