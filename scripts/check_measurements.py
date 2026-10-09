#!/usr/bin/env python3
"""Format check for measurements/ records (spec/measurement-matrix.md).

Fails on any record that pools replicates across candidate regions or split
axes, and on malformed / inconsistent records. Stdlib only.

Usage:
    scripts/check_measurements.py [--base REF] [PATH ...]

PATH may be record files or directories (default: measurements/records).
--base REF additionally enforces the append-only rule: any file under the
checked directories that exists at REF must be unchanged (not modified,
renamed or deleted) in the working tree / HEAD.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

N = 32  # spec/split-axis-plan.md (ratified working target)
REGIONS = {"I": "1", "II": "2", "III": "3"}  # region -> candidate
GEOMETRY = {"min", "2x"}
SIZING = {"min", "2x"}
EXPECTED = {"programmed", "unprogrammed"}
POOL_WORDS = {"all", "any", "pooled", "pool", "aggregate", "aggregated",
              "mixed", "avg", "average", "mean", "total", "both", "n/a", "na",
              "none", "*", ""}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PLACEHOLDER_RE = re.compile(r"<[^<>\n]*>")

# quantity -> (tag fields: header name -> table column, outcomes,
#              success outcome(s) counted in k, excluded outcomes)
COMMON_TAGS = {
    "Region": "region",
    "Candidate": "candidate",
    "Capacitor geometry": "geometry",
    "Access sizing": "sizing",
    "Pulse condition": "pulse_condition",
}
QUANTITIES = {
    "yield": {
        "tags": dict(COMMON_TAGS),
        "success": {"programmed"},
        "fail": {"not_programmed"},
        "excluded": {"excluded_preread_high", "excluded_protocol_error"},
    },
    "read_margin": {
        "tags": {**COMMON_TAGS, "Read condition": "read_condition",
                 "Expected state": "expected"},
        "success": {"read_agree"},
        "fail": {"read_flip"},
        "excluded": {"excluded_protocol_error"},
    },
    "retention": {
        "tags": {**COMMON_TAGS, "Stress point": "stress_point",
                 "Expected state": "expected"},
        "success": {"retained"},
        "fail": {"lost"},
        "excluded": {"excluded_protocol_error",
                     "excluded_pre_stress_mismatch"},
    },
}
REQUIRED_COMMON = ["Record ID", "Quantity", "Claim", "Die", "Temperature",
                   "VPP", "PULSE_WIDTH code", "Replicate count",
                   "CI method", "Counts", "Fraction", "CI",
                   "Supersedes", "Timestamp / author"]
FREE_TAG_FIELDS = {"Pulse condition", "Read condition", "Stress point"}

FIELD_RE = re.compile(r"^- \*\*(?P<k>[^*]+)\*\*:\s*(?P<v>.*?)\s*$")


def parse(text: str):
    fields: dict[str, str] = {}
    rows: list[list[str]] = []
    header: list[str] | None = None
    in_table = False
    for line in text.splitlines():
        m = FIELD_RE.match(line)
        if m and not in_table:
            fields[m["k"].strip()] = m["v"].strip().strip("`").strip()
            continue
        if line.startswith("## Per-cell outcomes"):
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                continue
            if header is None:
                header = [c.lower() for c in cells]
            else:
                rows.append(cells)
    return fields, header, rows


def check_text(text: str) -> list[str]:
    errs: list[str] = []
    fields, header, rows = parse(text)

    for k, v in fields.items():
        if PLACEHOLDER_RE.search(v):
            errs.append(f"unfilled placeholder in '{k}': {v}")
    for r in rows:
        if any(PLACEHOLDER_RE.search(c) for c in r):
            errs.append(f"unfilled placeholder in table row: {r}")
    if errs:
        return errs

    q = fields.get("Quantity", "")
    if q not in QUANTITIES:
        return [f"Quantity must be one of {sorted(QUANTITIES)}, got '{q}'"]
    spec = QUANTITIES[q]
    tags: dict[str, str] = spec["tags"]

    for k in REQUIRED_COMMON + list(tags):
        if not fields.get(k):
            errs.append(f"missing required field '{k}'")
    if errs:
        return errs

    # --- header tags: single value each, never a pooled/aggregated value ---
    for k in tags:
        v = fields[k]
        if v.lower() in POOL_WORDS or not ID_RE.match(v):
            errs.append(f"'{k}' = '{v}' looks pooled / multi-valued; a record "
                        "covers exactly one value per split axis")
    region = fields["Region"]
    if region not in REGIONS:
        errs.append(f"Region must be exactly one of {sorted(REGIONS)}, got '{region}'")
    elif fields["Candidate"] != REGIONS[region]:
        errs.append(f"Candidate {fields['Candidate']} does not match Region "
                    f"{region} (expects {REGIONS[region]})")
    if fields["Capacitor geometry"] not in GEOMETRY:
        errs.append(f"Capacitor geometry must be one of {sorted(GEOMETRY)}")
    if fields["Access sizing"] not in SIZING:
        errs.append(f"Access sizing must be one of {sorted(SIZING)}")
    if "Expected state" in tags and fields["Expected state"] not in EXPECTED:
        errs.append(f"Expected state must be one of {sorted(EXPECTED)}")
    if errs:
        return errs

    # --- table ---
    need_cols = ["row", "col", *tags.values(), "outcome"]
    if header is None:
        return ["missing '## Per-cell outcomes' table"]
    if header != need_cols:
        return [f"table columns must be exactly {need_cols}, got {header}"]
    allowed = spec["success"] | spec["fail"] | spec["excluded"]
    seen: set[tuple[int, int]] = set()
    counts = {o: 0 for o in allowed}
    for i, r in enumerate(rows, 1):
        if len(r) != len(header):
            errs.append(f"table row {i}: expected {len(header)} cells, got {len(r)}")
            continue
        d = dict(zip(header, r))
        try:
            rc = (int(d["row"]), int(d["col"]))
        except ValueError:
            errs.append(f"table row {i}: row/col must be integers")
            continue
        if not (0 <= rc[0] < N and 0 <= rc[1] < N):
            errs.append(f"table row {i}: row/col {rc} outside 0..{N - 1}")
        if rc in seen:
            errs.append(f"table row {i}: duplicate cell {rc}")
        seen.add(rc)
        for k, col in tags.items():
            if d[col] != fields[k]:
                errs.append(f"table row {i} (cell {rc}): {col}='{d[col]}' differs "
                            f"from record {k}='{fields[k]}' -- rows pooled "
                            "across splits")
        if d["outcome"] not in allowed:
            errs.append(f"table row {i}: outcome '{d['outcome']}' not in {sorted(allowed)}")
        else:
            counts[d["outcome"]] += 1
    if errs:
        return errs

    # --- replicate count and declared counts ---
    try:
        n = int(fields["Replicate count"])
    except ValueError:
        return ["Replicate count must be an integer"]
    if n != len(rows):
        errs.append(f"Replicate count {n} != {len(rows)} per-cell rows")
    if n < 1:
        errs.append("Replicate count must be >= 1")
    declared: dict[str, int] = {}
    for part in fields["Counts"].split(","):
        m = re.fullmatch(r"\s*([a-z_]+)\s*=\s*(\d+)\s*", part)
        if not m:
            return errs + [f"Counts must look like 'outcome=int, ...', got '{fields['Counts']}'"]
        declared[m[1]] = int(m[2])
    actual = {o: c for o, c in counts.items() if c}
    if {o: c for o, c in declared.items() if c} != actual:
        errs.append(f"declared Counts {declared} != recomputed {actual}")

    k = sum(counts[o] for o in spec["success"])
    n_eff = k + sum(counts[o] for o in spec["fail"])
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", fields["Fraction"])
    if not m:
        errs.append("Fraction must be 'k/n_eff'")
    elif (int(m[1]), int(m[2])) != (k, n_eff):
        errs.append(f"Fraction {fields['Fraction']} != recomputed {k}/{n_eff}")
    m = re.fullmatch(r"\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]", fields["CI"])
    if n_eff == 0:
        if fields["CI"].lower() != "undefined":
            errs.append("CI must be 'undefined' when n_eff = 0")
    elif not m:
        errs.append("CI must be '[lo, hi]'")
    else:
        lo, hi = float(m[1]), float(m[2])
        if not (0 <= lo <= k / n_eff <= hi <= 1):
            errs.append(f"CI [{lo}, {hi}] must satisfy 0 <= lo <= {k}/{n_eff} <= hi <= 1")
    return errs


def collect(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        out += sorted(p.glob("*.md")) if p.is_dir() else [p]
    return [f for f in out if f.name.upper() != "README.MD"]


def check_append_only(base: str, paths: list[Path]) -> list[str]:
    errs: list[str] = []
    dirs = [str(p) for p in paths]
    res = subprocess.run(
        ["git", "diff", "--name-status", "-M", base, "--", *dirs],
        capture_output=True, text=True)
    if res.returncode != 0:
        return [f"git diff against {base} failed: {res.stderr.strip()}"]
    for line in res.stdout.splitlines():
        status, *names = line.split("\t")
        if status[0] != "A":
            errs.append(f"append-only violation ({status}): {' -> '.join(names)}")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", type=Path,
                    default=[Path("measurements/records")])
    ap.add_argument("--base", help="git ref for the append-only check")
    a = ap.parse_args(argv)
    bad = 0
    for f in collect([p for p in a.paths if p.exists()]):
        for e in check_text(f.read_text()):
            print(f"{f}: {e}")
            bad += 1
    if a.base:
        for e in check_append_only(a.base, [p for p in a.paths if p.is_dir()] or a.paths):
            print(e)
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
