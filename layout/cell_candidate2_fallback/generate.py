#!/usr/bin/env python3
"""Deterministic generator for the Run 3 C2-fallback cell (bare capacitor).

Variant: spec/run3-test-chip-floorplan.md "Variant C2-fallback" and
spec/run3-bench-plan.md section 9 -- Candidate 2 with its `nfet_10v0_asym`
access device removed (issue #372: the PDK PCell's 20 native-runset findings
have no waiver path, and the fallback must pass the native runset without any
exception for PCell-internal geometry). The cell is two bare
`cap_nmos_06v0` capacitors, one per ratified capacitor-geometry level
(spec/capacitor-geometry-decision.md, Region II):

  cap_gmin : W = 1.0 um, L = 0.70 um  (Gmin -- the process-minimum legal W/L)
  cap_g2x  : W = 2.0 um, L = 0.70 um  (G2x -- 2x area via W only, L held)

Both blocks are `klt gen mos_array` (nfet, medium_voltage, gate contact, P+
tap ring), called with literal parameters only; no PDK PCell and no access
device exists anywhere in the cell. The only hand-drawn shapes are the
straps, labels and MOS-capacitor markers `klt` has no primitive for
(2AMLogic/klayout-tools#2953), exactly as in the sibling `cell_*`
generators. The committed GDS is reproduced byte-for-byte by this script
under the pinned klt (`uvx --from klayout-tools==0.9.2`).

Wiring (the chip's C2-fallback group in miniature, floorplan pad table):
the capacitors' S and D pads share one net BL (on the chip `BL_C2_Amin` is
shared by the 10 fallback instances); each gate is a private plate
(`PL_GMIN` / `PL_G2X`, per-instance PL pads); both tap rings tie to VB (the
p-substrate tie, `VSS_ANALOG` on the chip, generator placeholder).

The BL strap is metal1 and must leave each block through that block's
tap-ring exit gap (ring_gap_um 1.0, ring_gap_offset_um -0.7). The gaps sit
at different heights because each is centred on its device (measured at
klt 0.9.2, gf180mcuA: y 0.01..1.01 at W = 1.0, y 0.51..1.51 at W = 2.0), so
a single straight band through both gaps would be 0.04 um tall after the
0.23 um metal1.space.1 inset from each gap edge -- below the metal1 width
floor. The strap is therefore doglegged, the same remedy the
capacitor-geometry record measured for the 2x CN strap ("the 2x level's CN
strap is drawn as a doglegged (multi-segment) metal1 shape"): segment A
crosses the Gmin block's east gap inside y 0.26..0.76, the vertical join
sits between the rings -- block pitch DX = 5.0 um leaves 0.84 um between
the ring edges (2.93 to 3.77), enough for the 0.30 um segment (metal1
minimum width 0.23 um, M1.1) plus 0.23 um space to each ring -- and
segment B crosses the G2x block's west gap inside y 0.76..1.26. Each
segment overlaps every pad it connects by >= 0.26 um in y. VB is likewise
two straps joined in the inter-ring channel: the tap pads sit 1 um apart
(y 3.07..3.49 and 4.07..4.49) with the G2x gate pad (top edge y 3.17)
between them, so a single band would short PL_G2X -- found by the first
LVS run and fixed here, not assumed away.

Ports (Metal1 labels): BL (shared capacitor S/D plate), PL_GMIN and PL_G2X
(private plates), VB (both tap rings).

Usage:  generate.py            write cell_candidate2_fallback.gds next to
                               this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==0.9.2 klt` to
pin (put a wrapper for the pinned version on PATH; see layout/README.md).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared helpers (run, sha, PDK, layers)

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = "cell_candidate2_fallback.gds"
CELL = "cell_candidate2_fallback"
W_GMIN = 1.0       # um, Gmin level: DF.1c MOSCAP COMP-width floor
W_G2X = 2.0        # um, G2x level: 2x area via W only
L_CAP = 0.70       # um, 6 V minimum drawn gate length (PL.2_MV)
LABEL_M1 = [34, 10]   # gf180mcu extraction deck reads Metal1 pin labels from 34/10
# Gmin block at the origin (gap east), G2x block at (DX, 0) (gap west).
# Pitch 5.0 um: the sibling cells' 4.2 um pitch leaves only 0.04 um between
# the ring edges, with no room for the vertical dogleg segment the two gap
# heights force; 5.0 um leaves 0.84 um. Both blocks' x extents are identical
# (-1.23..2.93, measured klt 0.9.2) and widths grow in y only.
DX = 5.0
# Measured ring-gap y spans (klt 0.9.2, cap_w probes recorded in the
# docstring) inset by 0.23 um metal1.space.1, then 0.02 um inside that:
#   W=1.0 gap 0.01..1.01 -> window 0.24..0.78 -> strap 0.26..0.76
#   W=2.0 gap 0.51..1.51 -> window 0.74..1.28 -> strap 0.76..1.26
# Measured pad extents: S pad x 0..0.42, D pad x 1.28..1.70, y 0..W; both
# segments overlap their pads by >= 0.26 um in y. Measured tap pads:
# y = 2.28 + W (3.28 and 4.28), 0.42 um across, x 0.64..1.06 within a block.
# BL_JOIN: metal1 minimum width is 0.23 um (M1.1 / curated metal1.width.1;
# measured on the first native run, which flagged the original 0.14 um
# join), so the vertical join is 0.30 um wide, 0.27 um clear of each ring's
# metal1 edge (block bbox edges 2.93 and DX-1.23 = 3.77).
BL_A_Y0, BL_A_Y1 = 0.26, 0.76    # segment A: through the Gmin east gap
BL_B_Y0, BL_B_Y1 = 0.76, 1.26    # segment B: through the G2x west gap
BL_JOIN_X0, BL_JOIN_X1 = 3.20, 3.50  # vertical join between the rings
# VB: the two tap pads sit at different heights (y 3.07..3.49 at W = 1.0,
# y 4.07..4.49 at W = 2.0), and the G2x gate pad (y up to 3.17, measured)
# lies between them, so one straight band covering both pads would also
# short PL_G2X -- the first LVS run found exactly that (PL_G2X|VB merged).
# VB is therefore two straps, one per tap pad, joined by a vertical segment
# in the channel between the rings (same x as the BL join, 2 um above it).
VB1_Y0, VB1_Y1 = 3.07, 3.49      # over the Gmin tap pad
VB2_Y0, VB2_Y1 = 4.07, 4.49      # over the G2x tap pad
VB_JOIN_Y0, VB_JOIN_Y1 = 3.28, 4.28
STRAPS = {
    "shapes": [
        # BL dogleg: segment A (Gmin pads, through the east gap)
        {"layer": bg.METAL1, "rect_um": [0.06, BL_A_Y0, 3.32, BL_A_Y1]},
        # vertical join between the rings
        {"layer": bg.METAL1, "rect_um": [BL_JOIN_X0, BL_A_Y0, BL_JOIN_X1, BL_B_Y1]},
        # segment B (G2x pads, through the west gap), ending on the D pad edge
        {"layer": bg.METAL1, "rect_um": [3.32, BL_B_Y0, DX + 1.70, BL_B_Y1]},
        # VB: tie both tap rings, one strap per tap pad (the G2x gate pad
        # forbids a single band), joined in the inter-ring channel
        {"layer": bg.METAL1, "rect_um": [0.64, VB1_Y0, 3.35, VB1_Y1]},
        {"layer": bg.METAL1, "rect_um": [BL_JOIN_X0, VB_JOIN_Y0, BL_JOIN_X1, VB_JOIN_Y1]},
        {"layer": bg.METAL1, "rect_um": [3.35, VB2_Y0, DX + 1.06, VB2_Y1]},
        # MOS-capacitor markers over each COMP island (island x 0..1.28,
        # y 0..W; 0.1 um margin, as in the sibling cells)
        {"layer": bg.MOS_CAP_MK, "rect_um": [-0.1, -0.1, 1.38, W_GMIN + 0.1]},
        {"layer": bg.MOS_CAP_MK, "rect_um": [DX - 0.1, -0.1, DX + 1.38, W_G2X + 0.1]},
    ],
    "labels": [
        {"layer": LABEL_M1, "text": "BL", "at_um": [1.49, 0.5]},
        {"layer": LABEL_M1, "text": "PL_GMIN", "at_um": [0.85, 1.96]},
        {"layer": LABEL_M1, "text": "PL_G2X", "at_um": [DX + 0.85, 2.96]},
        {"layer": LABEL_M1, "text": "VB", "at_um": [2.0, 3.28]},
    ],
}


def cap_params(w_um, gap_side):
    # Literal parameters only (issue #372 acceptance criterion): the drawing
    # is entirely the PDK/klt generator's; nothing here edits a generated
    # shape. Levels from spec/capacitor-geometry-decision.md Region II.
    return {"w_um": w_um, "l_um": L_CAP, "rows": 1, "cols": 1, "dummy": 0,
            "flavor": "nfet", "voltage_flavor": "medium_voltage",
            "gate_contact": True, "add_guard_ring": True,
            "ring_gap_side": gap_side, **bg.GAP}


def build(workdir):
    def w(name, obj):
        p = os.path.join(workdir, name)
        with open(p, "w") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))
        return p

    blocks = (("cap_gmin", W_GMIN, "E"), ("cap_g2x", W_G2X, "W"))
    for name, width, side in blocks:
        out = bg.run(["klt", "gen", "mos_array", "--pdk", bg.PDK,
                      "--params", json.dumps(cap_params(width, side)),
                      "--cell-name", name,
                      "-o", os.path.join(workdir, name + ".gds"),
                      "--format", "json"])
        w(name + ".json", out)
    sp = w("straps_params.json", STRAPS)
    straps = bg.run(["klt", "draw", "--params", sp, "--cell-name", "straps",
                     "-o", os.path.join(workdir, "straps.gds"), "--format", "json"])
    w("straps.json", straps)
    req = {
        "schema": "klt.gen_compose.request/1", "pdk": {"variant": bg.PDK},
        "blocks": [{"id": b, "generator_report": b + ".json"}
                   for b, _, _ in blocks] + [{"id": "straps", "generator_report": "straps.json"}],
        "placement": {"strategy": "explicit",
                      "order": ["cap_gmin", "cap_g2x", "straps"],
                      "origins_um": {"cap_gmin": {"x": 0, "y": 0},
                                     "cap_g2x": {"x": DX, "y": 0},
                                     "straps": {"x": 0, "y": 0}}},
        "pins": [],
        "options": {"cell_name": CELL, "output": os.path.join(workdir, GDS)},
    }
    bg.run(["klt", "gen-compose", w("compose.json", req), "--format", "json"])
    return os.path.join(workdir, GDS)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    committed = os.path.join(HERE, GDS)
    with tempfile.TemporaryDirectory() as tmp:
        new = build(tmp)
        if args.check:
            if not os.path.isfile(committed):
                sys.exit(f"missing {committed}")
            a, b = bg.sha(new), bg.sha(committed)
            if a != b:
                sys.exit(f"DRIFT: regenerated sha256 {a} != committed {b}")
            print(f"OK: {GDS} sha256 {b}")
        else:
            shutil.copyfile(new, committed)
            print(f"wrote {committed} sha256 {bg.sha(committed)}")
