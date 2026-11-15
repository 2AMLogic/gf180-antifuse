#!/usr/bin/env python3
"""Generate the xschem sources for the N=32 array and its row/column
addressing stage (issue #64).

    design/gen_array.py            write the sources
    design/gen_array.py --check    fail if the committed sources differ from a
                                   fresh generation (no file is written)

WHY A GENERATOR
---------------
The array is 1024 cell instances, each carrying four geometry parameters, plus
a pass-gate and a level shifter per addressed line. Hand-placing that in xschem
is not repeatable, and the per-cell parameters are exactly what has to track
spec/split-axis-plan.md. So the *schematic sources* for the array are emitted
here, checked in, and netlisted by xschem like every other source in design/
(see regen-netlists.sh). The generated netlist is the derived artifact.

WHAT IT EMITS
-------------
  design/mux/ls_hv06.{sch,sym}   level shifter, 6 V thick-oxide tier
  design/mux/ls_hv10.{sch,sym}   level shifter, 10 V asymmetric tier
  design/mux/pg_n06.{sch,sym}    local HV pass-gate, nfet_06v0
  design/mux/pg_n10.{sch,sym}    local HV pass-gate, nfet_10v0_asym
  design/array/array_32x32.{sch,sym}   the full 32 x 32 array + addressing
  design/array/slice_*.{sch,sym}       reduced slices, same generator, same
                                       absolute (row, col) coordinates
  design/array/array_library.sch       netlist driver (see cells/cell_library.sch)

WHAT IS RATIFIED AND WHAT IS A CONVENTION OF THIS FILE
------------------------------------------------------
Ratified in spec/split-axis-plan.md (and re-read from the spec, independently
of this file, by design/check-array.py): N = 32; three contiguous column bands
0-10 / 11-21 / 22-31 carrying Candidates 1 / 2 / 3; two capacitor-geometry
levels and two access-sizing levels per band, interleaved, all four
combinations present.

NOT ratified, so fixed here as an explicit PROVISIONAL convention, each an
open item for the operator (see "PROVISIONAL resolutions - open items for
the operator" in design/README.md; the same marking is stamped into the
generated sources):
  (a) The numeric "min" geometry. The capacitor half of the plan's
      "process-minimum" level is fixed by spec/capacitor-geometry-decision.md
      (Minimum wcap x lcap = 1.0 x 0.28 um for cap_nmos_03v3 / cap_pmos_03v3,
      1.0 x 0.70 um for cap_nmos_06v0); the access half (wacc/lacc) is the
      plan's section-3 axis and still has no ratified record behind it.
      "min" here is the committed cell subcircuit's own parameter default
      (placeholders carried from the PDK symbol templates, see
      design/README.md), pending the authorised regeneration; "2x" doubles
      the capacitor WIDTH (2x area at fixed length) or the access-device
      WIDTH (fixed length).
  (b) The phase / pitch of the two interleaved sub-axes (see level_indices()).
  (c) Band axis = column, so rows span all three bands and the row stage
      (level shifter + return pass-gate + word line) is instantiated per
      (row, band) segment; each band has its own BLG/PLG bus and VDDH rail.
  (d) Region II level shifters/pass-gates use the 10 V asymmetric device pair;
      spec/architecture.md 1.1 only names nfet_06v0/pfet_06v0 "for the 6 V tier".
  (e) The NMOS pass-gate gate rail is the level shifter's VDDH rail, so a
      column gate passes at most VDDH - Vth (plus body effect); the bench holds
      BLG below VDDH. A boosted gate rail is a program-leg decision.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DESIGN_DIR = Path(__file__).resolve().parent
# Shared emitter. regen-netlists.sh runs this under `python3 -I`, which leaves
# the script directory off sys.path, so tools/ is added explicitly.
sys.path.insert(0, str(DESIGN_DIR / "tools"))
sys.path.insert(0, str(DESIGN_DIR.parent / "sim"))
from xschem_emit import Sch, sym_text, write_or_check  # noqa: E402
from harness import numfmt  # noqa: E402

CELL_NETLIST_DIR = DESIGN_DIR / "netlists"
MUX_DIR = DESIGN_DIR / "mux"
ARRAY_DIR = DESIGN_DIR / "array"

N = 32

# (band label, first col, last col, candidate number). Mirrors the region map
# table in spec/split-axis-plan.md; check-array.py re-reads the spec table and
# fails if this drifts from it.
BANDS = (
    ("I", 0, 10, 1),
    ("II", 11, 21, 2),
    ("III", 22, 31, 3),
)

# name -> (row0, row1, col0, col1), inclusive, absolute coordinates.
SLICES = {
    "slice_i_ii": (0, 3, 9, 12),      # straddles the Region I | II boundary
    "slice_ii_iii": (0, 3, 20, 23),   # straddles the Region II | III boundary
}

# Full-band slices (sim/array-slice-bench full-band leakage mode): every column
# of one band (11 / 11 / 10 per spec/split-axis-plan.md) over the same four
# rows 0..3 as SLICES (rows are a reduced subset; they cover all four
# capacitor x access sub-combinations of each band). Kept apart from SLICES:
# those must straddle a region boundary (design/check-array.py) and drive the
# existing selected-cell bench.
BAND_SLICES = {
    "band_i": (0, 3, 0, 10),
    "band_ii": (0, 3, 11, 21),
    "band_iii": (0, 3, 22, 31),
}

# pass-gate / level-shifter family per candidate (spec/architecture.md 1.1:
# nfet_06v0-class for Candidate 1/3, nfet_10v0_asym-class for Candidate 2).
PG_CELL = {1: "pg_n06", 2: "pg_n10", 3: "pg_n06"}
LS_CELL = {1: "ls_hv06", 2: "ls_hv10", 3: "ls_hv06"}
# Candidate 3's access device is a PMOS: its word line is active-low and its
# cell VB (n-well tie) goes to the band's high rail instead of VSS.
ACTIVE_LOW_WL = {1: False, 2: False, 3: True}


def band_of_col(c: int):
    for label, lo, hi, cand in BANDS:
        if lo <= c <= hi:
            return label, cand
    raise ValueError(f"column {c} outside 0..{N - 1}")


# ---------------------------------------------------------------------------
# Cell parameter levels
# ---------------------------------------------------------------------------


def _split_token(tok: str):
    m = re.fullmatch(r"([0-9.]+(?:[eE][+-]?[0-9]+)?)([a-zA-Z]?)", tok)
    if not m:
        raise ValueError(f"cannot parse SPICE literal {tok!r}")
    return float(m.group(1)), m.group(2)


def scale_token(tok: str, k: float) -> str:
    """Multiply a SPICE literal by k, keeping its unit-suffix style."""
    val, suf = _split_token(tok)
    txt = f"{val * k:.6g}"
    txt = re.sub(r"e([+-])0*(\d)", r"e\1\2", txt).replace("e+", "e")
    return f"{txt}{suf}"


def cell_defaults(cand: int) -> dict[str, str]:
    """wcap/lcap/wacc/lacc subcircuit defaults, read (not copied) from the
    committed derived cell netlist - the same source sim/ reads."""
    text = (CELL_NETLIST_DIR / f"cell_candidate{cand}.spice").read_text()
    d = numfmt.parse_defaults(text, raw=True)
    keys = ("wcap", "lcap", "wacc", "lacc")
    if not set(keys) <= d.keys():
        raise SystemExit(f"gen_array: no parameterized .subckt line in cell_candidate{cand}.spice")
    return {k: d[k] for k in keys}


def level_indices(r: int, c: int, c0: int) -> tuple[int, int]:
    """(capacitor level, access level), each 0 = "min", 1 = "2x".

    CONVENTION (not ratified - see module docstring). Coordinates are
    band-relative in the column direction (c0 = band's first column) so every
    band starts from the same phase and its four combinations are balanced:
      capacitor level : cell-pitch checkerboard,        (r + c') mod 2
      access level    : 2x2-block checkerboard,  (r//2 + c'//2) mod 2
    The two are independent (all four combinations occur in every 2x2 block
    pair) and neither forms a contiguous stripe.
    """
    cp = c - c0
    return (r + cp) % 2, (r // 2 + cp // 2) % 2


# PROVISIONAL stamp repeated in every generated array/slice source. Items (a)-(e)
# are open for the operator; see "PROVISIONAL resolutions - open items for the
# operator" in design/README.md for the alternative and the consequence of each.
PROVISIONAL_NOTE = [
    "PROVISIONAL CONVENTIONS (not ratified) - open items for the operator,",
    "numbered (a)-(e) with alternatives and consequences in design/README.md",
    '("PROVISIONAL resolutions - open items for the operator"):',
    "  (a) 'min' geometry = the cell subckt placeholder defaults; '2x' = width x2.",
    "  (b) interleave phase: cap (r+c') mod 2, access (r//2+c'//2) mod 2,",
    "      band-relative column c'.",
    "  (c) band axis = column; row stage per (row, band); per-band BLG/PLG/VDDH.",
    "  (d) Region II level shifters/pass-gates use the 10 V asymmetric pair.",
    "  (e) NMOS pass-gate gate rail = VDDH (passes at most VDDH - Vth).",
]


def cell_params(r: int, c: int) -> tuple[int, dict[str, str]]:
    label, cand = band_of_col(c)
    c0 = next(lo for lab, lo, _hi, _cd in BANDS if lab == label)
    d = cell_defaults(cand)
    ci, ai = level_indices(r, c, c0)
    return cand, {
        "wcap": scale_token(d["wcap"], 2) if ci else d["wcap"],
        "lcap": d["lcap"],
        "wacc": scale_token(d["wacc"], 2) if ai else d["wacc"],
        "lacc": d["lacc"],
    }


# NOTE for parameter names below: `ln` (and `exp`, `log`, ...) are ngspice
# expression functions; a subcircuit parameter named `ln` makes `l=ln` fail to
# evaluate. Hence wpdn/lpdn (pull-down) and wpup/lpup (pull-up).

# ---------------------------------------------------------------------------
# Mux-stage cells (design/mux/)
# ---------------------------------------------------------------------------

LS_NOTE = [
    "gf180-antifuse: level shifter (spec/architecture.md 1.1).",
    "",
    "Cross-coupled PMOS latch with NMOS pull-downs, referenced to VDDH (the",
    "region's programming-voltage rail during a program operation, a fixed",
    "logic-compatible bias during read). A thin-oxide (3.3 V) inverter makes the",
    "complement of the logic-domain select IN from VDDL, so the digital partition",
    "supplies one single-ended one-hot select line per row / column.",
    "",
    "Both latch outputs are actively driven at all times once the rails are up",
    "(spec/architecture.md 3 item 1: no decoder output may float). OUT follows",
    "IN; OUTB is its complement.",
    "",
    "Transistor widths are PLACEHOLDERS to be sized against the worst-case",
    "corner; nothing in this file claims a sized design.",
]


def gen_ls(family: str) -> tuple[str, str]:
    if family == "06":
        nk, pk, wn, ln, wp, lp = "nfet_06v0", "pfet_06v0", "10u", "0.70u", "1u", "0.55u"
        fam_note = ["Device family: nfet_06v0 / pfet_06v0 (6 V tier, Candidate 1/3 regions)."]
    else:
        nk, pk, wn, ln, wp, lp = "nfet_10v0_asym", "pfet_10v0_asym", "20u", "0.60u", "5u", "0.60u"
        fam_note = [
            "Device family: nfet_10v0_asym / pfet_10v0_asym (10 V tier, Candidate 2 region).",
            "DELIBERATE d/s ASSIGNMENT, as for the Candidate 2 cell: the drift-extended",
            "drain faces the high-swing node - the pull-down's drain is the latch output,",
            "the pull-up's drain is the latch output, sources go to VSS / VDDH.",
            "spec/architecture.md 1.1 names the 6 V devices 'for the 6 V tier'; using the",
            "asymmetric 10 V pair for the 10 V tier is this repo's reading of that, not",
            "separate ratified text.",
            "PROVISIONAL (open item d for the operator): the 10 V asymmetric family for",
            "this tier is a convention of the generator - alternative and consequence in",
            "design/README.md, 'PROVISIONAL resolutions - open items for the operator'.",
        ]
    s = Sch(LS_NOTE + [""] + fam_note)
    # logic-domain inverter (3.3 V thin oxide): INB = NOT IN
    s.mos("nfet_03v3", "M1", 0, 0, "2u", "0.28u", "INB", "IN", "VSS", "VSS")
    s.mos("pfet_03v3", "M2", 0, -120, "4u", "0.28u", "INB", "IN", "VDDL", "VDDL")
    # latch pull-downs (gate = logic-domain select)
    s.mos(nk, "M3", 300, 0, "wpdn", "lpdn", "OUTB", "IN", "VSS", "VSS")
    s.mos(nk, "M4", 600, 0, "wpdn", "lpdn", "OUT", "INB", "VSS", "VSS")
    # latch pull-ups (cross-coupled)
    s.mos(pk, "M5", 300, -140, "wpup", "lpup", "OUT", "OUTB", "VDDH", "VDDH")
    s.mos(pk, "M6", 600, -140, "wpup", "lpup", "OUTB", "OUT", "VDDH", "VDDH")
    for i, (kind, nm) in enumerate((("ipin", "IN"), ("ipin", "VDDL"), ("ipin", "VSS"),
                                    ("opin", "OUT"), ("opin", "OUTB"), ("ipin", "VDDH"))):
        s.port(kind, nm, -200 + 0, -240 + 40 * i)
    s.text(f"Level shifter, {'6 V' if family == '06' else '10 V asymmetric'} tier", -200, -300, 0.5)
    sch = s.render()
    sym = sym_text(
        [("IN", "in"), ("VDDL", "in"), ("VSS", "in")],
        [("OUT", "out"), ("OUTB", "out"), ("VDDH", "in")],
        fmt="@name @pinlist @symname wpdn=@wpdn lpdn=@lpdn wpup=@wpup lpup=@lpup",
        template=f"name=x1 wpdn={wn} lpdn={ln} wpup={wp} lpup={lp}",
        comment=LS_NOTE + [""] + fam_note,
        label=f"level shifter {'06v0' if family == '06' else '10v0_asym'}",
    )
    return sch, sym


def gen_pg(family: str) -> tuple[str, str]:
    if family == "06":
        k, w, l = "nfet_06v0", "20u", "0.70u"
        note = ["Device family: nfet_06v0 (Candidate 1/3 regions). Symmetric d/s."]
    else:
        k, w, l = "nfet_10v0_asym", "25u", "0.60u"
        note = [
            "Device family: nfet_10v0_asym (Candidate 2 region).",
            "DELIBERATE d/s ASSIGNMENT: d -> A, s -> B. Instances wire A to the node that",
            "must be blocked against the elevated voltage while the gate is off - the",
            "global bus for a column gate (bus at the program rail, column deselected),",
            "the array-side plate line for a row return gate. See design/README.md.",
        ]
    comment = [
        "gf180-antifuse: local high-voltage pass-gate (spec/architecture.md 1.1).",
        "",
        "One thick-oxide NMOS between A and B, gate G, bulk VB. The family is a",
        "per-region choice (the generator picks the cell by band); sizes are",
        "PLACEHOLDERS, not a sized design.",
        "",
    ] + note + [
        "",
        "PROVISIONAL (open item e for the operator): the gate is driven by the level",
        "shifter referenced to VDDH, so this NMOS passes at most VDDH - Vth (plus",
        "body effect); whether the program rail needs a boosted gate rail is open -",
        "alternative and consequence in design/README.md, 'PROVISIONAL resolutions -",
        "open items for the operator'.",
    ]
    s = Sch(comment)
    s.mos(k, "M1", 300, 0, "wpg", "lpg", "A", "G", "B", "VB")
    for i, (kind, nm) in enumerate((("iopin", "A"), ("iopin", "B"), ("ipin", "G"), ("ipin", "VB"))):
        s.port(kind, nm, 0, -100 + 40 * i)
    s.text(f"Local HV pass-gate, {k}", -50, -160, 0.5)
    sym = sym_text(
        [("A", "inout"), ("G", "in")],
        [("B", "inout"), ("VB", "in")],
        fmt="@name @pinlist @symname wpg=@wpg lpg=@lpg",
        template=f"name=x1 wpg={w} lpg={l}",
        comment=comment,
        label=k,
    )
    return s.render(), sym


# ---------------------------------------------------------------------------
# Array / slice
# ---------------------------------------------------------------------------

CELL_PITCH_X, CELL_PITCH_Y = 400, 220


def gen_array(name: str, r0: int, r1: int, c0: int, c1: int) -> tuple[str, str]:
    rows = list(range(r0, r1 + 1))
    cols = list(range(c0, c1 + 1))
    bands = [b for b in BANDS if any(b[1] <= c <= b[2] for c in cols)]

    def vb_net(cand: int, label: str) -> str:
        return f"VDDH_{label}" if ACTIVE_LOW_WL[cand] else "VSS"

    comment = [
        f"gf180-antifuse: {name} - GENERATED by design/gen_array.py. Do not hand-edit;",
        "edit the generator and rerun design/regen-netlists.sh.",
        "",
        f"Rows {r0}..{r1}, columns {c0}..{c1} of the N={N} array (absolute coordinates),",
        "with the row/column local high-voltage addressing stage of",
        "spec/architecture.md 1.1 (level shifter -> HV pass-gate).",
        "",
        "Per-cell wcap/lcap/wacc/lacc and candidate type follow the region map in",
        "spec/split-axis-plan.md; design/check-array.py fails if they drift.",
        "",
        "Nets: BL_<c> column bit line; WL_<r>_<band> / PL_<r>_<band> word / plate line",
        "of one row segment; BLG_<band> / PLG_<band> per-band global bus the (out of",
        "scope) program / read legs attach to; CSEL_<c> / RSEL_<r> single-ended",
        "one-hot selects from the digital partition; VDDH_<band> level-shifter rail.",
        "Candidate 3's word line is active-low (PMOS access) and its cell VB is the",
        "band's VDDH rail (n-well tie at the most positive potential).",
        "",
    ] + PROVISIONAL_NOTE
    s = Sch(comment)
    ports: list[tuple[str, str, str]] = []  # (xschem kind, net, direction for sym)

    # ---- cells
    for r in rows:
        for c in cols:
            label, cand = band_of_col(c)
            _, p = cell_params(r, c)
            i, j = c - c0, r - r0
            x = 400 + CELL_PITCH_X * i
            y = 300 + CELL_PITCH_Y * j
            s.inst(
                f"cell_candidate{cand}.sym", x, y,
                f"name=Xc_{r}_{c}\nwcap={p['wcap']}\nlcap={p['lcap']}\nwacc={p['wacc']}\nlacc={p['lacc']}\nm=1",
            )
            s.lab(f"BL_{c}", x - 80, y - 30)
            s.lab(f"WL_{r}_{label}", x - 80, y + 30)
            s.lab(f"PL_{r}_{label}", x + 80, y - 30)
            s.lab(vb_net(cand, label), x + 80, y + 30)

    # ---- column stage (below the array): level shifter then pass-gate
    col_y = 300 + CELL_PITCH_Y * len(rows) + 100
    for c in cols:
        label, cand = band_of_col(c)
        x = 400 + CELL_PITCH_X * (c - c0)
        ls_attrs = f"name=XLC_{c}"
        s.inst(f"{LS_CELL[cand]}.sym", x, col_y, ls_attrs)
        s.lab(f"CSEL_{c}", x - 80, col_y - 20)
        s.lab("VDDL", x - 80, col_y)
        s.lab("VSS", x - 80, col_y + 20)
        s.lab(f"CG_{c}", x + 80, col_y - 20)
        s.lab(f"CGB_{c}", x + 80, col_y)
        s.lab(f"VDDH_{label}", x + 80, col_y + 20)
        s.inst(f"{PG_CELL[cand]}.sym", x, col_y + 200, f"name=XPC_{c}")
        s.lab(f"BLG_{label}", x - 80, col_y + 190)     # A (drain side for the 10 V family)
        s.lab(f"CG_{c}", x - 80, col_y + 210)          # G
        s.lab(f"BL_{c}", x + 80, col_y + 190)          # B
        s.lab("VSS", x + 80, col_y + 210)              # VB

    # ---- row stage (left of the array): one per (row, band) segment
    for k, (label, _lo, _hi, cand) in enumerate(bands):
        xs = -300 - 700 * k
        for r in rows:
            y = 300 + CELL_PITCH_Y * (r - r0)
            low = ACTIVE_LOW_WL[cand]
            s.inst(f"{LS_CELL[cand]}.sym", xs, y, f"name=XLR_{r}_{label}")
            s.lab(f"RSEL_{r}", xs - 80, y - 20)
            s.lab("VDDL", xs - 80, y)
            s.lab("VSS", xs - 80, y + 20)
            if low:
                s.lab(f"RG_{r}_{label}", xs + 80, y - 20)
                s.lab(f"WL_{r}_{label}", xs + 80, y)      # OUTB drives the PMOS word line
            else:
                s.lab(f"WL_{r}_{label}", xs + 80, y - 20)  # OUT drives the NMOS word line
                s.lab(f"RGB_{r}_{label}", xs + 80, y)
            s.lab(f"VDDH_{label}", xs + 80, y + 20)
            gate = f"RG_{r}_{label}" if low else f"WL_{r}_{label}"
            s.inst(f"{PG_CELL[cand]}.sym", xs + 300, y, f"name=XPR_{r}_{label}")
            s.lab(f"PL_{r}_{label}", xs + 220, y - 10)     # A (array-side plate line)
            s.lab(gate, xs + 220, y + 10)                  # G
            s.lab(f"PLG_{label}", xs + 380, y - 10)        # B (return bus)
            s.lab("VSS", xs + 380, y + 10)                 # VB

    # ---- ports (order = symbol pin order)
    left = [(f"RSEL_{r}", "in") for r in rows] + [(f"CSEL_{c}", "in") for c in cols]
    right: list[tuple[str, str]] = []
    for label, *_ in bands:
        right += [(f"BLG_{label}", "inout"), (f"PLG_{label}", "inout")]
    for label, *_ in bands:
        right.append((f"VDDH_{label}", "in"))
    right += [("VDDL", "in"), ("VSS", "in")]
    kind_of = {"in": "ipin", "inout": "iopin"}
    for i, (nm, dr) in enumerate(left):
        s.port(kind_of[dr], nm, -2000, 100 + 30 * i)
    for i, (nm, dr) in enumerate(right):
        s.port(kind_of[dr], nm, -1800, 100 + 30 * i)
    s.text(f"{name}: rows {r0}-{r1}, cols {c0}-{c1} of the {N}x{N} array", -2000, 0, 0.8)

    sym = sym_text(
        left, right,
        fmt="@name @pinlist @symname", template="name=x1",
        comment=comment, label=name, width=400, pitch=20,
    )
    return s.render(), sym


def gen_driver() -> str:
    names = ["ls_hv06", "ls_hv10", "pg_n06", "pg_n10", "array_32x32", *SLICES, *BAND_SLICES]
    comment = [
        "gf180-antifuse: netlist driver for the array and addressing-stage library.",
        "GENERATED by design/gen_array.py. Not a circuit.",
        "",
        "Same reason as cells/cell_library.sch: xschem emits parameterized .subckt",
        "lines (the level shifter and pass-gate sizing parameters) only for",
        "sub-schematics, and split_files then writes one netlist per symbol.",
        "Netlisting this driver therefore produces ls_hv06.spice, ls_hv10.spice,",
        "pg_n06.spice, pg_n10.spice, array_32x32.spice and one file per slice.",
        "Its own top-level netlist is discarded.",
    ]
    s = Sch(comment)
    for i, nm in enumerate(names):
        s.inst(f"{nm}.sym", 300 + 500 * i, 300, f"name=X{i + 1}")
    s.text("Netlist driver - not a circuit. See the header comment in this file.", 160, 120, 0.5)
    return s.render()


def all_outputs() -> dict[Path, str]:
    out: dict[Path, str] = {}
    for fam in ("06", "10"):
        sch, sym = gen_ls(fam)
        out[MUX_DIR / f"ls_hv{fam}.sch"] = sch
        out[MUX_DIR / f"ls_hv{fam}.sym"] = sym
        sch, sym = gen_pg(fam)
        out[MUX_DIR / f"pg_n{fam}.sch"] = sch
        out[MUX_DIR / f"pg_n{fam}.sym"] = sym
    sch, sym = gen_array("array_32x32", 0, N - 1, 0, N - 1)
    out[ARRAY_DIR / "array_32x32.sch"] = sch
    out[ARRAY_DIR / "array_32x32.sym"] = sym
    for nm, (r0, r1, c0, c1) in {**SLICES, **BAND_SLICES}.items():
        sch, sym = gen_array(nm, r0, r1, c0, c1)
        out[ARRAY_DIR / f"{nm}.sch"] = sch
        out[ARRAY_DIR / f"{nm}.sym"] = sym
    out[ARRAY_DIR / "array_library.sch"] = gen_driver()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="diff against the committed sources; write nothing")
    args = ap.parse_args()

    return write_or_check(all_outputs(), DESIGN_DIR.parent, args.check, "design/gen_array.py")


if __name__ == "__main__":
    raise SystemExit(main())
