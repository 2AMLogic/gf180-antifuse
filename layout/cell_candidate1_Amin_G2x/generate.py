#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell at access Minimum x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md sections 2-3).

Grid point Amin_G2x: W_CAP = 0.84 um (2x area), W_ACC = 0.42 um (Minimum) --
the CN band lies inside the doubled cap pads (y 0..0.84) and overhangs the
Minimum access pad's top edge (y 0.42) by 0.06 um (metal over field, DRC
clean); the two TAP_N pads sit at different heights, so VB is one band
spanning both.

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um   (Minimum)
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
    pts.main(HERE, "Amin_G2x")
