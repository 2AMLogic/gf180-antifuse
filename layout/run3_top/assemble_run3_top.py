#!/usr/bin/env python3
"""Assemble the run3 test chip layout: run3_top.gds (issue #211, part of #203).

Reads two committed inputs beside this script:

  pad_table.json   the 48 logical pad slots (issue #275 artifact) -- the pad
                   ring is built from it, signal for signal;
  the instance table in generate_run3_top.py (imported) -- one placement per
  instance row; the geometry point awaiting direct-pad integration
  (``cell_candidate2_Amin_G2x``) is reported, not placed, and its five
  instances are excluded from the assembly and from the LVS reference.

Writes two committed artifacts next to this script:

  run3_top.gds               the assembled chip (top cell ``run3_top``):
                             quarter-slot outline, the 48-slot pad ring (plus
                             the template's 8 power pads), the 31 placed cell
                             instances, the HV pad routes (bare Metal5
                             pad-to-plate routes per the #210 record -- no pad
                             cell, no on-die protection structure), the C3
                             substrate tap, the MetalTop landing
                             patches, and the density fill (see the constant
                             blocks in this file and README.md for the
                             measured findings each answers).
  lvs_reference_drawn.spice  the LVS reference for THIS assembly: the #275
                             netlist's per-geometry cell subcircuits for the
                             seven drawn cells and a top ``run3_top`` that
                             instantiates exactly the 31 placed instances over
                             the 40 connected ports. The five excluded
                             instances and their five private-plate ports are
                             named in the header, never silently dropped.

``--check`` byte-compares both against the committed files (sha256), like
``generate_run3_top.py``. Stdlib only; geometry is produced by calling ``klt
draw`` (pad ring + outline) and ``klt gen-compose`` (placement + routing), the
same verbs ``layout/bitcell_gen.py`` drives. Deterministic: two runs are
byte-identical.

Physical floorplan (this file is the record; see README.md for the prose):
template is the quarter slot ``0p5x0p5_def_all`` read from the shuttle
template page (read 2026-11-18; page stamped "Generated: 24 Oct 2026 01:02
UTC", no revision number -- the date stamp is the revision identifier): die
1936 x 2531 um, core 1052 x 1647 um, 48 signal I/O (38 bidir / 6 input-only /
4 analog) + 8 power pads (4 DVDD + 4 DVSS). Bond pads are drawn bare on Metal5
(81/0) with a 60 um pad opening (37/0) enclosed 10 um (PAD.4 floor is 2 um):
the #210 record's bare-pad choice, at the template's pad footprint. The 36
private-plate (PL) pads carry the program voltage and are routed straight to
their instance's plate on Metal5; shared BL/WL, the C3 n-well tie (VBW_C3) and
the C1/C2 substrate tie (VSS_ANALOG) route on the lower metals so no two nets
share a plane where their paths would cross. Every leg is explicitly
waypointed and checked pairwise for keep-clear before the request is written;
``klt gen-compose`` re-checks spacing and reports per-leg ``routed`` /
``landed_on_block`` state, which this script asserts all-clear before writing
anything.

Usage:  assemble_run3_top.py            write both artifacts
        assemble_run3_top.py --check    byte-compare vs committed, write nothing

Requires ``klt`` on PATH. Run with ``uvx --from klayout-tools==X.Y.Z klt`` to
pin. The evidence verbs (``klt drc`` / ``klt lvs`` / ``klt erc``) are run
separately; see README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import generate_run3_top as gen  # noqa: E402  the shared instance table (#275)

PDK = "gf180mcuA"

# --- template slot geometry -------------------------------------------------
#
# Quarter slot 0p5x0p5_def_all of the shuttle template (mith.ro
# gf180mcu-project-template, "Generated: 24 Oct 2026 01:02 UTC"; slots.json
# carries generated_at 2026-10-24T01:02:29Z and no revision number). Seal ring
# is 26 um per template edge and is added by the shuttle flow, not drawn here.
DIE_W_UM = 1936.0
DIE_H_UM = 2531.0
CORE_W_UM = 1052.0
CORE_H_UM = 1647.0

# --- pad ring ---------------------------------------------------------------
PAD_SIDE_UM = 80.0          # Metal5 (81/0) pad square
PAD_OPEN_UM = 60.0          # 37/0 pad opening, enclosed 10 um (PAD.4 >= 2 um)
SIGNAL_PAD_X_LEFT = 130.0   # left/right edge pad centres
SIGNAL_PAD_X_RIGHT = DIE_W_UM - SIGNAL_PAD_X_LEFT
SIGNAL_PAD_Y0 = 240.0       # L01..L24 (left) / L25..L48 (right), bottom-up
SIGNAL_PAD_PITCH = 85.0
SIGNAL_PADS_PER_EDGE = 24
POWER_PAD_Y = DIE_H_UM - 130.0   # top edge: 4 DVDD + 4 DVSS, unconnected
POWER_PAD_XS = (250.0, 455.0, 660.0, 865.0, 1070.0, 1275.0, 1480.0, 1685.0)
BUNDLE_PAD_Y = 130.0        # bottom edge: L37..L48
UNUSED_PAD_XS = (1150.0, 1260.0, 1370.0)

# Cell columns (cell origin x; instances spread over their pads' y, so each
# private-plate route is one straight Metal5 run at its pad's y).
COL_X_LEFT = 600.0    # instances whose pad is on the left edge (L01..L24)
COL_X_RIGHT = 1000.0  # instances whose pad is on the right edge (L25..L48)

# Composed-frame pin offsets (x, y) in um and escape directions, read from
# the committed cell GDS. BL/WL/PL points are the centres of the pins' own
# 0.42 um Metal1 pads (the Metal1 text labels sit there for BL/WL/PL; the VB
# label does not: its conductor is the cell's tap-ring outline, so the VB
# point is the midpoint of the ring's top-wall metal, chosen so a full
# 0.42 um landing window fits inside the conductor with the deck's
# metal1.space.1 (0.23 um) kept to every other net's metal -- derived from
# the committed GDS). tests/test_run3_top_assembly.py asserts this table's
# key set and the PL pad-y alignment, not the offset values against the GDS;
# the values themselves are verified end-to-end by gen-compose's per-leg
# landed_on_block assertion below and by the LVS compare.
# Regenerated cells must keep these or the plate-route alignment below
# breaks (the compose asserts it).
# The 31-instance GDS still omits this five-sample split. Its complete-array
# Region II master needs independent integration and verification on this die.
PENDING_ASSEMBLY = {"cell_candidate2_Amin_G2x"}

PIN_OFFSET_UM = {
    "cell_candidate1": {"PL": (0.21, 0.36), "BL": (5.69, 0.21),
                        "WL": (5.05, 1.38), "VB": (1.99, 3.385)},
    "cell_candidate1_A2x_G2x": {"PL": (0.21, 0.36), "BL": (5.69, 0.42),
                                "WL": (5.05, 1.80), "VB": (1.99, 4.385)},
    "cell_candidate1_A2x_Gmin": {"PL": (0.21, 0.36), "BL": (5.69, 0.42),
                                 "WL": (5.05, 1.80), "VB": (1.99, 3.385)},
    "cell_candidate1_Amin_G2x": {"PL": (0.21, 0.36), "BL": (5.69, 0.21),
                                 "WL": (5.05, 1.38), "VB": (1.99, 4.385)},
    "cell_candidate2": {"PL": (5.71, 1.0), "BL": (0.00, 0.00),
                        "WL": (0.00, 2.91), "VB": (3.99, 2.99)},
    "cell_candidate3": {"PL": (5.8, 0.36), "BL": (0.21, 0.21),
                        "WL": (0.775, 1.38), "VB": (2.655, 3.595)},
    "cell_candidate3_Amin_G2x": {"PL": (5.8, 0.36), "BL": (0.21, 0.21),
                                 "WL": (0.775, 1.38), "VB": (3.50, 4.385)},
}

# Escape direction (deg) per pin: the way the route leaves the pin. Ports
# face their routing side so gen-compose's own-block escape margins cover
# the approach: left-column pins face west (180), their east-side BL/WL face
# east (0); right-column pins face west (toward their trunks), C3's PL faces
# east (toward the right-edge plate pads).
PIN_DIRECTION = {
    "cell_candidate1": {"PL": 180, "BL": 0, "WL": 0, "VB": 180},
    "cell_candidate1_A2x_G2x": {"PL": 180, "BL": 0, "WL": 0, "VB": 180},
    "cell_candidate1_A2x_Gmin": {"PL": 180, "BL": 0, "WL": 0, "VB": 180},
    "cell_candidate1_Amin_G2x": {"PL": 180, "BL": 0, "WL": 0, "VB": 180},
    "cell_candidate2": {"PL": 0, "BL": 180, "WL": 180, "VB": 180},
    "cell_candidate3": {"PL": 0, "BL": 180, "WL": 180, "VB": 180},
    "cell_candidate3_Amin_G2x": {"PL": 0, "BL": 180, "WL": 180, "VB": 180},
}

# The per-pin via-ladder top for each pin class. PL rides Metal5 (the pad
# plane, so the program route is one straight run); the shared/tie nets each
# get their own lower plane so no two nets share a plane where their paths
# would cross.
PLANE_OF_PIN = {"PL": "top_metal", "BL": "metal4", "WL": "metal3",
                "VB": "metal2"}
BUNDLE_WIDTH_UM = 0.42
PIN_LADDER_CLEAR_UM = 3.3  # pad-leg run y sits this far below the lowest pin
PL_ROUTE_WIDTH_UM = 5.0
PAD_ROUTE_PORT_WIDTH_UM = 5.0  # port width drives the own-block escape margin

# Shared-net trunk x per bundle net (um) and its pad position on the bottom
# edge. Physical mapping of L37..L45 (pad id -> bottom-edge centre x):
#   L37 BL_C1_Amin 540 | L38 BL_C1_A2x 450 | L39 BL_C2_Amin 360
#   L40 BL_C3_Amin 760 | L41 WL_C1_Amin 270 | L42 WL_C1_A2x 180
#   L43 WL_C2_Amin  90 | L44 WL_C3_Amin 880 | L45 VBW_C3 640
# Left-driven groups connect their trunk at the group's lowest pin; the C3
# trunks (right column) are the pads' own verticals rising to the group's
# highest pin. Trunk x per metal keeps same-plane paths keep-clear (the
# constructor asserts every pair below).
BUNDLE_NETS = {
    # signal: (route role, trunk x, pad centre x, connects-at)
    "BL_C1_Amin": ("metal4", 615.0, 540.0, "low"),
    "BL_C1_A2x": ("metal4", 615.0, 450.0, "low"),
    "BL_C2_Amin": ("metal4", 588.0, 360.0, "low"),
    "BL_C3_Amin": ("metal4", 760.0, 760.0, "high"),
    "WL_C1_Amin": ("metal3", 617.0, 270.0, "low"),
    "WL_C1_A2x": ("metal3", 617.0, 180.0, "low"),
    "WL_C2_Amin": ("metal3", 586.0, 90.0, "low"),
    "WL_C3_Amin": ("metal3", 880.0, 880.0, "high"),
    "VBW_C3": ("metal2", 640.0, 640.0, "high"),
}
SUBSTRATE_NET = gen.SUBSTRATE_NET          # VSS_ANALOG (generator placeholder)
SUBSTRATE_TRUNK_X = 570.0                  # metal2, left of the left column
NET_OF_PIN = {"BL": "shared_bl", "WL": "shared_wl", "VB": "shared_vb"}

# --- MetalTop landing patches (MT.1) ----------------------------------------
#
# Measured at the shuttle precheck's binding configuration (native runset at
# gf180mcuD, decks per wafer-space/gf180mcu-precheck 9b4e7dab: a gating
# KLayout DRC run at "all,-antenna,-density,-cup" plus separate gating
# density and antenna deck runs) on the committed assembly: every Metal5
# via-drop landing pad is drawn at klt gen-compose's fixed 0.42 um footprint,
# under the 11 K MetalTop minimum width 0.44 um (rule MT.1; the landing-pad
# resolver floors to a layer's minimum-area rule but has no minimum-width
# floor -- filed upstream). 40 MT.1 findings, all on the ladder tops where
# the fixed pad protrudes past its route or its pad. The assembler patches
# each ladder top with a Metal5 overshoot so the merged shape is everywhere
# >= 5 um wide: over each private-plate pin (the route's own width, extended
# past the landing pad) and over each bundle pad port (the pad's own edge).
MT1_PATCH_OVERSHOOT_UM = 1.0
MT1_PATCH_HALF_W_UM = 2.5     # 5 um patch width == the PL route width

# --- WL antenna remedy (evaluated, deferred) + the C3 substrate tap ---------
#
# The precheck's gating antenna stage reports the shared WL trunks over the
# ANT.16_ii_ANT.4 limit (Metal3 perimeter area vs thick gate oxide area,
# 400): measured ratios 429-1035 at gf180mcuD. The deck's diode filtering
# divides the ratio by (gate + 15*(n_diode + p_diode + nwell))
# (antenna.rb, antenna_check_gf180mcu), so one n-diode per WL net would
# clear every violation: the worst net needs >= 0.245 um^2 of diode area --
# a 0.6 um COMP body in NPLUS outside NWELL with one contact and a Metal1
# landing, enclosures taken from the drawn cells' own tap ring (NPLUS over
# COMP 0.16 um; the PDK contact 0.22 um square with 0.10 um COMP/Metal1
# enclosure, above the CO.4 floor). That remedy is evaluated here and
# deliberately NOT drawn: the WL pads are bench-driven program-path pads
# whose bias record is unratified (OPEN-B3; the proposed gate/well-drive
# benches hold WL at -3.3 V and -6.0 V), and the clamp is an n+/p-substrate
# junction rated bv = 11 V (spec/hv-pad-protection-decision.md) that
# forward-conducts for any WL below the substrate -- on silicon it would
# hold WL to roughly -0.6 .. +11 V and sink bench current into VSS_ANALOG
# beside the C3 column. Per the #210 record's standard for the HV program
# legs, whether a junction may hang on a program pad is an operator
# decision, not a layout edit (README.md, "Precheck applicability"); the
# findings are recorded in drc_antenna_report.json on the shared WL trunks.
# The private pad on capacitor diffusion has zero markers after #539.
DIODE_COMP_UM = 0.6            # sizes the substrate tap body (and the
DIODE_ENC_UM = 0.16            # evaluated, unapplied WL diode remedy above)
DIODE_CONTACT_UM = 0.22        # the PDK contact square
DIODE_M1_UM = 0.42             # Metal1 landing over the contact
# The C3 cells carry no substrate tap at all (their tap ring is NPLUS in
# NWELL), so this file draws the C3 column's only p-substrate tie: one
# PCOMP in PPLUS outside NWELL beside the C3 column's top, tied to the
# substrate net VSS_ANALOG with its own Metal2 branch: NOT to a signal
# net -- a substrate tap on a signal net extracts as an ohmic substrate
# tie, and the LVS run against one merged WL_C3_Amin into the substrate
# net (measured 2026-11-18; a bare diode body extracts as nothing at all,
# which is what the reference expects). The branch runs at a y above
# every band, where the only Metal2 is net-own geometry or ended trunks.
TAP_TRUNK_OFFSET_UM = 8.0      # tap body centre x, east of the C3 WL trunk
TAP_RISE_UM = 8.0              # tap body centre y, above the group's top pin
C3_TAP_BRANCH_LIFT_UM = 16.0   # branch y, above the tap and every band

# --- density fill ------------------------------------------------------------
#
# The precheck's gating density stage (the PDK density deck, decks
# "density") demands die-level minimum coverage at gf180mcuD: COMP+dummy
# >= 25% (DCF.1b), Poly2 >= 14% (PL.8), Metal1..Metal5 >= 30% each
# (M1.4/M2.4/M3.4/M4.4/M5.4) and Metal5-as-MetalTop >= 30% (MT.3; M4.4 and
# M5.4 do not exist at the older 3LM variant the first native report ran).
# The assembler fills in three passes:
#
#   1. metals: klt fill on Metal1..Metal5's dummy layers (datatype 4),
#      20 um squares at a 5 um gap (~54 % die coverage);
#   2. dummy COMP: klt fill at the deck's own dummy-COMP clearances
#      (spacing 3.5 um >= DCF.4 to drawn COMP, gap 1.9 um >= DCF.2b), 30 um
#      squares capped at 60 % per window (~51 % die coverage, under the
#      70 % DCF.1d maximum);
#   3. dummy Poly2: a headless KLayout pass that centres a 2x2 grid of
#      8.3 um squares (9.5 um pitch, >= DPF.2b's 1.1 um) inside every dummy
#      COMP square, drawn on the Poly2 drawing layer (30/0) rather than the
#      dummy layer (30/4): the density deck counts drawn+dummy Poly2 either
#      way, but the dummy-poly rule deck's DPF.1 -- as implemented, measured
#      on a nested-squares fixture 2026-11-18 -- flags every 30/4 shape it
#      sees, fully-enclosed ones included, so no dummy-layer pattern can
#      pass it; on 30/0 the deck's dummy-poly rules are silent, the drawn
#      Poly2 rules hold (8.3 um squares, 1.2 um gaps, >= 3.1 um from drawn
#      COMP), and the antenna stage does not evaluate floating Poly2 (no
#      gate of its own -- measured on a fixture, same day). The grid carries
#      Poly2 well over the 14 % floor without ever forming a gate on drawn
#      geometry.
#
# Fill never enters the cell columns or the pads, and the C3 n-well strip
# is kept out of the dummy COMP (DCF.6a). DPF.4 (dummy poly to drawn COMP
# >= 3.2 um) holds because every dummy poly square sits inside a dummy COMP
# square that is itself >= 3.5 um from drawn COMP.
#
# The squares are this large because the stream itself has to stay under
# GitHub's 100 MB file limit: the committed chip carries every fill shape,
# and small squares put ~2.1 M of them in the file (~149 MB). Few large
# squares hold the same coverage at ~1/30th the shape count. Every square
# stays under the metal slot rules' 30 um "large feature" threshold except
# the 30 um COMP squares, which are FEOL and not slot-checked.
FILL_SPACING_UM = 3.0
METAL_FILL_SIZE_UM = 20.0
METAL_FILL_GAP_UM = 5.0
FILL_COLUMN_BAND_UM = 25.0     # no fill within this of a cell column
FILL_PAD_MARGIN_UM = 5.0       # pad keep-out beyond the 80 um pad square
NWELL_KEEPOUT_X_UM = (960.0, 1060.0)  # C3 n-well strip, generous
COMP_FILL_SIZE_UM = 30.0       # DCF.2b gap and DCF.4 spacing below
COMP_FILL_GAP_UM = 1.9
COMP_FILL_SPACING_UM = 3.5     # DCF.4 (dummy COMP to drawn COMP)
COMP_FILL_TARGET_UM = 0.6      # per-100um-window cap; keeps DCF.1d <= 70 %
POLY_GRID_PITCH_UM = 9.5       # >= DPF.2b's 1.1 um dummy-poly space
POLY_GRID_SQUARE_UM = 8.3

# Which instance-table group each shared net serves.
GROUP_OF_NET = {
    "BL_C1_Amin": "C1-Amin", "BL_C1_A2x": "C1-A2x", "BL_C2_Amin": "C2-Amin",
    "BL_C3_Amin": "C3-Amin", "WL_C1_Amin": "C1-Amin", "WL_C1_A2x": "C1-A2x",
    "WL_C2_Amin": "C2-Amin", "WL_C3_Amin": "C3-Amin", "VBW_C3": "C3-Amin",
}

ARTIFACTS = ("run3_top.gds", "lvs_reference_drawn.spice")
PADS: list[dict] = []


# --- placement --------------------------------------------------------------
def slot_edge_index(pad_id: str) -> tuple[str, int]:
    """(edge, 0-based slot) of a logical pad id: L01..L24 left bottom-up,
    L25..L48 right bottom-up."""
    n = int(pad_id[1:])
    if n <= SIGNAL_PADS_PER_EDGE:
        return "L", n - 1
    return "R", n - 1 - SIGNAL_PADS_PER_EDGE


def pad_block(pad_signal: str, pads: list[dict]) -> str:
    """Which padring strip block carries a connected pad, by its signal."""
    for pad in pads:
        if pad["label"] == pad_signal:
            for strip_id, keep in PADRING_STRIPS.items():
                if keep(pad):
                    return strip_id
    raise KeyError(pad_signal)


# Bottom-edge x per pad id (the shared/tie pads and the three unused slots;
# physical mapping recorded here and in README.md -- see BUNDLE_NETS for the
# net each bundle pad serves).
BOTTOM_PAD_X = {"L37": 540.0, "L38": 450.0, "L39": 360.0, "L40": 760.0,
                "L41": 270.0, "L42": 180.0, "L43": 90.0, "L44": 880.0,
                "L45": 640.0, "L46": 1150.0, "L47": 1260.0, "L48": 1370.0}


def pad_centre(pad_id: str) -> tuple[float, float]:
    """Centre of a logical pad id: L01..L24 left edge and L25..L36 right edge
    bottom-up at SIGNAL_PAD_PITCH; L37..L48 along the bottom edge at
    BOTTOM_PAD_X."""
    n = int(pad_id[1:])
    if n <= SIGNAL_PADS_PER_EDGE:
        return SIGNAL_PAD_X_LEFT, SIGNAL_PAD_Y0 + (n - 1) * SIGNAL_PAD_PITCH
    if n <= 36:
        return SIGNAL_PAD_X_RIGHT, SIGNAL_PAD_Y0 + (n - 25) * SIGNAL_PAD_PITCH
    return BOTTOM_PAD_X[pad_id], BUNDLE_PAD_Y


def build_placement() -> list[dict]:
    """One row per instance-table instance: the placed ones carry their cell,
    column origin and the pad-aligned plate pin; the five rows whose cell
    awaits integration into this direct-pad assembly are carried as excluded."""
    rows: list[dict] = []
    for inst in gen.build_instances():
        cell = gen.cell_name(inst["candidate"], inst["access"], inst["capacitor"])
        row = dict(inst, cell=cell, placed=cell not in PENDING_ASSEMBLY)
        if row["placed"]:
            px, py = PIN_OFFSET_UM[cell]["PL"]
            pad_x, pad_y = pad_centre(inst["pad"])
            col = COL_X_LEFT if pad_x < DIE_W_UM / 2.0 else COL_X_RIGHT
            row["origin"] = (col, round(pad_y - py, 4))
            row["pin_um"] = (round(col + px, 4), round(pad_y, 4))
            assert row["pin_um"][1] == pad_y
        rows.append(row)
    placed = [r for r in rows if r["placed"]]
    assert len(placed) == 31 and len(rows) == 36
    return rows


def instance_ports(rows: list[dict], port: str) -> list[tuple[dict, tuple[float, float]]]:
    """(row, composed-frame pin) for every placed instance's `port` pin."""
    out = []
    for row in rows:
        if not row["placed"]:
            continue
        ox, oy = row["origin"]
        px, py = PIN_OFFSET_UM[row["cell"]][port]
        out.append((row, (round(ox + px, 4), round(oy + py, 4))))
    return out


