v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: PROGRAM LEG (spec/architecture.md 1.2 and 2).
*
*   VPP -> high-side switch (pfet_06v0) -> ballast (ppolyf_u_2k_6p0) -> BL
*
* The ballast is the primary, always-present current limit (2): it holds even
* if the switch drive or the WL-bias active limit (the second mechanism, owned
* by the WL level shifter of 1.1, not this leg) misbehaves. Switch drive is a
* cross-coupled pfet_06v0 level shifter referenced to VPP, so the switch is
* driven fully OFF (gate = VPP) and fully ON (gate = 0) from a 3.3 V enable.
* PROG_EN is gated by the local interlock: with READ_EN also high the switch
* stays OFF.
*
* Interface constraint (design/README.md): VPP must idle at or above VDD
* whenever the leg is OFF, otherwise the switch's drain-well junction is
* forward biased by the bit-line read level. Ballast sizing: see README.
* Device voltage tier: 6 V (pfet_06v0 / nfet_06v0). A Candidate 2 (10 V tier)
* variant is NOT captured here.
}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} -100 -340 0 0 {name=p1 lab=PROG_EN}
C {devices/ipin.sym} -100 -300 0 0 {name=p2 lab=READ_EN}
C {devices/iopin.sym} -100 -260 0 0 {name=p3 lab=VDD}
C {devices/iopin.sym} -100 -220 0 0 {name=p4 lab=VSS}
C {devices/iopin.sym} 1000 -340 0 0 {name=p5 lab=BL}
C {devices/iopin.sym} 1000 -300 0 0 {name=p6 lab=VPP}
C {leg_interlock.sym} 100 -250 0 0 {name=Xil lg=lg wn=wnl wp=wpl}
C {devices/lab_pin.sym} 20 -295 0 0 {name=l7 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 20 -265 0 0 {name=l8 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 20 -235 0 0 {name=l9 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 20 -205 0 0 {name=l10 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 180 -265 0 1 {name=l11 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 180 -235 0 1 {name=l12 sig_type=std_logic lab=RON_nc}
C {symbols/nfet_03v3.sym} 300 -80 0 0 {name=MN5
L=lg
W=wnl
nf=1
m=1
ad="'int((nf+1)/2) * wnl/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wnl/nf + 0.18u)'"
as="'int((nf+2)/2) * wnl/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wnl/nf + 0.18u)'"
nrd="'0.18u / wnl'" nrs="'0.18u / wnl'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X}
C {devices/lab_pin.sym} 320 -110 0 1 {name=l13 sig_type=std_logic lab=PONB}
C {devices/lab_pin.sym} 280 -80 0 0 {name=l14 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 320 -50 0 1 {name=l15 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 320 -80 0 1 {name=l16 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 300 -220 0 0 {name=MP5
L=lg
W=wpl
nf=1
m=1
ad="'int((nf+1)/2) * wpl/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wpl/nf + 0.18u)'"
as="'int((nf+2)/2) * wpl/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wpl/nf + 0.18u)'"
nrd="'0.18u / wpl'" nrs="'0.18u / wpl'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X}
C {devices/lab_pin.sym} 320 -190 0 1 {name=l17 sig_type=std_logic lab=PONB}
C {devices/lab_pin.sym} 280 -220 0 0 {name=l18 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 320 -250 0 1 {name=l19 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 320 -220 0 1 {name=l20 sig_type=std_logic lab=VDD}
C {symbols/pfet_06v0.sym} 520 0 0 0 {name=MLSP1
L=llsp
W=wlsp
nf=1
m=1
ad="'int((nf+1)/2) * wlsp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wlsp/nf + 0.18u)'"
as="'int((nf+2)/2) * wlsp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wlsp/nf + 0.18u)'"
nrd="'0.18u / wlsp'" nrs="'0.18u / wlsp'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 540 30 0 1 {name=l21 sig_type=std_logic lab=PG}
C {devices/lab_pin.sym} 500 0 0 0 {name=l22 sig_type=std_logic lab=PGB}
C {devices/lab_pin.sym} 540 -30 0 1 {name=l23 sig_type=std_logic lab=VPP}
C {devices/lab_pin.sym} 540 0 0 1 {name=l24 sig_type=std_logic lab=VPP}
C {symbols/pfet_06v0.sym} 680 0 0 0 {name=MLSP2
L=llsp
W=wlsp
nf=1
m=1
ad="'int((nf+1)/2) * wlsp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wlsp/nf + 0.18u)'"
as="'int((nf+2)/2) * wlsp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wlsp/nf + 0.18u)'"
nrd="'0.18u / wlsp'" nrs="'0.18u / wlsp'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 700 30 0 1 {name=l25 sig_type=std_logic lab=PGB}
C {devices/lab_pin.sym} 660 0 0 0 {name=l26 sig_type=std_logic lab=PG}
C {devices/lab_pin.sym} 700 -30 0 1 {name=l27 sig_type=std_logic lab=VPP}
C {devices/lab_pin.sym} 700 0 0 1 {name=l28 sig_type=std_logic lab=VPP}
C {symbols/nfet_06v0.sym} 520 140 0 0 {name=MLSN1
L=llsn
W=wlsn
nf=1
m=1
ad="'int((nf+1)/2) * wlsn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wlsn/nf + 0.18u)'"
as="'int((nf+2)/2) * wlsn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wlsn/nf + 0.18u)'"
nrd="'0.18u / wlsn'" nrs="'0.18u / wlsn'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 540 110 0 1 {name=l29 sig_type=std_logic lab=PG}
C {devices/lab_pin.sym} 500 140 0 0 {name=l30 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 540 170 0 1 {name=l31 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 540 140 0 1 {name=l32 sig_type=std_logic lab=VSS}
C {symbols/nfet_06v0.sym} 680 140 0 0 {name=MLSN2
L=llsn
W=wlsn
nf=1
m=1
ad="'int((nf+1)/2) * wlsn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wlsn/nf + 0.18u)'"
as="'int((nf+2)/2) * wlsn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wlsn/nf + 0.18u)'"
nrd="'0.18u / wlsn'" nrs="'0.18u / wlsn'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 700 110 0 1 {name=l33 sig_type=std_logic lab=PGB}
C {devices/lab_pin.sym} 660 140 0 0 {name=l34 sig_type=std_logic lab=PONB}
C {devices/lab_pin.sym} 700 170 0 1 {name=l35 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 700 140 0 1 {name=l36 sig_type=std_logic lab=VSS}
C {symbols/pfet_06v0.sym} 880 0 0 0 {name=MSW
L=lsw
W=wsw
nf=1
m=1
ad="'int((nf+1)/2) * wsw/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wsw/nf + 0.18u)'"
as="'int((nf+2)/2) * wsw/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wsw/nf + 0.18u)'"
nrd="'0.18u / wsw'" nrs="'0.18u / wsw'"
sa=0 sb=0 sd=0
model=pfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 900 30 0 1 {name=l37 sig_type=std_logic lab=RB_TOP}
C {devices/lab_pin.sym} 860 0 0 0 {name=l38 sig_type=std_logic lab=PG}
C {devices/lab_pin.sym} 900 -30 0 1 {name=l39 sig_type=std_logic lab=VPP}
C {devices/lab_pin.sym} 900 0 0 1 {name=l40 sig_type=std_logic lab=VPP}
C {symbols/ppolyf_u_2k_6p0.sym} 1060 60 0 0 {name=RB
W=rb_w
L=rb_l
model=ppolyf_u_2k_6p0
spiceprefix=X
m=1}
C {devices/lab_pin.sym} 1060 30 0 0 {name=l41 sig_type=std_logic lab=RB_TOP}
C {devices/lab_pin.sym} 1060 90 0 0 {name=l42 sig_type=std_logic lab=BL}
C {devices/lab_pin.sym} 1040 60 0 0 {name=l43 sig_type=std_logic lab=VSS}
T {PROGRAM LEG: VPP -> MSW (pfet_06v0) -> RB (ppolyf_u_2k_6p0 ballast) -> BL} -100 -440 0 0 0.3 0.3 {}
T {VPP-domain cross-coupled level shifter (drives MSW gate: 0 = on, VPP = off)} 500 -80 0 0 0.25 0.25 {}
