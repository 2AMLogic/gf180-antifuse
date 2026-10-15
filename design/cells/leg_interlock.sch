v {xschem version=3.4.7 file_version=1.2


* gf180-antifuse: PROG_EN / READ_EN mutual-exclusion gating (logic domain).
*
* PON = PROG_EN AND NOT READ_EN   (program leg permitted)
* RON = READ_EN AND NOT PROG_EN   (read leg permitted)
*
* PON and RON can never both be 1, and both are 0 when PROG_EN = READ_EN = 1.
* spec/architecture.md 1.2 requires the interlock upstream
* (READ_EN = NOT(PROG_EN OR PROG_ARM)); this block is the SECOND, local line
* of defence inside each leg, so a fault that asserts both enables upstream
* still leaves both legs OFF at the bit line. Static CMOS from the 3.3 V
* thin-oxide family, sized by the subckt parameters lg / wn / wp.
}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} -100 -300 0 0 {name=p0 lab=PROG_EN}
C {devices/ipin.sym} -100 -260 0 0 {name=p1 lab=READ_EN}
C {devices/iopin.sym} -100 -220 0 0 {name=p2 lab=VDD}
C {devices/iopin.sym} -100 -180 0 0 {name=p3 lab=VSS}
C {devices/opin.sym} 900 -300 0 0 {name=p4 lab=PON}
C {devices/opin.sym} 900 -260 0 0 {name=p5 lab=RON}
C {symbols/nfet_03v3.sym} 0 70 0 0 {name=MN1
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 20 40 0 1 {name=l7 sig_type=std_logic lab=PENB}
C {devices/lab_pin.sym} -20 70 0 0 {name=l8 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 20 100 0 1 {name=l9 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 20 70 0 1 {name=l10 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 0 -70 0 0 {name=MP1
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 20 -40 0 1 {name=l12 sig_type=std_logic lab=PENB}
C {devices/lab_pin.sym} -20 -70 0 0 {name=l13 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 20 -100 0 1 {name=l14 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 20 -70 0 1 {name=l15 sig_type=std_logic lab=VDD}
C {symbols/nfet_03v3.sym} 160 70 0 0 {name=MN2
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 180 40 0 1 {name=l17 sig_type=std_logic lab=RENB}
C {devices/lab_pin.sym} 140 70 0 0 {name=l18 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 180 100 0 1 {name=l19 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 180 70 0 1 {name=l20 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 160 -70 0 0 {name=MP2
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 180 -40 0 1 {name=l22 sig_type=std_logic lab=RENB}
C {devices/lab_pin.sym} 140 -70 0 0 {name=l23 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 180 -100 0 1 {name=l24 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 180 -70 0 1 {name=l25 sig_type=std_logic lab=VDD}
C {symbols/pfet_03v3.sym} 400 -100 0 0 {name=MP3a
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 420 -70 0 1 {name=l27 sig_type=std_logic lab=3_mid}
C {devices/lab_pin.sym} 380 -100 0 0 {name=l28 sig_type=std_logic lab=PENB}
C {devices/lab_pin.sym} 420 -130 0 1 {name=l29 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 420 -100 0 1 {name=l30 sig_type=std_logic lab=VDD}
C {symbols/pfet_03v3.sym} 400 0 0 0 {name=MP3b
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 420 30 0 1 {name=l32 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 380 0 0 0 {name=l33 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 420 -30 0 1 {name=l34 sig_type=std_logic lab=3_mid}
C {devices/lab_pin.sym} 420 0 0 1 {name=l35 sig_type=std_logic lab=VDD}
C {symbols/nfet_03v3.sym} 520 70 0 0 {name=MN3a
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 540 40 0 1 {name=l37 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 500 70 0 0 {name=l38 sig_type=std_logic lab=PENB}
C {devices/lab_pin.sym} 540 100 0 1 {name=l39 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 540 70 0 1 {name=l40 sig_type=std_logic lab=VSS}
C {symbols/nfet_03v3.sym} 640 70 0 0 {name=MN3b
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 660 40 0 1 {name=l42 sig_type=std_logic lab=PON}
C {devices/lab_pin.sym} 620 70 0 0 {name=l43 sig_type=std_logic lab=READ_EN}
C {devices/lab_pin.sym} 660 100 0 1 {name=l44 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 660 70 0 1 {name=l45 sig_type=std_logic lab=VSS}
C {symbols/pfet_03v3.sym} 400 200 0 0 {name=MP4a
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 420 230 0 1 {name=l47 sig_type=std_logic lab=4_mid}
C {devices/lab_pin.sym} 380 200 0 0 {name=l48 sig_type=std_logic lab=RENB}
C {devices/lab_pin.sym} 420 170 0 1 {name=l49 sig_type=std_logic lab=VDD}
C {devices/lab_pin.sym} 420 200 0 1 {name=l50 sig_type=std_logic lab=VDD}
C {symbols/pfet_03v3.sym} 400 300 0 0 {name=MP4b
L=lg
W=wp
nf=1
m=1
ad="'int((nf+1)/2) * wp/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wp/nf + 0.18u)'"
as="'int((nf+2)/2) * wp/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wp/nf + 0.18u)'"
nrd="'0.18u / wp'" nrs="'0.18u / wp'"
sa=0 sb=0 sd=0
model=pfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 420 330 0 1 {name=l52 sig_type=std_logic lab=RON}
C {devices/lab_pin.sym} 380 300 0 0 {name=l53 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 420 270 0 1 {name=l54 sig_type=std_logic lab=4_mid}
C {devices/lab_pin.sym} 420 300 0 1 {name=l55 sig_type=std_logic lab=VDD}
C {symbols/nfet_03v3.sym} 520 370 0 0 {name=MN4a
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 540 340 0 1 {name=l57 sig_type=std_logic lab=RON}
C {devices/lab_pin.sym} 500 370 0 0 {name=l58 sig_type=std_logic lab=RENB}
C {devices/lab_pin.sym} 540 400 0 1 {name=l59 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 540 370 0 1 {name=l60 sig_type=std_logic lab=VSS}
C {symbols/nfet_03v3.sym} 640 370 0 0 {name=MN4b
L=lg
W=wn
nf=1
m=1
ad="'int((nf+1)/2) * wn/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wn/nf + 0.18u)'"
as="'int((nf+2)/2) * wn/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wn/nf + 0.18u)'"
nrd="'0.18u / wn'" nrs="'0.18u / wn'"
sa=0 sb=0 sd=0
model=nfet_03v3
spiceprefix=X
}
C {devices/lab_pin.sym} 660 340 0 1 {name=l62 sig_type=std_logic lab=RON}
C {devices/lab_pin.sym} 620 370 0 0 {name=l63 sig_type=std_logic lab=PROG_EN}
C {devices/lab_pin.sym} 660 400 0 1 {name=l64 sig_type=std_logic lab=VSS}
C {devices/lab_pin.sym} 660 370 0 1 {name=l65 sig_type=std_logic lab=VSS}
T {Interlock: PON = PROG_EN & ~READ_EN ; RON = READ_EN & ~PROG_EN} -100 -420 0 0 0.3 0.3 {}