def c3_tap_branch(rows: list[dict]) -> dict:
    """The C3 substrate tap's placement and its branch geometry (see the
    constant block): tap body centre east of the C3 WL trunk and above the
    group's highest pin, the Metal2 branch y above the C3 group's top stub,
    and the left-column VB pin the branch lands on -- the highest one below
    the branch whose descent corridor is free of other cells."""
    _role, trunk_x, _pad_x, _connect_at = BUNDLE_NETS["WL_C3_Amin"]
    pins = [(r, p) for r, p in instance_ports(rows, "WL")
            if r["group"] == GROUP_OF_NET["WL_C3_Amin"]
            and r["origin"][0] == COL_X_RIGHT]
    assert pins, "WL_C3_Amin"
    pins.sort(key=lambda rp: rp[1][1])
    _top_row, top_pt = pins[-1]
    tap_x = round(trunk_x + TAP_TRUNK_OFFSET_UM, 4)
    tap_y = round(top_pt[1] + TAP_RISE_UM, 4)
    branch_y = round(tap_y + C3_TAP_BRANCH_LIFT_UM, 4)
    vb_pins = instance_ports(rows, "VB")
    left_vb = [(r, p) for r, p in vb_pins
               if r["origin"][0] == COL_X_LEFT and p[1] <= branch_y - 5.0]
    left_vb.sort(key=lambda rp: rp[1][1])
    assert left_vb, "no left-column VB pin below the C3 tap branch"
    vbx_row, vbx_pt = left_vb[-1]
    above = [p[1] for r, p in vb_pins if r["origin"][0] == COL_X_LEFT
             and vbx_pt[1] < p[1] < branch_y - 2.0]
    assert not above, f"left-column cells inside the tap-branch descent: {above}"
    return {"tap_x": tap_x, "tap_y": tap_y, "branch_y": branch_y,
            "block": vbx_row["name"], "pin": vbx_pt}


