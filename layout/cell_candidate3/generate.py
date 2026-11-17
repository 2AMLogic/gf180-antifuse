#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell (spec/cell-candidates.md).

Cell: thin-oxide PMOS capacitor (antifuse element, netlist `cap_pmos_03v3`)
in series with a 6.0 V PMOS access device (`pfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring, flavor pfet), `klt draw` (two metal1 straps)
and `klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum, as for candidate 1. The capacitor is drawn
at the ratified Minimum level, W = 1.0 um at L = 0.28 um
(`spec/capacitor-geometry-decision.md`: the PDK runset's 1 um `DF.1c`
"Min. COMP Width for MOSCAP" floor). The access width stays at the 0.42 um
generator floor (a contact-fit floor above the process minimum; the
schematic's default wacc is 0.30 um -- the access axis is out of scope here,
see README).

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um (schematic lacc)
  cap    : thin-oxide PMOS gate over COMP, W = 1.0 um, L = 0.28 um,
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
W_CAP = 1.0        # um, capacitor width -- the ratified Minimum level
                   # (spec/capacitor-geometry-decision.md, the DF.1c floor)
# Access block at (0,0), cap block at (DX,0). Access S (BL) is at x=0.21 and D
# (CN) at x=1.07; cap S/D at DX+0.21 / DX+1.07. Ring gaps face each other.
STRAPS = {"shapes": [
    # CN: access drain pad -> cap source pad -> cap drain pad (metal1). One
    # band through both tap rings' metal1 exit gaps: the gap spans rise with
    # the width (measured, klt gen mos_array: -0.28..0.72 um at W = 0.42,
    # 0.01..1.01 um at W = 1.0), and with the 0.23 um (metal1.space.1)
    # clearance required from every edge the common window is 0.24..0.49 --
    # 0.25..0.48 sits inside it with >= 0.24 um clearance and is exactly the
    # 0.23 um metal1 minimum WIDTH (M1.1) tall -- a thinner band fails M1.1
    # on its free-standing stretches between pads (observed on the first
    # generated cell), and the window has no room for a taller one (the same
    # derivation as layout/candidate1_points.py). The band overlaps both S/D
    # pads (each as tall as its device width).
    {"layer": bg.METAL1, "rect_um": [0.92, 0.25, DX + 1.22, 0.48]},
    # VB: tie both tap rings together along the north side. The TAP_N pad
    # centre rises with the width (centre = W + 2.28 um, measured), so the
    # band spans both pads -- min/max +/- 0.21 -- and tracks the widths
    # (access at bg.W_MIN, capacitor at W_CAP) instead of restating them as
    # literals. It clears the capacitor's metal1 gate pad
    # (y 1.75..2.17 at W_CAP = 1.0) by 0.32 um.
    {"layer": bg.METAL1,
     "rect_um": [0.49, bg.W_MIN + 2.28 - 0.21, DX + 0.79, W_CAP + 2.28 + 0.21]},
    # MOS-capacitor marker over the cap block's COMP island, which is as tall
    # as the device width (0,0)-(1.28, W_CAP) in the block frame -- so the
    # marker grows with W_CAP, keeping the 0.1 um margin. This is what makes
    # the deck read the thin-oxide gate as cap_pmos_03v3 instead of a pfet.
    # Not drawn over the access device.
    {"layer": bg.MOS_CAP_MK, "rect_um": [DX - 0.1, -0.1, DX + 1.38, W_CAP + 0.1]},
]}

if __name__ == "__main__":
    bg.main(
        HERE, gds_name="cell_candidate3.gds", cell="cell_candidate3",
        flavor="pfet", w_cap_um=W_CAP, l_cap_um=bg.L_CAP, w_acc_um=bg.W_MIN,
        l_acc=L_ACC, cap_gap_side="W", acc_gap_side="E",
        straps=STRAPS,
        origins_um={"acc": {"x": 0, "y": 0}, "cap": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_S"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
