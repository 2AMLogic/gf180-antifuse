#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell (spec/cell-candidates.md).

Cell: thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`)
in series with a 6.0 V NMOS access device (`nfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring), `klt draw` (two metal1 straps) and
`klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum of spec/split-axis-plan.md sections 2-3
(capacitor geometry = Minimum, access sizing = Minimum), clamped to the
smallest width `klt gen mos_array` will draw (W >= 0.42 um, a generator-side
contact-fit floor; the schematic's default wacc is 0.30 um -- see README).

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um
  cap    : thin-oxide NMOS gate over COMP, W = 0.42 um, L = 0.28 um,
           source and drain shorted (moscap) on net CN

Ports (text labels on Metal1): BL (access drain), WL (access gate),
PL (cap gate/plate), VB (both tap rings, strapped).

Usage:  generate.py            write cell_candidate1.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GDS_NAME = "cell_candidate1.gds"
PDK = "gf180mcuA"
CELL = "cell_candidate1"

W_MIN = 0.42       # um, generator floor (== Minimum level for both devices)
L_CAP = 0.28       # um, thin-oxide minimum drawn length
L_ACC = 0.70       # um, 6 V device minimum drawn length (schematic lacc)
DX = 4.2           # um, access-block x offset (keeps Pplus spacing >= 0.4)
GAP = {"ring_gap_um": 1.0, "ring_gap_offset_um": -0.7}
METAL1 = [34, 0]
# Ports are located in each block's local frame (reported by klt gen); the
# straps below are in the composed frame: cap block at (0,0), access at (DX,0).
STRAPS = {"shapes": [
    # CN: access source pad -> cap drain pad -> cap source pad (metal1)
    {"layer": METAL1, "rect_um": [0.06, 0.06, DX + 0.36, 0.36]},
    # VB: tie both tap rings together along the north side
    {"layer": METAL1, "rect_um": [0.64, 2.49, DX + 0.85, 2.91]},
]}


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode not in (0,):
        sys.exit(f"command failed ({r.returncode}): {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


def build(workdir):
    def gen(name, l_um, flavor_extra, gap_side):
        params = {"w_um": W_MIN, "l_um": l_um, "rows": 1, "cols": 1, "dummy": 0,
                  "flavor": "nfet", "gate_contact": True, "add_guard_ring": True,
                  "ring_gap_side": gap_side, **GAP, **flavor_extra}
        out = run(["klt", "gen", "mos_array", "--pdk", PDK, "--params",
                   json.dumps(params), "--cell-name", name,
                   "-o", os.path.join(workdir, name + ".gds"), "--format", "json"])
        with open(os.path.join(workdir, name + ".json"), "w") as fh:
            fh.write(out)

    gen("cap", L_CAP, {}, "E")
    gen("acc", L_ACC, {"voltage_flavor": "medium_voltage"}, "W")
    with open(os.path.join(workdir, "straps_params.json"), "w") as fh:
        json.dump(STRAPS, fh)
    out = run(["klt", "draw", "--params", os.path.join(workdir, "straps_params.json"),
               "--cell-name", "straps", "-o", os.path.join(workdir, "straps.gds"),
               "--format", "json"])
    with open(os.path.join(workdir, "straps.json"), "w") as fh:
        fh.write(out)
    req = {
        "schema": "klt.gen_compose.request/1", "pdk": {"variant": PDK},
        "blocks": [{"id": b, "generator_report": b + ".json"} for b in ("cap", "acc", "straps")],
        "placement": {"strategy": "explicit", "order": ["cap", "acc", "straps"],
                      "origins_um": {"cap": {"x": 0, "y": 0}, "acc": {"x": DX, "y": 0},
                                     "straps": {"x": 0, "y": 0}}},
        "pins": [{"net": "BL", "block": "acc", "port": "U0_D"},
                 {"net": "WL", "block": "acc", "port": "U0_G"},
                 {"net": "PL", "block": "cap", "port": "U0_G"},
                 {"net": "VB", "block": "cap", "port": "TAP_N"}],
        "options": {"cell_name": CELL, "output": os.path.join(workdir, GDS_NAME)},
    }
    rq = os.path.join(workdir, "compose.json")
    with open(rq, "w") as fh:
        json.dump(req, fh)
    run(["klt", "gen-compose", rq, "--format", "json"])
    return os.path.join(workdir, GDS_NAME)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    committed = os.path.join(HERE, GDS_NAME)
    with tempfile.TemporaryDirectory() as tmp:
        new = build(tmp)
        if args.check:
            if not os.path.isfile(committed):
                sys.exit(f"missing {committed}")
            a, b = sha(new), sha(committed)
            if a != b:
                sys.exit(f"DRIFT: regenerated sha256 {a} != committed {b}")
            print(f"OK: {GDS_NAME} sha256 {b}")
        else:
            shutil.copyfile(new, committed)
            print(f"wrote {committed} sha256 {sha(committed)}")


if __name__ == "__main__":
    main()
