#!/usr/bin/env python3
"""Pin quoted geometry intervals in layout/README.md to the committed GDS.

Three landed defects (#378, #391, #401) shared one shape: a prose geometry
number in a design-record README drifted from the committed artifact it
claims to quote, and nothing in the repo compared the two -- `npm run
check:ci` stayed green on both the defective and the corrected text. This
check closes that gap for the pilot claims recorded in
layout/geometry-claims.json (issue #407): the VB-strap north bands and cap
gate pads quoted by the candidate-1 and candidate-3 bullets.

Each claim pins BOTH ends of the quotation:

  * the prose end -- `readme_quote` must appear in layout/README.md
    (whitespace-normalised, so a markdown line-wrap inside the span is not
    a drift). Editing the sentence away from the pinned text, or updating
    the sidecar without the prose, fails;
  * the artifact end -- the committed GDS layout/<cell>/<cell>.gds must
    still contain, on `layer` inside `subcell`, a shape (raw shape or
    merged polygon) whose bbox equals `bbox_um` within `tolerance_um`.

Since issue #414 a claim may also pin the CORRESPONDENCE between those
ends: an optional per-claim `quote_values` maps bbox_um component names
(`left`, `bottom`, `right`, `top`) to indices into the `bbox_um` array
(e.g. {"bottom": 1, "top": 3}); the quote must then spell each consecutive
named pair as an adjacent `<num>..<num>` range -- whitespace-padded, a
`+ SYMBOL` offset decoration tolerated so the cand3 quotes' `2.49 + DPAD
.. 2.91 + DPAD` form is read as the pair (2.49, 2.91) -- with both
numerals equal to the indexed components within `tolerance_um`. Editing
README and the sidecar quote to the same wrong text therefore no longer
passes while `bbox_um` stays at the measured values, and keeping only the
sibling interval's numerals in a shared quote fails the dropped band's
claim. Since issue #419 the field is also mandatory wherever the quote
demonstrably spells an interval: a claim that omits `quote_values` while
its quote contains any adjacent `<num>..<num>` pair fails a coverage
guard -- deleting the field was otherwise the one-line "fix" to the
quote_values failure text that re-opened the #414 bypass a level up
(three-file coordinated edit: README prose, sidecar quote, deleted
field). Only a quote that pins no interval may omit the field, and such
claims behave exactly as before #414.

Measurement runs `klayout -b` (the repo has no klayout Python module) over
merged metal1-style regions exactly as the issue's hand re-derivation did.
A claim whose GDS, subcell, layer or bbox no longer resolves is a failure
naming the entry -- a stale record is a failure, not a pass; when a
geometry change deliberately lands, restate the entry (bbox and, if the
sentence moved, readme_quote) in the same commit.

Exit status: 0 = every claim verified at both ends; 1 = any claim failure
(each named on stdout); 2 = could not run (missing or malformed record,
missing README, klayout binary absent or failing -- the check fails closed,
it never skips). Stdlib only; run with `python3 -I`. Issues #407, #414,
#419.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RECORD = "layout/geometry-claims.json"
README = "layout/README.md"
SCHEMA = "layout-geometry-claims/1"
DEFAULT_TOLERANCE_UM = 0.001
KAYOUT_TIMEOUT_S = 120

LAYER_RE = re.compile(r"^(\d+)/(\d+)$")
WS_RE = re.compile(r"\s+")
REQUIRED_FIELDS = ("id", "cell", "subcell", "layer", "role", "bbox_um", "readme_quote")
COMPONENTS = ("left", "bottom", "right", "top")

# Numerals inside a readme_quote, for the quote_values correspondence end
# (issue #414). The '..' range separator is NOT part of a number: a token
# regex must not eat it as a decimal point.
NUM_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?")
# Between-text of an adjacent '<num>..<num>' pair: the '..' separator,
# optionally whitespace-padded, optionally carrying an offset decoration.
# Both decoration orders occur in the pilot quotes: '+ SYMBOL' before '..'
# (the cand3 raised-ring bands spell '2.49 + DPAD .. 2.91 + DPAD', the pair
# (2.49, 2.91)) and 'SYMBOL +' after '..' (the cand3 gate pad spells
# 'DX+0.43..DX+0.85', the pair (0.43, 0.85)).
RANGE_SEP_RE = re.compile(r"\s*(?:\+\s*[A-Za-z_]\w*\s*)?\.\.(?:\s*[A-Za-z_]\w*\s*\+)?\s*")

# Runs inside `klayout -b` (pya). REQUEST (base64 JSON) carries the GDS path
# and the (subcell, layer) probes; stdout carries the measurement back.
MEASURE_PY = r"""
import base64
import json
import pya

