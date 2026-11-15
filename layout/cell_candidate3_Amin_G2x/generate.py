#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell at access Minimum x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md section 2).

Same cell as `layout/cell_candidate3/` -- thin-oxide PMOS capacitor (antifuse
element, netlist `cap_pmos_03v3`) in series with a 6.0 V PMOS access device
(`pfet_06v0`) -- drawn at a different point of the split-axis grid. Drawn with
`klt gen` (mos_array primitives + tap ring, flavor pfet), `klt draw` (metal1
straps and the MOS-capacitor marker) and `klt gen-compose` (explicit
placement), for gf180mcu.

Geometry point: access sizing **Minimum**, capacitor geometry **2x**. The 2x is
taken on the capacitor's width at held drawn length, which doubles its area
exactly (0.84 x 0.28 = 0.2352 um2 against 0.42 x 0.28 = 0.1176 um2). Width is
the axis `sim/cell-device-characterization/` already scales for the G axis
(`sizing_multiplier` applied to `wcap`, `lcap` passed through), so "G2x" means
the same thing in `sim/` and in `layout/`. Both Minimum levels are the
generator's width floor (W >= 0.42 um, a contact-fit floor above the process
minimum), not the process minimum -- see layout/README.md.

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um   (Minimum)
  cap    : thin-oxide PMOS gate over COMP, W = 0.84 um, L = 0.28 um (2x area),
           source and drain shorted (moscap) on net CN

Terminal assignment (matches design/cells/cell_candidate3.sch): BL is the
access SOURCE, CN is the access DRAIN (mirror of the NMOS candidates). Well
connection: each device sits in its own N-well with an N+ tap ring; the two
tap rings are strapped (VB) so the access well and the capacitor well are one
net. Ports (Metal1 labels): BL, WL, PL (cap gate), VB.

Usage:  generate.py            write the GDS next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==0.8.0` to pin.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

HERE = os.path.dirname(os.path.abspath(__file__))
CELL = "cell_candidate3_Amin_G2x"
W_CAP = 0.84       # um, capacitor width = 2x the drawn Minimum (bg.W_MIN)
L_CAP = 0.28       # um, thin-oxide minimum drawn length (held, == bg.L_CAP)
W_ACC = 0.42       # um, access width = Minimum (== bg.W_MIN)
L_ACC = 0.55       # um, 6 V device drawn length (schematic lacc)
DX = 4.8  # um, cap-block x offset (N-well/Nplus spacing; 4.2 violated nwell.space.1)

# Composed frame: access block at (0,0), cap block at (DX,0). Doubling a device
# width grows its block in y only and leaves every x coordinate untouched
# (measured with klt gen mos_array 0.8.0 at exactly these parameters), which is
# why DX = 4.8 carries over from cell_candidate3/ -- confirmed by this cell's
# DRC report, not inferred from the block extents alone. The TAP_N pad centre
# moves with the width: y = 2.70 at W = 0.42 um, y = 3.12 at W = 0.84 um.
Y_TAP_CAP = 3.12   # cap block TAP_N pad centre at W_CAP
Y_TAP_ACC = 2.70   # access block TAP_N pad centre at W_ACC
# One VB rect tall enough to overlap both TAP_N pads (each 0.42 um across).
VB_Y0 = min(Y_TAP_CAP, Y_TAP_ACC) - 0.21
VB_Y1 = max(Y_TAP_CAP, Y_TAP_ACC) + 0.21

# CN leaves each tap ring through that ring's metal1 exit gap (ring_gap_um 1.0,
# ring_gap_offset_um -0.7). The gap is centred on the device, so it rises with
# the device width: measured GAP_E/GAP_W span y -0.28..0.72 at W = 0.42 um and
# y -0.07..0.93 at W = 0.84 um. CN crosses BOTH rings' gaps, so it must sit in
# their intersection with >= 0.23 um (metal1.space.1) clearance from each gap
# edge. cell_candidate3/'s band (0.06..0.36) leaves only 0.13 um below a
# doubled block's gap and does fail metal1.space.1 here (observed on the
# candidate-1 variant cells, same generator), so it is raised.
CN_Y0, CN_Y1 = 0.18, 0.48

STRAPS = {"shapes": [
    # CN: access drain pad -> cap source pad -> cap drain pad (metal1). The
    # S/D pads are as tall as the device width, so this band lies inside the
    # doubled cap pads (y 0..0.84) and overhangs the Minimum access pad's top
    # edge (y 0.42) by 0.06 um -- metal over field, DRC clean. It overlaps
    # every pad by >= 0.24 um in y.
    {"layer": bg.METAL1, "rect_um": [0.92, CN_Y0, DX + 1.22, CN_Y1]},
    # VB: tie both tap rings together along the north side. The two TAP_N pads
    # sit at different heights here (the cap block is the doubled one), so this
    # is one band spanning both rather than cell_candidate3/'s flat rect.
    {"layer": bg.METAL1, "rect_um": [0.49, VB_Y0, DX + 0.79, VB_Y1]},
    # MOS-capacitor marker (MOS_CAP_MK) over the cap block's COMP island
    # (DX,0)-(DX+1.28,0.84) -- the island is as tall as the device width, so it
    # grows with W_CAP; the 0.1 um margin matches cell_candidate3/. This is
    # what makes the deck read the thin-oxide gate as cap_pmos_03v3 instead of
    # a pfet. Not drawn over the access device.
    {"layer": bg.MOS_CAP_MK, "rect_um": [DX - 0.1, -0.1, DX + 1.38, W_CAP + 0.1]},
]}

if __name__ == "__main__":
    bg.main(
        HERE, gds_name=CELL + ".gds", cell=CELL,
        flavor="pfet", w_cap_um=W_CAP, l_cap_um=L_CAP, w_acc_um=W_ACC,
        l_acc=L_ACC, cap_gap_side="W", acc_gap_side="E",
        straps=STRAPS,
        origins_um={"acc": {"x": 0, "y": 0}, "cap": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_S"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
