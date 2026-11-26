#!/usr/bin/env python3
"""Fail if the generated array netlists drift from the ratified region map.

    design/check-array.py

Reads, and trusts neither of them to agree with the other:
  * spec/split-axis-plan.md      - the ratified region map table (column bands
                                   and the candidate occupying each)
  * design/netlists/*.spice      - the xschem-derived array, slice and cell
                                   netlists

and asserts, per band and per instance:

  1. All N*N cells exist exactly once, in the band the spec puts their column
     in, instantiating that band's candidate (cell_candidateK) - the
     "candidate type" check.
  2. The cell's own wiring is the right row / column / band (BL_<col>,
     WL_<row>_<band>, PL_<row>_<band>).
  3. wcap/lcap/wacc/lacc take exactly two levels per axis per band, derived
     from the committed cell subcircuit's own defaults: "min" = the default,
     capacitor "2x" = 2x wcap at the same lcap, access "2x" = 2x wacc at the
     same lacc. Nothing else (a hand-edited value, a swapped band's geometry)
     is accepted.
  4. The two interleaved sub-axes behave as spec/split-axis-plan.md requires,
     without hard-coding this repo's phase convention: the capacitor level is a
     cell-pitch checkerboard (no orthogonal neighbours share a level), the
     access level never forms a stripe wider than 2 cells (interleaved, not
     contiguous), and all four (capacitor level x access level) combinations
     are present, each within 10% of an even quarter of the band.
  5. The addressing stage is the one the band calls for: the level-shifter and
     pass-gate cell families match the candidate (06 V family for Candidates
     1/3, 10 V asymmetric family for Candidate 2), and each column / row-segment
     has exactly one of each, wired to its own line and band bus.
  6. Access-device orientation is the deliberate one in the derived cell
     netlists: BL on the DRAIN of nfet_06v0 (Candidate 1) and of the asymmetric
     nfet_10v0_asym (Candidate 2 - the drift-extended terminal faces BL, source
     to the cell node), BL on the SOURCE of pfet_06v0 (Candidate 3). Combined
     with check 2 (every cell's first pin is its column's BL_<col> net) this
     is the "Candidate 2 band keeps drain-to-BL orientation" check.
  7. Every slice instance carries the same candidate and parameters as the same
     absolute (row, col) in the full array.

Exit status 0 = no drift, 1 = drift (each violation printed), 2 = could not run.
stdlib only; run with `python3 -I`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DESIGN = Path(__file__).resolve().parent
ROOT = DESIGN.parent
SPEC = ROOT / "spec" / "split-axis-plan.md"
CELL_PARAMS = ("wcap", "lcap", "wacc", "lacc")
sys.path.insert(0, str(ROOT / "sim"))
from harness import numfmt  # noqa: E402
NL = DESIGN / "netlists"
N = 32
SLICES = ("slice_i_ii", "slice_ii_iii")
BAND_LABELS = ("I", "II", "III")

PG_FAMILY = {1: "pg_n06", 2: "pg_n10", 3: "pg_n06"}
LS_FAMILY = {1: "ls_hv06", 2: "ls_hv10", 3: "ls_hv06"}
ACTIVE_LOW = {1: False, 2: False, 3: True}

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


# ---------------------------------------------------------------------------
# Spec: region map
# ---------------------------------------------------------------------------


def parse_region_map() -> list[tuple[str, int, int, int]]:
    """[(label, col_lo, col_hi, candidate)] from the spec's region-map table."""
    rows = []
    for line in SPEC.read_text().splitlines():
        m = re.match(r"\|\s*(I{1,3})\s*\|\s*(\d+)\s*[–-]\s*(\d+)\b[^|]*\|[^|]*\|[^|]*\|\s*Candidate\s+(\d)\b", line)
        if m:
            rows.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
    if [r[0] for r in rows] != list(BAND_LABELS):
        raise SystemExit(f"check-array: could not read regions I/II/III from {SPEC} (got {rows})")
    lo = 0
    for label, a, b, _cand in rows:
        if a != lo or b < a:
            raise SystemExit(f"check-array: spec region map is not contiguous at region {label}: {rows}")
        lo = b + 1
    if lo != N:
        raise SystemExit(f"check-array: spec region map covers {lo} columns, expected N={N}")
    return rows


