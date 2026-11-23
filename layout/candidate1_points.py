"""Point table and shared geometry for the candidate-1 split-axis generators.

The four candidate-1 cells (`cell_candidate1`, `cell_candidate1_A2x_G2x`,
`cell_candidate1_A2x_Gmin`, `cell_candidate1_Amin_G2x`) draw the same cell --
thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`) in series
with a 6.0 V NMOS access device (`nfet_06v0`) -- at the four points of the
split-axis grid (spec/cell-candidates.md, spec/split-axis-plan.md sections
2-3). Each point's `(CELL, W_CAP, W_ACC)` triple is written exactly once, in
`POINTS`; the per-point `generate.py` files name one entry and defer here for
every shared constant, derivation and strap shape. The klt flow (`klt gen`
mos_array + tap ring, `klt draw` straps and marker, `klt gen-compose` explicit
placement, gf180mcu) and the `--check` byte-compare run in `bitcell_gen.py`,
unchanged; pin klt with `uvx --from klayout-tools==0.8.0`.

Capacitor widths are the levels ratified in
`spec/capacitor-geometry-decision.md`: Minimum W = 1.0 um (the PDK runset's
`DF.1c` "Min. COMP Width for MOSCAP" floor) and 2x-area W = 2.0 um, both at
the held L = 0.28 um. The access widths keep their section-3 split values;
that axis is not under a MOSCAP rule and is not touched here.

Ports (text labels on Metal1): BL (access drain), WL (access gate),
PL (cap gate/plate), VB (both tap rings, strapped).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

# Shared constants, identical at every ratified split point.
L_CAP = 0.28       # um, thin-oxide minimum drawn length (held on the 2x level,
                   # which doubles capacitor area exactly: 2.0 x 0.28 = 0.56
                   # um2 against 1.0 x 0.28 = 0.28 um2). Width is the axis
                   # sim/cell-device-characterization/ already scales for both
                   # split axes, so "A2x"/"G2x" mean the same thing in sim/ and
                   # in layout/.
L_ACC = 0.70       # um, 6 V device minimum drawn length (schematic lacc)
DX = 4.2           # um, access-block x offset (keeps Pplus spacing >= 0.4).
                   # Composed frame: cap block at (0,0), access at (DX,0).
                   # Doubling a width grows its block in y only and leaves every
                   # x coordinate untouched (measured, klt gen mos_array 0.8.0),
                   # which is why DX carries over from cell_candidate1/ --
                   # confirmed by the cells' DRC reports, not inferred from the
                   # block extents alone. The Minimum access width stays the
                   # generator floor (W >= 0.42 um, a contact-fit floor above
                   # the process minimum); the capacitor widths are the
                   # ratified levels -- see layout/README.md.

# Measured TAP_N pad centre per device width (klt gen mos_array): y = 2.70 um
# at W = 0.42 um, y = 3.12 at 0.84 (committed from the 0.8.0 pass), y = 3.28
# at 1.0 and y = 4.28 at 2.0 (measured the same way at 0.8.0 when the
# capacitor levels moved to the ratified 1.0/2.0 um). The tap ring's metal1
# north band tracks the device width as centre = W + 2.28 um at all four
# widths the grid draws. The same relation recurs in
# layout/candidate3_points.py at a different flavor, DX and L_ACC, so
# this is a tap-ring property, not a per-cell accident. A plain dict on
# purpose: spec/split-axis-plan.md sections 2-3 ratify exactly two levels per
# axis, so these entries cover the whole ratified grid, and an unmeasured
# width raises KeyError at generation time instead of extrapolating a
# tap-ring coordinate nobody verified.
Y_TAP_BY_W = {0.42: 2.70, 0.84: 3.12, 1.0: 3.28, 2.0: 4.28}

# CN leaves each tap ring through that ring's metal1 exit gap (ring_gap_um
# 1.0, ring_gap_offset_um -0.7); the gap is centred on the device, so it rises
# with the width: measured GAP_E/GAP_W spans y -0.28..0.72 at W = 0.42 um,
# -0.07..0.93 at 0.84, 0.01..1.01 at 1.0 and 0.51..1.51 at 2.0 (centre
# W/2 + 0.01 um, 1.0 um tall, at every width; spec/capacitor-geometry-decision.md
# tabulates the 1.0/2.0 runs). CN crosses BOTH rings' gaps, so a single-rect
# CN must sit in the intersection of both spans with >= 0.23 um
# (metal1.space.1) clearance from each edge. At the Minimum capacitor that
# intersection is 0.24..0.49 um (access at 0.42) or 0.24..0.70 um (access at
# 0.84), so one band serves both cap-1.0 points; 0.25..0.48 sits in each with
# >= 0.24 um clearance and is exactly the 0.23 um metal1 minimum WIDTH (M1.1)
# tall -- a thinner band fails M1.1 on its free-standing stretches between
# pads (observed on the first generated cell), and the window has no room
# for a taller one. At the 2x capacitor the inset windows are disjoint
# (cap 0.74..1.28 vs access -0.05..0.49 or 0.16..0.70) -- no single rect
# exists (measured and ratified as a constraint in
# spec/capacitor-geometry-decision.md); those points pass cn_dogleg(w_acc)
# instead. The inter-ring field is wide enough for the dogleg riser: the
# ring METAL1 outer edges are x 2.35 (capacitor) and DX - 1.07 = 3.13
# (access), leaving 0.78 um -- a 0.28 um riser clears both by >= 0.25 um.
# (Metal edges, not the comp/pplus tap-ring extents the ERC well boxes quote:
# the space rule that binds CN is metal1-to-metal1.)
CN_ROW = (0.25, 0.48)

# The candidate-1 split-axis points: key -> (cell directory, W_CAP um,
# W_ACC um). This table is the only place a point's constants are written;
# each cell_candidate1*/generate.py names exactly one entry. (The Minimum
# point's directory keeps its un-suffixed name cell_candidate1/ -- its
# reports are cited by signoff/manifest.json and its GDS sha256 is what its
# own `--check` pins; the grid point is C1_Amin_Gmin.)
# Maintenance: each generate.py docstring restates its point's two widths in
# prose. The GDS `--check` gate compares bytes, so it cannot catch a stale
# docstring; update the shim's docstring whenever a width here changes.
POINTS = {
    "Amin_Gmin": ("cell_candidate1",           1.0, 0.42),
    "A2x_G2x":   ("cell_candidate1_A2x_G2x",   2.0, 0.84),
    "A2x_Gmin":  ("cell_candidate1_A2x_Gmin",  1.0, 0.84),
    "Amin_G2x":  ("cell_candidate1_Amin_G2x",  2.0, 0.42),
}

PINS = [
    {"net": "BL", "block": "acc", "port": "U0_D"},
    {"net": "WL", "block": "acc", "port": "U0_G"},
    {"net": "PL", "block": "cap", "port": "U0_G"},
    {"net": "VB", "block": "cap", "port": "TAP_N"},
]


def cn_dogleg(w_acc):
    """CN strap rects for a cap-2.0 point, as `klt draw` expects them.

    No single rectangle crosses both ring gaps at W_CAP = 2.0 um -- the two
    gap windows are disjoint (see the CN comment above) -- so the strap is a
    doglegged three-rect metal1 shape: a capacitor-side band through the
    capacitor ring's gap, a riser across the inter-ring field, and an
    access-side band through the access ring's gap. Clearances, from the
    measured geometry: the cap row (y 0.78..1.25) clears the capacitor gap
    (0.51..1.51) by >= 0.26 um; the access row clears its gap (spans in the CN
    comment above) by >= 0.27 um and overlaps the access S pad (y 0..w_acc,
    x DX..DX + 0.42); the riser (x 2.60..2.88) clears both ring metal edges
    (2.35 and 3.13) by >= 0.25 um. The unmeasured-width KeyError of
    Y_TAP_BY_W applies here too.
    """
    acc_row = {0.42: (0.00, 0.45), 0.84: (0.20, 0.65)}[w_acc]
    return [
        [0.06, 0.78, 2.88, 1.25],                    # cap pads -> cap ring gap
        [2.60, 0.00, 2.88, 1.25],                    # riser, inter-ring field
        [2.60, acc_row[0], DX + 0.36, acc_row[1]],   # access ring gap -> S pad
    ]


def straps(w_cap, w_acc, cn_shapes=None):
    """Strap/marker rectangle list for a point, as `klt draw` expects it.

    Pad coverage (both grid cases): the S/D pads the CN band crosses are as
    tall as their device width, so at a doubled device the band lies inside
    that pad, and at a Minimum device it may overhang the pad's top edge --
    metal over field, DRC clean. The MOS-capacitor marker (MOS_CAP_MK) covers
    the cap block's COMP island (0,0)-(1.28, W_CAP), which is as tall as the
    device width; the 0.1 um margin matches cell_candidate1/. The marker is
    what makes the deck read the thin-oxide gate as cap_nmos_03v3 instead of
    an nfet, and is not drawn over the access device.

    VB is one flat band (min/max of the two TAP_N centres +/- 0.21) at
    cap-1.0 points, where it clears the capacitor's metal1 gate pad
    (x 0.43..0.85, y W_CAP + 0.75..W_CAP + 1.17) by >= 0.32 um. At cap-2.0
    points that gate pad (y 2.75..3.17) sits BETWEEN the two rings' metal
    north bands (access 2.45..2.91 or 2.87..3.33, capacitor 4.03..4.49), so a
    flat band would sweep through it and short PL to VB; there VB is two
    stacked bands -- one per ring, each over its TAP_N pad -- joined by a
    riser at x 1.10..1.50, right of the gate pad (0.25 um clearance).

    `cn_shapes` replaces the default single CN rect (a list of rect_um
    4-lists on METAL1) for a point that needs a doglegged strap; cap-2.0
    points pass cn_dogleg(w_acc) from main().
    """
    y_tap_cap = Y_TAP_BY_W[w_cap]
    y_tap_acc = Y_TAP_BY_W[w_acc]
    if cn_shapes is None:
        cn_shapes = [[0.06, CN_ROW[0], DX + 0.36, CN_ROW[1]]]
    shapes = [{"layer": bg.METAL1, "rect_um": r} for r in cn_shapes]
    if w_cap == 2.0:
        shapes += [
            # VB, access ring: band over the access TAP_N pad. Its x0 clears
            # the capacitor gate pad by 0.25 um (see the docstring).
            {"layer": bg.METAL1, "rect_um": [1.10, y_tap_acc - 0.21,
                                             DX + 0.85, y_tap_acc + 0.21]},
            # VB riser between the two stacked bands, right of the gate pad.
            {"layer": bg.METAL1, "rect_um": [1.10, y_tap_acc + 0.09,
                                             1.50, y_tap_cap - 0.09]},
            # VB, capacitor ring: band over the capacitor TAP_N pad, clear of
            # the gate pad in y (>= 0.90 um below it).
            {"layer": bg.METAL1, "rect_um": [0.64, y_tap_cap - 0.21,
                                             DX + 0.85, y_tap_cap + 0.21]},
        ]
    else:
        shapes += [
            # VB: tie both tap rings together along the north side. One band
            # tall enough to overlap both TAP_N pads (each 0.42 um across).
            {"layer": bg.METAL1, "rect_um": [0.64, min(y_tap_cap, y_tap_acc) - 0.21,
                                             DX + 0.85, max(y_tap_cap, y_tap_acc) + 0.21]},
        ]
    shapes += [
        # MOS_CAP_MK over the cap block's COMP island; grows with W_CAP.
        {"layer": bg.MOS_CAP_MK, "rect_um": [-0.1, -0.1, 1.38, w_cap + 0.1]},
    ]
    return {"shapes": shapes}


def main(here, point):
    """Run the klt flow for one POINTS entry named by a per-point generate.py.

    `here` is the calling cell directory; the CLI (write vs `--check`) and
    the byte-compare live in bitcell_gen.main.
    """
    cell, w_cap, w_acc = POINTS[point]
    bg.main(
        here, gds_name=cell + ".gds", cell=cell,
        flavor="nfet", w_cap_um=w_cap, l_cap_um=L_CAP, w_acc_um=w_acc,
        l_acc=L_ACC, cap_gap_side="E", acc_gap_side="W",
        straps=straps(w_cap, w_acc,
                      cn_shapes=cn_dogleg(w_acc) if w_cap == 2.0 else None),
        origins_um={"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=PINS,
    )
