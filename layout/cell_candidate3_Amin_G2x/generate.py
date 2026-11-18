#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell at access Minimum x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md section 2).

Same cell as `layout/cell_candidate3/` -- thin-oxide PMOS capacitor (antifuse
element, netlist `cap_pmos_03v3`) in series with a 6.0 V PMOS access device
(`pfet_06v0`) -- drawn at a different point of the split-axis grid. Drawn with
`klt gen` (mos_array primitives + tap ring, flavor pfet), `klt draw` (metal1
straps and the MOS-capacitor marker) and `klt gen-compose` (explicit
placement), for gf180mcu.

Geometry point: access sizing **Minimum**, capacitor geometry **2x**. The 2x
is taken on the capacitor's width at held drawn length, per the ratified
levels (`spec/capacitor-geometry-decision.md`): W 1.0 -> 2.0 um at L 0.28 um,
exactly doubling the area (2.0 x 0.28 = 0.56 um2 against 1.0 x 0.28 = 0.28
um2). Width is the axis `sim/cell-device-characterization/` already scales
for the G axis (`sizing_multiplier` applied to `wcap`, `lcap` passed
through), so "G2x" means the same thing in `sim/` and in `layout/`. The
Minimum capacitor is the ratified 1 um level (the PDK runset's `DF.1c`
"Min. COMP Width for MOSCAP" floor); the Minimum access width is still the
generator's contact-fit floor (W >= 0.42 um) -- see layout/README.md.

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um   (Minimum)
  cap    : thin-oxide PMOS gate over COMP, W = 2.0 um, L = 0.28 um (2x area),
           source and drain shorted (moscap) on net CN

Terminal assignment (matches design/cells/cell_candidate3.sch): BL is the
access SOURCE, CN is the access DRAIN (mirror of the NMOS candidates). Well
connection: each device sits in its own N-well with an N+ tap ring; the two
tap rings are strapped (VB) so the access well and the capacitor well are one
net. The access block's tap ring is drawn at the raised generator padding
RING_PAD_ACC (acc block only) -- the generator default misses two native-deck
well/Dualgate rules on this pfet + medium-voltage pairing; RING_PAD_ACC's
comment has the story. Ports (Metal1 labels): BL, WL, PL (cap gate), VB.

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
W_CAP = 2.0        # um, capacitor width = the ratified 2x-area level
                   # (spec/capacitor-geometry-decision.md: 2x doubles W at
                   # held L; 2.0 x 0.28 = 0.56 um2 = 2.000 x the Minimum)
L_CAP = 0.28       # um, thin-oxide minimum drawn length (held, == bg.L_CAP)
W_ACC = 0.42       # um, access width = Minimum (== bg.W_MIN)
L_ACC = 0.55       # um, 6 V device drawn length (schematic lacc)
RING_PAD_ACC = 1.29  # um, acc-block generator ring_padding_um. This variant
                    # pairs pfet with medium_voltage exactly like
                    # cell_candidate3/ does, so the generator default 0.5
                    # draws the same defective acc block: N-well 0.15 um
                    # inside the N+ tap ring (native DF.4d_MV wants 0.16
                    # overlap) and a Dualgate marker missing COMP enclosure
                    # (DV.6, 0.24 um) -- the same generator defect as
                    # cell_candidate3/ (#297, upstream
                    # 2AMLogic/klayout-tools#6503), cleared here the same way.
                    # 1.29 is the smallest padding that clears both on THIS
                    # composed cell, bisected here in 0.01 um steps at DX =
                    # 4.8 + (RING_PAD_ACC - 0.5) (native rule counts, klt drc
                    # --engine klayout, klayout-tools 0.9.2): 0.5 -> DF.4d_MV
                    # x5 + DV.6 x1 (the committed pre-fix state); 1.0 ->
                    # DF.4d_MV x9 + DV.6 x1 + DV.7 x1 (worse -- the counts are
                    # non-monotonic); 1.05-1.28 -> both clear but **DV.3 x5
                    # appears** ("Min. Dualgate to COMP space [unrelated]:
                    # 0.24 um" -- the raised ring's N+ escapes the core-
                    # anchored Dualgate marker; the window spans the whole
                    # 1.05-1.28 range on this cell too); **1.29 -> clean of
                    # all three**; 1.28, one step below, still reports DV.3 x5
                    # (minimality evidence); 1.30-1.40 stay clean, so 1.29 is
                    # the floor, not a window edge. The capacitor block keeps
                    # the default: it draws no Dualgate marker and its well
                    # overlap is legal. The generator response is the one
                    # filed upstream (public tracker, generic description):
                    # 2AMLogic/klayout-tools#6503.
DPAD = RING_PAD_ACC - 0.5  # um, how far the raised acc ring moves out on all
                    # four sides (measured: acc-block bbox (-1.23,-1.23)-
                    # (2.78,3.07) at 0.5 -> (-2.02,-2.02)-(3.57,3.86) at
                    # 1.29, klt gen mos_array 0.8.0; TAP_N centre 2.70 ->
                    # 3.49, U0_S/D/G untouched -- the acc block here is
                    # parameter-identical to cell_candidate3/'s, so #297's
                    # block-level measurements carry over).
