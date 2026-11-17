#!/usr/bin/env python3
"""Check the run3 chip-level artifacts against the spec sources that bind them.

Against the committed files (issue #275), verifies that:

  1. layout/run3_top/pad_table.json matches the pad table parsed from
     spec/run3-test-chip-floorplan.md -- every pad id, signal, direction,
     slot type and voltage class, the record's slot-type totals
     (38 bidirectional / 6 input-only / 4 analog) and voltage-class totals
     (36 HV / 9 standard / 3 n/a);
  2. every port of the top ``run3_top`` subckt in
     layout/run3_top/run3_top.spice has a pad. One-directional by design:
     UNUSED_1..3 are pads with no netlist port and must not fail;
  3. the netlist's per-cell geometry matches the source that binds each
     half -- capacitor W/L against the Decision table of
     spec/capacitor-geometry-decision.md (binding), access W/L against the
     drawn XM1 literals of the committed layout/cell_*/lvs_reference.spice.

The capacitor half deliberately disagrees with all seven committed drawn
cells until #296 lands; that expected disagreement is NOT checked here.
design/check-geometry-basis.py owns the design <-> layout geometry boundary.

Stdlib only. Exit 0 clean, 1 on any failure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FLOORPLAN = "spec/run3-test-chip-floorplan.md"
DECISION = "spec/capacitor-geometry-decision.md"
PAD_TABLE = "layout/run3_top/pad_table.json"
NETLIST = "layout/run3_top/run3_top.spice"
TOP = "run3_top"

# spec/run3-test-chip-floorplan.md "Pad table" totals.
SLOT_TOTALS = {"bidir": 38, "input-only": 6, "analog": 4}
VOLT_TOTALS = {"HV": 36, "standard": 9, "n/a": 3}

DIRECTIONS = {"bidir", "analog", "input", "none"}
SLOT_TYPES = {"bidir", "analog", "input-only"}
VOLT_CLASSES = {"HV", "standard", "n/a"}

PAD_ID_RE = re.compile(r"^L\d{2}$")
# spec/capacitor-geometry-decision.md "Decision" table row:
# | I | `cap_nmos_03v3` | 1.0 x 0.28 | 0.28 | 2.0 x 0.28 | 0.56 | 2.000 |
DECISION_ROW_RE = re.compile(
    r"^\|\s*(?P<region>I|II|III)\s*\|\s*`(?P<device>[a-z0-9_]+)`\s*\|"
    r"\s*(?P<min_w>[0-9.]+)\s*x\s*(?P<min_l>[0-9.]+)\s*\|\s*[0-9.]+\s*\|"
    r"\s*(?P<x2_w>[0-9.]+)\s*x\s*(?P<x2_l>[0-9.]+)\s*\|")
# Region map of spec/split-axis-plan.md: I = Candidate 1, II = 2, III = 3.
REGION_OF_CANDIDATE = {"1": "I", "2": "II", "3": "III"}
CAP_LEVEL_OF_NAME = {"min": "Minimum", "2x": "2x-area"}
CELL_RE = re.compile(r"^cell_candidate(\d)(_.*)?$")
# Drawn cells with no chip counterpart and no XM1 access line, by design:
# the Run 3 C2-fallback variant (#372, spec/run3-c2-fallback-proposed.md)
# is bare capacitors -- it exists on the chip only if the operator adopts
# the fallback for submission (#203), and its run3_top generator variant is
# recorded work-left-to-GDS, not a drift of this check's invariant. Its
# capacitor literals bind to spec/capacitor-geometry-decision.md through
# the cell's own generator `--check` hash and LVS, not through run3_top.
FALLBACK_CELLS = {"cell_candidate2_fallback"}


def _num(token: str) -> float:
    """'0.70u' -> 0.70."""
    return float(token.rstrip("u"))


def parse_floorplan_pads(text: str) -> tuple[list[dict], list[str]]:
    """Parse the record's pad table.

    Keys on the ``L\\d\\d`` pad-id column, so the record's other Markdown
    tables (instance counts, core-area budget) are not absorbed. Returns
    (rows, errors); structural "no rows at all" is a CheckError, everything
    else accumulates so one run reports every drifted aspect."""
    errs: list[str] = []
    rows: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 6 or not PAD_ID_RE.match(cells[0]):
            continue
        direction = cells[2].split()[0].lower() if cells[2] else ""
        slot = cells[3].replace(" slot", "").lower()
        volt = cells[4]
        row = {"pad": cells[0], "signal": cells[1].strip("`"),
               "direction": direction, "slot_type": slot, "voltage_class": volt}
        where = f"{FLOORPLAN}:{lineno} pad {row['pad']}"
        if direction not in DIRECTIONS:
            errs.append(f"{where}: unrecognized direction '{cells[2]}'")
        if slot not in SLOT_TYPES:
            errs.append(f"{where}: unrecognized slot type '{cells[3]}'")
        if volt not in VOLT_CLASSES:
            errs.append(f"{where}: unrecognized voltage class '{volt}'")
        rows.append(row)
    if not rows:
        raise CheckError([f"{FLOORPLAN}: no pad table rows found (keyed on the "
                          "L\\d\\d pad-id column)"])
    return rows, errs


def pad_id_completeness_errors(record: list[dict]) -> list[str]:
    ids = [r["pad"] for r in record]
    expected = [f"L{i:02d}" for i in range(1, 49)]
    if ids == expected:
        return []
    missing = sorted(set(expected) - set(ids))
    unexpected = sorted(set(ids) - set(expected))
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    return [f"{FLOORPLAN}: pad ids are not exactly L01-L48"
            + (f": missing {missing}" if missing else "")
            + (f": unexpected {unexpected}" if unexpected else "")
            + (f": duplicated {dupes}" if dupes else "")]


def parse_netlist(text: str, require_top: bool = True) -> dict:
    """Parse a subckt-call netlist into top ports and per-cell XM1/XC1 device
    lines. The per-cell drawn references have no ``run3_top``; pass
    ``require_top=False`` for those."""
    ports: list[str] = []
    cells: dict[str, dict] = {}
    current: str | None = None
    top_seen = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(".subckt"):
            toks = line.split()
            current = toks[1]
            top_seen += current == TOP
            cells[current] = {"ports": toks[2:], "xm1": None, "xc1": None}
            if current == TOP:
                ports = toks[2:]
        elif line.startswith(".ends"):
            current = None
        elif current is not None and line[:3].upper() in ("XM1", "XC1"):
            key = line[:3].lower()
            cells[current][key] = parse_device_line(line)
    if require_top and top_seen != 1:
        raise CheckError([f"{NETLIST}: expected exactly one .subckt {TOP}, "
                          f"found {top_seen}"])
    return {"ports": ports, "cells": cells}


def parse_device_line(line: str) -> dict:
    """'XM1 BL WL CN VB nfet_06v0 L=0.70u ...' -> device, nodes, params."""
    positional: list[str] = []
    params: dict[str, str] = {}
    for tok in line.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            params[k.lower()] = v
        else:
            positional.append(tok)
    return {"device": positional[-1], "nodes": positional[:-1],
            "params": params}


def check_pad_table(record_text: str, pad_table: dict, netlist_text: str) -> list[str]:
    """The core: committed pad_table.json vs floorplan record vs netlist ports."""
    try:
        record, errs = parse_floorplan_pads(record_text)
    except CheckError as e:
        return e.errors
    errs += pad_id_completeness_errors(record)
    by_pad = {p["pad"]: p for p in pad_table.get("pads", [])}
    if len(by_pad) != len(pad_table.get("pads", [])):
        errs.append(f"{PAD_TABLE}: duplicate pad entries")
    for r in record:
        j = by_pad.get(r["pad"])
        if j is None:
            errs.append(f"pad {r['pad']}: in {FLOORPLAN} but missing from {PAD_TABLE}")
            continue
        for field in ("signal", "direction", "slot_type", "voltage_class"):
            if j.get(field) != r[field]:
                errs.append(f"pad {r['pad']}: {field} {PAD_TABLE} "
                            f"'{j.get(field)}' != record '{r[field]}'")
    for pad, j in sorted(by_pad.items()):
        if pad not in {r["pad"] for r in record}:
            errs.append(f"pad {pad}: in {PAD_TABLE} but missing from {FLOORPLAN}")
    for kind, want in SLOT_TOTALS.items():
        got = sum(1 for r in record if r["slot_type"] == kind)
        if got != want:
            errs.append(f"slot-type totals: record has {got} {kind}, "
                        f"record specifies {want}")
    for kind, want in VOLT_TOTALS.items():
        got = sum(1 for r in record if r["voltage_class"] == kind)
        if got != want:
            errs.append(f"voltage-class totals: record has {got} {kind}, "
                        f"record specifies {want}")
    try:
        ports = parse_netlist(netlist_text)["ports"]
    except CheckError as e:
        return errs + e.errors
    signals = {r["signal"] for r in record}
    for port in ports:
        if port not in signals:
            errs.append(f"netlist port '{port}' has no pad in {FLOORPLAN} "
                        f"or {PAD_TABLE}")
    return errs


def parse_decision_capacitors(text: str) -> dict[str, dict]:
    """Parse the Decision table of the capacitor-geometry record:
    region -> {device, min (w, l), 2x (w, l)} in um."""
    table: dict[str, dict] = {}
    for line in text.splitlines():
        m = DECISION_ROW_RE.match(line)
        if m:
            table[m["region"]] = {
                "device": m["device"],
                "min": (float(m["min_w"]), float(m["min_l"])),
                "2x": (float(m["x2_w"]), float(m["x2_l"])),
            }
    if not table:
        raise CheckError([f"{DECISION}: Decision table not found"])
    return table


def check_geometry(netlist_text: str, decision_text: str,
                   drawn_cells: dict[str, str]) -> list[str]:
    """Each geometry half against the source that binds it (issue #275
    Implementation Guidance item 4)."""
    errs: list[str] = []
    net = parse_netlist(netlist_text)
    try:
        decision = parse_decision_capacitors(decision_text)
    except CheckError as e:
        return e.errors
    chip_cells = {n: c for n, c in net["cells"].items() if n != TOP}

    # --- capacitor half: ratified levels of the decision record ---
    for name in sorted(chip_cells):
        m = CELL_RE.match(name)
        if not m:
            errs.append(f"{name}: cell name does not match the "
                        "cell_candidate<N>[_level] convention")
            continue
        xc1 = chip_cells[name]["xc1"]
        if xc1 is None:
            errs.append(f"{name}: no XC1 capacitor line")
            continue
        region = REGION_OF_CANDIDATE[m.group(1)]
        want = decision.get(region)
        if want is None:
            errs.append(f"{name}: no Decision row for region {region} in {DECISION}")
            continue
        level = "2x" if "_G2x" in name else "min"
        w, l = want[level]
        got_dev = xc1["device"]
        if got_dev != want["device"]:
            errs.append(f"{name}: capacitor device '{got_dev}' != ratified "
                        f"'{want['device']}' (region {region}, {DECISION})")
        params = xc1["params"]
        got_w, got_l = params.get("c_width"), params.get("c_length")
        if got_w is None or got_l is None:
            errs.append(f"{name}: capacitor line missing c_width/c_length")
        else:
            try:
                if _num(got_w) != w or _num(got_l) != l:
                    errs.append(f"{name}: capacitor c_width={got_w} "
                                f"c_length={got_l} != ratified {level} "
                                f"{w:g} x {l:g} um (region {region}, "
                                f"{CAP_LEVEL_OF_NAME[level]}, {DECISION})")
            except ValueError:
                errs.append(f"{name}: unparsable capacitor geometry "
                            f"c_width={got_w} c_length={got_l}")

    # --- access half: drawn XM1 literals of the committed cells ---
    for name in sorted(drawn_cells):
        if name in FALLBACK_CELLS:
            continue  # bare-capacitor fallback (#372): no XM1, no chip cell yet
        drawn = parse_netlist(drawn_cells[name],
                              require_top=False)["cells"].get(name)
        if drawn is None:
            errs.append(f"{name}: drawn reference has no .subckt {name}")
            continue
        ref = drawn["xm1"]
        if name not in chip_cells:
            errs.append(f"{name}: drawn cell has no subckt in {NETLIST}")
            continue
        got = chip_cells[name]["xm1"]
        if got is None or ref is None:
            errs.append(f"{name}: missing XM1 access line "
                        f"({'netlist' if got is None else 'drawn reference'})")
            continue
        if got["device"] != ref["device"]:
            errs.append(f"{name}: access device '{got['device']}' != drawn "
                        f"'{ref['device']}' (layout/{name}/lvs_reference.spice)")
        for param in ("l", "w", "nf"):
            a, b = got["params"].get(param), ref["params"].get(param)
            if a is None or b is None:
                errs.append(f"{name}: access XM1 missing {param}= "
                            f"(netlist: {a}, drawn: {b})")
                continue
            try:
                if _num(a) != _num(b):
                    errs.append(f"{name}: access {param}={a} != drawn {param}={b} "
                                f"(layout/{name}/lvs_reference.spice)")
            except ValueError:
                errs.append(f"{name}: unparsable access {param} ({a} vs {b})")

    # --- cell-set guard: every chip cell without a drawn counterpart must be
    # a known no-drawn-cell point, not a silent new cell ---
    no_drawn_expected = {"cell_candidate2_Amin_G2x"}
    unbacked = sorted(set(chip_cells) - set(drawn_cells))
    if unbacked != sorted(no_drawn_expected):
        errs.append(f"chip cells with no committed drawn cell: {unbacked} != "
                    f"the expected {sorted(no_drawn_expected)} "
                    "(#296/#299 own the missing layout)")
    return errs


class CheckError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def run_checks(root: Path) -> list[str]:
    missing = [str(root / p) for p in (FLOORPLAN, DECISION, PAD_TABLE, NETLIST)
               if not (root / p).is_file()]
    if missing:
        return [f"missing committed file: {m}" for m in missing]
    errs = check_pad_table((root / FLOORPLAN).read_text(),
                           json.loads((root / PAD_TABLE).read_text()),
                           (root / NETLIST).read_text())
    drawn = {p.parent.name: p.read_text()
             for p in sorted((root / "layout").glob("cell_*/lvs_reference.spice"))}
    return errs + check_geometry((root / NETLIST).read_text(),
                                 (root / DECISION).read_text(), drawn)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="repository root (default: this script's repo)")
    args = ap.parse_args(argv)
    errs = run_checks(args.root)
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