# ---------------------------------------------------------------------------
# Netlist parsing
# ---------------------------------------------------------------------------


def cell_defaults(cand: int) -> dict[str, float]:
    d = numfmt.cell_defaults(NL / f"cell_candidate{cand}.spice")
    if not set(CELL_PARAMS) <= d.keys():
        raise SystemExit(f"check-array: no parameterized .subckt in cell_candidate{cand}.spice")
    return {k: d[k] for k in CELL_PARAMS}


def parse_instances(path: Path):
    """name -> (nets list, subckt, params dict) for every X instance line."""
    inst = {}
    for ln in numfmt.logical_lines(path.read_text()):
        if not ln.startswith("X"):
            continue
        toks = ln.split()
        params = {}
        while toks and "=" in toks[-1]:
            k, v = toks.pop().split("=", 1)
            params[k] = v
        name, subckt, nets = toks[0], toks[-1], toks[1:-1]
        inst[name] = (nets, subckt, params)
    return inst


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_array(inst, bands, label: str, rows: range, cols: range):
    """Checks 1-5 over the given window of the array. Returns the cell table."""
    cells: dict[tuple[int, int], tuple[int, dict[str, float]]] = {}
    band_of = {c: (lab, cand, lo) for lab, lo, hi, cand in bands for c in range(lo, hi + 1)}

    for r in rows:
        for c in cols:
            name = f"Xc_{r}_{c}"
            if name not in inst:
                err(f"{label}: cell ({r},{c}) missing")
                continue
            nets, subckt, p = inst[name]
            blab, cand, _lo = band_of[c]
            if subckt != f"cell_candidate{cand}":
                err(f"{label}: cell ({r},{c}) is {subckt}, region {blab} requires cell_candidate{cand}")
            want_nets = [f"BL_{c}", f"WL_{r}_{blab}", f"PL_{r}_{blab}", "VDDH_" + blab if ACTIVE_LOW[cand] else "VSS"]
            if nets != want_nets:
                err(f"{label}: cell ({r},{c}) wired {nets}, expected {want_nets}")
            try:
                cells[(r, c)] = (cand, {k: numfmt.spice_num(p[k]) for k in ("wcap", "lcap", "wacc", "lacc")})
            except KeyError as e:
                err(f"{label}: cell ({r},{c}) lacks parameter {e}")
            except ValueError as e:
                err(f"{label}: cell ({r},{c}): {e}")
    extra = {n for n in inst if n.startswith("Xc_")} - {f"Xc_{r}_{c}" for r in rows for c in cols}
    if extra:
        err(f"{label}: unexpected cell instances {sorted(extra)[:5]}")

    # stage instances: exactly one LS + PG per column, and per (row, band) segment
    for c in cols:
        blab, cand, _ = band_of[c]
        for pre, fam, want in (
            ("XLC", LS_FAMILY[cand], [f"CSEL_{c}", "VDDL", "VSS", f"CG_{c}", f"CGB_{c}", f"VDDH_{blab}"]),
            ("XPC", PG_FAMILY[cand], [f"BLG_{blab}", f"CG_{c}", f"BL_{c}", "VSS"]),
        ):
            got = inst.get(f"{pre}_{c}")
            if got is None:
                err(f"{label}: {pre}_{c} missing")
            elif got[1] != fam or got[0] != want:
                err(f"{label}: {pre}_{c} is {got[1]} {got[0]}, expected {fam} {want}")
    seg_bands = sorted({band_of[c][0] for c in cols}, key=BAND_LABELS.index)
    for blab in seg_bands:
        cand = next(b[3] for b in bands if b[0] == blab)
        for r in rows:
            low = ACTIVE_LOW[cand]
            lsout = ([f"RG_{r}_{blab}", f"WL_{r}_{blab}"] if low else [f"WL_{r}_{blab}", f"RGB_{r}_{blab}"])
            gate = f"RG_{r}_{blab}" if low else f"WL_{r}_{blab}"
            for pre, fam, want in (
                ("XLR", LS_FAMILY[cand], [f"RSEL_{r}", "VDDL", "VSS", *lsout, f"VDDH_{blab}"]),
                ("XPR", PG_FAMILY[cand], [f"PL_{r}_{blab}", gate, f"PLG_{blab}", "VSS"]),
            ):
                got = inst.get(f"{pre}_{r}_{blab}")
                if got is None:
                    err(f"{label}: {pre}_{r}_{blab} missing")
                elif got[1] != fam or got[0] != want:
                    err(f"{label}: {pre}_{r}_{blab} is {got[1]} {got[0]}, expected {fam} {want}")
    n_stage = len([n for n in inst if n[:3] in ("XLC", "XPC", "XLR", "XPR")])
    want_stage = 2 * len(cols) + 2 * len(rows) * len(seg_bands)
    if n_stage != want_stage:
        err(f"{label}: {n_stage} addressing-stage instances, expected {want_stage}")
    return cells


