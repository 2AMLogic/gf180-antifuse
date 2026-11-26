#!/usr/bin/env python3
"""Generate the program-leg / read-leg xschem sources in design/cells/.

    python3 design/tools/gen_leg_schematics.py            write the sources
    python3 design/tools/gen_leg_schematics.py --check    fail if the committed
                                                          sources differ from a
                                                          fresh generation

stdlib only. Writes, into design/cells/:

    leg_interlock.sch / .sym    PROG_EN / READ_EN mutual-exclusion gating
    program_leg.sch   / .sym    ballast + high-side switch + level shifter
    read_leg.sch      / .sym    isolation switch + clamp + sense amp + I_ref

WHY A GENERATOR. xschem connects a pin to a net by coincident coordinates, so
a hand-typed schematic needs every device pin coordinate worked out by hand.
This script holds the net list once; the shared emitter (xschem_emit.py) holds
the PDK symbol geometry, computes each pin's coordinate from it, and puts a
lab_pin on every pin -- the same labelled-pin style the cell schematics use.
The OUTPUT is an ordinary xschem schematic: open it in xschem, edit it there
if you like (then stop using this script), and design/regen-netlists.sh
derives the SPICE netlists from the .sch files either way.

The circuit content below is the design. Rationale lives in
design/README.md ("Program leg and read leg") and the on-canvas notes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Shared emitter. regen-netlists.sh runs this under `python3 -I`, which leaves
# the script directory off sys.path, so it is added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xschem_emit import Sch, sym_pin_offsets, sym_text, write_or_check  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
CELLS = REPO / "design" / "cells"


def comment_lines(hdr: str) -> list[str]:
    """The "* "-prefixed header blocks below, as the bare lines Sch() expects."""
    return [ln[2:] if ln.startswith("* ") else "" for ln in hdr.strip().splitlines()]


def new_sch(hdr: str) -> Sch:
    return Sch(comment_lines(hdr), flip_right_labels=True)


def leg_symbol(comment: str, template: str, left, right, fmt_params: str, desc: str) -> str:
    """Subcircuit symbol (shared sym_text, 30-unit pin pitch) with the m multiplier."""
    return sym_text(left, right, fmt=f"@name @pinlist @symname {fmt_params} m=@m",
                    template=f"{template} m=1", comment=[comment], label=desc, pitch=30)


def pin_offsets(left, right):
    return sym_pin_offsets(left, right, pitch=30)


def sub(s: Sch, name, sym, x, y, pinmap, pin_offsets, params=""):
    s.inst(sym, x, y, f"name={name}{params}")
    s.pin_labels(x, y, pin_offsets, pinmap)


# ---------------------------------------------------------------------------
# leg_interlock
# ---------------------------------------------------------------------------
IL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VDD", "inout"), ("VSS", "inout")]
IL_PINS_R = [("PON", "out"), ("RON", "out")]


def inv(s, tag, x, y, a, z, lg, wn, wp, vdd="VDD", vss="VSS"):
    s.mos("nfet_03v3", f"MN{tag}", x, y + 70, wn, lg, z, a, vss, vss)
    s.mos("pfet_03v3", f"MP{tag}", x, y - 70, wp, lg, z, a, vdd, vdd)


def nor2(s, tag, x, y, a, b, z, lg, wn, wp, vdd="VDD", vss="VSS"):
    # series PMOS stack (a upper, b lower), parallel NMOS pair
    s.mos("pfet_03v3", f"MP{tag}a", x, y - 100, wp, lg, f"{tag}_mid", a, vdd, vdd)
    s.mos("pfet_03v3", f"MP{tag}b", x + 0, y, wp, lg, z, b, f"{tag}_mid", vdd)
    s.mos("nfet_03v3", f"MN{tag}a", x + 120, y + 70, wn, lg, z, a, vss, vss)
    s.mos("nfet_03v3", f"MN{tag}b", x + 240, y + 70, wn, lg, z, b, vss, vss)


def gen_interlock(out):
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
    s = new_sch(hdr)
    for i, (p, d) in enumerate(IL_PINS_L):
        s.port("ipin" if d == "in" else "iopin", p, -100, -300 + 40 * i)
    s.port("opin", "PON", 900, -300)
    s.port("opin", "RON", 900, -260)
    p = dict(lg="lg", wn="wn", wp="wp")
    inv(s, "1", 0, 0, "PROG_EN", "PENB", **p)
    inv(s, "2", 160, 0, "READ_EN", "RENB", **p)
    nor2(s, "3", 400, 0, "PENB", "READ_EN", "PON", **p)
    nor2(s, "4", 400, 300, "RENB", "PROG_EN", "RON", **p)
    s.text("Interlock: PON = PROG_EN & ~READ_EN ; RON = READ_EN & ~PROG_EN", -100, -420)
    out[CELLS / "leg_interlock.sch"] = s.render()
    symtxt = leg_symbol(
        "gf180-antifuse: symbol for the PROG_EN/READ_EN interlock gating block.",
        "name=x1 lg=0.28u wn=1u wp=2u", IL_PINS_L, IL_PINS_R,
        "lg=@lg wn=@wn wp=@wp", "PON/RON mutually exclusive")
    out[CELLS / "leg_interlock.sym"] = symtxt
    return pin_offsets(IL_PINS_L, IL_PINS_R)


# ---------------------------------------------------------------------------
# program_leg
# ---------------------------------------------------------------------------
PL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VDD", "inout"), ("VSS", "inout")]
PL_PINS_R = [("BL", "inout"), ("VPP", "inout")]


def gen_program(out, il_offs):
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
    s = new_sch(hdr)
    for i, (pin, d) in enumerate(PL_PINS_L):
        s.port("ipin" if d == "in" else "iopin", pin, -100, -340 + 40 * i)
    s.port("iopin", "BL", 1000, -340)
    s.port("iopin", "VPP", 1000, -300)
    sub(s, "Xil", "leg_interlock.sym", 100, -250,
          {"PROG_EN": "PROG_EN", "READ_EN": "READ_EN", "VDD": "VDD", "VSS": "VSS",
           "PON": "PON", "RON": "RON_nc"}, il_offs,
          " lg=lg wn=wnl wp=wpl")
    inv(s, "5", 300, -150, "PON", "PONB", "lg", "wnl", "wpl")
    # level shifter (VPP domain)
    s.mos("pfet_06v0", "MLSP1", 520, 0, "wlsp", "llsp", "PG", "PGB", "VPP", "VPP")
    s.mos("pfet_06v0", "MLSP2", 680, 0, "wlsp", "llsp", "PGB", "PG", "VPP", "VPP")
    s.mos("nfet_06v0", "MLSN1", 520, 140, "wlsn", "llsn", "PG", "PON", "VSS", "VSS")
    s.mos("nfet_06v0", "MLSN2", 680, 140, "wlsn", "llsn", "PGB", "PONB", "VSS", "VSS")
    # switch + ballast
    s.mos("pfet_06v0", "MSW", 880, 0, "wsw", "lsw", "RB_TOP", "PG", "VPP", "VPP")
    s.res("ppolyf_u_2k_6p0", "RB", 1060, 60, "rb_w", "rb_l", "RB_TOP", "BL", "VSS")
    s.text("PROGRAM LEG: VPP -> MSW (pfet_06v0) -> RB (ppolyf_u_2k_6p0 ballast) -> BL", -100, -440)
    s.text("VPP-domain cross-coupled level shifter (drives MSW gate: 0 = on, VPP = off)", 500, -80, 0.25)
    out[CELLS / "program_leg.sch"] = s.render()
    symtxt = leg_symbol(
        "gf180-antifuse: symbol for the program leg.",
        "name=x1 rb_w=2u rb_l=7.5u wsw=20u lsw=0.7u wlsp=0.5u llsp=0.7u wlsn=2u llsn=0.7u "
        "lg=0.28u wnl=1u wpl=2u",
        PL_PINS_L, PL_PINS_R,
        "rb_w=@rb_w rb_l=@rb_l wsw=@wsw lsw=@lsw wlsp=@wlsp llsp=@llsp wlsn=@wlsn llsn=@llsn "
        "lg=@lg wnl=@wnl wpl=@wpl", "ballast + switch to VPP")
    out[CELLS / "program_leg.sym"] = symtxt


# ---------------------------------------------------------------------------
# read_leg
# ---------------------------------------------------------------------------
RL_PINS_L = [("PROG_EN", "in"), ("READ_EN", "in"), ("VCLAMP", "in"), ("IREF", "in"),
             ("VDD", "inout"), ("VSS", "inout")]
RL_PINS_R = [("BL", "inout"), ("SENSE", "out"), ("RDATA", "out")]


def gen_read(out, il_offs):
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
    s = new_sch(hdr)
    for i, (pin, d) in enumerate(RL_PINS_L):
        s.port("ipin" if d == "in" else "iopin", pin, -100, -420 + 40 * i)
    s.port("iopin", "BL", 1100, -420)
    s.port("opin", "SENSE", 1100, -380)
    s.port("opin", "RDATA", 1100, -340)
    sub(s, "Xil", "leg_interlock.sym", 100, -250,
          {"PROG_EN": "PROG_EN", "READ_EN": "READ_EN", "VDD": "VDD", "VSS": "VSS",
           "PON": "PON_nc", "RON": "RON"}, il_offs, " lg=lg wn=wnl wp=wpl")
    s.mos("nfet_06v0", "MSW", 400, 0, "wsw", "lsw", "CS", "RON", "BL", "VSS")
    s.mos("nfet_03v3", "MCL", 400, -140, "wcl", "lcl", "PIN", "VCLAMP", "CS", "VSS")
    s.mos("pfet_03v3", "MPI", 600, -140, "wmp", "lmp", "PIN", "PIN", "VDD", "VDD")
    s.mos("pfet_03v3", "MPO", 760, -140, "wmp", "lmp", "SENSE", "PIN", "VDD", "VDD")
    s.mos("nfet_03v3", "MNI", 600, 140, "wmn", "lmn", "IREF", "IREF", "VSS", "VSS")
    s.mos("nfet_03v3", "MNO", 760, 140, "wmn", "lmn", "SENSE", "IREF", "VSS", "VSS")
    inv(s, "6", 900, 0, "SENSE", "SB", "lg", "wnl", "wpl")
    inv(s, "7", 1000, 0, "SB", "RDATA", "lg", "wnl", "wpl")
    s.text("READ LEG: BL - MSW - MCL(clamp) - MPI/MPO (mirror) vs IREF mirror -> SENSE -> RDATA", -100, -500)
    out[CELLS / "read_leg.sch"] = s.render()
    symtxt = leg_symbol(
        "gf180-antifuse: symbol for the read leg.",
        "name=x1 wsw=10u lsw=0.7u wcl=4u lcl=0.28u wmp=4u lmp=1u wmn=2u lmn=1u "
        "lg=0.28u wnl=1u wpl=2u",
        RL_PINS_L, RL_PINS_R,
        "wsw=@wsw lsw=@lsw wcl=@wcl lcl=@lcl wmp=@wmp lmp=@lmp wmn=@wmn lmn=@lmn "
        "lg=@lg wnl=@wnl wpl=@wpl", "sense amp + I_ref branch")
    out[CELLS / "read_leg.sym"] = symtxt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="diff against the committed sources; write nothing")
    args = ap.parse_args()

    out: dict[Path, str] = {}
    offs = gen_interlock(out)
    gen_program(out, offs)
    gen_read(out, offs)
    return write_or_check(out, REPO, args.check, "design/tools/gen_leg_schematics.py")


if __name__ == "__main__":
    raise SystemExit(main())
