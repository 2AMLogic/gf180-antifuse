#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell at access Minimum x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md sections 2-3).

Grid point Amin_G2x: capacitor W_CAP = 2.0 um -- the ratified 2x-area level
(spec/capacitor-geometry-decision.md: 2x doubles W at held L) -- x access
W_ACC = 0.42 um (Minimum). At W_CAP = 2.0 um the capacitor's metal1 gate pad
sits between the two rings' north bands, so VB is two stacked bands joined by
a riser, and the two ring gaps' legal CN windows are disjoint, so CN is a
doglegged three-rect strap; both derivations live in candidate1_points.py.

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um   (Minimum)
  cap    : thin-oxide NMOS gate over COMP, W = 2.0 um, L = 0.28 um (2x area),
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