def check_levels(cells, bands):
    """Check 3 and 4, on the full array."""
    for blab, lo, hi, cand in bands:
        d = cell_defaults(cand)
        cap_levels = {(d["wcap"], d["lcap"]): 0, (2 * d["wcap"], d["lcap"]): 1}
        acc_levels = {(d["wacc"], d["lacc"]): 0, (2 * d["wacc"], d["lacc"]): 1}

        def find(levels, a, b):
            for (x, y), idx in levels.items():
                if numfmt.close(x, a) and numfmt.close(y, b):
                    return idx
            return None

        lv: dict[tuple[int, int], tuple[int, int]] = {}
        for r in range(N):
            for c in range(lo, hi + 1):
                if (r, c) not in cells:
                    continue
                _cand, p = cells[(r, c)]
                ci = find(cap_levels, p["wcap"], p["lcap"])
                ai = find(acc_levels, p["wacc"], p["lacc"])
                if ci is None:
                    err(f"region {blab}: cell ({r},{c}) wcap/lcap = {p['wcap']:g}/{p['lcap']:g} is not a ratified level "
                        f"(min {d['wcap']:g}/{d['lcap']:g} or 2x width)")
                if ai is None:
                    err(f"region {blab}: cell ({r},{c}) wacc/lacc = {p['wacc']:g}/{p['lacc']:g} is not a ratified level "
                        f"(min {d['wacc']:g}/{d['lacc']:g} or 2x width)")
                if ci is not None and ai is not None:
                    lv[(r, c)] = (ci, ai)
        if len(lv) != N * (hi - lo + 1):
            continue  # already reported
        # capacitor axis: checkerboard
        for (r, c), (ci, _ai) in lv.items():
            for dr, dc in ((0, 1), (1, 0)):
                nb = lv.get((r + dr, c + dc))
                if nb is not None and nb[0] == ci:
                    err(f"region {blab}: capacitor level not a checkerboard at ({r},{c})-({r + dr},{c + dc})")
        # access axis: interleaved, never a stripe wider than 2
        for r in range(N):
            run = 1
            for c in range(lo + 1, hi + 1):
                run = run + 1 if lv[(r, c)][1] == lv[(r, c - 1)][1] else 1
                if run > 2:
                    err(f"region {blab}: access level constant over >2 columns in row {r} (contiguous, not interleaved)")
                    break
        for c in range(lo, hi + 1):
            run = 1
            for r in range(1, N):
                run = run + 1 if lv[(r, c)][1] == lv[(r - 1, c)][1] else 1
                if run > 2:
                    err(f"region {blab}: access level constant over >2 rows in column {c} (contiguous, not interleaved)")
                    break
        # four combinations, evenly populated
        pop = N * (hi - lo + 1)
        counts = {(a, b): 0 for a in (0, 1) for b in (0, 1)}
        for v in lv.values():
            counts[v] += 1
        for combo, k in counts.items():
            if not (0.9 * pop / 4 <= k <= 1.1 * pop / 4):
                err(f"region {blab}: (cap,acc) level combination {combo} has {k} cells of {pop} "
                    f"(expected ~{pop / 4:.0f}, +-10%)")
        print(f"ok: region {blab} (cols {lo}-{hi}, Candidate {cand}): {pop} cells, "
              f"combination populations " + ", ".join(f"{k}:{v}" for k, v in counts.items()))


