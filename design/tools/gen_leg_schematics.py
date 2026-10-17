#!/usr/bin/env python3
"""Generate the program-leg / read-leg xschem sources in design/cells/.

    python3 design/tools/gen_leg_schematics.py

stdlib only. Writes, into design/cells/:

    leg_interlock.sch / .sym    PROG_EN / READ_EN mutual-exclusion gating
    program_leg.sch   / .sym    ballast + high-side switch + level shifter
    read_leg.sch      / .sym    isolation switch + clamp + sense amp + I_ref

WHY A GENERATOR. xschem connects a pin to a net by coincident coordinates, so
a hand-typed schematic needs every device pin coordinate worked out by hand.
This script holds the (small) device-placement table and the net list
once, computes each pin's coordinate from the PDK symbol geometry, and puts a
lab_pin on every pin -- the same labelled-pin style the cell schematics use.
The OUTPUT is an ordinary xschem schematic: open it in xschem, edit it there
if you like (then stop using this script), and design/regen-netlists.sh
derives the SPICE netlists from the .sch files either way.

The circuit content below is the design. Rationale lives in
design/README.md ("Program leg and read leg") and the on-canvas notes.
"""

from __future__ import annotations

from pathlib import Path

CELLS = Path(__file__).resolve().parent.parent / "cells"

# Pin offsets (relative to the symbol origin, rot=0, flip=0), read out of the
# PDK symbols in libs.tech/xschem/symbols/.
MOS_PINS = {
    "n": {"D": (20, -30), "G": (-20, 0), "S": (20, 30), "B": (20, 0)},
    "p": {"S": (20, -30), "G": (-20, 0), "D": (20, 30), "B": (20, 0)},
}
RES_PINS = {"P": (0, -30), "M": (0, 30), "B": (-20, 0)}

MOS_ATTR = (
    "L={l}\nW={w}\nnf=1\nm=1\n"
    "ad=\"'int((nf+1)/2) * {w}/nf * 0.18u'\"\n"
    "pd=\"'2*int((nf+1)/2) * ({w}/nf + 0.18u)'\"\n"
    "as=\"'int((nf+2)/2) * {w}/nf * 0.18u'\"\n"
    "ps=\"'2*int((nf+2)/2) * ({w}/nf + 0.18u)'\"\n"
    "nrd=\"'0.18u / {w}'\" nrs=\"'0.18u / {w}'\"\n"
    "sa=0 sb=0 sd=0\nmodel={model}\nspiceprefix=X\n"
)


class Sch:
    def __init__(self, header: str):
        self.header = header
        self.body: list[str] = []
        self.notes: list[str] = []

    # -- primitives -------------------------------------------------------
    def label(self, x, y, net, right=False):
        self.body.append(
            f"C {{devices/lab_pin.sym}} {x} {y} 0 {1 if right else 0} "
            f"{{name=l{len(self.body)} sig_type=std_logic lab={net}}}"
        )

    def port(self, x, y, net, kind):
        # kind: ipin / opin / iopin ; rot 0 = pin text to the right of the point
        self.body.append(
            f"C {{devices/{kind}.sym}} {x} {y} 0 0 {{name=p{len(self.body)} lab={net}}}"
        )

    def mos(self, name, pol, model, x, y, w, l, d, g, s, b):
        pins = MOS_PINS[pol]
        sym = f"symbols/{model}.sym"
        attrs = MOS_ATTR.format(w=w, l=l, model=model)
        self.body.append(f"C {{{sym}}} {x} {y} 0 0 {{name={name}\n{attrs}}}")
        for pin, net in (("D", d), ("G", g), ("S", s), ("B", b)):
            px, py = pins[pin]
            self.label(x + px, y + py, net, right=px > 0)

    def res(self, name, model, x, y, w, l, p, m, b):
        self.body.append(
            f"C {{symbols/{model}.sym}} {x} {y} 0 0 {{name={name}\nW={w}\nL={l}\n"
            f"model={model}\nspiceprefix=X\nm=1}}"
        )
        for pin, net in (("P", p), ("M", m), ("B", b)):
            px, py = RES_PINS[pin]
            self.label(x + px, y + py, net, right=px >= 0)

    def sub(self, name, sym, x, y, pinmap, pin_offsets, params=""):
        self.body.append(f"C {{{sym}}} {x} {y} 0 0 {{name={name}{params}}}")
        for pin, net in pinmap.items():
            px, py = pin_offsets[pin]
            self.label(x + px, y + py, net, right=px > 0)

    def text(self, x, y, s, size=0.3):
        self.notes.append(f"T {{{s}}} {x} {y} 0 0 {size} {size} {{}}")

    def render(self) -> str:
        return (
            "v {xschem version=3.4.7 file_version=1.2\n\n"
            + self.header.rstrip()
            + "\n}\nG {}\nK {}\nV {}\nS {}\nE {}\n"
            + "\n".join(self.body + self.notes)
            + "\n"
        )


