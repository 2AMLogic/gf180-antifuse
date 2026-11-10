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
           capacitor's S and D (Metal2 over Via1, so the strap crosses the
           PCell's tap ring without touching it)

Geometry: the PCell clamps W up to 4 um (a request for 0.42 um draws the same
cell), so the access device is W = 4 um, L = 0.6 um (schematic lacc). The
capacitor is the generator-minimum W = 0.42 um at the 6 V minimum L = 0.56 um,
source and drain shorted on CN, with the MOS-capacitor marker added by hand
(no `klt gen` MOS-capacitor marker for a gate-contacted unit).

Ports (Metal1 labels): BL (access drain), WL (access gates), PL (capacitor
gate), VB (both tap rings strapped). The PCell tap ring is closed, so it has no
`klt` port; the labels are drawn by `klt draw`.

Usage:  generate.py            write cell_candidate2.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitcell_gen as bg  # noqa: E402  shared helpers (run, sha, layers)

HERE = os.path.dirname(os.path.abspath(__file__))
GDS = "cell_candidate2.gds"
CELL = "cell_candidate2"
W_ACC = 4.0        # um, PCell minimum W (smaller requests are clamped to this)
L_ACC = 0.6        # um, schematic lacc
L_CAP = 0.56       # um, 6 V minimum drawn length
LABEL_M1 = [34, 10]   # gf180mcu extraction deck reads Metal1 pin labels from 34/10
VIA1 = [35, 0]
METAL2 = [36, 0]
# Access PCell at the origin; capacitor block at (CX, CY). CY aligns the
# capacitor S/D pad centres (CY+0.21) with the vias on the PCell source stripes.
CX, CY = 5.5, 0.79
# Source stripes (Metal1) x = +/-[1.53, 1.91]; via centres y = 1.0.
STRAPS = {
    "shapes": [
        # CN: Metal2 bar over both source stripes, the ring, and the cap S/D pads
        {"layer": METAL2, "rect_um": [-1.97, 0.75, CX + 1.62, 1.25]},
        {"layer": VIA1, "rect_um": [-1.85, 0.87, -1.59, 1.13]},
        {"layer": VIA1, "rect_um": [1.59, 0.87, 1.85, 1.13]},
        {"layer": VIA1, "rect_um": [CX + 0.08, CY + 0.08, CX + 0.34, CY + 0.34]},
        {"layer": VIA1, "rect_um": [CX + 1.22, CY + 0.08, CX + 1.48, CY + 0.34]},
        # WL: join the two access gate pads (Metal1)
        {"layer": bg.METAL1, "rect_um": [-0.4, 2.72, 0.4, 3.1]},
        # VB: tie the PCell ring to the capacitor ring (Metal1, clear of the gap)
        {"layer": bg.METAL1, "rect_um": [2.4, CY + 2.0, CX - 0.9, CY + 2.42]},
        # MOS-capacitor marker over the capacitor COMP island
        {"layer": bg.MOS_CAP_MK, "rect_um": [CX - 0.1, CY - 0.1, CX + 1.66, CY + 0.52]},
    ],
    "labels": [
        {"layer": LABEL_M1, "text": "BL", "at_um": [0.0, 0.0]},
        {"layer": LABEL_M1, "text": "WL", "at_um": [0.0, 2.9]},
        {"layer": LABEL_M1, "text": "PL", "at_um": [CX + 0.78, CY + 1.38]},
        {"layer": LABEL_M1, "text": "VB", "at_um": [4.0, CY + 2.2]},
    ],
}


def build(workdir):
    def w(name, obj):
        p = os.path.join(workdir, name)
        with open(p, "w") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))
        return p

    acc = bg.run(["klt", "gen", "--pdk", bg.PDK, "--pdk-pcell",
                  "gf180mcu_klayoutapi/nfet_10v0_asym", "--params",
                  json.dumps({"w": W_ACC, "l": L_ACC}), "--cell-name", "acc",
                  "-o", os.path.join(workdir, "acc.gds"), "--format", "json"])
    w("acc.json", acc)
    cap_params = {"w_um": bg.W_MIN, "l_um": L_CAP, "rows": 1, "cols": 1, "dummy": 0,
                  "flavor": "nfet", "voltage_flavor": "medium_voltage",
                  "gate_contact": True, "add_guard_ring": True,
                  "ring_gap_side": "W", **bg.GAP}
    cap = bg.run(["klt", "gen", "mos_array", "--pdk", bg.PDK, "--params",
                  json.dumps(cap_params), "--cell-name", "cap",
                  "-o", os.path.join(workdir, "cap.gds"), "--format", "json"])
    w("cap.json", cap)
    sp = w("straps_params.json", STRAPS)
    straps = bg.run(["klt", "draw", "--params", sp, "--cell-name", "straps",
                     "-o", os.path.join(workdir, "straps.gds"), "--format", "json"])
    w("straps.json", straps)
    req = {
        "schema": "klt.gen_compose.request/1", "pdk": {"variant": bg.PDK},
        "blocks": [{"id": b, "generator_report": b + ".json"} for b in ("acc", "cap", "straps")],
        "placement": {"strategy": "explicit", "order": ["acc", "cap", "straps"],
                      "origins_um": {"acc": {"x": 0, "y": 0}, "cap": {"x": CX, "y": CY},
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
