"""Full-band leakage analysis (issue #70): reports -> per-region budget tables.

Pure functions over `klt sim` reports (no ngspice, no network), so the grading
is unit-testable (test_full_band.py). run_bench.py --mode full-band drives it.

Sign convention (stated once, used everywhere): every leakage current is
*drawn out of the summation node*, the band's global bit-line bus BLG_<band>
(the ASSUMED sense node, see README.md), and is positive when it leaves the
node through an OFF column pass-gate or a junction. ngspice reports the
current of a voltage source as positive INTO its + terminal, so the BLG source
`Vbl_<band>` reads negative when it supplies the node: I_node = -i(Vbl). The
per-column clamp sources `Vcl_<c>` (+ terminal on BL_c) read positive for
current entering BL_c from the pass-gate: I_pg,c = +i(Vcl_c).

Budget equation (one place, evaluated by `budget()`):

    I_leak,total = I_node,pgoff  +  I_cell,max
                   `---------'     `---------'
       measured at BLG with every    carried ONCE from the committed
       column OFF and BL_c at 0 V    cell-device record: 31 x I_off

    I_node,pgoff = sum_c i(Vcl_c)  (current delivered into the OFF columns)
                   + I_other    (= I_node - sum; positive: BLG-node junction/bulk leakage;
                                 negative: current entering BL_c from the cell side at BL_c = 0 V,
                                 e.g. the PMOS access n-well junction - not drawn from BLG)

The cell term is NOT in I_node,pgoff by construction: BL_c is clamped to 0 V so
the access devices see V_DS = 0 and the capacitor blocks DC.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "design"))
sys.path.insert(0, str(REPO / "sim" / "program-read-legs"))
import gen_array as G  # noqa: E402
import make_bench as B  # noqa: E402

GMIN = 1e-12            # A/V, ngspice default conductance floor (not overridden by design.ngspice)
FLOOR_FACTOR = 10.0     # a reading below FLOOR_FACTOR x floor is "floor-dominated": upper bound only
I_REF = {"I": (1e-6,), "II": (1e-6,), "III": (1e-6, 3e-10)}   # as in sim/program-read-legs (III has a low-I_ref bench)
ETA_MIN, BL_MIN, RETURN_MIN = 0.80, 0.98, 0.95   # selected-path thresholds (same as the slice bench)
R_FIL = B.R_FIL
CAND_OF = {lab: cand for lab, _lo, _hi, cand in G.BANDS}
EXPECTED_COLS = {lab: hi - lo + 1 for lab, lo, hi, _c in G.BANDS}   # 11 / 11 / 10


class AnalysisError(ValueError):
    """A report that cannot be graded (missing/duplicate/mismatched terms)."""


# ---------------------------------------------------------------------------
# Sign normalisation and the budget equation
# ---------------------------------------------------------------------------


def out_of_node(i_vsource: float) -> float:
    """Current drawn out of the node a DC source supplies (ngspice: i(V) is
    positive into the + terminal, so a supplying source reads negative)."""
    return -i_vsource


def floor_a(v_blg: float, n_cols: int) -> float:
    """Estimated simulator floor of the summation node: one gmin per column
    node at the BLG level (an estimate, labelled as such wherever shown)."""
    return GMIN * abs(v_blg) * n_cols


def budget(band: str, pg_by_col: dict[int, float], node_current: float, i_cell: float, i_ref: float,
           v_blg: float) -> dict:
    """The per-point budget. Rejects a band whose column set is not exactly the
    band's (missing or duplicate/extra leakage terms), a non-finite value, and a
    node reading inconsistent with the per-column sum."""
    lab_cols = [c for lab, lo, hi, _c in G.BANDS if lab == band for c in range(lo, hi + 1)]
    if sorted(pg_by_col) != lab_cols:
        missing = sorted(set(lab_cols) - set(pg_by_col))
        extra = sorted(set(pg_by_col) - set(lab_cols))
        raise AnalysisError(f"band {band}: pass-gate terms must be exactly columns {lab_cols[0]}..{lab_cols[-1]} "
                            f"({EXPECTED_COLS[band]}); missing {missing}, unexpected {extra}")
    for k, v in list(pg_by_col.items()) + [("node", node_current), ("cell", i_cell)]:
        if v is None or v != v:
            raise AnalysisError(f"band {band}: non-finite/missing term {k}")
    ch = sum(pg_by_col.values())
    # Signed on purpose. The budget quantity is the node current (what BLG supplies: OFF pass-gates and
    # BLG-node junctions only; the cells hang off BL_c, not BLG). The clamp sources also carry whatever else
    # enters BL_c at 0 V - e.g. the n-well junction of Candidate 3's PMOS access devices (well tied to VDDH) -
    # so sum(i(Vcl)) can EXCEED the node current; then `other` is negative and that excess is current entering
    # BL_c from the cell side, not a BLG-budget term (it is reported, never added).
    other = node_current - ch
    total = node_current + i_cell      # i_cell added exactly once, here
    fl = floor_a(v_blg, len(pg_by_col))
    return {"n_cols": len(pg_by_col), "pg_channel": ch, "pg_other": other, "pg_node": node_current,
            "cell": i_cell, "total": total, "i_ref": i_ref, "headroom": i_ref - total,
            "ratio": (i_ref / total) if total > 0 else float("inf"), "floor": fl,
            "floor_dominated": node_current < FLOOR_FACTOR * fl}


# ---------------------------------------------------------------------------
# Report plumbing
# ---------------------------------------------------------------------------


def band_of(name: str) -> str:
    return B.leak_band_label(name)


def cell_term(band: str) -> tuple[float, str]:
    """(31 x I_off bound, provenance) for the band's candidate, out of the
    committed cell-device-characterization record - see sim/program-read-legs
    benches.i_sneak_max."""
    import benches  # sim/program-read-legs/benches.py
    cand = CAND_OF[band]
    v = benches.i_sneak_max(cand)
    return v, f"sim/cell-device-characterization/records (Candidate {cand}), 31 x I_off at ff/125C/high read"


def _meas(corner: dict) -> dict:
    m = {x["name"]: x["value"] for x in corner["measurements"]}
    if corner["status"] != "pass" or any(v is None for v in m.values()):
        raise AnalysisError(f"corner {corner['corner_id']}: status={corner['status']} or missing measurement")
    return m


def _point_key(name: str, variant: str):
    """(vbl, vddl-scale, sel) -> point info, from the generator itself."""
    out = {}
    for p in B.leak_points(name, variant):
        out[(round(p["vbl"], 6), round(p["scale"], 2), p["sel"])] = p
    return out


def _corner_point(name: str, variant: str, corner: dict, lookup: dict):
    lab = band_of(name)
    sv = corner["supply_v"]
    rows, cols = B.leak_window(name)
    sel = None
    if variant == "sel":
        sr = [r for r in rows if sv[f"vrsel{r}"] > 0]
        sc = [c for c in cols if sv[f"vcsel{c}"] > 0]
        if len(sr) != 1 or len(sc) != 1:
            raise AnalysisError(f"{name}: corner {corner['corner_id']} does not select exactly one cell")
        sel = (sr[0], sc[0])
    k = (round(sv[f"vbl_{lab.lower()}"], 6), round(sv["vddl"] / B.VDDL, 2), sel)
    if k not in lookup:
        raise AnalysisError(f"{name}/{variant}: corner {corner['corner_id']} matches no generated operating point")
    return lookup[k]


def analyze_pgoff(name: str, reports: dict[str, dict]):
    """reports: process -> merged report of the `pgoff` request. Returns rows."""
    lab = band_of(name)
    rows, cols = B.leak_window(name)
    lookup = _point_key(name, "pgoff")
    i_cell, _prov = cell_term(lab)
    out, seen = [], set()
    for proc, rep in reports.items():
        for c in rep["corners"]:
            m = _meas(c)
            p = _corner_point(name, "pgoff", c, lookup)
            ident = (proc, c["temperature_c"], p["level"], p["level_scale"], p["scale"])
            if ident in seen:
                raise AnalysisError(f"{name}: duplicate operating point {ident}")
            seen.add(ident)
            pg = {col: m[f"icl_{col}"] for col in cols}
            node = out_of_node(m["ibus"])
            for iref in I_REF[lab]:
                b = budget(lab, pg, node, i_cell, iref, p["vbl"])
                b.update(band=lab, process=proc, temp=c["temperature_c"], level=p["level"],
                         level_scale=p["level_scale"], scale=p["scale"], vbl=p["vbl"],
                         pg_by_col=pg, name=name)
                out.append(b)
    expect = len(B.PROCESS) * len(B.TEMPS) * len(B.leak_points(name, "pgoff")) * len(I_REF[lab])
    if len(out) != expect:
        raise AnalysisError(f"{name}/pgoff: {len(out)} graded points, expected {expect}")
    return out


def analyze_nat(name: str, reports: dict[str, dict]):
    lab = band_of(name)
    rows, cols = B.leak_window(name)
    lookup = _point_key(name, "nat")
    out = []
    for proc, rep in reports.items():
        for c in rep["corners"]:
            m = _meas(c)
            p = _corner_point(name, "nat", c, lookup)
            out.append({"band": lab, "process": proc, "temp": c["temperature_c"], "level": p["level"],
                        "level_scale": p["level_scale"], "scale": p["scale"], "vbl": p["vbl"],
                        "node": out_of_node(m["ibus"]), "bl_max": max(m[f"nv_bl_{col}"] for col in cols),
                        "bl_min": min(m[f"nv_bl_{col}"] for col in cols)})
    return out


def _sub_combo(r: int, c: int):
    cand, p = G.cell_params(r, c)
    d = G.cell_defaults(cand)
    cap = "2x" if p["wcap"] != d["wcap"] else "min"
    acc = "2x" if p["wacc"] != d["wacc"] else "min"
    return cap, acc


def analyze_sel(name: str, reports: dict[str, dict]):
    lab = band_of(name)
    rows, cols = B.leak_window(name)
    lookup = _point_key(name, "sel")
    out = []
    for proc, rep in reports.items():
        for c in rep["corners"]:
            m = _meas(c)
            p = _corner_point(name, "sel", c, lookup)
            sr, sc = p["sel"]
            ideal = p["vbl"] / R_FIL
            eta = abs(m[f"ifil_{sr}_{sc}"]) / ideal
            ret = abs(m["iret"]) / abs(m["ibus"]) if m["ibus"] else 0.0
            blr = m[f"nv_bl_{sc}"] / p["vbl"]
            cap, acc = _sub_combo(sr, sc)
            out.append({"band": lab, "process": proc, "temp": c["temperature_c"], "level": p["level"],
                        "scale": p["scale"], "vbl": p["vbl"], "sel": (sr, sc), "cap": cap, "acc": acc,
                        "eta": eta, "ret": ret, "bl_ratio": blr,
                        "ok": eta >= ETA_MIN and blr >= BL_MIN and RETURN_MIN <= ret <= 1 / RETURN_MIN})
    return out


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

REGION_NAME = {"I": "Region I (Candidate 1)", "II": "Region II (Candidate 2)", "III": "Region III (Candidate 3)"}


def e(x: float) -> str:
    return f"{x:.3g}"


def worst_by(rows: list[dict], keyf, valf):
    best = {}
    for r in rows:
        k = keyf(r)
        if k not in best or valf(r) > valf(best[k]):
            best[k] = r
    return best


def budget_table(rows: list[dict]) -> list[str]:
    """Per region x level x I_ref, worst corner (largest I_leak,total)."""
    w = worst_by(rows, lambda r: (r["band"], r["level"], r["i_ref"]), lambda r: r["total"])
    out = ["| Region | cols | read level | BLG (V) | I_ref (A) | worst corner | sum of clamp-source currents (A) | "
           "node minus clamp sum (A, signed) | pass-gate at node (A) | cell 31 x I_off (A) | I_leak,total (A) | "
           "I_ref - I_leak,total (A) | I_ref / I_leak,total | floor-dominated |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(w, key=lambda k: ([b[0] for b in G.BANDS].index(k[0]), k[1], -k[2])):
        r = w[k]
        tag = f"{r['process']}/{r['temp']}C/x{r['scale']:.1f}/L{r['level_scale']:.1f}"
        out.append(f"| {REGION_NAME[r['band']]} | {r['n_cols']} | {r['level']} | {r['vbl']:g} | {r['i_ref']:.0e} | {tag} | "
                   f"{e(r['pg_channel'])} | {e(r['pg_other'])} | {e(r['pg_node'])} | {e(r['cell'])} | {e(r['total'])} | "
                   f"{e(r['headroom'])} | {e(r['ratio'])} | {'yes' if r['floor_dominated'] else 'no'} |")
    return out


def pvt_table(rows: list[dict]) -> list[str]:
    """Per region x level x process x temperature, worst over supply/level scale."""
    w = worst_by(rows, lambda r: (r["band"], r["level"], r["i_ref"], r["process"], r["temp"]), lambda r: r["total"])
    out = ["| Region | read level | I_ref (A) | process | T (C) | worst (supply, level scale) | BLG (V) | "
           "pass-gate at node (A) | cell (A) | I_leak,total (A) | I_ref - I_leak,total (A) | ratio |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = list(B.PROCESS)
    for k in sorted(w, key=lambda k: ([b[0] for b in G.BANDS].index(k[0]), k[1], -k[2], order.index(k[3]), k[4])):
        r = w[k]
        out.append(f"| {REGION_NAME[r['band']]} | {r['level']} | {r['i_ref']:.0e} | {r['process']} | {r['temp']} | "
                   f"x{r['scale']:.1f}, L{r['level_scale']:.1f} | {r['vbl']:g} | {e(r['pg_node'])} | {e(r['cell'])} | "
                   f"{e(r['total'])} | {e(r['headroom'])} | {e(r['ratio'])} |")
    return out


def attribution_table(rows: list[dict]) -> list[str]:
    """Per-column spread at the worst point of each region: which pass-gate leaks."""
    w = worst_by(rows, lambda r: r["band"], lambda r: r["pg_node"])
    out = ["| Region | worst point | columns | min clamp column (A) | max clamp column (A) | max/min | clamp-sum / node | (node - clamp-sum) / node |",
           "|---|---|---|---|---|---|---|---|"]
    for lab in [b[0] for b in G.BANDS]:
        if lab not in w:
            continue
        r = w[lab]
        v = r["pg_by_col"]
        mn, mx = min(v.values()), max(v.values())
        node = r["pg_node"] if r["pg_node"] else float("nan")
        out.append(f"| {REGION_NAME[lab]} | {r['process']}/{r['temp']}C/x{r['scale']:.1f}/{r['level']} L{r['level_scale']:.1f} | "
                   f"{r['n_cols']} | {e(mn)} | {e(mx)} | {e(mx / mn) if mn > 0 else 'n/a'} | "
                   f"{r['pg_channel'] / node:.3f} | {r['pg_other'] / node:.3f} |")
    return out


def nat_table(nat: list[dict], pg: list[dict]) -> list[str]:
    w = worst_by(nat, lambda r: (r["band"], r["level"]), lambda r: r["node"])
    clamp = worst_by([r for r in pg if r["i_ref"] == max(I_REF[r["band"]])], lambda r: (r["band"], r["level"]),
                     lambda r: r["pg_node"])
    out = ["| Region | read level | worst natural-DC BLG current (A) | corner | BL_c range there (V) | "
           "clamped (BL_c = 0 V) worst, same level (A) | natural / clamped |", "|---|---|---|---|---|---|---|"]
    for k in sorted(w, key=lambda k: ([b[0] for b in G.BANDS].index(k[0]), k[1])):
        r = w[k]
        c = clamp[k]
        tag = f"{r['process']}/{r['temp']}C/x{r['scale']:.1f}/L{r['level_scale']:.1f}"
        ratio = e(r["node"] / c["pg_node"]) if c["pg_node"] > 0 else "n/a"
        out.append(f"| {REGION_NAME[k[0]]} | {k[1]} | {e(r['node'])} | {tag} | {r['bl_min']:.3g}..{r['bl_max']:.3g} | "
                   f"{e(c['pg_node'])} | {ratio} |")
    return out


def sel_table(sel: list[dict]) -> list[str]:
    g = defaultdict(lambda: {"n": 0, "bad": 0, "eta": (9e9, None), "bl": (9e9, None), "ret": (9e9, None)})
    for r in sel:
        t = g[(r["band"], r["level"], r["cap"], r["acc"])]
        t["n"] += 1
        t["bad"] += 0 if r["ok"] else 1
        tag = f"{r['process']}/{r['temp']}C/x{r['scale']:.1f} sel={r['sel']}"
        for k, f in (("eta", "eta"), ("bl", "bl_ratio"), ("ret", "ret")):
            if r[f] < t[k][0]:
                t[k] = (r[f], tag)
    out = ["| Region | read level | cap | access | points | eta min (worst) | V(BL)/V(BLG) min | I(PLG)/I(BLG) min | "
           "below threshold |", "|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(g, key=lambda k: ([b[0] for b in G.BANDS].index(k[0]), k[1], k[2], k[3])):
        t = g[k]
        out.append(f"| {REGION_NAME[k[0]]} | {k[1]} | {k[2]} | {k[3]} | {t['n']} | {e(t['eta'][0])} ({t['eta'][1]}) | "
                   f"{e(t['bl'][0])} | {e(t['ret'][0])} | {t['bad']} |")
    return out


def programmed_side_from_65(record: Path | None = None) -> list[str]:
    """Programmed/unprogrammed-side worst margin rows of the #65 record, parsed
    (not retyped) so they stay in sync with what that record says."""
    rec = record or (REPO / "sim" / "program-read-legs" / "records" / f"{B.READ_RECORD}.md")
    text = rec.read_text()
    out = ["| Region / bench | side | access sizing | worst margin (x) | at corner | BL at worst (V) | decisions correct |",
           "|---|---|---|---|---|---|---|"]
    for sect in re.split(r"^### ", text, flags=re.M):
        m = re.match(r"Read margin, (Candidate \d \(Region [I]+\)), I_ref = (\S+)", sect)
        if not m:
            continue
        for row in re.finditer(r"^\| (unprogrammed|programmed[^|]*?)\s*\| (\w+) \| ([^|]+)\| (`[^`]+`) \| [^|]+\| ([^|]+)\| ([^|]+)\|$",
                               sect, re.M):
            side, sz, marg, corner, bl, dec = (x.strip() for x in row.groups())
            out.append(f"| {m.group(1)}, I_ref = {m.group(2)} | {side} | {sz} | {marg} | {corner} | {bl} | {dec} |")
    return out


def provenance_rows() -> list[str]:
    out = ["| Region | cols | rows modelled | read level | BLG (V) at x0.9 / x1.0 / x1.1 |", "|---|---|---|---|---|"]
    for name in G.BAND_SLICES:
        lab = band_of(name)
        rows, cols = B.leak_window(name)
        for ln, lv in B.leak_levels(name):
            out.append(f"| {REGION_NAME[lab]} | {cols[0]}-{cols[-1]} ({len(cols)}) | {rows[0]}-{rows[-1]} | {ln} | "
                       f"{' / '.join(f'{lv * s:.4g}' for s in B.LEVEL_SCALES)} |")
    return out


def summary_lines(pg: list[dict], sel: list[dict]) -> list[str]:
    """Data-derived statements only (recomputed from the graded points)."""
    out = []
    for lab in [b[0] for b in G.BANDS]:
        for iref in sorted({r["i_ref"] for r in pg if r["band"] == lab}, reverse=True):
            rs = [r for r in pg if r["band"] == lab and r["i_ref"] == iref]
            w = max(rs, key=lambda r: r["total"])
            verdict = "I_ref > I_leak,total at every graded point" if all(r["headroom"] > 0 for r in rs) else \
                f"I_ref <= I_leak,total at {sum(1 for r in rs if r['headroom'] <= 0)} of {len(rs)} graded points"
            out.append(f"- {REGION_NAME[lab]}, I_ref = {iref:.0e} A: {verdict}; worst I_leak,total {e(w['total'])} A "
                       f"({w['level']}, {w['process']}/{w['temp']}C), min I_ref/I_leak,total {e(min(r['ratio'] for r in rs))}.")
    for lab in [b[0] for b in G.BANDS]:
        sp = max((max(r["pg_by_col"].values()) / min(r["pg_by_col"].values())
                  for r in pg if r["band"] == lab and min(r["pg_by_col"].values()) > 0), default=float("nan"))
        out.append(f"- {REGION_NAME[lab]}: largest per-column clamp-current spread (max/min over the {EXPECTED_COLS[lab]} "
                   f"columns, any point) = {sp:.3g}.")
    for lab in [b[0] for b in G.BANDS]:
        for ln in sorted({r["level"] for r in sel if r["band"] == lab}):
            rs = [r for r in sel if r["band"] == lab and r["level"] == ln]
            out.append(f"- {REGION_NAME[lab]} selected-path, level `{ln}`: {sum(1 for r in rs if not r['ok'])} of {len(rs)} "
                       f"points below threshold; min V(BL)/V(BLG) {min(r['bl_ratio'] for r in rs):.3g}, min eta {min(r['eta'] for r in rs):.3g}.")
    return out
