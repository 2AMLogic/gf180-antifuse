#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell at access 2x x
capacitor Minimum (spec/cell-candidates.md, spec/split-axis-plan.md sections
2-3).

Grid point A2x_Gmin: capacitor W_CAP = 1.0 um (the ratified Minimum level,
spec/capacitor-geometry-decision.md: the 1 um DF.1c MOSCAP COMP-width floor)
x access W_ACC = 0.84 um (the section-3 2x width). CN crosses the rings on Metal2.
VB is one band spanning both tap-ring pads; derivations in
candidate1_points.py.

  access : nfet_06v0 (Dualgate marker), W = 0.84 um, L = 0.70 um   (2x width)
  cap    : thin-oxide NMOS gate over COMP, W = 1.0 um, L = 0.28 um (Minimum),
           gate on CN, source and drain shorted on PL

Point table, shared constants, strap derivation and flow call:
layout/candidate1_points.py. This file names only this point.

Usage:  generate.py            write the GDS next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==0.8.0` to pin.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import candidate1_points as pts  # noqa: E402  point table + shared geometry

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    pts.main(HERE, "A2x_Gmin")
