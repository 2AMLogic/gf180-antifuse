#!/usr/bin/env python3
"""Assemble the run3 test chip layout: run3_top.gds (issue #211, part of #203).

Reads two committed inputs beside this script:

  pad_table.json   the 48 logical pad slots (issue #275 artifact) -- the pad
                   ring is built from it, signal for signal;
  the instance table in generate_run3_top.py (imported) -- one placement per
  instance row; the one geometry point with no drawn cell
  (``cell_candidate2_Amin_G2x``) is reported, not placed, and its five
  instances are excluded from the assembly and from the LVS reference.

Writes two committed artifacts next to this script:

  run3_top.gds               the assembled chip (top cell ``run3_top``):
                             quarter-slot outline, the 48-slot pad ring (plus
                             the template's 8 power pads), the 31 placed cell
                             instances, and the HV pad routes (bare Metal5
                             pad-to-plate routes per the #210 record -- no pad
                             cell, no on-die protection structure).
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
# the committed GDS, and asserted by tests/test_run3_top_assembly.py).
# Regenerated cells must keep these or the plate-route alignment below
# breaks (the compose asserts it).
PIN_OFFSET_UM = {
    "cell_candidate1": {"PL": (0.64, 1.96), "BL": (5.69, 0.21),
                        "WL": (5.05, 1.38), "VB": (1.99, 3.385)},
    "cell_candidate1_A2x_G2x": {"PL": (0.64, 2.96), "BL": (5.69, 0.42),
                                "WL": (5.05, 1.80), "VB": (1.99, 4.385)},
    "cell_candidate1_A2x_Gmin": {"PL": (0.64, 1.96), "BL": (5.69, 0.42),
                                 "WL": (5.05, 1.80), "VB": (1.99, 3.385)},
    "cell_candidate1_Amin_G2x": {"PL": (0.64, 2.96), "BL": (5.69, 0.21),
                                 "WL": (5.05, 1.38), "VB": (1.99, 4.385)},
    "cell_candidate2": {"PL": (6.35, 2.75), "BL": (0.00, 0.00),
                        "WL": (0.00, 2.91), "VB": (3.99, 2.99)},
    "cell_candidate3": {"PL": (6.23, 1.96), "BL": (0.21, 0.21),
                        "WL": (0.775, 1.38), "VB": (2.655, 3.595)},
    "cell_candidate3_Amin_G2x": {"PL": (6.23, 2.96), "BL": (0.21, 0.21),
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
    column origin and the pad-aligned plate pin; the five rows whose cell has
    no drawn GDS are carried as excluded, never placed."""
    rows: list[dict] = []
    for inst in gen.build_instances():
        cell = gen.cell_name(inst["candidate"], inst["access"], inst["capacitor"])
        row = dict(inst, cell=cell, placed=cell not in gen.NO_DRAWN_CELL)
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


def _orient(seg):
    x1, y1, x2, y2 = seg
    if y1 == y2:
        return ("H", y1, min(x1, x2), max(x1, x2))
    assert x1 == x2, seg
    return ("V", x1, min(y1, y2), max(y1, y2))


def _pt_seg(p, seg) -> float:
    (px, py), (x1, y1, x2, y2) = p, seg
    o, v, lo, hi = _orient(seg)
    if o == "H":
        cx = max(lo, min(hi, px))
        return ((px - cx) ** 2 + (py - v) ** 2) ** 0.5
    cy = max(lo, min(hi, py))
    return ((px - v) ** 2 + (py - cy) ** 2) ** 0.5


def _seg_dist(a, b) -> float:
    """Exact minimum distance between two axis-aligned closed segments."""
    oa, va, lo_a, hi_a = _orient(a)
    ob, vb, lo_b, hi_b = _orient(b)
    if oa == "H" and ob == "V":
        if lo_a <= vb <= hi_a and lo_b <= va <= hi_b:
            return 0.0
    if oa == "V" and ob == "H":
        if lo_b <= va <= hi_b and lo_a <= vb <= hi_a:
            return 0.0
    best = float("inf")
    for p in ((a[0], a[1]), (a[2], a[3])):
        best = min(best, _pt_seg(p, b))
    for p in ((b[0], b[1]), (b[2], b[3])):
        best = min(best, _pt_seg(p, a))
    return best


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


def padring_block(pads: list[dict], strip_id: str) -> dict:
    strip_pads = [pad for pad in pads if PADRING_STRIPS[strip_id](pad)]
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
    for strip_id in PADRING_STRIPS:
        pads_gds = workdir / f"{strip_id}.gds"
        draw_req = padring_block(pads, strip_id)
        r = subprocess.run(
            ["klt", "draw", "--params", json.dumps(draw_req),
             "--cell-name", strip_id, "-o", str(pads_gds), "--format", "json"],
            capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"klt draw failed ({r.returncode}):\n{r.stdout}{r.stderr}")
        ports = padring_ports(pads)
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

    out = [
        "* LVS reference for layout/run3_top/run3_top.gds -- DERIVED, do not edit.",
        "* Generated by layout/run3_top/assemble_run3_top.py from the #275",
        "* generator's tables (import generate_run3_top), restricted to the",
        "* instances this assembly can place:",
        "*",
        f"*   excluded (no drawn cell, {gen.NO_DRAWN_CELL}, #296/#299):",
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
    placed_cells = sorted({r["cell"] for r in rows if r["placed"]})
    for cand, acc, cap in gen._geometry_points():
        name = gen.cell_name(cand, acc, cap)
        if name in placed_cells:
            out.append(gen._cell_subckt(cand, acc, cap))
            out.append("")
    out.append("* ---- top: 31 placed instances, 40 connected ports ----")
    out.append("")
    out.append(".subckt run3_top " + " ".join(ports))
    last_group = None
    for row in rows:
        if not row["placed"]:
            continue
        if row["group"] != last_group:
            cand = row["candidate"]
            sub = "A2x" if row["access"] == "A2x" else "Amin"
            bl = f"BL_C1_{sub}" if cand == "C1" else f"BL_{cand}_Amin"
            wl = bl.replace("BL_", "WL_")
            vb = gen.VBW_NET if cand == "C3" else SUBSTRATE_NET
            out.append(f"* Group {row['group']}: shared {bl} / {wl}, private PL"
                       f" per instance, bodies to {vb}.")
            last_group = row["group"]
        vb = gen.VBW_NET if row["candidate"] == "C3" else SUBSTRATE_NET
        out.append(f"{row['name']} {bl} {wl} {row['signal']} {vb} {row['cell']}")
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
        reference = emit_lvs_reference(rows)
        new = {"run3_top.gds": out_gds.read_bytes(),
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
    print(f"placed 31 instances; excluded (no drawn cell): {excluded}")


if __name__ == "__main__":
    main()
