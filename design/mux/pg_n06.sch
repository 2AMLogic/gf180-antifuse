v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: local high-voltage pass-gate (spec/architecture.md 1.1).
*
* One thick-oxide NMOS between A and B, gate G, bulk VB. The family is a
* per-region choice (the generator picks the cell by band); sizes are
* PLACEHOLDERS, not a sized design.
*
* Device family: nfet_06v0 (Candidate 1/3 regions). Symmetric d/s.
}
G {}
K {}
V {}
S {}
E {}
C {symbols/nfet_06v0.sym} 300 0 0 0 {name=M1
L=lpg
W=wpg
nf=1
m=1
ad="'int((nf+1)/2) * wpg/nf * 0.18u'"
pd="'2*int((nf+1)/2) * (wpg/nf + 0.18u)'"
as="'int((nf+2)/2) * wpg/nf * 0.18u'"
ps="'2*int((nf+2)/2) * (wpg/nf + 0.18u)'"
nrd="'0.18u / wpg'" nrs="'0.18u / wpg'"
sa=0 sb=0 sd=0
model=nfet_06v0
spiceprefix=X}
C {devices/lab_pin.sym} 320 -30 0 0 {name=l1 sig_type=std_logic lab=A}
C {devices/lab_pin.sym} 280 0 0 0 {name=l2 sig_type=std_logic lab=G}
C {devices/lab_pin.sym} 320 30 0 0 {name=l3 sig_type=std_logic lab=B}
C {devices/lab_pin.sym} 320 0 0 0 {name=l4 sig_type=std_logic lab=VB}
C {devices/iopin.sym} 0 -100 0 0 {name=p5 lab=A}
C {devices/iopin.sym} 0 -60 0 0 {name=p6 lab=B}
C {devices/ipin.sym} 0 -20 0 0 {name=p7 lab=G}
C {devices/ipin.sym} 0 20 0 0 {name=p8 lab=VB}
T {Local HV pass-gate, nfet_06v0} -50 -160 0 0 0.5 0.5 {}
