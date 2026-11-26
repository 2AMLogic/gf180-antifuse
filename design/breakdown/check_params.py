#!/usr/bin/env python3
"""design/breakdown/check_params.py -- provenance and drift checks for the
behavioral breakdown model (issue #62).

    python3 design/breakdown/check_params.py

Fails (exit 1) if any of these is violated:

1. Every ``.param`` in ``breakdown_params.spice`` is immediately preceded by
   exactly one ``* @param <name> unit=<u> provenance=<label> -- <note>``
   annotation naming the same parameter, with a non-empty unit and note.
2. ``<label>`` is one of ``assumed`` / ``literature`` / ``measured``.
3. Nothing is labelled ``measured`` while ``measurements/`` holds no data
   (i.e. nothing but README files).
4. ``af_breakdown.spice`` and ``cell_candidates_bd.spice`` declare no
   ``.param`` of their own with a numeric literal -- all model numbers live
   in the one labelled file (subcircuit-line switch defaults and the
   geometry pass-through defaults are checked separately below).
5. Each ``cell_candidateN_bd`` wrapper's wcap/lcap/wacc/lacc defaults equal
   the committed ``design/netlists/cell_candidateN.spice`` defaults, so the
   wrapper cannot silently drift from the schematic-derived netlist.

stdlib only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PARAMS = HERE / "breakdown_params.spice"
ELEMENT = HERE / "af_breakdown.spice"
WRAPPERS = HERE / "cell_candidates_bd.spice"
NETLISTS = REPO / "design" / "netlists"
MEASUREMENTS = REPO / "measurements"

LABELS = ("assumed", "literature", "measured")
ANNOT_RE = re.compile(
    r"^\*\s*@param\s+(?P<name>\w+)\s+unit=(?P<unit>\S+)\s+provenance=(?P<prov>\S+)\s+--\s+(?P<note>\S.*)$"
)
PARAM_RE = re.compile(r"^\.param\s+(?P<name>\w+)\s*=\s*(?P<value>\S+)\s*$", re.IGNORECASE)
GEOM_KEYS = ("wcap", "lcap", "wacc", "lacc")


def parse_params(text: str) -> tuple[dict[str, dict], list[str]]:
    """Return ({name: {value, unit, provenance, note}}, [errors])."""
    errors: list[str] = []
    params: dict[str, dict] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.lower().startswith(".param"):
            continue
        m = PARAM_RE.match(line.strip())
        if not m:
            errors.append(f"{PARAMS.name}:{i+1}: .param must be one `name = value` per line: {line!r}")
            continue
        name = m.group("name")
        prev = lines[i - 1] if i > 0 else ""
        a = ANNOT_RE.match(prev.strip())
        if not a:
            errors.append(f"{PARAMS.name}:{i+1}: .param {name} has no `* @param` annotation on the line above")
            continue
        if a.group("name") != name:
            errors.append(f"{PARAMS.name}:{i+1}: annotation names {a.group('name')!r} but .param is {name!r}")
            continue
        prov = a.group("prov")
        if prov not in LABELS:
            errors.append(f"{PARAMS.name}:{i+1}: {name}: provenance {prov!r} not in {LABELS}")
        if name in params:
            errors.append(f"{PARAMS.name}:{i+1}: {name} defined twice")
        try:
            value = float(m.group("value"))
        except ValueError:
            errors.append(f"{PARAMS.name}:{i+1}: {name}: value {m.group('value')!r} is not a plain number")
            value = None
        params[name] = {"value": value, "unit": a.group("unit"), "provenance": prov, "note": a.group("note")}
    # every annotation must be followed by its .param
    for i, line in enumerate(lines):
        if ANNOT_RE.match(line.strip()):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.lower().startswith(".param"):
                errors.append(f"{PARAMS.name}:{i+1}: dangling `* @param` annotation (no .param on the next line)")
    return params, errors


def read_param_values(path: Path = PARAMS) -> dict[str, float]:
    """Read the numeric values or raise ValueError with all parser diagnostics."""
    params, errors = parse_params(path.read_text())
    if errors:
        raise ValueError("\n".join(errors))
    return {name: param["value"] for name, param in params.items()}


def measurements_have_data() -> bool:
    if not MEASUREMENTS.is_dir():
        return False
    for p in MEASUREMENTS.rglob("*"):
        if p.is_file() and p.name.lower() != "readme.md":
            return True
    return False


def subckt_defaults(text: str, subckt: str) -> dict[str, str]:
    """Collect key=value defaults from a .subckt line and its + continuations."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^\.subckt\s+{re.escape(subckt)}\s", line, re.IGNORECASE):
            chunk = [line]
            j = i + 1
            while j < len(lines) and lines[j].startswith("+"):
                chunk.append(lines[j][1:])
                j += 1
            return dict(re.findall(r"(\w+)=(\S+)", " ".join(chunk)))
    raise ValueError(f"subckt {subckt} not found")


def main() -> int:
    errors: list[str] = []

    params, perr = parse_params(PARAMS.read_text())
    errors += perr
    if not params:
        errors.append(f"{PARAMS.name}: no parameters found")

    measured = [n for n, p in params.items() if p["provenance"] == "measured"]
    if measured and not measurements_have_data():
        errors.append(
            f"labelled `measured` but measurements/ holds no data: {', '.join(measured)}"
        )

    for f in (ELEMENT, WRAPPERS):
        for i, line in enumerate(f.read_text().splitlines()):
            m = re.match(r"^\.param\s+(\w+)\s*=\s*(.*)$", line.strip(), re.IGNORECASE)
            if m and re.search(r"(?<![\w.])\d", m.group(2)):
                # expressions over subckt parameters are fine; numeric
                # literals other than the structural ln(2)/1 in the Weibull
                # quantile and the 1 in (1-ubd) are not.
                literal_free = re.sub(r"\bln\(2\)|\b1/beta\b|\(1-ubd\)|\b1/\(1-ubd\)", "", m.group(2))
                if re.search(r"(?<![\w.])\d", literal_free):
                    errors.append(f"{f.name}:{i+1}: .param {m.group(1)} carries a numeric literal; move it to {PARAMS.name}")

    wtext = WRAPPERS.read_text()
    for n in (1, 2, 3):
        try:
            wdef = subckt_defaults(wtext, f"cell_candidate{n}_bd")
            ndef = subckt_defaults((NETLISTS / f"cell_candidate{n}.spice").read_text(), f"cell_candidate{n}")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        for k in GEOM_KEYS:
            if wdef.get(k) != ndef.get(k):
                errors.append(
                    f"{WRAPPERS.name}: cell_candidate{n}_bd default {k}={wdef.get(k)!r} != "
                    f"design/netlists/cell_candidate{n}.spice {k}={ndef.get(k)!r}"
                )

    by_label = {lab: sorted(n for n, p in params.items() if p["provenance"] == lab) for lab in LABELS}
    print(f"{PARAMS.relative_to(REPO)}: {len(params)} parameters")
    for lab in LABELS:
        print(f"  {lab:10s} {len(by_label[lab]):2d}  {' '.join(by_label[lab])}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("OK: every parameter labelled; no `measured` without data; wrappers match netlist defaults.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
