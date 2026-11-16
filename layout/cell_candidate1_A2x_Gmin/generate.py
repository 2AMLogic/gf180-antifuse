#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell at access 2x x
capacitor Minimum (spec/cell-candidates.md, spec/split-axis-plan.md sections
2-3).

Grid point A2x_Gmin: W_CAP = 0.42 um (Minimum), W_ACC = 0.84 um (2x width) --
the CN band lies inside the doubled access pad (y 0..0.84) and overhangs the
Minimum cap pads' top edge (y 0.42) by 0.06 um (metal over field, DRC clean);
the two TAP_N pads sit at different heights, so VB is one band spanning both.

  access : nfet_06v0 (Dualgate marker), W = 0.84 um, L = 0.70 um   (2x width)
  cap    : thin-oxide NMOS gate over COMP, W = 0.42 um, L = 0.28 um (Minimum),
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
    pts.main(HERE, "A2x_Gmin")
