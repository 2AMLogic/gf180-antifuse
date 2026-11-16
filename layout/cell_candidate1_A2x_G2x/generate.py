#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell at access 2x x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md sections 2-3).

Grid point A2x_G2x: W_CAP = W_ACC = 0.84 um, the 2x level on both axes -- both
blocks doubled, so the CN band lies inside every S/D pad (y 0..0.84) and VB is
cell_candidate1/'s flat rect shifted +0.42 um in y.

  access : nfet_06v0 (Dualgate marker), W = 0.84 um, L = 0.70 um   (2x width)
  cap    : thin-oxide NMOS gate over COMP, W = 0.84 um, L = 0.28 um (2x area),
           source and drain shorted (moscap) on net CN

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
    pts.main(HERE, "A2x_G2x")
