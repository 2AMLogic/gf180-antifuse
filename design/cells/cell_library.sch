v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: netlist driver for the antifuse cell library.
*
* This schematic exists only so that xschem emits each cell as a
* PARAMETERIZED .subckt definition. xschem writes the .subckt parameter
* defaults (wcap / lcap / wacc / lacc, taken from each cell symbol's
* template) only when a cell is netlisted as a sub-schematic - netlisting a
* cell schematic directly at top level emits a bare ".subckt <name> <pins>"
* line with no parameters, which ngspice then rejects when a caller tries to
* override wcap/lcap on the instance line.
*
* With split_files enabled (see design/xschemrc), netlisting THIS schematic
* writes one file per cell - cell_candidate1.spice, cell_candidate2.spice,
* cell_candidate3.spice - which are the committed derived netlists in
* design/netlists/. This driver's own top-level netlist is discarded.
*
* Regenerate with design/regen-netlists.sh; verify reproducibility with
* design/regen-netlists.sh --check.
}
G {}
K {}
V {}
S {}
E {}
C {cell_candidate1.sym} 220 -300 0 0 {name=X1}
C {cell_candidate2.sym} 480 -300 0 0 {name=X2}
C {cell_candidate3.sym} 740 -300 0 0 {name=X3}
T {Netlist driver - not a circuit. See the header comment in this file.} 160 -420 0 0 0.5 0.5 {}
