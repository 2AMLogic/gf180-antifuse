"""Grading and aggregation for sim/integrated-transition (stdlib only).

Pure functions over klt corner dicts, so they are unit-testable without a
simulator. Thresholds below are THIS bench's own acceptance numbers, repeated in
every record; they are not spec values.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import limits as LIM

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from harness.modload import load_module  # noqa: E402

# array-slice-bench also has a make_bench.py. All users of this bench share B.
B = load_module(HERE / "make_bench.py", "sim_it_make_bench")

G = B.G

# --- acceptance thresholds of this bench (not spec numbers) ---------------------
V_FRAC = 0.10        # a node counts as "unchanged" if it moves < 10 % of VDD
I_ARM_FRAC = 0.10    # armed-state current into the read leg must stay below 10 % of I_ref
V_OFF_TOL = 0.10     # an unselected select line must stay within 0.1 V of its OFF level
SETTLE_FRAC = 0.10   # sense node "settled" = within 10 % of VDD of its final value, RDATA rail-clean

SCEN_KEYS = ("tvr", "tcsl", "tpe", "tpf", "tren", "tdis")


class Ungradable(Exception):
    pass


def decode(sl: str, sv: dict) -> dict:
    """Operating-point description from a corner's supply_v (independent of corner order)."""
    rows, cols = B.window(sl)
    sr = [r for r in rows if sv[f"ven_r{r}"] > 0.5]
    sc = [c for c in cols if sv[f"ven_c{c}"] > 0.5]
    if len(sr) != 1 or len(sc) != 1:
        raise Ungradable("selected cell not unique")
    tim = tuple(round(sv[f"v{k}"], 6) for k in SCEN_KEYS)
    scen = next((n for n, d in B.SCENARIOS.items() if tuple(round(d[k], 6) for k in SCEN_KEYS) == tim), None)
    g = sv["vgfil"]
    var = next((n for n, gv in B.VARIANTS.items() if abs(gv - g) <= 1e-12 + 1e-6 * abs(gv)), None)
    if scen is None or var is None:
        raise Ungradable(f"unknown scenario/variant {tim} {g}")
    cell = (sr[0], sc[0])
    lab, cand = G.band_of_col(cell[1])
    c0 = next(lo for l, lo, _h, _c in G.BANDS if l == lab)
    cap, acc = G.level_indices(cell[0], cell[1], c0)
    return {"cell": cell, "band": lab, "cand": cand, "cap": ("min", "2x")[cap], "acc": ("min", "2x")[acc],
            "scen": scen, "var": var, "scale": round(sv["vdd"] / B.VDD, 2), "vdd": sv["vdd"],
            "tren": sv["vtren"], "bands": B.bands_in(cols)}


def _need(m: dict, *names):
    out = []
    for n in names:
        v = m.get(n)
        if v is None or v != v:
            raise Ungradable(f"measurement {n} missing")
        out.append(v)
    return out


def exc(m, name_max, name_min, idle):
    hi, lo = _need(m, name_max, name_min)
    return max(abs(hi - idle), abs(lo - idle))


def settle(m: dict, band: str, vdd: float, tren: float, expect_high: bool):
    """(decision-stable delay, analog-settled delay, final RDATA correct). Delays in us after READ_EN;
    None if not reached within the sample grid. Grid samples at or before READ_EN are not read samples."""
    bl = band.lower()
    sense = _need(m, *[f"sense_s{i}_{bl}" for i in range(len(B.SAMPLES))])
    rd = _need(m, *[f"rdata_s{i}_{bl}" for i in range(len(B.SAMPLES))])
    idx = [i for i, t in enumerate(B.SAMPLES) if t > tren + 1e-9]
    if not idx:
        return None, None, False
    correct = [(r > vdd / 2) == expect_high for r in rd]
    clean = [r <= V_FRAC * vdd or r >= (1 - V_FRAC) * vdd for r in rd]
    fin_s, fin_r = sense[-1], rd[-1]
    t_dec = t_set = None
    for i in idx:
        tail = range(i, len(B.SAMPLES))
        if t_dec is None and all(correct[j] for j in tail):
            t_dec = B.SAMPLES[i] - tren
        if t_set is None and all(abs(sense[j] - fin_s) <= SETTLE_FRAC * vdd and clean[j]
                                 and (rd[j] > vdd / 2) == (fin_r > vdd / 2) for j in tail):
            t_set = B.SAMPLES[i] - tren
    return t_dec, t_set, correct[-1]


