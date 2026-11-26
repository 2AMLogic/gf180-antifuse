#!/usr/bin/env python3
"""Deterministic generator for the candidate-2 bitcell (spec/cell-candidates.md).

Cell: 6.0 V thick-oxide NMOS capacitor (antifuse element, netlist
`cap_nmos_06v0`) in series with the 10 V drain-extended access device
`nfet_10v0_asym` (the PDK's own `gf180mcu_klayoutapi/nfet_10v0_asym` PCell,
instantiated with `klt gen --pdk-pcell`). The capacitor is `klt gen mos_array`
(Dualgate marker), the two blocks are tied with `klt draw` straps and placed
with `klt gen-compose`, for gf180mcu.

Source/drain assignment (deliberate; design/cells/cell_candidate2.sch):
  d -> BL  the PCell's centre COMP stripe (the drift-extended, high-voltage
           terminal, between the two gate fingers)
  s -> CN  the PCell's two outer COMP stripes, strapped together and to the
           capacitor gate (Metal2 over Via1, so the strap crosses the
           PCell's tap ring without touching it)

Geometry: the PCell clamps W up to 4 um (a request for 0.42 um draws the same
cell) and always draws two gate fingers sharing the centre drain, so the access
device is 2 x W = 4 um (8 um total), L = 0.6 um (schematic lacc). The capacitor
is drawn at the ratified Minimum level, W = 1.0 um at L = 0.70 um
(`spec/capacitor-geometry-decision.md`: the PDK runset's 1 um `DF.1c` "Min.
COMP Width for MOSCAP" floor, and the 0.7 um `PL.2_MV` 6 V n-gate minimum the
old 0.56 um length violated), source and drain shorted on PL, with the
MOS-capacitor marker added by hand (no `klt gen` MOS-capacitor marker for a
gate-contacted unit). Both dimensions now clear their native-deck rules; the
remaining native findings on this cell live inside the PDK's own
`nfet_10v0_asym` PCell (`CO.4`/`DF.6_MV`/`PL.4_MV`) and are the operator
ruling's business (#299), not this cell's drawn geometry.

Ports (Metal1 labels): BL (access drain), WL (access gates), PL (capacitor
diffusion), VB (both tap rings strapped). The PCell tap ring is closed, so it has no
`klt` port; the labels are drawn by `klt draw`.

Usage:  generate.py            write cell_candidate2.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = "cell_candidate2.gds"
CELL = "cell_candidate2"
W_ACC = 4.0        # um, PCell minimum W (smaller requests are clamped to this)
L_ACC = 0.6        # um, schematic lacc
W_CAP = 1.0        # um, capacitor width -- the ratified Minimum level (the
                   # DF.1c MOSCAP COMP-width floor;
                   # spec/capacitor-geometry-decision.md). Previously the
                   # generator floor (bg.W_MIN); passed explicitly now.
L_CAP = 0.70       # um, 6 V n-gate minimum drawn length (PL.2_MV); the drawn
                   # 0.56 um violated it
LABEL_M1 = [34, 10]   # gf180mcu extraction deck reads Metal1 pin labels from 34/10
# Access PCell at the origin, capacitor at (CX, CY). Route CN below the
# assembled VB landing at y = 2.99 and above the PL landing at y = 1.0.
CX, CY = 5.5, 0.79
GATE = (CX + 0.78, CY + W_CAP + 0.96)
STRAPS = {
    "shapes": [
        # Both outer source stripes reach the capacitor gate.
        *bg.metal2_route((-1.72, 1.0), (1.72, 1.0)),
        bg.via1(-1.72, 1.0), bg.via1(1.72, 1.0), bg.via1(*GATE),
        *bg.metal2_route(GATE, (GATE[0], 1.85), (1.72, 1.85), (1.72, 1.0)),
        # Short the capacitor's two diffusion pads to the private plate.
        {"layer": bg.METAL1, "rect_um": [CX + 0.06, 0.87, CX + 1.56, 1.13]},
        # WL: join the two access gate pads (Metal1)
        {"layer": bg.METAL1, "rect_um": [-0.4, 2.72, 0.4, 3.1]},
        # VB: tie the PCell ring to the capacitor ring (Metal1, clear of the gap).
        # Still lands on the capacitor ring's metal1 W-side band after the
        # growth: the ring's exit gap (0.01..1.01 um at W_CAP = 1.0, plus CY)
        # tops out at CY + 1.01 = 1.80 um and the band sits at CY + 2.0..2.42.
        {"layer": bg.METAL1, "rect_um": [2.4, CY + 2.0, CX - 0.9, CY + 2.42]},
        # MOS-capacitor marker over the capacitor COMP island (as tall as
        # W_CAP, so the top edge tracks it; 0.1 um margin)
        {"layer": bg.MOS_CAP_MK, "rect_um": [CX - 0.1, CY - 0.1, CX + 1.66, CY + W_CAP + 0.1]},
    ],
    "labels": [
        {"layer": LABEL_M1, "text": "BL", "at_um": [0.0, 0.0]},
        {"layer": LABEL_M1, "text": "WL", "at_um": [0.0, 2.9]},
        {"layer": LABEL_M1, "text": "PL", "at_um": [CX + 0.21, 1.0]},
        {"layer": LABEL_M1, "text": "VB", "at_um": [4.0, CY + 2.2]},
    ],
}


def build(workdir):
    acc = bg.run(["klt", "gen", "--pdk", bg.PDK, "--pdk-pcell",
                  "gf180mcu_klayoutapi/nfet_10v0_asym", "--params",
                  json.dumps({"w": W_ACC, "l": L_ACC}), "--cell-name", "acc",
                  "-o", os.path.join(workdir, "acc.gds"), "--format", "json"])
    with open(os.path.join(workdir, "acc.json"), "w") as fh:
        fh.write(acc)
    cap_params = {"w_um": W_CAP, "l_um": L_CAP, "rows": 1, "cols": 1, "dummy": 0,
                  "flavor": "nfet", "voltage_flavor": "medium_voltage",
                  "gate_contact": True, "add_guard_ring": True,
                  "ring_gap_side": "W", **bg.GAP}
    cap = bg.run(["klt", "gen", "mos_array", "--pdk", bg.PDK, "--params",
                  json.dumps(cap_params), "--cell-name", "cap",
                  "-o", os.path.join(workdir, "cap.gds"), "--format", "json"])
    with open(os.path.join(workdir, "cap.json"), "w") as fh:
        fh.write(cap)
    bg.draw_straps(workdir, STRAPS)
    return bg.compose(workdir, GDS, CELL, ("acc", "cap", "straps"),
                      {"acc": {"x": 0, "y": 0}, "cap": {"x": CX, "y": CY},
                       "straps": {"x": 0, "y": 0}}, [])


if __name__ == "__main__":
    bg.drive(HERE, GDS, build)
