v {xschem version=3.4.7 file_version=1.2


* gf180-antifuse: READ LEG (spec/architecture.md 1.2 and 4).
*
*   BL <- MSW (nfet_06v0 isolation) <- MCL (nfet_03v3 clamp) <- MPI (diode pfet)
*
* Current-threshold sense: the bit-line current flows through the diode
* connected MPI and is mirrored by MPO into node SENSE, where it meets I_ref
* (IREF pin, mirrored by MNI/MNO). SENSE goes high when I_bitline > I_ref, and
* two inverters give RDATA = 1 (programmed) / 0 (unprogrammed or unselected).
* MCL fixes the bit-line read voltage at about VCLAMP - Vgs: a source-follower
* clamp, so the read voltage varies with PVT and that variation is part of the
* margin table, not hidden. MSW is a thick-oxide (6 V) device so the OFF leg
* can sit on a bit line at VPP during a program pulse. RON (interlock) is its
* gate: READ_EN & ~PROG_EN. I_ref is bench-supplied (no on-die reference
* generation is designed here).
}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} -100 -420 0 0 {name=p0 lab=PROG_EN}
C {devices/ipin.sym} -100 -380 0 0 {name=p1 lab=READ_EN}
C {devices/ipin.sym} -100 -340 0 0 {name=p2 lab=VCLAMP}
C {devices/ipin.sym} -100 -300 0 0 {name=p3 lab=IREF}
C {devices/iopin.sym} -100 -260 0 0 {name=p4 lab=VDD}
C {devices/iopin.sym} -100 -220 0 0 {name=p5 lab=VSS}
C {devices/iopin.sym} 1100 -420 0 0 {name=p6 lab=BL}
C {devices/opin.sym} 1100 -380 0 0 {name=p7 lab=SENSE}
C {devices/opin.sym} 1100 -340 0 0 {name=p8 lab=RDATA}
C {leg_interlock.sym} 100 -250 0 0 {name=Xil lg=lg wn=wnl wp=wpl}
C {devices/lab_pin.sym} 20 -370 0 0 {name=l10 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 20 -340 0 0 {name=l11 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 20 -310 0 0 {name=l12 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 20 -280 0 0 {name=l13 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 180 -370 0 1 {name=l14 sig_type=std_logic lab=PON_nc}
C {devices/lab_pin.sym} 180 -340 0 1 {name=l15 sig_type=std_logic lab=RON}
C {symbols/nfet_06v0.sym} 400 0 0 0 {name=MSW
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
model=nfet_06v0
spiceprefix=X
}
C {devices/lab_pin.sym} 420 -30 0 1 {name=l17 sig_type=std_logic lab=CS}
C {devices/lab_pin.sym} 380 0 0 0 {name=l18 sig_type=std_logic lab=RON}
C {devices/lab_pin.sym} 420 30 0 1 {name=l19 sig_type=std_logic lab=BL}
C {devices/lab_pin.sym} 420 0 0 1 {name=l20 sig_type=std_logic lab=VSS}
C {symbols/nfet_03v3.sym} 400 -140 0 0 {name=MCL
L=lcl
W=wcl
nf=1
m=1
ad="'int((nf+1)/2) * wcl/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wcl/nf + 0.18u)'"
as="'int((nf+2)/2) * wcl/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wcl/nf + 0.18u)'"
nrd="'0.18u / wcl'" nrs="'0.18u / wcl'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 420 -170 0 1 {name=l22 sig_type=std_logic lab=PIN}
C {devices/lab_pin.sym} 380 -140 0 0 {name=l23 sig_type=std_logic lab=VCLAMP}
C {devices/lab_pin.sym} 420 -110 0 1 {name=l24 sig_type=std_logic lab=CS}
C {devices/lab_pin.sym} 420 -140 0 1 {name=l25 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 600 -140 0 0 {name=MPI
L=lmp
W=wmp
nf=1
m=1
ad="'int((nf+1)/2) * wmp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wmp/nf + 0.18u)'"
as="'int((nf+2)/2) * wmp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wmp/nf + 0.18u)'"
nrd="'0.18u / wmp'" nrs="'0.18u / wmp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 620 -110 0 1 {name=l27 sig_type=std_logic lab=PIN}
C {devices/lab_pin.sym} 580 -140 0 0 {name=l28 sig_type=std_logic lab=PIN}
C {devices/lab_pin.sym} 620 -170 0 1 {name=l29 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 620 -140 0 1 {name=l30 sig_type=std_logic lab=VDD}
C {symbols/pfet_03v3.sym} 760 -140 0 0 {name=MPO
L=lmp
W=wmp
nf=1
m=1
ad="'int((nf+1)/2) * wmp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wmp/nf + 0.18u)'"
as="'int((nf+2)/2) * wmp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wmp/nf + 0.18u)'"
nrd="'0.18u / wmp'" nrs="'0.18u / wmp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 780 -110 0 1 {name=l32 sig_type=std_logic lab=SENSE}
C {devices/lab_pin.sym} 740 -140 0 0 {name=l33 sig_type=std_logic lab=PIN}
C {devices/lab_pin.sym} 780 -170 0 1 {name=l34 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 780 -140 0 1 {name=l35 sig_type=std_logic lab=VDD}
C {symbols/nfet_03v3.sym} 600 140 0 0 {name=MNI
L=lmn
W=wmn
nf=1
m=1
ad="'int((nf+1)/2) * wmn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wmn/nf + 0.18u)'"
as="'int((nf+2)/2) * wmn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wmn/nf + 0.18u)'"
nrd="'0.18u / wmn'" nrs="'0.18u / wmn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 620 110 0 1 {name=l37 sig_type=std_logic lab=IREF}
C {devices/lab_pin.sym} 580 140 0 0 {name=l38 sig_type=std_logic lab=IREF}
C {devices/lab_pin.sym} 620 170 0 1 {name=l39 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 620 140 0 1 {name=l40 sig_type=std_logic lab=VSS}
C {symbols/nfet_03v3.sym} 760 140 0 0 {name=MNO
L=lmn
W=wmn
nf=1
m=1
ad="'int((nf+1)/2) * wmn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wmn/nf + 0.18u)'"
as="'int((nf+2)/2) * wmn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wmn/nf + 0.18u)'"
nrd="'0.18u / wmn'" nrs="'0.18u / wmn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 780 110 0 1 {name=l42 sig_type=std_logic lab=SENSE}
C {devices/lab_pin.sym} 740 140 0 0 {name=l43 sig_type=std_logic lab=IREF}
C {devices/lab_pin.sym} 780 170 0 1 {name=l44 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 780 140 0 1 {name=l45 sig_type=std_logic lab=VSS}
C {symbols/nfet_03v3.sym} 900 70 0 0 {name=MN6
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
spiceprefix=X
}
C {devices/lab_pin.sym} 920 40 0 1 {name=l47 sig_type=std_logic lab=SB}
C {devices/lab_pin.sym} 880 70 0 0 {name=l48 sig_type=std_logic lab=SENSE}
C {devices/lab_pin.sym} 920 100 0 1 {name=l49 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 920 70 0 1 {name=l50 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 900 -70 0 0 {name=MP6
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
spiceprefix=X
}
C {devices/lab_pin.sym} 920 -40 0 1 {name=l52 sig_type=std_logic lab=SB}
C {devices/lab_pin.sym} 880 -70 0 0 {name=l53 sig_type=std_logic lab=SENSE}
C {devices/lab_pin.sym} 920 -100 0 1 {name=l54 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 920 -70 0 1 {name=l55 sig_type=std_logic lab=VDD}
C {symbols/nfet_03v3.sym} 1000 70 0 0 {name=MN7
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
spiceprefix=X
}
C {devices/lab_pin.sym} 1020 40 0 1 {name=l57 sig_type=std_logic lab=RDATA}
C {devices/lab_pin.sym} 980 70 0 0 {name=l58 sig_type=std_logic lab=SB}
C {devices/lab_pin.sym} 1020 100 0 1 {name=l59 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 1020 70 0 1 {name=l60 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 1000 -70 0 0 {name=MP7
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
spiceprefix=X
}
C {devices/lab_pin.sym} 1020 -40 0 1 {name=l62 sig_type=std_logic lab=RDATA}
C {devices/lab_pin.sym} 980 -70 0 0 {name=l63 sig_type=std_logic lab=SB}
C {devices/lab_pin.sym} 1020 -100 0 1 {name=l64 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 1020 -70 0 1 {name=l65 sig_type=std_logic lab=VDD}
T {READ LEG: BL - MSW - MCL(clamp) - MPI/MPO (mirror) vs IREF mirror -> SENSE -> RDATA} -100 -500 0 0 0.3 0.3 {}
