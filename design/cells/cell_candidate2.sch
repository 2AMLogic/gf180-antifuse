v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: Candidate 2 (high-voltage regime) antifuse cell.
* Ratified in spec/cell-candidates.md: cap_nmos_06v0 (6.0 V thick oxide,
* toxe = 15.2 nm) as the programmable element, in series with
* nfet_10v0_asym (10 V LDNMOS, SM-BB-000149 HV process module) as the
* access/isolation device.
*
* DELIBERATE SOURCE/DRAIN ASSIGNMENT - see the on-canvas note and
* design/README.md. nfet_10v0_asym is drain-extended: its d terminal, and
* only its d terminal, carries the drift resistance rdrift in the PDK
* subcircuit (smbb000149.ngspice). d is therefore the high-voltage-blocking
* terminal and is wired to BL, the program-supply/array side. s is wired to
* the cell node CN.
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
C {symbols/nfet_10v0_asym.sym} 280 -450 0 0 {name=M1
L=lacc
W=wacc
nf=1
m=1
ad="'wacc * 1.48u'"
pd="'2 * (wacc + 1.48u)'"
as="'wacc * 0.48u'"
ps="'2 * (wacc + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=nfet_10v0_asym
spiceprefix=X
}
C {symbols/cap_nmos_06v0.sym} 300 -350 0 0 {name=C1
W=wcap
L=lcap
model=cap_nmos_06v0
spiceprefix=X
m=1}
T {Candidate 2 - high-voltage cell: cap_nmos_06v0 + nfet_10v0_asym} 130 -620 0 0 0.5 0.5 {}
T {DELIBERATE SOURCE/DRAIN ASSIGNMENT - do not treat this device as a
symmetric pass gate. spec/cell-candidates.md flags nfet_10v0_asym as an
asymmetric drain-extended LDNMOS whose source and drain are not
interchangeable, and requires the assignment to be made explicitly.

Assignment made here: d -> BL, s -> CN.

Basis, read out of the PDK subcircuit in
libs.tech/ngspice/smbb000149.ngspice:
  - the drift resistance rdrift is in series with the d terminal only;
    the s terminal connects straight to the BSIM4 core device;
  - the default diffusion parasitics are asymmetric in the same
    direction: ad = W*1.48u on the drain side vs as = W*0.48u on the
    source side.
The drain is therefore the terminal built to stand off the elevated
voltage, so it faces BL - the bit line that sits at the program-supply
rail during a program pulse, and that an UNSELECTED cell in the same
column must also block. The source faces CN, the cell node, which is the
lower-potential side of the access device throughout a program pulse
(before breakdown CN charges toward BL through M1; after breakdown CN is
pulled down toward PL through the filament).} 480 -620 0 0 0.3 0.3 {}
T {BL: bit line. Program-voltage and sense node - array side.
WL: word line. Access-device gate.
CN: cell node. Capacitor gate plate, isolated from BL by M1.
PL: plate line. Capacitor body/well plate, program return.
VB: access-device bulk tie.} 480 -230 0 0 0.3 0.3 {}