def sym_file(name, header, template, left, right, fmt_params, desc):
    """Subcircuit symbol: box +-60 wide, pins at +-80, 60 apart."""
    h = max(len(left), len(right)) * 30 + 30
    lines = [
        "v {xschem version=3.4.7 file_version=1.2\n\n" + header.rstrip() + "\n}",
        "G {}",
        "K {type=subcircuit",
        f'format="@name @pinlist @symname {fmt_params} m=@m"',
        f'template="{template} m=1"',
        "}",
        "V {}\nS {}\nE {}",
        f"L 4 -60 {-h} 60 {-h} {{}}",
        f"L 4 -60 {h} 60 {h} {{}}",
        f"L 4 -60 {-h} -60 {h} {{}}",
        f"L 4 60 {-h} 60 {h} {{}}",
    ]
    pin_offsets = {}
    for i, (pin, direction) in enumerate(left):
        y = -h + 30 + 30 * i
        lines += [f"L 4 -80 {y} -60 {y} {{}}",
                  f"B 5 -82.5 {y-2.5} -77.5 {y+2.5} {{name={pin} dir={direction}}}",
                  f"T {{{pin}}} -55 {y-5} 0 0 0.2 0.2 {{}}"]
        pin_offsets[pin] = (-80, y)
    for i, (pin, direction) in enumerate(right):
        y = -h + 30 + 30 * i
        lines += [f"L 4 60 {y} 80 {y} {{}}",
                  f"B 5 77.5 {y-2.5} 82.5 {y+2.5} {{name={pin} dir={direction}}}",
                  f"T {{{pin}}} 55 {y-5} 0 1 0.2 0.2 {{}}"]
        pin_offsets[pin] = (80, y)
    lines += [f"T {{@symname}} -52 -5 0 0 0.3 0.3 {{}}",
              f"T {{@name}} -60 {-h-15} 0 0 0.25 0.25 {{}}",
              f"T {{{desc}}} -60 {h+10} 0 0 0.2 0.2 {{}}"]
    return "\n".join(lines) + "\n", pin_offsets


def write(name, text):
    (CELLS / name).write_text(text)
    print("wrote", f"design/cells/{name}")


# ---------------------------------------------------------------------------
# leg_interlock
# ---------------------------------------------------------------------------
IL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VDD", "inout"), ("VSS", "inout")]
IL_PINS_R = [("PON", "out"), ("RON", "out")]


def inv(s, tag, x, y, a, z, lg, wn, wp, vdd="VDD", vss="VSS"):
    s.mos(f"MN{tag}", "n", "nfet_03v3", x, y + 70, wn, lg, z, a, vss, vss)
    s.mos(f"MP{tag}", "p", "pfet_03v3", x, y - 70, wp, lg, z, a, vdd, vdd)