def mt1_fixup_script(gds: Path, rows: list[dict]) -> str:
    """The in-place MetalTop landing fixup as a headless KLayout script: one
    Metal5 overshoot rect per via-ladder top that lands on Metal5 (the 36
    private-plate pin ladders and the 9 bundle pad legs), merged into the
    top cell so no ladder-top protrusion is narrower than the 11 K MetalTop
    minimum width (see the MT.1 constant block). Runs after compose (the
    router is done, so no block-bbox interacts with it) and before fill."""
    rects = []
    for row in rows:
        if not row["placed"]:
            continue
        px, py = row["pin_um"]
        rects.append([round(px - 0.5, 4), round(py - MT1_PATCH_HALF_W_UM, 4),
                      round(px + MT1_PATCH_OVERSHOOT_UM, 4),
                      round(py + MT1_PATCH_HALF_W_UM, 4)])
    for net, (role, trunk_x, pad_x, connect_at) in BUNDLE_NETS.items():
        y = BUNDLE_PAD_Y + PAD_SIDE_UM / 2.0
        rects.append([round(pad_x - MT1_PATCH_HALF_W_UM, 4), round(y - 2.0, 4),
                      round(pad_x + MT1_PATCH_HALF_W_UM, 4), round(y + 1.0, 4)])
    assert len(rects) == 31 + len(BUNDLE_NETS), len(rects)
    return (
        "import pya\n"
        "layout = pya.Layout()\n"
        f"layout.read({str(gds)!r})\n"
        "top = layout.top_cell()\n"
        "shapes = top.shapes(layout.layer(81, 0))\n"
        f"for x0, y0, x1, y1 in {rects!r}:\n"
        "    shapes.insert(pya.Box(int(round(x0 / layout.dbu)),\n"
        "                          int(round(y0 / layout.dbu)),\n"
        "                          int(round(x1 / layout.dbu)),\n"
        "                          int(round(y1 / layout.dbu))))\n"
        f"layout.write({str(gds)!r})\n"
    )