def line_dev(m: dict, sl: str, d: dict):
    """Worst deviation of any UNSELECTED select line from its OFF level (V), and which line.

    Rows: word line of every row except the selected row (the select is shared by the row's segments in
    both bands, so the selected row is ON in both). Columns: column pass-gate gate of every column but the
    selected one. OFF level: 0 V, except an active-low word line (Region III), whose OFF level is VDDH."""
    rows, cols = B.window(sl)
    sr, sc = d["cell"]
    worst, where = 0.0, None
    for b in d["bands"]:
        bl = b.lower()
        vddh = B.RAILS[b] * d["scale"]
        cand = next(x[3] for x in G.BANDS if x[0] == b)
        for r in rows:
            if r == sr:
                continue
            names = [(f"wl_{r}_{bl}", vddh if G.ACTIVE_LOW_WL[cand] else 0.0)]
            if G.ACTIVE_LOW_WL[cand]:
                names.append((f"rg_{r}_{bl}", 0.0))
            for n, off in names:
                hi, lo = _need(m, f"ln_max_{n}", f"ln_min_{n}")
                dev = max(hi - off, off - lo, 0.0)
                if dev > worst:
                    worst, where = dev, n
    for c in cols:
        if c == sc:
            continue
        hi, lo = _need(m, f"ln_max_cg_{c}", f"ln_min_cg_{c}")
        dev = max(hi, -lo, 0.0)
        if dev > worst:
            worst, where = dev, f"cg_{c}"
    return worst, where


def grade(sl: str, corner: dict) -> dict:
    """Per-point result row. Raises Ungradable if anything needed is missing."""
    if corner.get("status") not in ("pass", "inconclusive", "fail"):
        raise Ungradable(f"status={corner.get('status')}")
    d = decode(sl, corner["supply_v"])
    m = {x["name"]: x["value"] for x in corner["measurements"]}
    vdd, ob = d["vdd"], [b for b in d["bands"] if b != d["band"]]
    sb = d["band"].lower()
    r = dict(d)
    r["process"], r["temp"] = corner["process"], corner["temperature_c"]
    r["expect_high"] = d["var"] != "unprog"

    # --- armed isolation (both bands: the idle band's legs must stay quiet too) ------------------
    for tag, b in [("sel", d["band"])] + [("idle", x) for x in ob]:
        bl = b.lower()
        sidle, ridle = _need(m, f"sense_idle_{bl}", f"rdata_idle_{bl}")
        r[f"arm_sense_{tag}"] = exc(m, f"sense_max_arm_{bl}", f"sense_min_arm_{bl}", sidle)
        r[f"arm_rdata_{tag}"] = exc(m, f"rdata_max_arm_{bl}", f"rdata_min_arm_{bl}", ridle)
        pon, ron = _need(m, f"pon_max_arm_{bl}", f"ron_max_arm_{bl}")
        r[f"arm_legon_{tag}"] = max(pon, ron)
        (iend,) = _need(m, f"ird_armavg_{bl}")
        r[f"arm_iread_{tag}"] = abs(iend)
        (ipg,) = _need(m, f"ipg_armavg_{bl}")
        r[f"arm_iprog_{tag}"] = abs(ipg)
        (bo,) = _need(m, f"both_max_{bl}")
        r[f"both_{tag}"] = bo
    # --- pulse-phase isolation of the selected band's read leg ------------------------------------
    sidle, ridle = _need(m, f"sense_idle_{sb}", f"rdata_idle_{sb}")
    r["pul_sense"] = exc(m, f"sense_max_pul_{sb}", f"sense_min_pul_{sb}", sidle)
    r["pul_rdata"] = exc(m, f"rdata_max_pul_{sb}", f"rdata_min_pul_{sb}", ridle)
    (r["pul_ron"],) = _need(m, f"ron_max_pul_{sb}")
    (r["pul_ipg"],) = _need(m, f"ipg_pulavg_{sb}")
    (r["pul_ird"],) = _need(m, f"ird_pulavg_{sb}")
    (r["rd_ipg"],) = _need(m, f"ipg_rdavg_{sb}")
    (r["rd_ird"],) = _need(m, f"ird_rdavg_{sb}")
    # --- the transition ---------------------------------------------------------------------------
    t_dec, t_set, ok = settle(m, d["band"], vdd, d["tren"], r["expect_high"])
    r["t_dec"], r["t_settle"], r["dec_ok"] = t_dec, t_set, ok
    hi, lo = _need(m, f"rdata_max_rd_{sb}", f"rdata_min_rd_{sb}")
    r["rd_rdata_max"], r["rd_rdata_min"] = hi, lo
    r["false_high"] = (not r["expect_high"]) and hi > V_FRAC * vdd
    (r["rd_sense_max"],) = _need(m, f"sense_max_rd_{sb}")
    (r["blg_final"],) = _need(m, f"blg_s{len(B.SAMPLES) - 1}_{sb}")
    (r["blg_pulse_max"],) = _need(m, f"blg_max_pul_{sb}")
    # --- unselected-line bias -----------------------------------------------------------------------
    r["off_dev"], r["off_line"] = line_dev(m, sl, d)
    # --- checks (booleans; False = a bench criterion is not met) ----------------------------------
    chk = {}
    chk["armed_sense"] = all(r[f"arm_sense_{t}"] <= V_FRAC * vdd for t in ("sel", "idle") if f"arm_sense_{t}" in r)
    chk["armed_rdata"] = all(r[f"arm_rdata_{t}"] <= V_FRAC * vdd for t in ("sel", "idle") if f"arm_rdata_{t}" in r)
    chk["armed_legs_off"] = all(r[f"arm_legon_{t}"] <= V_FRAC * vdd for t in ("sel", "idle") if f"arm_legon_{t}" in r)
    chk["armed_iread"] = all(r[f"arm_iread_{t}"] <= I_ARM_FRAC * B.I_REF for t in ("sel", "idle") if f"arm_iread_{t}" in r)
    chk["exclusion"] = all(r[f"both_{t}"] <= V_FRAC * vdd for t in ("sel", "idle") if f"both_{t}" in r)
    chk["pulse_read_off"] = r["pul_ron"] <= V_FRAC * vdd
    chk["pulse_sense"] = r["pul_sense"] <= V_FRAC * vdd and r["pul_rdata"] <= V_FRAC * vdd
    chk["decision"] = bool(ok) and t_dec is not None
    chk["no_false_high"] = not r["false_high"]
    chk["unselected_off"] = r["off_dev"] <= V_OFF_TOL
    r["chk"] = chk
    return r


