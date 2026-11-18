#!/usr/bin/env python3
"""Deterministic generator for the candidate-3 bitcell (spec/cell-candidates.md).

Cell: thin-oxide PMOS capacitor (antifuse element, netlist `cap_pmos_03v3`)
in series with a 6.0 V PMOS access device (`pfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring, flavor pfet), `klt draw` (metal1 straps and
the MOS-capacitor marker) and `klt gen-compose` (explicit placement), for
gf180mcu.

Geometry point: Minimum x Minimum, as for candidate 1 (grid `C3_Amin_Gmin`).
The capacitor is drawn at the ratified Minimum level, W = 1.0 um at L = 0.28 um
(`spec/capacitor-geometry-decision.md`: the PDK runset's 1 um `DF.1c`
"Min. COMP Width for MOSCAP" floor). The access width stays at the 0.42 um
generator floor (a contact-fit floor above the process minimum; the
schematic's default wacc is 0.30 um -- the access axis is out of scope here,
see README).

  access : pfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.55 um (schematic lacc)
  cap    : thin-oxide PMOS gate over COMP, W = 1.0 um, L = 0.28 um,
           source and drain shorted (moscap) on net CN
  The access block's tap ring is drawn at the raised generator padding
  RING_PAD_ACC (1.29 um, acc block only) -- the generator default misses two
  native-deck well/Dualgate rules; candidate3_points.py's RING_PAD_ACC
  comment has the story.

Terminal assignment (matches design/cells/cell_candidate3.sch): BL is the
access SOURCE, CN is the access DRAIN. Well connection: each device sits in
its own N-well with an N+ tap ring; the two tap rings are strapped (VB) so
the access well and the capacitor well are one net. Ports (Metal1 labels):
BL, WL, PL (cap gate), VB.

Point table, shared constants, strap derivation and flow call:
layout/candidate3_points.py. This file names only this point.

Usage:  generate.py            write cell_candidate3.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==0.8.0` to pin.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import candidate3_points as pts  # noqa: E402  point table + shared geometry

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    pts.main(HERE, "Amin_Gmin")