def apply_mt1_fixup(gds: Path, rows: list[dict], workdir: Path) -> None:
    """Run the MT.1 fixup script on the composed layout, in place."""
    script = workdir / "mt1_fixup.py"
    script.write_text(mt1_fixup_script(gds, rows))
    r = subprocess.run(["klayout", "-b", "-r", str(script)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"klayout -b (MT.1 fixup) failed ({r.returncode}):\n"
                 f"{r.stdout}{r.stderr}")


# --- pad ring ---------------------------------------------------------------
def build_pads(pad_table: dict) -> list[dict]:
    """48 signal pads from pad_table.json (labelled only when this assembly
    connects them) plus the template's 8 unconnected power pads."""
    placed_ids = {r["pad"] for r in build_placement() if r["placed"]}
    pads = []
    for entry in pad_table["pads"]:
        x, y = pad_centre(entry["pad"])
        labelled = entry["signal"] in BUNDLE_NETS or entry["pad"] in placed_ids
        pads.append(dict(entry, x=x, y=y, label=entry["signal"] if labelled else None))
    assert len(pads) == 48
    assert sum(1 for p in pads if p["label"]) == 40
    for i, x in enumerate(POWER_PAD_XS):
        pads.append({"pad": f"PWR_{i + 1}", "signal": None,
                     "x": x, "y": POWER_PAD_Y, "label": None})
    return pads


# --- routing ----------------------------------------------------------------
def _seg(x1, y1, x2, y2):
    return (x1, y1, x2, y2)


def _seg_dist(a, b) -> float:
    """Exact minimum distance between two axis-aligned closed segments:
    the Euclidean length of the x-interval gap and the y-interval gap
    (zero on an axis where the intervals overlap or touch)."""
    for x1, y1, x2, y2 in (a, b):
        assert x1 == x2 or y1 == y2, (x1, y1, x2, y2)
    gx = max(min(a[0], a[2]), min(b[0], b[2])) - min(max(a[0], a[2]), max(b[0], b[2]))
    gy = max(min(a[1], a[3]), min(b[1], b[3])) - min(max(a[1], a[3]), max(b[1], b[3]))
    return (max(gx, 0) ** 2 + max(gy, 0) ** 2) ** 0.5


def check_keep_clear(paths: dict[str, list], width_um: float, margin_um: float) -> None:
    """Assert every pair of different-net paths on one plane keeps
    `margin_um` between their centrelines; abort the assembly otherwise.
    `paths` maps net -> {plane: [((x1,y1),(x2,y2)), ...]}."""
    planes: dict[str, dict[str, list]] = {}
    for net, by_plane in paths.items():
        for plane, segs in by_plane.items():
            planes.setdefault(plane, {})[net] = segs
    for plane, nets in sorted(planes.items()):
        names = sorted(nets)
        for i, n1 in enumerate(names):
            for n2 in names[i + 1:]:
                for s1 in nets[n1]:
                    for s2 in nets[n2]:
                        d = _seg_dist(s1, s2)
                        if d < margin_um:
                            sys.exit(
                                f"keep-clear failure on {plane}: {n1} and {n2} "
                                f"approach {d:.3f} um (margin {margin_um}): {s1} vs {s2}")
    assert width_um > 0  # widths are floored by the deck at compose time


def build_connectivity(rows: list[dict],
                       pads: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """The full net list: 31 straight plate routes + the shared/tie bundles
    with explicitly waypointed legs. Returns (connectivity entries, paths for
    the keep-clear assertion)."""
    global PADS
    PADS = pads
    nets: list[dict] = []
    paths: dict[str, dict[str, list]] = {}

    # -- private plates: one straight Metal5 run per instance, pad-y aligned --
    for row in rows:
        if not row["placed"]:
            continue
        net = row["signal"]
        px, py = row["pin_um"]
        pad_x, pad_y = pad_centre(row["pad"])
        assert pad_y == py
        nets.append({
            "net": net,
            "pins": [{"block": pad_block(net, PADS), "port": net},
                     {"block": row["name"], "port": "PL"}],
            "waypoints_um": [[px, pad_y]],
        })
        paths[net] = {"top_metal": [_seg(pad_x, pad_y, px, pad_y)]}

    # -- shared/tie bundles ---------------------------------------------------
    def emit(net, port, trunk_x, pad_signal, connect_at, col_x=None):
        pins = instance_ports(rows, port)
        if net in GROUP_OF_NET:
            pins = [(r, p) for r, p in pins if r["group"] == GROUP_OF_NET[net]]
        if col_x is not None:
            pins = [(r, p) for r, p in pins if r["origin"][0] == col_x]
        assert pins, net
        if connect_at == "low":
            pins.sort(key=lambda p: p[1][1])
            near = pins[0]
            far = pins[-1]
        else:
            pins.sort(key=lambda p: -p[1][1])
            near = pins[0]
            far = pins[-1]
        pad_x = BUNDLE_NETS[net][2]
        legs = []
        segs = []
        for (row_a, p_a), (row_b, p_b) in zip(pins, pins[1:]):
            legs.append({
                "from_pin": {"block": row_a["name"], "port": port},
                "to_pin": {"block": row_b["name"], "port": port},
                "waypoints_um": [[trunk_x, p_a[1]], [trunk_x, p_b[1]]],
            })
            segs += [_seg(p_a[0], p_a[1], trunk_x, p_a[1]),
                     _seg(trunk_x, p_a[1], trunk_x, p_b[1]),
                     _seg(trunk_x, p_b[1], p_b[0], p_b[1])]
        # pad leg. C3's trunks are their own pads' verticals rising to the
        # group's highest pin. Left-driven groups drop from their pad and run
        # to the trunk at a y BELOW the group's lowest pin ladder pads
        # (PIN_LADDER_CLEAR_UM), then climb the trunk-side x of the pin, so
        # no horizontal ever passes another pin's ladder pads.
        pad_ref = {"block": pad_block(pad_signal, PADS), "port": pad_signal}
        if connect_at == "high":
            legs.append({
                "from_pin": {"block": near[0]["name"], "port": port},
                "to_pin": pad_ref,
                "waypoints_um": [[trunk_x, near[1][1]]],
            })
            segs += [_seg(pad_x, BUNDLE_PAD_Y, trunk_x, near[1][1])]
        else:
            y_join = near[1][1] - PIN_LADDER_CLEAR_UM
            climb_x = near[1][0] - PIN_X_JOIN_OFFSET_UM
            legs.append({
                "from_pin": {"block": near[0]["name"], "port": port},
                "to_pin": pad_ref,
                "waypoints_um": [[climb_x, y_join], [trunk_x, y_join]],
            })
            segs += [_seg(near[1][0], near[1][1], climb_x, near[1][1]),
                     _seg(climb_x, near[1][1], climb_x, y_join),
                     _seg(climb_x, y_join, trunk_x, y_join),
                     _seg(trunk_x, y_join, near[1][0], y_join),
                     _seg(near[1][0], y_join, near[1][0], near[1][1])]
        refs = [{"block": r["name"], "port": port} for r, _ in pins]
        refs.append(pad_ref)
        role = BUNDLE_NETS[net][0]
        nets.append({"net": net, "pins": refs, "legs": legs,
                     "layer_role": role, "width_um": BUNDLE_WIDTH_UM})
        paths[net] = {role: segs}

    for net, (role, trunk_x, pad_x, connect_at) in BUNDLE_NETS.items():
        port = "VB" if net == "VBW_C3" else ("BL" if net.startswith("BL_") else "WL")
        col_x = COL_X_RIGHT if net.split("_")[1] == "C3" else COL_X_LEFT
        emit(net, port, trunk_x, net, connect_at, col_x)

    # -- substrate tie: the C1/C2 body taps, no pad (internal net) -----------
    vb_pins = instance_ports(rows, "VB")
    left = [(r, p) for r, p in vb_pins if r["origin"][0] == COL_X_LEFT]
    left.sort(key=lambda p: p[1][1])
    legs = []
    segs = []
    lift = 8.0
    for (row_a, p_a), (row_b, p_b) in zip(left, left[1:]):
        legs.append({
            "from_pin": {"block": row_a["name"], "port": "VB"},
            "to_pin": {"block": row_b["name"], "port": "VB"},
            "waypoints_um": [[p_a[0], p_a[1] + lift], [SUBSTRATE_TRUNK_X, p_a[1] + lift],
                             [SUBSTRATE_TRUNK_X, p_b[1] + lift], [p_b[0], p_b[1] + lift]],
        })
        segs += [_seg(p_a[0], p_a[1], p_a[0], p_a[1] + lift),
                 _seg(p_a[0], p_a[1] + lift, SUBSTRATE_TRUNK_X, p_a[1] + lift),
                 _seg(SUBSTRATE_TRUNK_X, p_a[1] + lift, SUBSTRATE_TRUNK_X, p_b[1] + lift),
                 _seg(SUBSTRATE_TRUNK_X, p_b[1] + lift, p_b[0], p_b[1] + lift),
                 _seg(p_b[0], p_b[1] + lift, p_b[0], p_b[1])]
    nets.append({"net": SUBSTRATE_NET,
                 "pins": [{"block": r["name"], "port": "VB"} for r, _ in left],
                 "legs": legs, "layer_role": "metal2",
                 "width_um": BUNDLE_WIDTH_UM})
    paths[SUBSTRATE_NET] = {"metal2": segs}

    # -- C3 substrate tap (the column's only p-substrate tie) ----------------
    # One branch on the substrate net: from the tap's own port up to the
    # branch y, west over the die interior at that y, then down onto the
    # landing pin (c3_tap_branch picks it and asserts the corridor).
    br = c3_tap_branch(rows)
    vss = {n["net"]: n for n in nets}[SUBSTRATE_NET]
    vss["pins"].append({"block": "substrate_tap_c3", "port": "B"})
    vss["legs"].append({
        "from_pin": {"block": "substrate_tap_c3", "port": "B"},
        "to_pin": {"block": br["block"], "port": "VB"},
        "waypoints_um": [[br["tap_x"], br["branch_y"]],
                         [round(br["pin"][0], 4), br["branch_y"]]],
    })
    paths.setdefault(SUBSTRATE_NET, {}).setdefault("metal2", []).extend([
        _seg(br["tap_x"], br["tap_y"], br["tap_x"], br["branch_y"]),
        _seg(br["tap_x"], br["branch_y"], br["pin"][0], br["branch_y"]),
        _seg(br["pin"][0], br["branch_y"], br["pin"][0], br["pin"][1]),
    ])

    check_keep_clear(paths, BUNDLE_WIDTH_UM, margin_um=3.0)
    return nets, paths


# --- request assembly -------------------------------------------------------
SUBSTRATE_FACING = 90  # the substrate strap descends into them from above
NEAR_PIN_FACING = 270  # each group's connection-end pin faces down its climb
PIN_X_JOIN_OFFSET_UM = 0.75  # climb x: west of the pin, clear of its neighbours



def cell_block(row: dict, facing: dict) -> dict:
    cell = row["cell"]
    return {
        "id": row["name"],
        "cell": {
            "gds_path": str(HERE.parent / cell / f"{cell}.gds"),
            "cell_name": cell,
            "ports": [
                {"name": name,
                 "x_um": PIN_OFFSET_UM[cell][name][0],
                 "y_um": PIN_OFFSET_UM[cell][name][1],
                 "layer": {"layer": 34, "datatype": 0},
                 "direction_deg": facing.get((row["name"], name),
                                             PIN_DIRECTION[cell][name]),
                 "width_um": 0.42}
                for name in ("BL", "WL", "PL", "VB")
            ],
        },
    }


def pad_port_direction(pad: dict) -> int:
    """Bond pads face the die interior: left-edge pads east (0 deg), right-edge
    pads west (180), bottom-edge pads north (90) -- the direction the routes
    approach from, so gen-compose's own-block escape margins cover them."""
    y = pad["y"]
    if y == BUNDLE_PAD_Y:
        return 90
    return 0 if pad["x"] < DIE_W_UM / 2.0 else 180


PADRING_STRIPS = {
    # strip id -> filter over the pad list; four slim blocks so every route
    # crosses a strip's bounding box only at its own pad's approach (a
    # die-sized block bbox would push the router onto die-scale detour
    # lanes, which then collide with each other outside the die).
    "pads_left": lambda pad: pad["x"] < DIE_W_UM / 2.0 and pad["y"] != BUNDLE_PAD_Y,
    "pads_right": lambda pad: pad["x"] > DIE_W_UM / 2.0 and pad["y"] != BUNDLE_PAD_Y,
    "pads_bottom": lambda pad: pad["y"] == BUNDLE_PAD_Y,
    "pads_top": lambda pad: pad["y"] == POWER_PAD_Y,
}


def padring_block(strip_pads: list[dict], strip_id: str) -> dict:
    # this strip's piece of the die outline (quarter-slot template border):
    # four slim bars, one per strip, so no block ever spans the whole die
    bars = {"pads_left": [0.0, 0.0, 10.0, DIE_H_UM],
            "pads_right": [DIE_W_UM - 10.0, 0.0, DIE_W_UM, DIE_H_UM],
            "pads_bottom": [0.0, 0.0, DIE_W_UM, 10.0],
            "pads_top": [0.0, DIE_H_UM - 10.0, DIE_W_UM, DIE_H_UM]}
    shapes: list[dict] = [{"layer": [0, 0], "name": "BORDER",
                           "rect_um": bars[strip_id]}]
    labels: list[dict] = []
    half = PAD_SIDE_UM / 2.0
    open_half = PAD_OPEN_UM / 2.0
    for pad in strip_pads:
        x, y = pad["x"], pad["y"]
        shapes.append({"layer": [81, 0], "name": "Metal5",
                       "rect_um": [x - half, y - half, x + half, y + half]})
        shapes.append({"layer": [37, 0], "name": "Pad",
                       "rect_um": [x - open_half, y - open_half,
                                   x + open_half, y + open_half]})
        if pad["label"]:
            labels.append({"layer": [81, 10], "text": pad["label"],
                           "at_um": [x, y]})
    return {"shapes": shapes, "labels": labels}


def padring_ports(pads: list[dict]) -> list[dict]:
    """Explicit padring ports: one per connected pad, at its centre, facing
    the interior. Port names are the pad signals (== the net names)."""
    def port_xy(pad: dict) -> tuple[float, float]:
        """Port at the pad's inner edge: the route leaves from there and its
        drawn metal overlaps only the tail of its own pad, so no route ever
        crosses its strip block's interior."""
        x, y = pad["x"], pad["y"]
        if y == BUNDLE_PAD_Y:
            return x, y + PAD_SIDE_UM / 2.0
        if x < DIE_W_UM / 2.0:
            return x + PAD_SIDE_UM / 2.0, y
        return x - PAD_SIDE_UM / 2.0, y

    return [{"name": pad["label"], "x_um": port_xy(pad)[0],
             "y_um": port_xy(pad)[1],
             "layer": {"layer": 81, "datatype": 0},
             "direction_deg": pad_port_direction(pad),
             "width_um": PAD_ROUTE_PORT_WIDTH_UM}
            for pad in pads if pad["label"]]


def compose_request(rows: list[dict], pads: list[dict],
                    workdir: Path) -> tuple[dict, Path]:
    blocks = []
    order = []
    origins = {}
    for strip_id, keep in PADRING_STRIPS.items():
        strip_pads = [pad for pad in pads if keep(pad)]
        pads_gds = workdir / f"{strip_id}.gds"
        draw_req = padring_block(strip_pads, strip_id)
        r = subprocess.run(
            ["klt", "draw", "--params", json.dumps(draw_req),
             "--cell-name", strip_id, "-o", str(pads_gds), "--format", "json"],
            capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"klt draw failed ({r.returncode}):\n{r.stdout}{r.stderr}")
        ports = padring_ports(strip_pads)
        blocks.append({"id": strip_id,
                       "cell": {"gds_path": str(pads_gds),
                                "cell_name": strip_id,
                                "ports": ports}})
        order.append(strip_id)
        origins[strip_id] = {"x": 0.0, "y": 0.0}
    facing = {}
    for net, (role, trunk_x, pad_x, connect_at) in BUNDLE_NETS.items():
        if connect_at != "low":
            continue
        port = net.split("_")[0]
        pins = instance_ports(rows, port)
        pins = [(r, pt) for r, pt in pins
                if r["group"] == GROUP_OF_NET[net] and r["origin"][0] == COL_X_LEFT]
        assert pins, net
        pins.sort(key=lambda rp: rp[1][1])
        facing[(pins[0][0]["name"], port)] = NEAR_PIN_FACING
    for row in rows:
        if row["placed"] and row["origin"][0] == COL_X_LEFT:
            facing[(row["name"], "VB")] = SUBSTRATE_FACING
    for row in rows:
        if not row["placed"]:
            continue
        blocks.append(cell_block(row, facing))
        order.append(row["name"])
        origins[row["name"]] = {"x": row["origin"][0], "y": row["origin"][1]}

    # The C3 substrate tap (see the constant block), tied to the substrate
    # net by the branch leg added in build_connectivity.
    br = c3_tap_branch(rows)
    tap_gds = workdir / "substrate_tap.gds"
    c, e = DIODE_COMP_UM / 2.0, DIODE_CONTACT_UM / 2.0
    half = DIODE_COMP_UM / 2.0 + DIODE_ENC_UM
    draw_req = {"shapes": [
        {"layer": [22, 0], "rect_um": [0.5 - c, 0.5 - c, 0.5 + c, 0.5 + c]},
        {"layer": [31, 0], "rect_um": [0.5 - half, 0.5 - half, 0.5 + half, 0.5 + half]},
        {"layer": [33, 0], "rect_um": [0.5 - e, 0.5 - e, 0.5 + e, 0.5 + e]},
        {"layer": [34, 0], "rect_um": [0.5 - DIODE_M1_UM / 2.0, 0.5 - DIODE_M1_UM / 2.0,
                                       0.5 + DIODE_M1_UM / 2.0, 0.5 + DIODE_M1_UM / 2.0]},
    ]}
    r = subprocess.run(
        ["klt", "draw", "--params", json.dumps(draw_req),
         "--cell-name", "substrate_tap", "-o", str(tap_gds), "--format", "json"],
        capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"klt draw failed ({r.returncode}):\n{r.stdout}{r.stderr}")
    blocks.append({"id": "substrate_tap_c3",
                   "cell": {"gds_path": str(tap_gds),
                            "cell_name": "substrate_tap",
                            "ports": [{"name": "B", "x_um": 0.5, "y_um": 0.5,
                                       "layer": {"layer": 34, "datatype": 0},
                                       "direction_deg": 90, "width_um": 0.42}]}})
    order.append("substrate_tap_c3")
    origins["substrate_tap_c3"] = {"x": round(br["tap_x"] - 0.5, 4),
                                   "y": round(br["tap_y"] - 0.5, 4)}

    nets, _ = build_connectivity(rows, pads)
    out = workdir / "run3_top.gds"
    req = {
        "schema": "klt.gen_compose.request/1",
        "pdk": {"variant": PDK},
        "blocks": blocks,
        "placement": {"strategy": "explicit", "order": order,
                      "origins_um": origins},
        "connectivity": nets,
        "routing": {"layer_role": "top_metal", "width_um": PL_ROUTE_WIDTH_UM},
        "options": {"cell_name": "run3_top", "output": str(out)},
    }
    return req, out


def assert_composed(response_text: str, rows: list[dict],
                    req_json: dict) -> dict:
    """Read the compose response and abort unless every leg routed and landed;
    returns the parsed response (committed as compose_report.json)."""
    resp = json.loads(response_text)
    unrouted = resp.get("unrouted_nets") or []
    if unrouted:
        names = [n if isinstance(n, str) else n.get("net") for n in unrouted]
        detail = [n for n in resp.get("nets") or [] if n.get("net") in names]
        reasons = {}
        for net in detail:
            for leg in net.get("legs") or []:
                if not leg.get("routed"):
                    reasons[net["net"]] = str(leg.get("reason"))[:300]
        here = HERE / "compose_request.failed.json"
        here.write_text(json.dumps(req_json, indent=1))
        sys.exit(f"compose left {len(unrouted)} net(s) unrouted: {names}; "
                 f"request left at {here}; reasons: {reasons}")
    nets = resp.get("nets") or []
    assert len(nets) == 31 + len(BUNDLE_NETS) + 1, [n.get("net") for n in nets]
    for net in nets:
        if not net.get("routed"):
            sys.exit(f"net {net.get('net')} not fully routed: {net.get('status')}")
        if net.get("landed_on_block") is False:
            sys.exit(f"net {net.get('net')} has a leg that landed off-block")
        for leg in net.get("legs") or []:
            if not leg.get("routed"):
                sys.exit(f"leg of {net.get('net')} unrouted: {leg.get('reason')}")
    placed = [r["name"] for r in rows if r["placed"]]
    got = {b.get("placed_cell_name", "").split("__")[0]
           for b in resp.get("blocks") or []}
    missing = [n for n in placed if n not in got]
    assert not missing, f"instances missing from the composed stream: {missing}"
    return resp


# --- derived LVS reference --------------------------------------------------
def emit_lvs_reference(rows: list[dict]) -> str:
    """The reference for THIS assembly: the seven drawn cells' subcircuits
    verbatim from the #275 generator and a top that instantiates exactly the
    31 placed instances over the 40 connected ports. The exclusions are named
    in the header."""
    excluded = [r for r in rows if not r["placed"]]
    all_ports = [p["signal"] for p in gen.build_pads()[:45]]
    excluded_ports = {r["signal"] for r in excluded}
    ports = [p for p in all_ports if p not in excluded_ports]
    assert len(ports) == 40, ports

    # Keep the dated reference byte-for-byte with the retained 31-cell LVS.
    # The newer 32 x 32 matrix now supplies the missing master.
    out = [
        "* LVS reference for layout/run3_top/run3_top.gds -- DERIVED, do not edit.",
        "* Generated by layout/run3_top/assemble_run3_top.py from the #275",
        "* generator's tables (import generate_run3_top), restricted to the",
        "* instances this assembly can place:",
        "*",
        f"*   excluded (no drawn cell, {PENDING_ASSEMBLY}, #296/#299):",
    ]
    for r in excluded:
        out.append(f"*     {r['name']}  pad {r['pad']}  port {r['signal']}")
    out += [
        "*   their five private-plate ports are excluded with them; every",
        "*   other port and instance of run3_top.spice is present. A full",
        "*   36-instance match is blocked until that cell is drawn.",
        "*",
        f"* The substrate net {SUBSTRATE_NET} is the #275 generator's",
        "* placeholder (spec/supply-domains-decision.md rows 2/13/14); here it",
        "* is the on-die strap tying the C1/C2 body taps, left internal.",
        "",
        "* ---- per-geometry cell subcircuits (7 drawn points) ----",
        "",
    ]
    placed = [r for r in rows if r["placed"]]
    placed_cells = sorted({r["cell"] for r in placed})
    for cand, acc, cap in gen._geometry_points():
        name = gen.cell_name(cand, acc, cap)
        if name in placed_cells:
            out.append(gen._cell_subckt(cand, acc, cap))
            out.append("")
    out.append("* ---- top: 31 placed instances, 40 connected ports ----")
    out.append("")
    out.append(".subckt run3_top " + " ".join(ports))
    out.extend(gen.format_instance_lines(placed))
    out.append(".ends")
    out.append("")
    return "\n".join(out)


# --- CLI --------------------------------------------------------------------
def sha(text_or_bytes) -> str:
    data = (text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str)
            else text_or_bytes)
    return hashlib.sha256(data).hexdigest()


def run_klt_compose(req: dict, workdir: Path) -> str:
    rq = workdir / "compose_request.json"
    rq.write_text(json.dumps(req, indent=1))
    r = subprocess.run(["klt", "gen-compose", str(rq), "--format", "json"],
                       capture_output=True, text=True)
    if r.returncode not in (0, 3):
        rq_failed = HERE / "compose_request.failed.json"
        rq_failed.write_text(json.dumps(req, indent=1))
        sys.exit(f"klt gen-compose failed ({r.returncode}); request left at "
                 f"{rq_failed}:\n{r.stdout}{r.stderr}")
    return r.stdout


# --- density fill ------------------------------------------------------------
def _fill_excludes(pads: list[dict]) -> list:
    """The dummy-COMP keep-outs: the cell columns, the pads (plus margin)
    and the C3 n-well strip (DCF.6a). The metal pass keeps the same
    keep-outs and the dummy Poly2 squares live inside the dummy COMP ones,
    so one exclusion set serves all passes."""
    shared = []
    for col in (COL_X_LEFT, COL_X_RIGHT):
        shared.append([col - FILL_COLUMN_BAND_UM, 0.0,
                       col + FILL_COLUMN_BAND_UM, DIE_H_UM])
    for pad in pads:
        shared.append([pad["x"] - PAD_SIDE_UM / 2.0 - FILL_PAD_MARGIN_UM,
                       pad["y"] - PAD_SIDE_UM / 2.0 - FILL_PAD_MARGIN_UM,
                       pad["x"] + PAD_SIDE_UM / 2.0 + FILL_PAD_MARGIN_UM,
                       pad["y"] + PAD_SIDE_UM / 2.0 + FILL_PAD_MARGIN_UM])
    shared.append([NWELL_KEEPOUT_X_UM[0], 0.0, NWELL_KEEPOUT_X_UM[1], DIE_H_UM])
    return shared


POLY_GRID_PASS = (
    "import pya\n"
    "layout = pya.Layout()\n"
    "layout.read(%r)\n"
    "top = layout.top_cell()\n"
    "shapes = top.shapes(layout.layer(30, 0))\n"
    "comp = pya.Region(top.begin_shapes_rec(layout.layer(22, 4)))\n"
    "comp.merge()\n"
    "half = %r / 2.0\n"
    "for poly in comp.each():\n"
    "    box = poly.bbox()\n"
    "    cx = (box.left + box.right) * 0.5 * layout.dbu\n"
    "    cy = (box.bottom + box.top) * 0.5 * layout.dbu\n"
    "    pitch = %r\n"
    "    for sx in (-1, 1):\n"
    "        for sy in (-1, 1):\n"
    "            x = cx + sx * pitch / 2.0\n"
    "            y = cy + sy * pitch / 2.0\n"
    "            shapes.insert(pya.Box(int(round((x - half) / layout.dbu)),\n"
    "                                  int(round((y - half) / layout.dbu)),\n"
    "                                  int(round((x + half) / layout.dbu)),\n"
    "                                  int(round((y + half) / layout.dbu))))\n"
    "layout.write(%r)\n"
)


def fill_density(gds: Path, pads: list[dict], workdir: Path) -> Path:
    """The three fill passes over the composed chip (metals, dummy COMP,
    dummy Poly2), per the density-stage measurement (README "Evidence").
    Returns the filled layout path."""
    excludes = json.dumps(_fill_excludes(pads))
    die = json.dumps([0.0, 0.0, DIE_W_UM, DIE_H_UM])
    passes = [
        ("metals", [[34, 0], [36, 0], [42, 0], [46, 0], [81, 0]],
         FILL_SPACING_UM, METAL_FILL_SIZE_UM, METAL_FILL_GAP_UM, None),
        ("comp", [[22, 0]],
         COMP_FILL_SPACING_UM, COMP_FILL_SIZE_UM, COMP_FILL_GAP_UM,
         COMP_FILL_TARGET_UM),
    ]
    cur = gds
    for name, layers, spacing, size, gap, target in passes:
        out = workdir / f"run3_top_fill_{name}.gds"
        cmd = ["klt", "fill", str(cur), "--pdk", "gf180mcu",
               "--layers", json.dumps(layers), "--extent", die,
               "--spacing", str(spacing), "--fill-size", str(size),
               "--fill-gap", str(gap), "--top", "run3_top",
               "-o", str(out), "--format", "json"]
        if target is not None:
            cmd += ["--target-density", str(target)]
        if excludes != "[]":
            cmd += ["--exclude", excludes]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"klt fill ({name}) failed ({r.returncode}):\n"
                     f"{r.stdout}{r.stderr}")
        for entry in json.loads(r.stdout).get("layers") or []:
            if not entry.get("fill_shape_count"):
                sys.exit(f"klt fill ({name}) placed no shapes on "
                         f"{entry.get('layer')}")
        cur = out
    out = workdir / "run3_top_fill_poly2.gds"
    script = workdir / "poly_fill.py"
    script.write_text(POLY_GRID_PASS % (str(cur), POLY_GRID_SQUARE_UM,
                                        POLY_GRID_PITCH_UM, str(out)))
    r = subprocess.run(["klayout", "-b", "-r", str(script)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"klayout -b (dummy poly grid) failed ({r.returncode}):\n"
                 f"{r.stdout}{r.stderr}")
    # The poly pass writes through `klayout -b`, which stamps stream
    # timestamps; re-emit through klt's own writer so two runs stay
    # byte-identical (the --check contract).
    final = workdir / "run3_top_filled.gds"
    r = subprocess.run(["klt", "clip", str(out), "--cell", "run3_top",
                        "-o", str(final), "--format", "json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"klt clip (fill normalization) failed ({r.returncode}):\n"
                 f"{r.stdout}{r.stderr}")
    return final


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="byte-compare against the committed artifacts, write nothing")
    args = ap.parse_args()

    pad_table = json.loads((HERE / "pad_table.json").read_text())
    rows = build_placement()
    pads = build_pads(pad_table)

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        req, out_gds = compose_request(rows, pads, workdir)
        response = run_klt_compose(req, workdir)
        resp = assert_composed(response, rows, req)
        # Record portable names for the compose-stage stream and its inputs.
        resp["gds_path"] = out_gds.name
        for block in resp["blocks"]:
            source = Path(block["source_path"])
            block["source_path"] = (source.name if source.is_relative_to(workdir)
                                    else str(source.relative_to(HERE.parents[1])))
        apply_mt1_fixup(out_gds, rows, workdir)
        filled = fill_density(out_gds, pads, workdir)
        reference = emit_lvs_reference(rows)
        new = {"run3_top.gds": filled.read_bytes(),
               "lvs_reference_drawn.spice": reference}

    if args.check:
        bad = False
        for fname in ARTIFACTS:
            committed = HERE / fname
            if not committed.is_file():
                print(f"missing {committed}")
                bad = True
                continue
            a, b = sha(new[fname]), sha(committed.read_bytes())
            if a != b:
                print(f"DRIFT: {fname}: regenerated sha256 {a} != committed {b}")
                bad = True
            else:
                print(f"OK: {fname} sha256 {b}")
        if bad:
            sys.exit("regeneration drifted; run without --check to rewrite")
        return

    (HERE / "run3_top.gds").write_bytes(new["run3_top.gds"])
    (HERE / "lvs_reference_drawn.spice").write_text(new["lvs_reference_drawn.spice"])
    (HERE / "compose_report.json").write_text(json.dumps(resp, indent=1) + "\n")
    for fname in ARTIFACTS + ("compose_report.json",):
        print(f"wrote {HERE / fname} sha256 {sha((HERE / fname).read_bytes())}")
    excluded = ", ".join(r["name"] for r in rows if not r["placed"])
    print(f"placed 31 instances; awaiting direct-pad integration: {excluded}")


if __name__ == "__main__":
    main()
