v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: Candidate 3 (polarity variant) antifuse cell.
* Ratified in spec/cell-candidates.md: cap_pmos_03v3 (3.3 V thin oxide,
* PMOS polarity counterpart to Candidate 1) as the programmable element, in
* series with pfet_06v0 (6.0 V thick oxide) as the access/isolation device.
*
* C1 is placed rotated 180 degrees so that its gate plate faces CN and its
* body/well plate faces PL, matching the Candidate 1 and 2 topology - the
* PDK cap_pmos_03v3 symbol draws its gate pin on the opposite side from
* cap_nmos_03v3 / cap_nmos_06v0.
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
C {symbols/pfet_06v0.sym} 280 -450 0 0 {name=M1
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
model=pfet_06v0
spiceprefix=X
}
C {symbols/cap_pmos_03v3.sym} 300 -350 2 0 {name=C1
W=wcap
L=lcap
model=cap_pmos_03v3
spiceprefix=X
m=1}
T {Candidate 3 - polarity variant: cap_pmos_03v3 + pfet_06v0} 150 -620 0 0 0.5 0.5 {}
T {Access device terminal assignment:
pfet_06v0 is a symmetric-drain/source thick-oxide logic device
- spec/cell-candidates.md - so D/S here is a drawing convention,
not an electrical constraint. Same convention as Candidates 1 and 2:
the array/program-supply side terminal is the one at the higher
potential during a program pulse. For a PMOS that is the SOURCE, so
BL wires to s and CN wires to d - the mirror image of the NMOS
candidates, which is why the PDK pfet_06v0 symbol draws s on top.

VB is the n-well tie and must be held at the most positive potential
the cell sees; which array rail that is, is an array-level decision
deferred with the rest of the array.} 480 -600 0 0 0.3 0.3 {}
T {BL: bit line. Program-voltage and sense node - array side.
WL: word line. Access-device gate.
CN: cell node. Capacitor gate plate, isolated from BL by M1.
PL: plate line. Capacitor body/well plate, program return.
VB: access-device bulk tie - n-well.} 480 -340 0 0 0.3 0.3 {}
