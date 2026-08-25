v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: Candidate 1 (baseline) antifuse cell.
* Ratified in spec/cell-candidates.md: cap_nmos_03v3 (3.3 V thin oxide,
* toxe = 8 nm) as the programmable element, in series with nfet_06v0
* (6.0 V thick oxide) as the access/isolation device.
*
* Capacitor geometry is exposed as the subcircuit parameters wcap / lcap,
* access-device geometry as wacc / lacc. The defaults carried on
* cell_candidate1.sym are the PDK symbol template defaults, NOT an assertion
* of process-minimum geometry - see design/README.md.
}
G {}
K {}
V {}
S {}
E {}
N 300 -540 300 -480 {lab=BL}
N 200 -450 260 -450 {lab=WL}
N 300 -450 400 -450 {lab=VB}
N 300 -420 300 -400 {lab=CN}
N 300 -400 300 -380 {lab=CN}
N 300 -320 300 -260 {lab=PL}
C {devices/iopin.sym} 300 -540 3 0 {name=p1 lab=BL}
C {devices/iopin.sym} 200 -450 2 0 {name=p2 lab=WL}
C {devices/iopin.sym} 300 -260 1 0 {name=p3 lab=PL}
C {devices/iopin.sym} 400 -450 0 0 {name=p4 lab=VB}
C {devices/lab_pin.sym} 300 -400 0 1 {name=l1 sig_type=std_logic lab=CN}
C {symbols/nfet_06v0.sym} 280 -450 0 0 {name=M1
L=lacc
W=wacc
nf=1
m=1
ad="'int((nf+1)/2) * wacc/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wacc/nf + 0.18u)'"
as="'int((nf+2)/2) * wacc/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wacc/nf + 0.18u)'"
nrd="'0.18u / wacc'" nrs="'0.18u / wacc'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X
}
C {symbols/cap_nmos_03v3.sym} 300 -350 0 0 {name=C1
W=wcap
L=lcap
model=cap_nmos_03v3
spiceprefix=X
m=1}
T {Candidate 1 - baseline cell: cap_nmos_03v3 + nfet_06v0} 160 -620 0 0 0.5 0.5 {}
T {Access device terminal assignment:
nfet_06v0 is a symmetric-drain/source thick-oxide logic device
- spec/cell-candidates.md - so D/S here is a drawing convention,
not an electrical constraint. Convention used across all three
candidates: the array/program-supply side terminal is the one that
sits at the higher potential during a program pulse (drain for an
NMOS access device, source for a PMOS one).} 480 -560 0 0 0.3 0.3 {}
T {BL: bit line. Program-voltage and sense node - array side.
WL: word line. Access-device gate.
CN: cell node. Capacitor gate plate, isolated from BL by M1.
PL: plate line. Capacitor body/well plate, program return.
VB: access-device bulk tie.} 480 -380 0 0 0.3 0.3 {}
