"""Point table and shared geometry for the candidate-1 split-axis generators.

The three split cells (`cell_candidate1_A2x_G2x`, `cell_candidate1_A2x_Gmin`,
`cell_candidate1_Amin_G2x`) draw the same cell as `layout/cell_candidate1/` --
thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`) in series
with a 6.0 V NMOS access device (`nfet_06v0`) -- at different points of the
split-axis grid (spec/cell-candidates.md, spec/split-axis-plan.md sections
2-3). Each point's `(CELL, W_CAP, W_ACC)` triple is written exactly once, in
`POINTS`; the per-point `generate.py` files name one entry and defer here for
every shared constant, derivation and strap shape. The klt flow (`klt gen`
mos_array + tap ring, `klt draw` straps and marker, `klt gen-compose` explicit
placement, gf180mcu) and the `--check` byte-compare run in `bitcell_gen.py`,
unchanged; pin klt with `uvx --from klayout-tools==0.8.0`.

Ports (text labels on Metal1): BL (access drain), WL (access gate),
PL (cap gate/plate), VB (both tap rings, strapped).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

# Shared constants, identical at every ratified split point.
L_CAP = 0.28       # um, thin-oxide minimum drawn length (held on the 2x level,
                   # which doubles capacitor area exactly: 0.84 x 0.28 = 0.2352
                   # um2 against 0.42 x 0.28 = 0.1176 um2). Width is the axis
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
                   # block extents alone. Both Minimum levels are the generator
                   # width floor (W >= 0.42 um, a contact-fit floor above the
                   # process minimum), not the process minimum -- see
                   # layout/README.md.

# Measured TAP_N pad centre per device width (klt gen mos_array 0.8.0): y =
# 2.70 um at W = 0.42 um, y = 3.12 um at W = 0.84 um. The same pair recurs in
# cell_candidate3_Amin_G2x/generate.py at a different flavor, DX and L_ACC, so
# this is a tap-ring property, not a per-cell accident. A plain dict on
# purpose: spec/split-axis-plan.md sections 2-3 ratify exactly two levels per
# axis, so these entries cover the whole ratified grid, and an unmeasured
# width raises KeyError at generation time instead of extrapolating a
# tap-ring coordinate nobody verified.
Y_TAP_BY_W = {0.42: 2.70, 0.84: 3.12}

# CN band, one derivation valid at every point. CN leaves each tap ring
# through that ring's metal1 exit gap (ring_gap_um 1.0, ring_gap_offset_um
# -0.7); the gap is centred on the device, so it rises with the width:
# measured GAP_E/GAP_W span y -0.28..0.72 at W = 0.42 um and y -0.07..0.93 at
# W = 0.84 um. CN crosses BOTH rings' gaps, so it must sit in their
# intersection with >= 0.23 um (metal1.space.1) clearance from each gap edge:
# insetting the measured spans gives -0.05..0.49 at a Minimum ring and
# 0.16..0.70 at a doubled ring, and 0.18..0.48 lies in both.
# cell_candidate1/'s band (0.06..0.36) leaves only 0.13 um below a doubled
# block's gap and does fail metal1.space.1 here, so it is raised.
CN_Y0, CN_Y1 = 0.18, 0.48

# The candidate-1 split-axis points: key -> (cell directory, W_CAP um,
# W_ACC um). This table is the only place a point's constants are written;
# each cell_candidate1_*/generate.py names exactly one entry.
POINTS = {
    "A2x_G2x":  ("cell_candidate1_A2x_G2x",  0.84, 0.84),
    "A2x_Gmin": ("cell_candidate1_A2x_Gmin", 0.42, 0.84),
    "Amin_G2x": ("cell_candidate1_Amin_G2x", 0.84, 0.42),
}

PINS = [
    {"net": "BL", "block": "acc", "port": "U0_D"},
    {"net": "WL", "block": "acc", "port": "U0_G"},
    {"net": "PL", "block": "cap", "port": "U0_G"},
    {"net": "VB", "block": "cap", "port": "TAP_N"},
]


def straps(w_cap, w_acc, cn_shapes=None):
    """Strap/marker rectangle list for a point, as `klt draw` expects it.

    Pad coverage (both grid cases): the S/D pads the CN band crosses are as
    tall as their device width, so at a doubled device the band lies inside
    that pad (y 0..0.84), and at a Minimum device it overhangs the pad's top
    edge (y 0.42) by 0.06 um -- metal over field, DRC clean. Either way the
    band overlaps every pad it crosses by >= 0.24 um in y. The MOS-capacitor
    marker (MOS_CAP_MK) covers the cap block's COMP island
    (0,0)-(1.28, W_CAP), which is as tall as the device width; the 0.1 um
    margin matches cell_candidate1/. The marker is what makes the deck read
    the thin-oxide gate as cap_nmos_03v3 instead of an nfet, and is not drawn
    over the access device.

    `cn_shapes` replaces the default single CN rect (a list of rect_um
    4-lists on METAL1) for a point that needs a doglegged strap; one
    rectangle covers every point in POINTS today, but a net is not limited
    to one rect.
    """
    y_tap_cap = Y_TAP_BY_W[w_cap]
    y_tap_acc = Y_TAP_BY_W[w_acc]
    # One VB rect tall enough to overlap both TAP_N pads (each 0.42 um
    # across). With both blocks doubled (A2x_G2x) this is cell_candidate1/'s
    # flat rect shifted +0.42 um in y; at the mixed points the two pads sit
    # at different heights and it is one band spanning both.
    vb_y0 = min(y_tap_cap, y_tap_acc) - 0.21
    vb_y1 = max(y_tap_cap, y_tap_acc) + 0.21
    if cn_shapes is None:
        cn_shapes = [[0.06, CN_Y0, DX + 0.36, CN_Y1]]
    shapes = [{"layer": bg.METAL1, "rect_um": r} for r in cn_shapes]
    shapes += [
        # VB: tie both tap rings together along the north side.
        {"layer": bg.METAL1, "rect_um": [0.64, vb_y0, DX + 0.85, vb_y1]},
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
        straps=straps(w_cap, w_acc),
        origins_um={"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=PINS,
    )
