#!/usr/bin/env python3
"""Deterministic generator for the candidate-1 bitcell (spec/cell-candidates.md).

Cell: thin-oxide NMOS capacitor (antifuse element, netlist `cap_nmos_03v3`)
in series with a 6.0 V NMOS access device (`nfet_06v0`). Drawn with `klt gen`
(mos_array primitives + tap ring), `klt draw` (Metal1 and Metal2 straps) and
`klt gen-compose` (explicit placement), for gf180mcu.

Geometry point: Minimum x Minimum of spec/split-axis-plan.md sections 2-3
(capacitor geometry = Minimum, access sizing = Minimum; grid point
`C1_Amin_Gmin`). The capacitor is drawn at the ratified Minimum level,
W = 1.0 um at L = 0.28 um (`spec/capacitor-geometry-decision.md`: the PDK
runset's 1 um `DF.1c` "Min. COMP Width for MOSCAP" floor). The access width
stays at the 0.42 um generator floor (a contact-fit floor above the process
minimum; the schematic's default wacc is 0.30 um -- the access axis is out
of scope here, see README).

  access : nfet_06v0 (Dualgate marker), W = 0.42 um, L = 0.70 um
  cap    : thin-oxide NMOS gate over COMP, W = 1.0 um, L = 0.28 um,
           gate on CN, source and drain shorted on PL

Metal2 joins the access source to the capacitor gate (CN). Metal1 joins the
two capacitor diffusion pads on PL and straps both well taps on VB.

Ports (text labels on Metal1): BL (access drain), WL (access gate),
PL (cap diffusion), VB (both tap rings, strapped).

Point table, shared constants, strap derivation and flow call:
layout/candidate1_points.py. This file names only this point. (This cell's
directory keeps its un-suffixed name `cell_candidate1/` -- its reports are
cited by `signoff/manifest.json` and its GDS sha256 is what its own `--check`
pins.)

Usage:  generate.py            write cell_candidate1.gds next to this script
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
    pts.main(HERE, "Amin_Gmin")
