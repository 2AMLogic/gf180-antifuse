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
           capacitor gate (Metal2 over Via1, so the strap crosses the
           PCell's tap ring without touching it)

Geometry: the PCell clamps W up to 4 um (a request for 0.42 um draws the same
cell) and always draws two gate fingers sharing the centre drain, so the access
device is 2 x W = 4 um (8 um total), L = 0.6 um (schematic lacc). The capacitor
is drawn at the ratified Minimum level, W = 1.0 um at L = 0.70 um
(`spec/capacitor-geometry-decision.md`: the PDK runset's 1 um `DF.1c` "Min.
COMP Width for MOSCAP" floor, and the 0.7 um `PL.2_MV` 6 V n-gate minimum the
old 0.56 um length violated), source and drain shorted on PL, with the
MOS-capacitor marker added by hand (no `klt gen` MOS-capacitor marker for a
gate-contacted unit). Both dimensions now clear their native-deck rules; the
remaining native findings on this cell live inside the PDK's own
`nfet_10v0_asym` PCell (`CO.4`/`DF.6_MV`/`PL.4_MV`) and are the operator
ruling's business (#299), not this cell's drawn geometry.

Ports (Metal1 labels): BL (access drain), WL (access gates), PL (capacitor
diffusion), VB (both tap rings strapped). The PCell tap ring is closed, so it has no
`klt` port; the labels are drawn by `klt draw`.

Usage:  generate.py            write cell_candidate2.gds next to this script
        generate.py --check    regenerate to a temp dir and compare with the
                               committed GDS (exit 1 on drift)
Requires `klt` on PATH. Run with `uvx --from klayout-tools==X.Y.Z klt` to pin.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from candidate2_points import main

if __name__ == "__main__":
    main(str(HERE), "Amin_Gmin")