def nor2(s, tag, x, y, a, b, z, lg, wn, wp, vdd="VDD", vss="VSS"):
    # series PMOS stack (a upper, b lower), parallel NMOS pair
    s.mos(f"MP{tag}a", "p", "pfet_03v3", x, y - 100, wp, lg, f"{tag}_mid", a, vdd, vdd)
    s.mos(f"MP{tag}b", "p", "pfet_03v3", x + 0, y, wp, lg, z, b, f"{tag}_mid", vdd)
    s.mos(f"MN{tag}a", "n", "nfet_03v3", x + 120, y + 70, wn, lg, z, a, vss, vss)
    s.mos(f"MN{tag}b", "n", "nfet_03v3", x + 240, y + 70, wn, lg, z, b, vss, vss)


def gen_interlock():
    hdr = """
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
"""
    s = Sch(hdr)
    for i, (p, d) in enumerate(IL_PINS_L):
        s.port(-100, -300 + 40 * i, p, "ipin" if d == "in" else "iopin")
    s.port(900, -300, "PON", "opin")
    s.port(900, -260, "RON", "opin")
    p = dict(lg="lg", wn="wn", wp="wp")
    inv(s, "1", 0, 0, "PROG_EN", "PENB", **p)
    inv(s, "2", 160, 0, "READ_EN", "RENB", **p)
    nor2(s, "3", 400, 0, "PENB", "READ_EN", "PON", **p)
    nor2(s, "4", 400, 300, "RENB", "PROG_EN", "RON", **p)
    s.text(-100, -420, "Interlock: PON = PROG_EN & ~READ_EN ; RON = READ_EN & ~PROG_EN")
    write("leg_interlock.sch", s.render())
    symtxt, offs = sym_file(
        "leg_interlock",
        "* gf180-antifuse: symbol for the PROG_EN/READ_EN interlock gating block.",
        "name=x1 lg=0.28u wn=1u wp=2u", IL_PINS_L, IL_PINS_R,
        "lg=@lg wn=@wn wp=@wp", "PON/RON mutually exclusive")
    write("leg_interlock.sym", symtxt)
    return offs


# ---------------------------------------------------------------------------
# program_leg
# ---------------------------------------------------------------------------
PL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VDD", "inout"), ("VSS", "inout")]
PL_PINS_R = [("BL", "inout"), ("VPP", "inout")]


def gen_program(il_offs):
    hdr = """
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
"""
    s = Sch(hdr)
    for i, (pin, d) in enumerate(PL_PINS_L):
        s.port(-100, -340 + 40 * i, pin, "ipin" if d == "in" else "iopin")
    s.port(1000, -340, "BL", "iopin")
    s.port(1000, -300, "VPP", "iopin")
    s.sub("Xil", "leg_interlock.sym", 100, -250,
          {"PROG_EN": "PROG_EN", "READ_EN": "READ_EN", "VDD": "VDD", "VSS": "VSS",
           "PON": "PON", "RON": "RON_nc"}, il_offs,
          " lg=lg wn=wnl wp=wpl")
    inv(s, "5", 300, -150, "PON", "PONB", "lg", "wnl", "wpl")
    # level shifter (VPP domain)
    s.mos("MLSP1", "p", "pfet_06v0", 520, 0, "wlsp", "llsp", "PG", "PGB", "VPP", "VPP")
    s.mos("MLSP2", "p", "pfet_06v0", 680, 0, "wlsp", "llsp", "PGB", "PG", "VPP", "VPP")
    s.mos("MLSN1", "n", "nfet_06v0", 520, 140, "wlsn", "llsn", "PG", "PON", "VSS", "VSS")
    s.mos("MLSN2", "n", "nfet_06v0", 680, 140, "wlsn", "llsn", "PGB", "PONB", "VSS", "VSS")
    # switch + ballast
    s.mos("MSW", "p", "pfet_06v0", 880, 0, "wsw", "lsw", "RB_TOP", "PG", "VPP", "VPP")
    s.res("RB", "ppolyf_u_2k_6p0", 1060, 60, "rb_w", "rb_l", "RB_TOP", "BL", "VSS")
    s.text(-100, -440, "PROGRAM LEG: VPP -> MSW (pfet_06v0) -> RB (ppolyf_u_2k_6p0 ballast) -> BL")
    s.text(500, -80, "VPP-domain cross-coupled level shifter (drives MSW gate: 0 = on, VPP = off)", 0.25)
    write("program_leg.sch", s.render())
    symtxt, offs = sym_file(
        "program_leg", "* gf180-antifuse: symbol for the program leg.",
        "name=x1 rb_w=2u rb_l=7.5u wsw=20u lsw=0.7u wlsp=0.5u llsp=0.7u wlsn=2u llsn=0.7u "
        "lg=0.28u wnl=1u wpl=2u",
        PL_PINS_L, PL_PINS_R,
        "rb_w=@rb_w rb_l=@rb_l wsw=@wsw lsw=@lsw wlsp=@wlsp llsp=@llsp wlsn=@wlsn llsn=@llsn "
        "lg=@lg wnl=@wnl wpl=@wpl", "ballast + switch to VPP")
    write("program_leg.sym", symtxt)