DX = 4.8 + DPAD  # um, cap-block x offset. Grows with the acc ring so the
                 # proven 0.79 um ring-to-ring n-well gap (4.8 at the default
                 # padding) is kept; DX = 4.2, a 0.19 um gap, violated
                 # nwell.space.1 historically (measured on cell_candidate3/).
Y_TAP_CAP = 4.28   # cap block TAP_N pad centre at W_CAP
Y_TAP_ACC = 2.70 + DPAD  # access block TAP_N pad centre: 2.70 at W_ACC and
                         # the default padding, + DPAD with the raised ring
                         # (measured, klt gen mos_array 0.8.0).

# CN leaves each tap ring through that ring's metal1 exit gap (ring_gap_um 1.0,
# ring_gap_offset_um -0.7). The gap is centred on the device, so it rises with
# the device width: measured GAP_W/GAP_E spans y -0.28..0.72 at W = 0.42 um
# (access, E side) and y 0.51..1.51 at W_CAP = 2.0 um (capacitor, W side) --
# centre W/2 + 0.01 um at every width, 1.0 um tall, and padding-independent in
# y (the gap follows the pads, not the ring). With the 0.23 um
# (metal1.space.1) clearance required from every gap edge the legal windows
# are -0.05..0.49 and 0.74..1.28: DISJOINT at the 2x capacitor, so no
# single-rect CN exists here (the same measured constraint as the
# candidate-1 G2x cells; spec/capacitor-geometry-decision.md). The strap is a
# doglegged three-rect metal1 shape: an access-side band through the access
# ring's gap, a riser across the inter-ring field, and a capacitor-side band
# through the capacitor ring's gap. Binding metal edges (measured from the
# generated blocks): the access ring's metal1 outer edge sits at x 2.77 + DPAD
# (2.77 at the default padding, + DPAD with the raised ring) and the
# capacitor ring's metal1 outer edge at DX - 1.07 = 3.73 + DPAD, so the field
# stays 0.96 um wide (DX tracks DPAD) and the riser (x 3.02 + DPAD ..
# 3.48 + DPAD) clears both by >= 0.25 um at every padding. The access row
# (y 0.0..0.45) clears its gap by >= 0.27 um and overlaps the access D pad
# (x 0.86..1.28, y 0..0.42); the cap row (y 0.78..1.25) clears its gap by
# >= 0.26 um and overlaps both capacitor S/D pads (each as tall as W_CAP).

# VB cannot be one flat band here either: the capacitor's metal1 gate pad
# (x DX + 0.43..DX + 0.85, y W_CAP + 0.75..W_CAP + 1.17 = 2.75..3.17) sits
# BETWEEN the two rings' metal north bands (access metal y 2.45 + DPAD ..
# 2.91 + DPAD over the raised ring, capacitor metal y 4.03..4.49), and a band
# spanning both would sweep through it and short PL to VB. Two stacked bands
# -- one per ring, each over its TAP_N pad -- joined by a riser at
# x 3.05 + DPAD .. 3.45 + DPAD (left of the capacitor ring's metal edge,
# clear of the gate pad and both CN rows) connect them instead.
STRAPS = {"shapes": [
    # CN, access side: access D pad -> through the access ring gap, ending in
    # the inter-ring field.
    {"layer": bg.METAL1, "rect_um": [0.92, 0.00, 3.48 + DPAD, 0.45]},
    # CN riser across the inter-ring field.
    {"layer": bg.METAL1, "rect_um": [3.02 + DPAD, 0.00, 3.48 + DPAD, 1.25]},
    # CN, capacitor side: through the capacitor ring gap -> both S/D pads.
    {"layer": bg.METAL1, "rect_um": [3.02 + DPAD, 0.78, DX + 1.22, 1.25]},
    # VB, access ring: band over the access TAP_N pad (which rides the raised
    # ring via Y_TAP_ACC).
    {"layer": bg.METAL1, "rect_um": [0.49, Y_TAP_ACC - 0.21, 3.48 + DPAD,
                                     Y_TAP_ACC + 0.21]},
    # VB riser between the stacked bands.
    {"layer": bg.METAL1, "rect_um": [3.05 + DPAD, Y_TAP_ACC + 0.09,
                                     3.45 + DPAD, Y_TAP_CAP - 0.09]},
    # VB, capacitor ring: band over the capacitor TAP_N pad (clear of the
    # gate pad in y by 0.90 um).
    {"layer": bg.METAL1, "rect_um": [0.49, Y_TAP_CAP - 0.21, DX + 0.79, Y_TAP_CAP + 0.21]},
    # MOS-capacitor marker (MOS_CAP_MK) over the cap block's COMP island
    # (DX,0)-(DX+1.28,2.0) -- the island is as tall as the device width, so it
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
        ring_padding_acc_um=RING_PAD_ACC,
        straps=STRAPS,
        origins_um={"acc": {"x": 0, "y": 0}, "cap": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=[{"net": "BL", "block": "acc", "port": "U0_S"},
              {"net": "WL", "block": "acc", "port": "U0_G"},
              {"net": "PL", "block": "cap", "port": "U0_G"},
              {"net": "VB", "block": "cap", "port": "TAP_N"}],
    )
