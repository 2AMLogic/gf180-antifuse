v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: level shifter (spec/architecture.md 1.1).
*
* Cross-coupled PMOS latch with NMOS pull-downs, referenced to VDDH (the
* region's programming-voltage rail during a program operation, a fixed
* logic-compatible bias during read). A thin-oxide (3.3 V) inverter makes the
* complement of the logic-domain select IN from VDDL, so the digital partition
* supplies one single-ended one-hot select line per row / column.
*
* Both latch outputs are actively driven at all times once the rails are up
* (spec/architecture.md 3 item 1: no decoder output may float). OUT follows
* IN; OUTB is its complement.
*
* Transistor widths are PLACEHOLDERS to be sized against the worst-case
* corner; nothing in this file claims a sized design.
*
* Device family: nfet_10v0_asym / pfet_10v0_asym (10 V tier, Candidate 2 region).
* DELIBERATE d/s ASSIGNMENT, as for the Candidate 2 cell: the drift-extended
* drain faces the high-swing node - the pull-down's drain is the latch output,
* the pull-up's drain is the latch output, sources go to VSS / VDDH.
* spec/architecture.md 1.1 names the 6 V devices 'for the 6 V tier'; using the
* asymmetric 10 V pair for the 10 V tier is this repo's reading of that, not
* separate ratified text.
}
G {}
K {}
V {}
S {}
E {}
C {symbols/nfet_03v3.sym} 0 0 0 0 {name=M1
L=0.28u
W=2u
nf=1
m=1
ad="'int((nf+1)/2) * 2u/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (2u/nf + 0.18u)'"
as="'int((nf+2)/2) * 2u/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (2u/nf + 0.18u)'"
nrd="'0.18u / 2u'" nrs="'0.18u / 2u'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {devices/lab_pin.sym} 20 -30 0 0 {name=l1 sig_type=std_logic lab=INB}
C {devices/lab_pin.sym} -20 0 0 0 {name=l2 sig_type=std_logic lab=IN}
C {devices/lab_pin.sym} 20 30 0 0 {name=l3 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 20 0 0 0 {name=l4 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 0 -120 0 0 {name=M2
L=0.28u
W=4u
nf=1
m=1
ad="'int((nf+1)/2) * 4u/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (4u/nf + 0.18u)'"
as="'int((nf+2)/2) * 4u/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (4u/nf + 0.18u)'"
nrd="'0.18u / 4u'" nrs="'0.18u / 4u'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X}
C {devices/lab_pin.sym} 20 -90 0 0 {name=l5 sig_type=std_logic lab=INB}
C {devices/lab_pin.sym} -20 -120 0 0 {name=l6 sig_type=std_logic lab=IN}
C {devices/lab_pin.sym} 20 -150 0 0 {name=l7 sig_type=std_logic lab=VDDL}
C {devices/lab_pin.sym} 20 -120 0 0 {name=l8 sig_type=std_logic lab=VDDL}
C {symbols/nfet_10v0_asym.sym} 300 0 0 0 {name=M3
L=lpdn
W=wpdn
nf=1
m=1
ad="'wpdn * 1.48u'"
pd="'2 * (wpdn + 1.48u)'"
as="'wpdn * 0.48u'"
ps="'2 * (wpdn + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=nfet_10v0_asym
spiceprefix=X}
C {devices/lab_pin.sym} 320 -30 0 0 {name=l9 sig_type=std_logic lab=OUTB}
C {devices/lab_pin.sym} 280 0 0 0 {name=l10 sig_type=std_logic lab=IN}
C {devices/lab_pin.sym} 320 30 0 0 {name=l11 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 320 0 0 0 {name=l12 sig_type=std_logic lab=VSS}
C {symbols/nfet_10v0_asym.sym} 600 0 0 0 {name=M4
L=lpdn
W=wpdn
nf=1
m=1
ad="'wpdn * 1.48u'"
pd="'2 * (wpdn + 1.48u)'"
as="'wpdn * 0.48u'"
ps="'2 * (wpdn + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=nfet_10v0_asym
spiceprefix=X}
C {devices/lab_pin.sym} 620 -30 0 0 {name=l13 sig_type=std_logic lab=OUT}
C {devices/lab_pin.sym} 580 0 0 0 {name=l14 sig_type=std_logic lab=INB}
C {devices/lab_pin.sym} 620 30 0 0 {name=l15 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 620 0 0 0 {name=l16 sig_type=std_logic lab=VSS}
C {symbols/pfet_10v0_asym.sym} 300 -140 0 0 {name=M5
L=lpup
W=wpup
nf=1
m=1
ad="'wpup * 1.78u'"
pd="'2 * (wpup + 1.78u)'"
as="'wpup * 0.48u'"
ps="'2 * (wpup + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=pfet_10v0_asym
spiceprefix=X}
C {devices/lab_pin.sym} 320 -110 0 0 {name=l17 sig_type=std_logic lab=OUT}
C {devices/lab_pin.sym} 280 -140 0 0 {name=l18 sig_type=std_logic lab=OUTB}
C {devices/lab_pin.sym} 320 -170 0 0 {name=l19 sig_type=std_logic lab=VDDH}
C {devices/lab_pin.sym} 320 -140 0 0 {name=l20 sig_type=std_logic lab=VDDH}
C {symbols/pfet_10v0_asym.sym} 600 -140 0 0 {name=M6
L=lpup
W=wpup
nf=1
m=1
ad="'wpup * 1.78u'"
pd="'2 * (wpup + 1.78u)'"
as="'wpup * 0.48u'"
ps="'2 * (wpup + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=pfet_10v0_asym
spiceprefix=X}
C {devices/lab_pin.sym} 620 -110 0 0 {name=l21 sig_type=std_logic lab=OUTB}
C {devices/lab_pin.sym} 580 -140 0 0 {name=l22 sig_type=std_logic lab=OUT}
C {devices/lab_pin.sym} 620 -170 0 0 {name=l23 sig_type=std_logic lab=VDDH}
C {devices/lab_pin.sym} 620 -140 0 0 {name=l24 sig_type=std_logic lab=VDDH}
C {devices/ipin.sym} -200 -240 0 0 {name=p25 lab=IN}
C {devices/ipin.sym} -200 -200 0 0 {name=p26 lab=VDDL}
C {devices/ipin.sym} -200 -160 0 0 {name=p27 lab=VSS}
C {devices/opin.sym} -200 -120 0 0 {name=p28 lab=OUT}
C {devices/opin.sym} -200 -80 0 0 {name=p29 lab=OUTB}
C {devices/ipin.sym} -200 -40 0 0 {name=p30 lab=VDDH}
T {Level shifter, 10 V asymmetric tier} -200 -300 0 0 0.5 0.5 {}