# ---------------------------------------------------------------------------
# read_leg
# ---------------------------------------------------------------------------
RL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VCLAMP", "in"), ("IREF", "in"),
             ("VDD", "inout"), ("VSS", "inout")]
RL_PINS_R = [("BL", "inout"), ("SENSE", "out"), ("RDATA", "out")]


def gen_read(il_offs):
    hdr = """
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
"""
    s = Sch(hdr)
    for i, (pin, d) in enumerate(RL_PINS_L):
        s.port(-100, -420 + 40 * i, pin, "ipin" if d == "in" else "iopin")
    s.port(1100, -420, "BL", "iopin")
    s.port(1100, -380, "SENSE", "opin")
    s.port(1100, -340, "RDATA", "opin")
    s.sub("Xil", "leg_interlock.sym", 100, -250,
          {"PROG_EN": "PROG_EN", "READ_EN": "READ_EN", "VDD": "VDD", "VSS": "VSS",
           "PON": "PON_nc", "RON": "RON"}, il_offs, " lg=lg wn=wnl wp=wpl")
    s.mos("MSW", "n", "nfet_06v0", 400, 0, "wsw", "lsw", "CS", "RON", "BL", "VSS")
    s.mos("MCL", "n", "nfet_03v3", 400, -140, "wcl", "lcl", "PIN", "VCLAMP", "CS", "VSS")
    s.mos("MPI", "p", "pfet_03v3", 600, -140, "wmp", "lmp", "PIN", "PIN", "VDD", "VDD")
    s.mos("MPO", "p", "pfet_03v3", 760, -140, "wmp", "lmp", "SENSE", "PIN", "VDD", "VDD")
    s.mos("MNI", "n", "nfet_03v3", 600, 140, "wmn", "lmn", "IREF", "IREF", "VSS", "VSS")
    s.mos("MNO", "n", "nfet_03v3", 760, 140, "wmn", "lmn", "SENSE", "IREF", "VSS", "VSS")
    inv(s, "6", 900, 0, "SENSE", "SB", "lg", "wnl", "wpl")
    inv(s, "7", 1000, 0, "SB", "RDATA", "lg", "wnl", "wpl")
    s.text(-100, -500, "READ LEG: BL - MSW - MCL(clamp) - MPI/MPO (mirror) vs IREF mirror -> SENSE -> RDATA")
    write("read_leg.sch", s.render())
    symtxt, _ = sym_file(
        "read_leg", "* gf180-antifuse: symbol for the read leg.",
        "name=x1 wsw=10u lsw=0.7u wcl=4u lcl=0.28u wmp=4u lmp=1u wmn=2u lmn=1u "
        "lg=0.28u wnl=1u wpl=2u",
        RL_PINS_L, RL_PINS_R,
        "wsw=@wsw lsw=@lsw wcl=@wcl lcl=@lcl wmp=@wmp lmp=@lmp wmn=@wmn lmn=@lmn "
        "lg=@lg wnl=@wnl wpl=@wpl", "sense amp + I_ref branch")
    write("read_leg.sym", symtxt)


if __name__ == "__main__":
    offs = gen_interlock()
    gen_program(offs)
    gen_read(offs)
