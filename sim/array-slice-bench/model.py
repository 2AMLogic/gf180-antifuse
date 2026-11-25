#!/usr/bin/env python3
"""sim/array-slice-bench model.py -- the bench's shared grading library.

Slice corner grading and per-region aggregation: the bench acceptance
thresholds (this bench's own, not spec numbers), the committed-cell map
loader, the per-corner grader and the per-region / per-sub-combination
worst-case aggregation. The CLI entry point is run_bench.py, which loads
this module (and render.py) via harness.modload and re-exports this
surface; render.py imports one-way from this module, and fullband.py reads
the selected-path thresholds from here (they are the same bench's). Nothing
in this module imports render.py, fullband.py or the CLI.

``repo`` is a parameter everywhere a netlist is read, never a module-level
constant read inside this file: the CLI passes its own ``REPO`` at call
time, so callers that repoint the CLI's tree (tests grading against a
throwaway checkout) keep redirecting every read.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(REPO_ROOT / "design"))
from harness import numfmt as NF  # noqa: E402
import gen_array as G  # noqa: E402
import make_bench as B  # noqa: E402

# Grading thresholds. Bench acceptance criteria of THIS record, not spec numbers.
ETA_MIN = 0.80          # selected-cell access-path current / ideal (V_BL / R_FIL)
RETURN_MIN = 0.95       # |I(PLG)| / |I(BLG)| for the selected cell's band
BL_MIN = 0.98           # V(selected BL_c) / V(BLG)
PL_MAX = 0.02           # V(selected cell's PL) / V(BLG)
ISO_MAX = 1e-3          # unselected-cell / bus current relative to ideal
R_FIL = B.R_FIL

_num = NF.spice_num


def load_netlist_cells(sl: str, repo: Path = REPO_ROOT) -> dict:
    """(row, col) -> (candidate, wcap, wacc) as carried by the committed derived
    slice netlist (design/netlists/<slice>.spice) - not recomputed from the
    generator's index formula."""
    text = (repo / "design" / "netlists" / f"{sl}.spice").read_text()
    out = {}
    for m in re.finditer(r"^Xc_(\d+)_(\d+) \S+ \S+ \S+ \S+ cell_candidate(\d) wcap=(\S+) lcap=\S+ wacc=(\S+)", text, re.M):
        out[(int(m.group(1)), int(m.group(2)))] = (int(m.group(3)), _num(m.group(4)), _num(m.group(5)))
    return out


def sub_combo(cells: dict, r: int, c: int) -> tuple[str, str]:
    """('min'|'2x' capacitor, 'min'|'2x' access) of cell (r, c), read from the
    slice's own committed cell map (no module-global cache to populate first,
    so a grading can never read another slice's cells)."""
    cand, wcap, wacc = cells[(r, c)]
    d = G.cell_defaults(cand)
    cap = "2x" if abs(wcap - 2 * _num(d["wcap"])) < 1e-12 else "min"
    acc = "2x" if abs(wacc - 2 * _num(d["wacc"])) < 1e-12 else "min"
    return cap, acc


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def grade_corner(sl: str, corner: dict, cells: dict):
    sv = corner["supply_v"]
    rows, cols = B.window(sl)
    sel_r = [r for r in rows if sv[f"vrsel{r}"] > 0]
    sel_c = [c for c in cols if sv[f"vcsel{c}"] > 0]
    if len(sel_r) != 1 or len(sel_c) != 1:
        raise SystemExit(f"{sl}: corner {corner['corner_id']} does not select exactly one cell")
    sr, sc = sel_r[0], sel_c[0]
    m = {x["name"]: x["value"] for x in corner["measurements"]}
    if corner["status"] not in ("pass",) or any(v is None for v in m.values()):
        return {"sel": (sr, sc), "error": f"status={corner['status']}"}
    blab, _ = G.band_of_col(sc)
    bl = blab.lower()
    vbl = {lab: sv[f"vbl_{lab.lower()}"] for lab, *_ in B.bands_in(cols)}
    ideal = {lab: v / R_FIL for lab, v in vbl.items()}

    res = {"sel": (sr, sc), "band": blab, "cand": cells[(sr, sc)][0]}
    res["cap"], res["acc"] = sub_combo(cells, sr, sc)
    isel = abs(m[f"ifil_{sr}_{sc}"])
    res["eta"] = isel / ideal[blab]
    res["return"] = abs(m[f"iret_{bl}"]) / abs(m[f"ibus_{bl}"]) if m[f"ibus_{bl}"] else 0.0
    res["bl"] = m[f"nv_bl_{sc}"] / vbl[blab]
    res["pl"] = abs(m[f"nv_pl_{sr}_{bl}"]) / vbl[blab]
    res["reach_ok"] = (res["eta"] >= ETA_MIN and RETURN_MIN <= res["return"] <= 1.0 / RETURN_MIN
                       and res["bl"] >= BL_MIN and res["pl"] <= PL_MAX)

    iso = defaultdict(float)   # (band, class) -> worst ratio
    for r in rows:
        for c in cols:
            if (r, c) == (sr, sc):
                continue
            lab, _ = G.band_of_col(c)
            cls = "same_col" if c == sc else ("same_row" if r == sr else "other")
            ratio = abs(m[f"ifil_{r}_{c}"]) / ideal[lab]
            key = (lab, cls)
            iso[key] = max(iso[key], ratio)
    for lab in vbl:
        if lab != blab:  # a band whose bus is powered but not selected
            key = (lab, "bus")
            iso[key] = abs(m[f"ibus_{lab.lower()}"]) / ideal[lab]
    res["iso"] = dict(iso)
    res["iso_ok"] = all(v <= ISO_MAX for v in iso.values())
    return res


def analyze(sl: str, report: dict, repo: Path = REPO_ROOT) -> list[dict]:
    cells = load_netlist_cells(sl, repo)
    per = []
    for c in report["corners"]:
        g = grade_corner(sl, c, cells)
        g["process"], g["temp"] = c["process"], c["temperature_c"]
        g["scale"] = round(c["supply_v"]["vddl"] / B.VDDL, 2)
        per.append(g)
    return per


def region_tables(sl: str, per: list[dict]):
    """Per region and per (cap, acc) sub-combination worst cases."""
    reach = defaultdict(lambda: {"n": 0, "bad": 0, "eta": (9e9, None), "ret": (9e9, None),
                                  "bl": (9e9, None), "pl": (0.0, None), "err": 0})
    iso = defaultdict(lambda: {"n": 0, "bad": 0, "worst": (0.0, None)})
    errors = 0
    for g in per:
        tag = f"{g['process']}/{g['temp']}C/x{g['scale']:.1f}"
        if "error" in g:
            errors += 1
            continue
        sr, sc = g["sel"]
        key = (g["band"], g["cand"], g["cap"], g["acc"])
        t = reach[key]
        t["n"] += 1
        t["bad"] += 0 if g["reach_ok"] else 1
        for fld, k, better in (("eta", "eta", min), ("ret", "return", min), ("bl", "bl", min)):
            if g[k] < t[fld][0]:
                t[fld] = (g[k], f"{tag} sel=({sr},{sc})")
        if g["pl"] > t["pl"][0]:
            t["pl"] = (g["pl"], f"{tag} sel=({sr},{sc})")
        for (lab, cls), ratio in g["iso"].items():
            u = iso[(lab, cls)]
            u["n"] += 1
            u["bad"] += 0 if ratio <= ISO_MAX else 1
            if ratio > u["worst"][0]:
                u["worst"] = (ratio, f"{tag} sel=({sr},{sc})")
    return reach, iso, errors
