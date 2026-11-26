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
PL (shorted capacitor diffusion pads), VB (both tap rings, strapped).
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
    {"net": "PL", "block": "cap", "port": "U0_S"},
    {"net": "VB", "block": "cap", "port": "TAP_N"},
]


def straps(w_cap, w_acc):
    """Route CN on Metal2, PL across the diffusion pads and VB over both taps."""
    y_tap_cap = Y_TAP_BY_W[w_cap]
    y_tap_acc = Y_TAP_BY_W[w_acc]
    # The jog clears the assembled WL via ladder at every access width.
    shapes = bg.signed_cap_straps(0, w_cap, (DX + 0.21, w_acc / 2), 3.95)
    if w_cap == 2.0:
        shapes += [
            # VB, access ring: band over the access TAP_N pad. Its x0 clears
            # the capacitor gate pad by 0.25 um.
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
        straps=straps(w_cap, w_acc),
        origins_um={"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                    "straps": {"x": 0, "y": 0}},
        pins=PINS,
    )