# ---------------------------------------------------------------------------
# Stress
# ---------------------------------------------------------------------------

_CELL = re.compile(r"\.xc_(\d+)_(\d+)\.")


def stress_rows(sl: str, corner: dict, d: dict, man: dict):
    """Yield (key, device, model, pair, region, role, cls, peak, limit, source) for each probe."""
    m = {x["name"]: x["value"] for x in corner["measurements"]}
    sr, sc = d["cell"]
    for k, info in man.items():
        peak = m.get(k)
        if peak is None or peak != peak:
            raise Ungradable(f"probe {k} missing")
        role, cls, selected = info["role"], "-", False
        if role == "cell":
            mm = _CELL.search(info["device"])
            r, c = int(mm.group(1)), int(mm.group(2))
            selected = (r, c) == (sr, sc)
            band_sel = G.band_of_col(c)[0] == d["band"]
            cls = ("selected" if selected else "same_col" if c == sc else "same_row" if r == sr
                   else "other" if band_sel else "idle_band")
        lim, src = LIM.limit_for(info["model"], info["pair"], role, selected)
        yield k, info["device"], info["model"], info["pair"], info["region"], role, cls, peak, lim, src


def aggregate_stress(rows_iter, tag):
    """Fold stress rows into the worst case per (region, role, class, model, pair)."""
    agg = {}
    for key, dev, model, pair, region, role, cls, peak, lim, src in rows_iter:
        k = (region, role, cls, model, pair)
        a = agg.get(k)
        if a is None:
            a = agg[k] = {"peak": -1.0, "where": None, "dev": None, "limit": lim, "source": src, "n": 0, "over": 0}
        a["n"] += 1
        if lim is not None and peak > lim:
            a["over"] += 1
        if peak > a["peak"]:
            a["peak"], a["where"], a["dev"] = peak, tag, dev
    return agg


def merge_stress(into: dict, other: dict):
    for k, a in other.items():
        t = into.get(k)
        if t is None:
            into[k] = dict(a)
            continue
        t["n"] += a["n"]
        t["over"] += a["over"]
        if a["peak"] > t["peak"]:
            t["peak"], t["where"], t["dev"] = a["peak"], a["where"], a["dev"]
