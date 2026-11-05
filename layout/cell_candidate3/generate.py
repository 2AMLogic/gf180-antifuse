#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell (spec/cell-candidates.md).

Cell: thin-oxide PMOS capacitor (antifuse element, netlist `cap_pmos_03v3`)
in series with a 6.0 V PMOS access device (`pfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring, flavor pfet), `klt draw` (two metal1 straps)
and `klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum, as for candidate 1, clamped to the smallest
width `klt gen mos_array` will draw (W >= 0.42 um).

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um (schematic lacc)
  cap    : thin-oxide PMOS gate over COMP, W = 0.42 um, L = 0.28 um,
           source and drain shorted (moscap) on net CN

Terminal assignment (matches design/cells/cell_candidate3.sch): BL is the
access SOURCE, CN is the access DRAIN. Well connection: each device sits in its
own N-well with an N+ tap ring; the two tap rings are strapped (VB) so the
access well and the capacitor well are one net. Ports (Metal1 labels): BL, WL,
PL (cap gate), VB.

Usage:  generate.py            write cell_candidate3.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

HERE = os.path.dirname(os.path.abspath(__file__))
L_ACC = 0.55       # um, schematic lacc
DX = 4.8  # um, cap-block x offset (N-well/Nplus spacing; 4.2 violated nwell.space.1)
# Access block at (0,0), cap block at (DX,0). Access S (BL) is at x=0.21 and D
# (CN) at x=1.07; cap S/D at DX+0.21 / DX+1.07. Ring gaps face each other.
STRAPS = {"shapes": [
    # CN: access drain pad -> cap source pad -> cap drain pad (metal1)
    {"layer": bg.METAL1, "rect_um": [0.92, 0.06, DX + 1.22, 0.36]},
    # VB: tie both tap rings together along the north side
    {"layer": bg.METAL1, "rect_um": [0.49, 2.49, DX + 0.79, 2.91]},
    # MOS-capacitor marker over the cap block's COMP island
    {"layer": bg.MOS_CAP_MK, "rect_um": [DX - 0.1, -0.1, DX + 1.38, 0.52]},
]}

if __name__ == "__main__":
    bg.main(
        HERE, gds_name="cell_candidate3.gds", cell="cell_candidate3",
        flavor="pfet", l_acc=L_ACC, cap_gap_side="W", acc_gap_side="E",
        straps=STRAPS,
        origins_um={"acc": {"x": 0, "y": 0}, "cap": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_S"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
