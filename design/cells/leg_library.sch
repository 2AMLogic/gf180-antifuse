v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: netlist driver for the program-leg / read-leg library.
*
* Same purpose as cell_library.sch (see its header): xschem emits parameter
* defaults on a .subckt line only when the block is netlisted as a
* sub-schematic, so this driver instantiates one of each block and, with
* split_files on (design/xschemrc), writes one parameterized netlist per
* block - leg_interlock.spice, program_leg.spice, read_leg.spice. This
* driver's own top-level netlist is discarded.
*
* Regenerate with design/regen-netlists.sh; verify with --check.
}
G {}
K {}
V {}
S {}
E {}
C {leg_interlock.sym} 220 -300 0 0 {name=X1}
C {program_leg.sym} 480 -300 0 0 {name=X2}
C {read_leg.sym} 740 -300 0 0 {name=X3}
T {Netlist driver - not a circuit. See the header comment in this file.} 160 -420 0 0 0.5 0.5 {}
