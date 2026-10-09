v {xschem version=3.4.7 file_version=1.2

* gf180-antifuse: local high-voltage pass-gate (spec/architecture.md 1.1).
*
* One thick-oxide NMOS between A and B, gate G, bulk VB. The family is a
* per-region choice (the generator picks the cell by band); sizes are
* PLACEHOLDERS, not a sized design.
*
* Device family: nfet_10v0_asym (Candidate 2 region).
* DELIBERATE d/s ASSIGNMENT: d -> A, s -> B. Instances wire A to the node that
* must be blocked against the elevated voltage while the gate is off - the
* global bus for a column gate (bus at the program rail, column deselected),
* the array-side plate line for a row return gate. See design/README.md.
}
G {}
K {}
V {}
S {}
E {}
C {symbols/nfet_10v0_asym.sym} 300 0 0 0 {name=M1
L=lpg
W=wpg
nf=1
m=1
ad="'wpg * 1.48u'"
pd="'2 * (wpg + 1.48u)'"
as="'wpg * 0.48u'"
ps="'2 * (wpg + 0.48u)'"
nrd=0 nrs=0
sa=0 sb=0 sd=0
model=nfet_10v0_asym
spiceprefix=X}
C {devices/lab_pin.sym} 320 -30 0 0 {name=l1 sig_type=std_logic lab=A}
C {devices/lab_pin.sym} 280 0 0 0 {name=l2 sig_type=std_logic lab=G}
C {devices/lab_pin.sym} 320 30 0 0 {name=l3 sig_type=std_logic lab=B}
C {devices/lab_pin.sym} 320 0 0 0 {name=l4 sig_type=std_logic lab=VB}
C {devices/iopin.sym} 0 -100 0 0 {name=p5 lab=A}
C {devices/iopin.sym} 0 -60 0 0 {name=p6 lab=B}
C {devices/ipin.sym} 0 -20 0 0 {name=p7 lab=G}
C {devices/ipin.sym} 0 20 0 0 {name=p8 lab=VB}
T {Local HV pass-gate, nfet_10v0_asym} -50 -160 0 0 0.5 0.5 {}