def check_orientation() -> None:
    want = {1: ("nfet_06v0", "d"), 2: ("nfet_10v0_asym", "d"), 3: ("pfet_06v0", "s")}
    for cand, (model, pin) in want.items():
        m = re.search(r"^XM1 (\S+) (\S+) (\S+) (\S+) (\S+)", (NL / f"cell_candidate{cand}.spice").read_text(), re.M)
        if not m:
            err(f"cell_candidate{cand}: no XM1 access device line")
            continue
        d, g, s, b, mod = m.groups()
        bl_pin = d if pin == "d" else s
        cn_pin = s if pin == "d" else d
        if mod != model or bl_pin != "BL" or cn_pin != "CN" or g != "WL":
            err(f"cell_candidate{cand}: access device is {mod} d={d} g={g} s={s}; required {model} with BL on the "
                f"{'drain' if pin == 'd' else 'source'} and CN on the other terminal")
        else:
            print(f"ok: Candidate {cand} access device {model}: BL on the {'drain' if pin == 'd' else 'source'}, CN opposite")


def main() -> int:
    bands = parse_region_map()
    check_orientation()
    print("spec/split-axis-plan.md region map: " +
          "; ".join(f"{lab} cols {lo}-{hi} = Candidate {cand}" for lab, lo, hi, cand in bands))

    arr = parse_instances(NL / "array_32x32.spice")
    cells = check_array(arr, bands, "array_32x32", range(N), range(N))
    check_levels(cells, bands)

    for sl in SLICES:
        inst = parse_instances(NL / f"{sl}.spice")
        rs = sorted({int(m.group(1)) for n in inst if (m := re.fullmatch(r"Xc_(\d+)_\d+", n))})
        cs = sorted({int(m.group(1)) for n in inst if (m := re.fullmatch(r"Xc_\d+_(\d+)", n))})
        if not rs or not cs:
            err(f"{sl}: no cell instances")
            continue
        scells = check_array(inst, bands, sl, range(rs[0], rs[-1] + 1), range(cs[0], cs[-1] + 1))
        labs = {next(b[0] for b in bands if b[1] <= c <= b[2]) for c in cs}
        if len(labs) < 2:
            err(f"{sl}: spans only region {sorted(labs)}, a slice must straddle a region boundary")
        for key, (cand, p) in scells.items():
            if key not in cells or cells[key][0] != cand or any(not numfmt.close(cells[key][1][k], p[k]) for k in p):
                err(f"{sl}: cell {key} differs from the same cell of array_32x32")
        print(f"ok: {sl} rows {rs[0]}-{rs[-1]} cols {cs[0]}-{cs[-1]} straddles {'|'.join(sorted(labs, key=BAND_LABELS.index))}")

    if errors:
        print(f"\nDRIFT: {len(errors)} violation(s) against {SPEC.relative_to(ROOT)}:", file=sys.stderr)
        for e in errors[:50]:
            print(f"  - {e}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1
    print("array region-map check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
