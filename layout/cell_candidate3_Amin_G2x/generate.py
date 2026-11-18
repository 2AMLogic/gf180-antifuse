#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell at access Minimum x
capacitor 2x (spec/cell-candidates.md, spec/split-axis-plan.md section 2).

Same cell as `layout/cell_candidate3/` -- thin-oxide PMOS capacitor (antifuse
element, netlist `cap_pmos_03v3`) in series with a 6.0 V PMOS access device
(`pfet_06v0`) -- drawn at a different point of the split-axis grid. Drawn with
`klt gen` (mos_array primitives + tap ring, flavor pfet), `klt draw` (metal1
straps and the MOS-capacitor marker) and `klt gen-compose` (explicit
placement), for gf180mcu.

Geometry point: access sizing **Minimum**, capacitor geometry **2x** (grid
`C3_Amin_G2x`; the floorplan spends pads L32-L36 on it,
`spec/run3-test-chip-floorplan.md`). The 2x is taken on the capacitor's width
at held drawn length, per the ratified levels
(`spec/capacitor-geometry-decision.md`): W 1.0 -> 2.0 um at L 0.28 um,
exactly doubling the area (2.0 x 0.28 = 0.56 um2 against 1.0 x 0.28 = 0.28
um2). Width is the axis `sim/cell-device-characterization/` already scales
for the G axis (`sizing_multiplier` applied to `wcap`, `lcap` passed
through), so "G2x" means the same thing in `sim/` and in `layout/`. The
Minimum capacitor is the ratified 1 um level (the PDK runset's `DF.1c`
"Min. COMP Width for MOSCAP" floor); the Minimum access width is still the
generator's contact-fit floor (W >= 0.42 um) -- see layout/README.md.

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um   (Minimum)
  cap    : thin-oxide PMOS gate over COMP, W = 2.0 um, L = 0.28 um (2x area),
           source and drain shorted (moscap) on net CN

At W_CAP = 2.0 um the two ring gaps' legal CN windows are disjoint, so CN is
a doglegged three-rect strap, and VB is two stacked bands joined by a riser;
both derivations live in candidate3_points.py.

Terminal assignment (matches design/cells/cell_candidate3.sch): BL is the
access SOURCE, CN is the access DRAIN (mirror of the NMOS candidates). Well
connection: each device sits in its own N-well with an N+ tap ring; the two
tap rings are strapped (VB) so the access well and the capacitor well are one
net. The access block's tap ring is drawn at the raised generator padding
RING_PAD_ACC (acc block only) -- the generator default misses two native-deck
well/Dualgate rules on this pfet + medium-voltage pairing;
candidate3_points.py's RING_PAD_ACC comment has the story. Ports (Metal1
labels): BL, WL, PL (cap gate), VB.

Point table, shared constants, strap derivation and flow call:
layout/candidate3_points.py. This file names only this point.

Usage:  generate.py            write the GDS next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Pin the version named in layout/candidate3_points.py
(a pin bump edits that one place, not this shim).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import candidate3_points as pts  # noqa: E402  point table + shared geometry

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    pts.main(HERE, "Amin_G2x")
