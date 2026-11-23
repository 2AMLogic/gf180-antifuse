"""Point table and shared geometry for the candidate-3 split-axis generators.

The two split cells (`cell_candidate3`, `cell_candidate3_Amin_G2x`) draw the
same cell -- thin-oxide PMOS capacitor (antifuse element, netlist
`cap_pmos_03v3`) in series with a 6.0 V PMOS access device (`pfet_06v0`) --
at two points of the split-axis grid (spec/cell-candidates.md,
spec/split-axis-plan.md section 2). Both points hold the access width at the
generator floor, so a point's `(CELL, W_CAP)` pair is written exactly once,
in `POINTS`; the per-point `generate.py` files name one entry and defer here
for every shared constant, derivation and strap shape. The klt flow (`klt
gen` mos_array + tap ring, `klt draw` straps and marker, `klt gen-compose`
explicit placement, gf180mcu) and the `--check` byte-compare run in
`bitcell_gen.py`, unchanged; pin klt with `uvx --from klayout-tools==0.8.0`.

Capacitor widths are the levels ratified in
`spec/capacitor-geometry-decision.md`: Minimum W = 1.0 um (the PDK runset's
`DF.1c` "Min. COMP Width for MOSCAP" floor) and 2x-area W = 2.0 um, both at
the held L = 0.28 um; 2x doubles the area exactly (2.0 x 0.28 = 0.56 um2
against 1.0 x 0.28 = 0.28 um2). The access axis is not touched here.

Unlike candidate 1 (layout/candidate1_points.py), the access block's tap ring
is drawn at the raised generator padding `RING_PAD_ACC` (acc block only):
this pfet + medium_voltage pairing misses two native-deck well/Dualgate rules
at the generator default, and the padding raises the acc ring (and its TAP_N
pad) by `DPAD` on all four sides -- hence `DX`, `Y_TAP_ACC` and the VB flat
band's min edge all track `DPAD`, and the strap shapes split by W_CAP
(single-band vs doglegged CN, flat vs stacked VB).

Ports (text labels on Metal1): BL (access source), WL (access gate),
PL (cap gate/plate), VB (both tap rings, strapped).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

# Shared constants, identical at every ratified split point.
L_ACC = 0.55       # um, 6 V device drawn length (schematic lacc)
RING_PAD_ACC = 1.29  # um, acc-block generator ring_padding_um. Both points
                     # pair pfet with medium_voltage exactly the same way, so
                     # the generator default 0.5 draws the same defective acc
                     # block: N-well 0.15 um inside the N+ tap ring (native
                     # DF.4d_MV wants 0.16 overlap) and a Dualgate marker
                     # missing COMP enclosure (DV.6, 0.24 um) -- both
                     # generator-owned (#297, upstream
                     # 2AMLogic/klayout-tools#6503). 1.29 is the smallest
                     # padding that clears both on the COMPOSED cell,
                     # bisected in 0.01 um steps at
                     # DX = 4.8 + (RING_PAD_ACC - 0.5) (native rule counts,
                     # klt drc --engine klayout, klayout-tools 0.9.2):
                     # 0.5 -> DF.4d_MV x5 + DV.6 x1 (the committed pre-fix
                     # state); 1.0 -> DF.4d_MV x9 + DV.6 x1 + DV.7 x1 (worse
                     # -- the counts are non-monotonic in padding:
                     # DF.4d_MV 5 -> 9 -> 0 across 0.5/1.0/1.05); 1.05-1.28
                     # -> both clear but DV.3 x5 appears ("Min. Dualgate to
                     # COMP space [unrelated]: 0.24 um" -- the raised ring's
                     # N+ escapes the core-anchored Dualgate marker; the
                     # window spans the whole 1.05-1.28 range); 1.29 -> clean
                     # of all three; 1.28, one step below, still reports
                     # DV.3 x5 (minimality evidence); 1.30-1.40 stay clean,
                     # so 1.29 is the floor, not a window edge. The cap block
                     # keeps the default: it draws no Dualgate marker and its
                     # well overlap is legal. The generator response is the
                     # one filed upstream (public tracker, generic
                     # description): 2AMLogic/klayout-tools#6503; the
                     # per-cell story is in layout/README.md.
DPAD = RING_PAD_ACC - 0.5  # um, how far the raised acc ring moves out on all
                           # four sides (measured: acc-block bbox
                           # (-1.23,-1.23)-(2.78,3.07) at 0.5 ->
                           # (-2.02,-2.02)-(3.57,3.86) at 1.29, klt gen
                           # mos_array 0.8.0; TAP_N centre 2.70 -> 3.49,
                           # U0_S/D/G untouched -- the acc block is
                           # parameter-identical at both points, so #297's
                           # block-level measurements carry over).
DX = 4.8 + DPAD  # um, cap-block x offset. Grows with the acc ring so the
                 # proven 0.79 um ring-to-ring gap is kept (4.8 at the
                 # default padding; DX = 4.2, a 0.19 um gap, violated
                 # nwell.space.1 historically -- measured on cell_candidate3/,
                 # whose pre-#297 literal DX = 5.59 is this same expression
                 # evaluated at RING_PAD_ACC = 1.29). The access block sits
                 # at (0,0), the cap block at (DX,0). Access S (BL) is at
                 # x=0.21 and D (CN) at x=1.07; cap S/D at DX+0.21 / DX+1.07.
                 # Ring gaps face each other.

# Measured capacitor-block TAP_N pad centre per device width (klt gen
# mos_array): the centre is W + 2.28 um at both widths the grid draws (3.28
# at the Minimum 1.0, 4.28 at the 2x 2.0; the same relation is tabulated in
# layout/candidate1_points.py -- a tap-ring property, not a per-cell
# accident). Plain dict on purpose: spec/split-axis-plan.md section 2
# ratifies exactly two capacitor levels, so these entries cover the whole
# ratified grid, and an unmeasured width raises KeyError at generation time
# instead of extrapolating a tap-ring coordinate nobody verified.
Y_TAP_CAP_BY_W = {1.0: 3.28, 2.0: 4.28}

# Access-block TAP_N pad centre: 2.70 at W_ACC = bg.W_MIN and the default
# padding, + DPAD with the raised ring (measured, klt gen mos_array 0.8.0).
# Both points keep the access at the generator floor, so one constant serves
# the whole grid.
Y_TAP_ACC = 2.70 + DPAD

# CN (access drain -> capacitor shorted S/D, metal1) leaves each tap ring
# through that ring's metal1 exit gap (ring_gap_um 1.0, ring_gap_offset_um
# -0.7). The gap is centred on the device, so it rises with the width:
# measured GAP_E/GAP_W spans y -0.28..0.72 at W = 0.42 um (access, E side),
# 0.01..1.01 at W_CAP = 1.0 and 0.51..1.51 at W_CAP = 2.0 um (capacitor, W
# side) -- centre W/2 + 0.01 um at every width, 1.0 um tall, and
# padding-independent in y (the gap follows the pads, not the ring). With the
# 0.23 um (metal1.space.1) clearance required from every edge, the common
# window at the Minimum point (access W = 0.42, cap W_CAP = 1.0) is
# 0.24..0.49 -- 0.25..0.48 sits inside it with >= 0.24 um clearance and is
# exactly the 0.23 um metal1 minimum WIDTH (M1.1) tall -- a thinner band
# fails M1.1 on its free-standing stretches between pads (observed on the
# first generated cell), and the window has no room for a taller one (the
# same derivation as layout/candidate1_points.py). The band overlaps both
# S/D pads (each as tall as its device width). At the 2x capacitor the legal
# windows are DISJOINT (access -0.05..0.49 vs capacitor 0.74..1.28) -- no
# single-rect CN exists (the same measured constraint as the candidate-1 G2x
# cells; spec/capacitor-geometry-decision.md) and the strap becomes a
# doglegged three-rect shape: an access-side band through the access ring's
# gap, a riser across the inter-ring field, and a capacitor-side band
# through the capacitor ring's gap. Binding metal edges there (measured from
# the generated blocks): the access ring's metal1 outer edge sits at
# x 2.77 + DPAD (2.77 at the default padding, + DPAD with the raised ring)
# and the capacitor ring's metal1 outer edge at DX - 1.07 = 3.73 + DPAD, so
# the field stays 0.96 um wide (DX tracks DPAD) and the riser
# (x 3.02 + DPAD .. 3.48 + DPAD) clears both by >= 0.25 um at every padding.
# (Metal edges, not the comp/pplus tap-ring extents the ERC well boxes quote:
# the space rule that binds CN is metal1-to-metal1.)
CN_BAND_Y = (0.25, 0.48)  # the Minimum point's single band, y span


def cn_dogleg():
    """CN strap rects for the 2x point, as `klt draw` expects them.

    The two ring gaps' legal CN windows are disjoint at W_CAP = 2.0 um (see
    the CN comment above), so the strap is a doglegged three-rect metal1
    shape: an access-side band from the access D pad through the access
    ring's gap into the inter-ring field, a riser across that field, and a
    capacitor-side band through the capacitor ring's gap over both S/D pads.
    The access row (y 0.0..0.45) overlaps the access D pad at x 1.13..1.55,
    y 0..0.42, measured off the committed GDS (the BL/U0_S pad is x 0..0.42;
    the 0.86..1.28 range in pre-#400 comments was the capacitor block's
    second S/D pad column, not the access device's). Both candidate-3
    points keep W_ACC = bg.W_MIN, so the rows are constants.
    """
    return [
        [0.92, 0.00, 3.48 + DPAD, 0.45],         # access D pad -> acc ring gap
        [3.02 + DPAD, 0.00, 3.48 + DPAD, 1.25],  # riser, inter-ring field
        [3.02 + DPAD, 0.78, DX + 1.22, 1.25],    # acc ring gap -> both S/D pads
    ]


def straps(w_cap):
    """Strap/marker rectangle list for a point, as `klt draw` expects it.

    Pad coverage (both grid cases): the S/D pads the CN band crosses are as
    tall as their device width, so at a doubled device the band lies inside
    that pad, and at a Minimum device it may overhang the pad's top edge --
    metal over field, DRC clean.

    VB is one flat band (min/max of the two TAP_N centres +/- 0.21) at the
    Minimum capacitor, where it clears the capacitor's metal1 gate pad
    (x DX + 0.43..DX + 0.85, y W_CAP + 0.75..W_CAP + 1.17 = 1.75..2.17) by
    >= 1.1 um. At the 2x capacitor the same gate pad (y 2.75..3.17, measured
    on the committed GDS) sits BELOW both rings' metal north bands (access
    y 2.49 + DPAD .. 2.91 + DPAD = 3.28..3.70 over the raised ring, measured
    off the committed GDS, capacitor y 4.07..4.49): its top edge is 0.11 um
    below the raised access band's bottom edge. The flat shape fails there
    on spacing, not a short: a flat band covering both TAP_N pads at the
    same +/- 0.21 overlap every strap here uses would have its bottom edge
    at y 3.28 (the access pad centre 3.49 - 0.21), yet it must still reach
    the capacitor TAP_N pad across the gate pad's x column (both sit at
    x DX + 0.43..DX + 0.85), which puts metal1 0.11 um from the gate pad --
    under the 0.23 um metal1.space.1 minimum. Measured on the scratch
    single-flat-band variant (y 3.28..4.49): exactly one metal1.space.1
    finding, bbox (5.818,3.170)-(6.440,3.280) um (klt drc --deck gf180mcu;
    the committed GDS is clean on the same rule). (Older revisions of this
    rationale -- here and in layout/README.md -- said the pad sat BETWEEN
    the north bands and that a flat band would short PL to VB; that reading
    predates #389's ring raise, which moved the access band clear above the
    pad, and is stale -- the re-measurement landed as #400, which also
    corrected the README bullet.) So there VB is two
    stacked bands -- one per ring, each over its TAP_N pad -- joined by a
    riser at x 3.05 + DPAD .. 3.45 + DPAD, left of the capacitor ring's
    metal edge and clear of the gate pad and both CN rows.
    """
    y_tap_cap = Y_TAP_CAP_BY_W[w_cap]
    shapes = []
    if w_cap == 2.0:
        shapes += [{"layer": bg.METAL1, "rect_um": r} for r in cn_dogleg()]
        shapes += [
            # VB, access ring: band over the access TAP_N pad (which rides
            # the raised ring via Y_TAP_ACC).
            {"layer": bg.METAL1, "rect_um": [0.49, Y_TAP_ACC - 0.21,
                                             3.48 + DPAD, Y_TAP_ACC + 0.21]},
            # VB riser between the stacked bands.
            {"layer": bg.METAL1, "rect_um": [3.05 + DPAD, Y_TAP_ACC + 0.09,
                                             3.45 + DPAD, y_tap_cap - 0.09]},
            # VB, capacitor ring: band over the capacitor TAP_N pad (clear
            # of the gate pad in y by 0.90 um).
            {"layer": bg.METAL1, "rect_um": [0.49, y_tap_cap - 0.21,
                                             DX + 0.79, y_tap_cap + 0.21]},
        ]
    else:
        shapes += [
            # CN: access drain pad -> cap source pad -> cap drain pad
            # (metal1); one band through both tap rings' exit gaps (see the
            # CN comment above).
            {"layer": bg.METAL1,
             "rect_um": [0.92, CN_BAND_Y[0], DX + 1.22, CN_BAND_Y[1]]},
            # VB: tie both tap rings together along the north side. The
            # TAP_N pad centre rises with the width (centre = W + 2.28 um,
            # measured), so the band spans both pads -- min/max +/- 0.21 --
            # and tracks the widths (access at bg.W_MIN, capacitor at
            # w_cap) instead of restating them as literals. RING_PAD_ACC
            # raises the access ring (and its pad) by DPAD, so the min edge
            # tracks it too; the band would otherwise narrow below the
            # 0.23 um metal1 minimum width (M1.1) as the min edge climbs
            # toward the fixed capacitor side, so the max edge keeps the
            # band at least 0.23 um tall (measured M1.1 at 1.3 um padding
            # without this floor).
            {"layer": bg.METAL1,
             "rect_um": [0.49, bg.W_MIN + 2.28 + DPAD - 0.21,
                         DX + 0.79,
                         max(w_cap + 2.28 + 0.21,
                             bg.W_MIN + 2.28 + DPAD - 0.21 + 0.23)]},
        ]
    shapes += [
        # MOS-capacitor marker (MOS_CAP_MK) over the cap block's COMP island
        # (DX,0)-(DX+1.28,w_cap) -- the island is as tall as the device
        # width, so the marker grows with W_CAP, keeping the 0.1 um margin.
        # This is what makes the deck read the thin-oxide gate as
        # cap_pmos_03v3 instead of a pfet. Not drawn over the access device.
        {"layer": bg.MOS_CAP_MK, "rect_um": [DX - 0.1, -0.1, DX + 1.38,
                                             w_cap + 0.1]},
    ]
    return {"shapes": shapes}


# The candidate-3 split-axis points: key -> (cell directory, W_CAP um). This
# table is the only place a point's constants are written; each
# cell_candidate3*/generate.py names exactly one entry. (The Minimum point's
# directory keeps its un-suffixed name cell_candidate3/ -- its reports are
# cited by layout/README.md and its GDS sha256 is what its own `--check`
# pins; the grid point is C3_Amin_Gmin.)
# Maintenance: each generate.py docstring restates its point's width in
# prose. The GDS `--check` gate compares bytes, so it cannot catch a stale
# docstring; update the shim's docstring whenever a width here changes.
POINTS = {
    "Amin_Gmin": ("cell_candidate3",          1.0),
    "Amin_G2x":  ("cell_candidate3_Amin_G2x", 2.0),
}

PINS = [
    {"net": "BL", "block": "acc", "port": "U0_S"},
    {"net": "WL", "block": "acc", "port": "U0_G"},
    {"net": "PL", "block": "cap", "port": "U0_G"},
    {"net": "VB", "block": "cap", "port": "TAP_N"},
]


def main(here, point):
    """Run the klt flow for one POINTS entry named by a per-point generate.py.

    `here` is the calling cell directory; the CLI (write vs `--check`) and
    the byte-compare live in bitcell_gen.main.
    """
    cell, w_cap = POINTS[point]
    bg.main(
        here, gds_name=cell + ".gds", cell=cell,
        flavor="pfet", w_cap_um=w_cap, l_cap_um=bg.L_CAP, w_acc_um=bg.W_MIN,
        l_acc=L_ACC, cap_gap_side="W", acc_gap_side="E",
        ring_padding_acc_um=RING_PAD_ACC,
        straps=straps(w_cap),
        origins_um={"acc": {"x": 0, "y": 0}, "cap": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=PINS,
    )