REQUEST = json.loads(base64.b64decode("__REQUEST_B64__"))
ly = pya.Layout()
ly.read(REQUEST["gds"])
dbu = ly.dbu
tops = ly.top_cells()
if len(tops) != 1:
    raise SystemExit("expected exactly one top cell, found %d" % len(tops))
top = tops[0]
result = {"gds": REQUEST["gds"], "dbu": dbu, "probes": {}}
for probe in REQUEST["probes"]:
    name, lp = probe["subcell"], probe["layer_pair"]
    key = probe["key"]
    li = ly.layer(lp[0], lp[1])
    region = pya.Region()
    found = False

    def walk(cell, tf):
        global found
        for inst in cell.each_inst():
            child = inst.cell
            child_tf = tf * inst.trans
            if child.name == name:
                found = True
                for sh in child.shapes(li).each():
                    region.insert(sh.polygon.transformed(child_tf))
            walk(child, child_tf)

    walk(top, pya.Trans())
    entry = {"found": found, "raw": [], "merged": []}
    if found:
        for poly in region.each():
            b = poly.bbox()
            entry["raw"].append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
        for poly in region.merged().each():
            b = poly.bbox()
            entry["merged"].append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
    result["probes"][key] = entry
print(json.dumps(result))
"""


class CannotRun(Exception):
    """Exit-2 class: the check could not execute at all."""


def normalize_ws(text: str) -> str:
    """Collapse every whitespace run (incl. markdown line-wraps) to one space."""
    return WS_RE.sub(" ", text).strip()


def bbox_matches(candidate: list[float], claimed: list[float], tol: float) -> bool:
    return len(candidate) == 4 and all(
        abs(a - b) <= tol for a, b in zip(candidate, claimed)
    )


def parse_layer(spec: str) -> tuple[int, int]:
    m = LAYER_RE.match(spec)
    if not m:
        raise ValueError(f"layer {spec!r} is not 'layer/datatype' (e.g. '34/0')")
    return int(m.group(1)), int(m.group(2))


def quote_range_pairs(quote: str) -> list[tuple[float, float]]:
    """Adjacent '<num>..<num>' pairs in `quote`, as (float, float) in order.

    Tokens are every decimal number; a pair is two consecutive tokens whose
    between-text is just the '..' range separator (whitespace-padded, a
    '+ SYMBOL' offset decoration tolerated). Prose neighbours like
    '2.91 or 2.91' or '3.70 = 2.49' are not pairs.
    """
    toks = [(m.start(), m.end(), float(m.group())) for m in NUM_TOKEN_RE.finditer(quote)]
    pairs: list[tuple[float, float]] = []
    for a, b in zip(toks, toks[1:]):
        if RANGE_SEP_RE.fullmatch(quote[a[1]:b[0]]):
            pairs.append((a[2], b[2]))
    return pairs


def quote_spells_range(quote: str, v1: float, v2: float, tol: float) -> bool:
    """True when some adjacent pair in `quote` equals (v1, v2) within `tol`."""
    return any(abs(a - v1) <= tol and abs(b - v2) <= tol for a, b in quote_range_pairs(quote))


def load_record(root: Path) -> tuple[dict, list[dict], float]:
    path = root / RECORD
    if not path.is_file():
        raise CannotRun(f"{RECORD} not found under --root {root}")
    try:
        rec = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise CannotRun(f"{RECORD} is not valid JSON: {e}")
    if not isinstance(rec, dict) or rec.get("schema") != SCHEMA:
        raise CannotRun(f"{RECORD} schema must be {SCHEMA!r}")
    claims = rec.get("claims")
    if not isinstance(claims, list) or not claims:
        raise CannotRun(f"{RECORD} has no claims list")
    tol = rec.get("tolerance_um", DEFAULT_TOLERANCE_UM)
    if not isinstance(tol, (int, float)) or tol < 0:
        raise CannotRun(f"{RECORD} tolerance_um must be a non-negative number")
    seen: set[str] = set()
    for c in claims:
        if not isinstance(c, dict):
            raise CannotRun(f"{RECORD} claim entry is not an object")
        for field in REQUIRED_FIELDS:
            if field not in c:
                raise CannotRun(f"{RECORD} claim missing field {field!r}")
        if c["id"] in seen:
            raise CannotRun(f"{RECORD} duplicate claim id {c['id']!r}")
        seen.add(c["id"])
        for field in ("cell", "subcell", "role", "readme_quote"):
            if not isinstance(c[field], str) or not c[field]:
                raise CannotRun(f"{RECORD} claim {c['id']!r}: {field} must be a non-empty string")
        try:
            parse_layer(c["layer"])
        except ValueError as e:
            raise CannotRun(f"{RECORD} claim {c['id']!r}: {e}")
        bbox = c["bbox_um"]
        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
            or not all(isinstance(v, (int, float)) and v == v for v in bbox)
        ):
            raise CannotRun(f"{RECORD} claim {c['id']!r}: bbox_um must be 4 numbers [left, bottom, right, top]")
        qvals = c.get("quote_values")
        if qvals is not None:
            if not isinstance(qvals, dict) or not qvals:
                raise CannotRun(
                    f"{RECORD} claim {c['id']!r}: quote_values must be a non-empty object "
                    f"mapping bbox_um component names to indices"
                )
            if len(qvals) < 2:
                raise CannotRun(
                    f"{RECORD} claim {c['id']!r}: quote_values must name at least two "
                    f"components (a '<a>..<b>' range); got {sorted(qvals)}"
                )
            for name, idx in qvals.items():
                if name not in COMPONENTS:
                    raise CannotRun(
                        f"{RECORD} claim {c['id']!r}: quote_values key {name!r} is not a "
                        f"bbox_um component (one of {', '.join(COMPONENTS)})"
                    )
                if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx <= 3:
                    raise CannotRun(
                        f"{RECORD} claim {c['id']!r}: quote_values[{name!r}]={idx!r} names a "
                        f"component absent from bbox_um (must be an index into the 4-element array)"
                    )
    return rec, claims, float(tol)


def measure_gds(klayout: str, gds: Path, probes: list[dict]) -> dict:
    """Run the embedded pya probe script; return its parsed JSON output."""
    request = {"gds": str(gds), "probes": probes}
    b64 = base64.b64encode(json.dumps(request).encode()).decode()
    with tempfile.NamedTemporaryFile("w", suffix="_measure.py", delete=False) as f:
        f.write(MEASURE_PY.replace("__REQUEST_B64__", b64))
        script = f.name
    try:
        proc = subprocess.run(
            [klayout, "-b", "-r", script],
            capture_output=True,
            text=True,
            timeout=KAYOUT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        raise CannotRun(f"klayout timed out after {KAYOUT_TIMEOUT_S}s measuring {gds}")
    finally:
        Path(script).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise CannotRun(f"klayout failed on {gds} (exit {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
    parsed = None
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            break
    if parsed is None or "probes" not in parsed:
        raise CannotRun(f"klayout produced no measurement JSON for {gds}: {proc.stdout.strip()!r}")
    return parsed


def check_claims(klayout: str, root: Path, claims: list[dict], readme_norm: str, tol: float) -> list[str]:
    failures: list[str] = []
    by_cell: dict[str, list[dict]] = {}
    for c in claims:
        by_cell.setdefault(c["cell"], []).append(c)

    for cell, entries in sorted(by_cell.items()):
        gds = root / "layout" / cell / f"{cell}.gds"
        probes: dict[str, dict] = {}
        for c in entries:
            key = f"{c['subcell']}|{c['layer']}"
            if key not in probes:
                probes[key] = {
                    "key": key,
                    "subcell": c["subcell"],
                    "layer_pair": list(parse_layer(c["layer"])),
                }
        if not gds.is_file():
            for c in entries:
                failures.append(f"{c['id']}: GDS not found at {gds.relative_to(root)}")
            continue
        measured = measure_gds(klayout, gds, list(probes.values()))["probes"]

        for c in entries:
            quote = normalize_ws(c["readme_quote"])
            if quote not in readme_norm:
                failures.append(
                    f"{c['id']}: readme_quote not found in {README} "
                    f"(whitespace-normalised): {quote!r}"
                )
            pairs = quote_range_pairs(quote)
            qvals = c.get("quote_values")
            if qvals:
                named = sorted(qvals.items(), key=lambda kv: kv[1])
                for (n1, i1), (n2, i2) in zip(named, named[1:]):
                    if not quote_spells_range(quote, c["bbox_um"][i1], c["bbox_um"][i2], tol):
                        failures.append(
                            f"{c['id']}: quote_values: {README} quote does not spell "
                            f"bbox_um {n1} ({c['bbox_um'][i1]}) .. {n2} ({c['bbox_um'][i2]}) "
                            f"as an adjacent '<num>..<num>' pair within {tol} um; "
                            f"pairs found in quote: {pairs}"
                        )
            elif pairs:
                # Coverage guard (#419): a quote that demonstrably spells an
                # interval must pin it. Deleting quote_values while the quote
                # still spells a pair would otherwise re-open the #414
                # coordinated-edit bypass one level up.
                failures.append(
                    f"{c['id']}: coverage guard: readme_quote spells the '<num>..<num>' "
                    f"pair(s) {pairs} but the claim omits quote_values, so the quote's "
                    f"numerals are not pinned to bbox_um (#419); deleting the field "
                    f"re-opens the #414 coordinated-edit bypass. Add quote_values naming "
                    f"the bbox_um components the quote spells (e.g. "
                    f'{{"bottom": 1, "top": 3}}), or reword the quote to prose that '
                    f"pins no interval"
                )
            key = f"{c['subcell']}|{c['layer']}"
            probe = measured.get(key, {"found": False, "raw": [], "merged": []})
            if not probe["found"]:
                failures.append(
                    f"{c['id']}: subcell {c['subcell']!r} not found in {gds.relative_to(root)}"
                )
                continue
            candidates = probe["raw"] + probe["merged"]
            if not candidates:
                failures.append(
                    f"{c['id']}: layer {c['layer']} has no shapes in subcell "
                    f"{c['subcell']!r} of {gds.relative_to(root)}"
                )
                continue
            if not any(bbox_matches(cand, c["bbox_um"], tol) for cand in candidates):
                failures.append(
                    f"{c['id']}: bbox differs from GDS: claimed {c['bbox_um']} um, "
                    f"no raw or merged {c['layer']} shape in {c['subcell']!r} matches "
                    f"within {tol} um; measured candidates: {sorted(candidates)}"
                )
    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT), help="repo root (default: the repo containing this script)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        _rec, claims, tol = load_record(root)
        readme_path = root / README
        if not readme_path.is_file():
            raise CannotRun(f"{README} not found under --root {root}")
        readme_norm = normalize_ws(readme_path.read_text())
        klayout = shutil.which("klayout")
        if not klayout:
            raise CannotRun("klayout not found on PATH; cannot measure the committed GDS (fails closed)")
        failures = check_claims(klayout, root, claims, readme_norm, tol)
    except CannotRun as e:
        print(f"cannot run: {e}", file=sys.stderr)
        return 2

    for f in failures:
        print(f"FAIL {f}")
    print(f"{len(claims)} geometry claims checked, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
