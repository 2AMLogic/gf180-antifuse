#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell (spec/cell-candidates.md).

Cell: thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`)
in series with a 6.0 V NMOS access device (`nfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring), `klt draw` (two metal1 straps) and
`klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum of spec/split-axis-plan.md sections 2-3
(capacitor geometry = Minimum, access sizing = Minimum), clamped to the
smallest width `klt gen mos_array` will draw (W >= 0.42 um, a generator-side
contact-fit floor; the schematic's default wacc is 0.30 um -- see README).

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um
  cap    : thin-oxide NMOS gate over COMP, W = 0.42 um, L = 0.28 um,
           source and drain shorted (moscap) on net CN

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

HERE = os.path.dirname(os.path.abspath(__file__))
L_ACC = 0.70       # um, 6 V device minimum drawn length (schematic lacc)
DX = 4.2           # um, access-block x offset (keeps Pplus spacing >= 0.4)
# Ports are located in each block's local frame (reported by klt gen); the
# straps below are in the composed frame: cap block at (0,0), access at (DX,0).
STRAPS = {"shapes": [
    # CN: access source pad -> cap drain pad -> cap source pad (metal1)
    {"layer": bg.METAL1, "rect_um": [0.06, 0.06, DX + 0.36, 0.36]},
    # VB: tie both tap rings together along the north side
    {"layer": bg.METAL1, "rect_um": [0.64, 2.49, DX + 0.85, 2.91]},
    # MOS-capacitor marker (MOS_CAP_MK) over the cap block's COMP island
    # (0,0)-(1.28,0.42); this is what makes the deck read the thin-oxide gate
    # as cap_nmos_03v3 instead of an nfet. Not drawn over the access device.
    {"layer": bg.MOS_CAP_MK, "rect_um": [-0.1, -0.1, 1.38, 0.52]},
]}

if __name__ == "__main__":
    bg.main(
        HERE, gds_name="cell_candidate1.gds", cell="cell_candidate1",
        flavor="nfet", l_acc=L_ACC, cap_gap_side="E", acc_gap_side="W",
        straps=STRAPS,
        origins_um={"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_D"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
