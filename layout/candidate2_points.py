"""Two-finger GF180 LDNMOS bitcells for the four Region II split points."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitcell_gen as bg  # noqa: E402  shared klt flow + --check (layout/bitcell_gen.py)

POINTS = {
    "Amin_Gmin": ("cell_candidate2", 1.0, 4.0),
    "Amin_G2x": ("cell_candidate2_Amin_G2x", 2.0, 4.0),
    "A2x_Gmin": ("cell_candidate2_A2x_Gmin", 1.0, 8.0),
    "A2x_G2x": ("cell_candidate2_A2x_G2x", 2.0, 8.0),
}
L_ACC = 0.60
L_CAP = 0.70       # um, 6 V n-gate minimum drawn length (PL.2_MV); the drawn
                   # 0.56 um violated it
LABEL_M1 = [34, 10]   # gf180mcu extraction deck reads Metal1 pin labels from 34/10
# Access PCell at the origin, capacitor at (CX, CY). Route CN below the
# assembled VB landing at y = 2.99 and above the PL landing at y = 1.0.
CX, CY = 5.5, 0.79
def straps(w_cap, w_acc):
    # The PCell centers its two fingers at the origin. Its north gate pads
    # rise by half the added finger width. The two source stripes still span y=1.
    rise = (w_acc - 4.0) / 2
    gate = (CX + 0.78, CY + w_cap + 0.96)
    return {
        "shapes": [
            # Both outer source stripes reach the capacitor gate.
            *bg.metal2_route((-1.72, 1.0), (1.72, 1.0)),
            bg.via1(-1.72, 1.0), bg.via1(1.72, 1.0), bg.via1(*gate),
            *bg.metal2_route(gate, (gate[0], 1.85), (1.72, 1.85), (1.72, 1.0)),
            # Short the capacitor's two diffusion pads to the private plate.
            {"layer": bg.METAL1, "rect_um": [CX + 0.06, 0.87, CX + 1.56, 1.13]},
            # WL: join the two access gate pads (Metal1)
            {"layer": bg.METAL1, "rect_um": [-0.4, 2.72 + rise, 0.4, 3.1 + rise]},
            # VB: tie the PCell ring to the capacitor ring (Metal1, clear of the gap).
            # Still lands on the capacitor ring's metal1 W-side band after the
            # growth: the ring's exit gap (0.01..1.01 um at w_cap = 1.0, plus CY)
            # tops out at CY + 1.01 = 1.80 um and the band sits at CY + 2.0..2.42.
            {"layer": bg.METAL1, "rect_um": [2.4, CY + 2.0, CX - 0.9, CY + 2.42]},
            # MOS-capacitor marker over the capacitor COMP island (as tall as
            # w_cap, so the top edge tracks it; 0.1 um margin)
            {"layer": bg.MOS_CAP_MK, "rect_um": [CX - 0.1, CY - 0.1, CX + 1.66, CY + w_cap + 0.1]},
        ],
        "labels": [
            {"layer": LABEL_M1, "text": "BL", "at_um": [0.0, 0.0]},
            {"layer": LABEL_M1, "text": "WL", "at_um": [0.0, 2.9 + rise]},
            {"layer": LABEL_M1, "text": "PL", "at_um": [CX + 0.21, 1.0]},
            {"layer": LABEL_M1, "text": "VB", "at_um": [4.0, CY + 2.2]},
        ],
    }

def build(workdir, cell, w_cap, w_acc):
    acc = bg.run(["klt", "gen", "--pdk", bg.PDK, "--pdk-pcell",
                  "gf180mcu_klayoutapi/nfet_10v0_asym", "--params",
                  json.dumps({"w": w_acc, "l": L_ACC}), "--cell-name", "acc",
                  "-o", os.path.join(workdir, "acc.gds"), "--format", "json"])
    with open(os.path.join(workdir, "acc.json"), "w") as fh:
        fh.write(acc)
    cap_params = {"w_um": w_cap, "l_um": L_CAP, "rows": 1, "cols": 1, "dummy": 0,
                  "flavor": "nfet", "voltage_flavor": "medium_voltage",
                  "gate_contact": True, "add_guard_ring": True,
                  "ring_gap_side": "W", **bg.GAP}
    cap = bg.run(["klt", "gen", "mos_array", "--pdk", bg.PDK, "--params",
                  json.dumps(cap_params), "--cell-name", "cap",
                  "-o", os.path.join(workdir, "cap.gds"), "--format", "json"])
    with open(os.path.join(workdir, "cap.json"), "w") as fh:
        fh.write(cap)
    bg.draw_straps(workdir, straps(w_cap, w_acc))
    return bg.compose(workdir, cell + ".gds", cell, ("acc", "cap", "straps"),
                      {"acc": {"x": 0, "y": 0}, "cap": {"x": CX, "y": CY},
                       "straps": {"x": 0, "y": 0}}, [])


def main(here, point):
    cell, w_cap, w_acc = POINTS[point]
    bg.drive(here, cell + ".gds", lambda workdir: build(workdir, cell, w_cap, w_acc))
