#!/usr/bin/env python3
"""sim/programming-yield -- programming-yield Monte Carlo campaign (issue #66).

Per ratified candidate (== per grid region), per access-sizing sub-
configuration, per program-pulse condition (spec/split-axis-plan.md section
4) and per PVT corner, it draws `n` Monte Carlo samples of the breakdown-
threshold quantile (`ubd`) and the filament-resistance draw (`zrf`) of the
behavioral breakdown element in design/breakdown/, applies the program pulse
in a transient, and counts successes. Everything is a `klt sim` request with
a `monte_carlo` block submitted to the batch fleet; a failed submit is
recorded and NEVER falls back to a local grid.

    python3 sim/programming-yield/run_experiment.py --check-env
    python3 sim/programming-yield/run_experiment.py --candidates 1 --n 24
    python3 sim/programming-yield/run_experiment.py --smoke 1      # ONE sample, locally (probe)
    python3 sim/programming-yield/run_experiment.py --render RID --candidates 1

Stdlib only. The bench library of sim/cell-breakdown-model is imported, not
copied, so the candidates, bias placeholders, geometry levels and fleet
workarounds are identical by construction.
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


BM = _load(SIM_DIR / "cell-breakdown-model" / "run_experiment.py", "sim_bdmodel_lib")
CHAR = BM.CHAR
CHECK = BM.CHECK
BD_DIR = BM.BD_DIR

# --- campaign definition (documented in README "Design of the campaign") ---
# Pulse conditions, as multiples of the candidate's own V_bd(t_ref) and a pulse
# flat-top width. The nominal centre is (1.00 x V_bd(t_ref), t_ref): by the
# model's construction a median cell has D = 1 there, so the curve is centred
# on its own steep part for every candidate (relative structure identical
# across regions, absolute voltages different -- split-axis-plan.md sect. 4).
NOMINAL_FRAC, NOMINAL_TW = 1.00, 1e-6
V_FRACS = (0.96, 1.00, 1.04)             # voltage sweep at the nominal width
WIDTHS = (0.25e-6, 1e-6, 4e-6)           # width sweep at the nominal voltage
SIZINGS = ("min", "2x")                  # access-device width levels run
GEOM = "min"                             # capacitor geometry level run (README: why only one)
MC_SEED = 20261013
MC_VARY = "mismatch"
CONF_Z = 1.959964                        # 95 % two-sided
TR, T1 = 100e-9, 1e-6                    # edge time, pulse start (as the trigger bench)
TSTEP, TAFTER = 10e-9, 1e-6              # max step; settle time after the pulse
UB_FLOOR = 1e-6                          # clamp of the uniform draw away from {0,1}
SIGN = {"n": 1.0, "p": -1.0}


def proc_seed(proc: str) -> int:
    """A distinct monte_carlo.seed per process corner, so the PVT corners of a condition are independent
    sample sets (klt derives draws from seed, corner index, sample index, and each request here has only
    the temperature as its corner axis)."""
    return MC_SEED + 1000 * C.MOSCAP_CORNERS.index(proc)


def fmt(x: float) -> str:
    return BM.fmt(x)


def conditions() -> list[dict]:
    """The 5 pulse conditions, nominal listed once."""
    seen, out = set(), []
    for frac, tw in [(f, NOMINAL_TW) for f in V_FRACS] + [(NOMINAL_FRAC, w) for w in WIDTHS]:
        if (frac, tw) in seen:
            continue
        seen.add((frac, tw))
        out.append({"frac": frac, "tw": tw, "axis": "voltage" if tw == NOMINAL_TW else "width",
                    "tag": f"v{frac:.2f}_w{tw * 1e6:g}u".replace(".", "p")})
    return out


def vbd_ref(cand, params: dict) -> float:
    return BM.vbd_ref(cand, params)


def tstop(tw: float) -> float:
    return T1 + 2 * TR + tw + TAFTER


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------


def body_yield(pdk, cand, defaults, body_dir: Path, lib_root: str, sizing: str, tw: float) -> tuple[str, list[dict]]:
    """One breakdown event per deck. The two draws are .params evaluated once
    per run from the `.options seed=` klt writes from monte_carlo.seed."""
    out = [BM.body_header(pdk, body_dir, f"Candidate {cand.n} programming-yield bench (tran), "
                          f"access {sizing}, tw={tw:g}", cand, "trigger", lib_root)]
    out.append(f".param t1={fmt(T1)} tr={fmt(TR)} tw={fmt(tw)}")
    out.append(f".param ubd_s={{min(max(aunif(0.5,0.5),{UB_FLOOR:g}),{1 - UB_FLOOR:g})}}")
    out.append(".param zrf_s={agauss(0,1,1)}")
    out.append("VBL BL 0 DC 0")
    out.append(f"VWL WL 0 DC {fmt(cand.moscap_wl_on)}")
    out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
    out.append("BSH SH 0 V = '0.5*(1-cos(pi*min(max((time-t1)/tr,0),1)))"
               " - 0.5*(1-cos(pi*min(max((time-t1-tr-tw)/tr,0),1)))'")
    out.append("VAMP AMP 0 DC 0")
    out.append("BPL PL 0 V = 'v(amp)*v(sh)'")
    geo = BM.geometry(cand, defaults, sizing, GEOM)
    out.append(f"XA BL WL PL VB {cand.subckt}_bd {geo} bden=1 prog=0 dyn=1 ubd={{ubd_s}} zrf={{zrf_s}}")
    # NOTE: the draws are read back from the INSTANCE (probe nodes in af_breakdown), never from a
    # second reference to the .param: ngspice re-evaluates aunif/agauss at every reference.
    t_end = tstop(tw)
    t_meas = t_end - 0.1e-6
    ms = [
        BM.meas("tran", "st", "v(xa.xbd.st)", t_meas, "1"),
        BM.meas("tran", "dmg", "v(xa.xbd.dmg)", t_meas, "1"),
        BM.meas("tran", "ubd", "v(xa.xbd.ubdn)", t_meas, "1"),
        BM.meas("tran", "zrf", "v(xa.xbd.zrfn)", t_meas, "1"),
        # steady post-event current: end of the flat top, where the charging (displacement) current is gone
        BM.meas("tran", "ifl", "i(vbl)", T1 + TR + tw - 20e-9, "A"),
        {"name": "ipk_hi", "spice": ".meas tran ipk_hi MAX i(vbl)", "unit": "A"},
        {"name": "ipk_lo", "spice": ".meas tran ipk_lo MIN i(vbl)", "unit": "A"},
    ]
    return "\n".join(out) + "\n", ms


def make_request(cand, pdk, ms: list[dict], tw: float, fracs: list[float], n: int,
                 corners_proc: list[str], temps: list[float], seed: int) -> dict:
    two_lib = "smbb000149" in cand.extra_mos_libs
    del two_lib  # the capacitor corner is swept via sm141064 in every case (as the trigger bench)
    vbd = vbd_ref(cand, PARAMS)
    return {
        "netlist": "body.spice",
        "engine": "ngspice",
        "backend": BM.KLT_BACKEND,
        "batch": dict(BM.BATCH_OPTS),
        "measurements": ms,
        "options": {"timeout_s": 300, "keep_artifacts": True},
        "models": {"pdk": pdk.variant, "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": mc, "sections": ["typical", mc]} for mc in corners_proc],
            "temperature_c": temps,
            "supply_v": {"vamp": [round(SIGN[cand.polarity] * f * vbd, 6) for f in fracs]},
        },
        "analysis": {"kind": "tran", "args": f"{fmt(TSTEP)} {fmt(tstop(tw))} uic"},
        "monte_carlo": {"n": n, "seed": seed, "vary": MC_VARY},
    }


PARAMS: dict = {}
SUPERSEDES: list = [None]
KLT_CMD = BM.KLT_CMD

# --- read-margin criterion --------------------------------------------------
Z_GRID = (-3, -2, -1, 0, 1, 2, 3, 4)    # filament draw levels of the read table
READ_TEMPS = (-40.0, 27.0, 125.0)
READ_PROCESS, READ_RAIL = "ss", round(CHAR.V_READ_NOM * (1 - CHAR.SUPPLY_TOL), 6)
I_BOUND_DEFAULT = 1e-3                   # ASSUMED peak-current bound (A); NOT ratified
LATCHED, INTACT = 0.99, 0.01             # st thresholds


def ztag(z: int) -> str:
    return "z" + ("p" if z >= 0 else "m") + str(abs(z))


def body_readtab(pdk, cand, defaults, body_dir: Path, lib_root: str) -> tuple[str, list[dict]]:
    """Programmed-cell read current vs filament draw z, per sizing, at the
    read rail's low corner: the lookup the per-sample read decision uses."""
    out = [BM.body_header(pdk, body_dir, f"Candidate {cand.n} programmed-read table (z grid)", cand, "access_op", lib_root)]
    out.append(f"VBL BL 0 DC {fmt(CHAR.V_READ_NOM)}")
    out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
    out.append("VPL PL 0 DC 0")
    out.append("VDMY DMY 0 DC 0")
    out.append(f"VWLON WLON 0 DC {fmt(cand.wl_on)}")
    ms: list[dict] = []
    for sz in SIZINGS:
        geo = BM.geometry(cand, defaults, sz, GEOM)
        for z in Z_GRID:
            t = f"{sz}_{ztag(z)}"
            out.append(f"VM_{t} BL B_{t} 0")
            out.append(f"X_{t} B_{t} WLON PL VB {cand.subckt}_bd {geo} bden=1 prog=1 dyn=0 zrf={z}")
            ms.append(BM.meas("dc", f"i_{t}", f"i(vm_{t})", BM.DC_AT, "A"))
    return "\n".join(out) + "\n", ms


def make_readtab_request(cand, pdk, ms: list[dict]) -> dict:
    req = BM.make_request("access_op", cand, pdk, ms, PARAMS)
    req["corners"]["process"] = [p for p in req["corners"]["process"] if p["name"] == READ_PROCESS]
    req["corners"]["supply_v"] = {"vbl": [READ_RAIL]}
    req["corners"]["temperature_c"] = list(READ_TEMPS)
    return req


def make_request(cand, pdk, ms: list[dict], tw: float, fracs: list[float], n: int,
                 corners_proc: list[str], temps: list[float], seed: int) -> dict:
    vbd = vbd_ref(cand, PARAMS)
    return {
        "netlist": "body.spice",
        "engine": "ngspice",
        "backend": BM.KLT_BACKEND,
        "batch": dict(BM.BATCH_OPTS),
        "measurements": ms,
        "options": {"timeout_s": 300, "keep_artifacts": True},
        "models": {"pdk": pdk.variant, "lib": "libs.tech/ngspice/sm141064.ngspice"},
        "corners": {
            "process": [{"name": mc, "sections": ["typical", mc]} for mc in corners_proc],
            "temperature_c": temps,
            "supply_v": {"vamp": [round(SIGN[cand.polarity] * f * vbd, 6) for f in fracs]},
        },
        "analysis": {"kind": "tran", "args": f"{fmt(TSTEP)} {fmt(tstop(tw))} uic"},
        "monte_carlo": {"n": n, "seed": seed, "vary": MC_VARY},
    }


def gtag(sz: str, cnd: dict, proc: str) -> str:
    """One request per (sizing, condition, process corner), 300 samples: the fleet kills a job at
    3600 s, and 900- and 2700-sample requests exceeded it on the slower decks (README "Job size")."""
    return f"y_access-{sz}_{cnd['tag']}_{proc}"


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = CONF_Z) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def analytic_yield(cand, params: dict, frac: float, tw: float) -> float:
    """P(D reaches 1) for a constant-field pulse of effective width tw+tr:
    D = T/(tq t50) >= 1  <=>  u <= 1 - exp(-ln2 (T/t50)^beta). Ignores the
    edges' shape, the stock capacitor's divider and the completion term, so it
    is a cross-check of the sampler and the bookkeeping, not a prediction."""
    tox = params[f"c{cand.n}_bd_tox"]["value"]
    ebd, tref, gam, beta = (params[k]["value"] for k in ("bd_ebd", "bd_tref", "bd_gam", "bd_beta"))
    e = frac * vbd_ref(cand, params) / tox
    t50 = tref * math.exp(-gam * (e - ebd))
    x = (tw + TR) / t50
    return 1.0 - math.exp(-math.log(2) * x ** beta)


def zcrit_from_table(tab: dict[int, float], i_ref: float) -> float | None:
    """Largest filament draw z with I_read(z) >= I_ref, log-linear in z,
    linearly extrapolated past the grid ends. None if the table is unusable."""
    zs = sorted(z for z, i in tab.items() if i and i > 0)
    if len(zs) < 2 or i_ref <= 0:
        return None
    ly = {z: math.log(tab[z]) for z in zs}
    target = math.log(i_ref)
    for a, b in zip(zs, zs[1:]):
        if (ly[a] - target) * (ly[b] - target) <= 0 and ly[a] != ly[b]:
            return a + (target - ly[a]) * (b - a) / (ly[b] - ly[a])
    a, b = (zs[0], zs[1]) if ly[zs[0]] < target else (zs[-2], zs[-1])
    if ly[a] == ly[b]:
        return None
    return a + (target - ly[a]) * (b - a) / (ly[b] - ly[a])


def quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def sci(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.4e}"


@dataclass
class Sample:
    ok: bool                    # all measurements present, klt status pass
    st: float | None = None
    dmg: float | None = None
    ubd: float | None = None
    zrf: float | None = None
    ipk: float | None = None
    ikind: str = "pulse"        # "flat-top" (|i(VBL)| at the end of the flat top) or "pulse" (max over the pulse)


@dataclass
class Group:
    request_ok: bool = False
    status: str = ""
    remote: dict | None = None
    error: str | None = None
    samples: dict = field(default_factory=dict)   # (frac, process, temp) -> [Sample]
    seeds: dict | None = None
    jobs: list = field(default_factory=list)   # [{status, remote, error, label}]


def parse_group(cand, report: dict | None, params: dict) -> Group:
    g = Group()
    if report is None:
        return g
    g.request_ok = True
    g.status = report.get("status", "?")
    env = report.get("environment", {})
    g.remote = env.get("remote")
    g.seeds = env.get("monte_carlo")
    g.jobs.append({"status": g.status, "remote": g.remote, "error": None})
    vbd = vbd_ref(cand, params)
    for c in report["corners"]:
        sv = c.get("supply_v") or {}
        frac = round(abs(sv.get("vamp", 0.0)) / vbd, 2)
        key = (frac, c["process"], int(round(c["temperature_c"])))
        vals = {m["name"].lower(): m["value"] for m in c["measurements"]}
        need = ("st", "dmg", "ubd", "zrf", "ipk_hi", "ipk_lo")
        good = c["status"] == "pass" and all(vals.get(k) is not None for k in need)
        if good:
            if vals.get("ifl") is not None:
                smp = Sample(True, vals["st"], vals["dmg"], vals["ubd"], vals["zrf"], abs(vals["ifl"]), "flat-top")
            else:
                smp = Sample(True, vals["st"], vals["dmg"], vals["ubd"], vals["zrf"],
                             max(abs(vals["ipk_hi"]), abs(vals["ipk_lo"])), "pulse")
        else:
            smp = Sample(False)
        g.samples.setdefault(key, []).append(smp)
    return g


def classify(s: Sample, zcrit: float | None, read_defined: bool, ibound: float) -> str:
    """'ok' | 'fail' | 'inconclusive' for one sample."""
    if not s.ok:
        return "inconclusive"
    if INTACT < s.st < LATCHED:
        return "inconclusive"           # partly formed filament: neither state
    if s.st <= INTACT:
        return "fail"                   # did not program
    if s.ipk > ibound:
        return "fail"                   # latched, but peak current out of bound
    if read_defined and (zcrit is None or s.zrf > zcrit):
        return "fail"                   # latched, but reads wrong at the worst read corner
    return "ok"


def parse_record_figs(rid: str) -> dict[str, float]:
    """I_sneak_max and worst-corner I_prog_min out of the #62 record (not retyped)."""
    txt = (SIM_DIR / "cell-breakdown-model" / "records" / f"{rid}.md").read_text()
    sn = re.search(r"headline, st: I_sneak_max = ([0-9.eE+-]+) A", txt)
    pm = re.search(r"worst over all 45 resolved corners: \*\*([0-9.eE+-]+) A\*\*", txt)
    out = {}
    if sn:
        out["i_sneak_max"] = float(sn.group(1))
    if pm:
        out["i_prog_min_wc"] = float(pm.group(1))
    return out


def stored_bd_record(cand) -> str | None:
    """The #62 static-bench record of this candidate (the one with an I_prog_min section)."""
    for rp in sorted((SIM_DIR / "cell-breakdown-model" / "records").glob("*.md")):
        t = rp.read_text()
        if f"**I_prog_min (Candidate {cand.n})**" in t:
            return rp.stem
    return None


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def report_path(gdir: Path) -> Path | None:
    for name in ("report.json.gz", "report.json"):
        if (gdir / name).is_file():
            return gdir / name
    return None


def read_report(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as fh:
            return json.load(fh)
    return json.loads(path.read_text())


def run_group(bdir: Path, req: dict) -> tuple[dict | None, str | None]:
    R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
    report, err = BM.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
    if report is not None and "corners" in report:
        # gzip: the plain reports are ~1 MB per 300 samples; the content is byte-identical once gunzipped
        gz = bdir / "report.json.gz"
        if gz.exists():
            raise FileExistsError(f"refusing to overwrite existing evidence file: {gz}")
        with gzip.GzipFile(gz, "wb", mtime=0) as fh:
            fh.write((json.dumps(report, indent=2) + "\n").encode())
        return report, None
    R.write_once(bdir / "submit-error.txt", (err or json.dumps(report)[:4000]) + "\n")
    return None, err or "no corners in report"


def snapshot(cand) -> str:
    return BM.snapshot(cand)

# ---------------------------------------------------------------------------
# Loading saved results (the record is always rendered from the saved reports)
# ---------------------------------------------------------------------------


def merge_into(dst: Group, src: Group) -> None:
    dst.request_ok = dst.request_ok or src.request_ok
    for k, v in src.samples.items():
        dst.samples.setdefault(k, []).extend(v)
    dst.jobs.extend(src.jobs)
    if dst.status in ("", "pass") or src.status not in ("", "pass"):
        dst.status = src.status or dst.status


def load_run(cand, rid: str) -> tuple[dict[tuple[str, str], Group], dict | None, str | None]:
    groups: dict[tuple[str, str], Group] = {}
    base = THIS_DIR / "corners" / rid

    def load_dir(gdir: Path) -> Group | None:
        rp = report_path(gdir)
        if rp is not None:
            return parse_group(cand, read_report(rp), PARAMS)
        if (gdir / "submit-error.txt").is_file():
            g = Group()
            g.error = (gdir / "submit-error.txt").read_text()
            g.jobs.append({"status": "submit-error", "remote": None, "error": g.error})
            return g
        return None

    for sz in SIZINGS:
        for cnd in conditions():
            dirs = sorted(base.glob(f"y_access-{sz}_{cnd['tag']}_*"))
            # first-run layout: one request per (sizing, width) holding every voltage of that width
            old = base / f"y_access-{sz}_tw{cnd['tw'] * 1e6:g}u".replace(".", "p")
            if not dirs and old.is_dir():
                dirs = [old]
            merged = Group()
            seen = False
            for d in dirs:
                g = load_dir(d)
                if g is not None:
                    merge_into(merged, g)
                    seen = True
            if seen:
                groups[(sz, cnd["tag"])] = merged
    rt = report_path(base / "readtab")
    readtab = read_report(rt) if rt is not None else None
    rerr = (base / "readtab" / "submit-error.txt")
    return groups, readtab, rerr.read_text() if rerr.is_file() else None


def read_tables(readtab: dict | None) -> dict[str, dict[str, dict[int, float]]]:
    """sizing -> corner-id -> {z: |I_read|}"""
    out: dict[str, dict[str, dict[int, float]]] = {}
    if not readtab:
        return out
    for c in readtab["corners"]:
        cid = C.corner_id(c["process"], int(round(c["temperature_c"])),
                          C.fmt_node_supply("bl", (c.get("supply_v") or {}).get("vbl", 0.0)))
        for m in c["measurements"]:
            mm = re.match(r"i_(min|2x)_z([pm])(\d)$", m["name"].lower())
            if mm and m["value"] is not None and c["status"] == "pass":
                z = int(mm.group(3)) * (1 if mm.group(2) == "p" else -1)
                out.setdefault(mm.group(1), {}).setdefault(cid, {})[z] = abs(m["value"])
    return out


def worst_table(per_corner: dict[str, dict[int, float]]) -> dict[int, float]:
    """Pointwise minimum over the read corners: the worst-case read at each z."""
    z_all = sorted({z for t in per_corner.values() for z in t})
    return {z: min(t[z] for t in per_corner.values() if z in t) for z in z_all}


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def render_record(pdk, cand, rid: str, groups, readtab, rerr, params: dict, dirty, ibound: float,
                  n: int, note: str | None) -> str:
    vbd = vbd_ref(cand, params)
    conds = conditions()
    a: list[str] = []
    P_ = a.append
    P_(f"# Record {rid}")
    P_("")
    P_(f"- **Record ID**: {rid}")
    P_(f"- **Claim**: issue #66 -- programming yield of Candidate {cand.n} / Region {cand.region}, "
       "success fraction vs pulse condition (`spec/split-axis-plan.md` section 4), per access-sizing "
       "sub-configuration and PVT corner. Substantiates T1 item 6 (Monte Carlo evidence) only in the "
       "conditional form stated in the banner below.")
    P_(f"- **Netlist provenance**: schematic (design/netlists/{cand.netlist} wrapped by design/breakdown/"
       f"cell_candidates_bd.spice), {'dirty' if dirty else 'clean'} tree at run time")
    if note:
        P_(f"- **Run note**: {note}")
    P_("")
    P_("> **PROVENANCE BANNER -- READ FIRST.** Every number below is **conditional on the ASSUMED "
       "breakdown statistics** of `design/breakdown/breakdown_params.spice` (critical field, "
       "field-acceleration, Weibull shape, completion time, filament median and spread are all labelled "
       "`assumed`; only the oxide thicknesses are `literature`; nothing is `measured`). These yields are "
       "**not a prediction of gf180 silicon**. They show how the *design axes* move a yield curve under "
       "that stated model, and they exercise the harness; they cannot replace measured breakdown data "
       "from `measurements/`.")
    P_("")
    P_("- **Model parameters** (sha256 of `design/breakdown/breakdown_params.spice`: "
       f"`{BM.sha256(BD_DIR / 'breakdown_params.spice')}`):")
    P_("")
    P_("  | Parameter | Value | Unit | Provenance |")
    P_("  |---|---|---|---|")
    for k in (f"c{cand.n}_bd_tox", "bd_ebd", "bd_tref", "bd_gam", "bd_beta", "bd_tcomp", "bd_rf_med", "bd_rf_sig"):
        pr = params[k]
        P_(f"  | `{k}` | {sci(pr['value'])} | {pr.get('unit', '')} | {pr['provenance']} |")
    P_("")
    P_(f"  Derived: V_bd(t_ref) = **{vbd:.3f} V** (assumed, not a gf180 number). Pulse polarity "
       f"{'positive' if cand.polarity == 'n' else 'negative'} (as the #62 trigger bench).")
    P_("")
    P_("- **Success criterion** (per sample; a sample is exactly one of ok / fail / inconclusive):")
    P_(f"  1. the breakdown state is **latched** at the end of the transient: `st >= {LATCHED}` "
       f"(`st <= {INTACT}` is *not programmed* = fail; anything in between is a half-formed filament "
       "and is **inconclusive**, not counted either way);")
    kinds = {x.ikind for g in groups.values() for smp in g.samples.values() for x in smp if x.ok}
    if kinds == {"flat-top"}:
        what = ("the **steady post-event current**, |i(VBL)| at the end of the pulse flat top (20 ns before the "
                "falling edge). The whole-pulse maximum is not used for this candidate: the stock capacitor's "
                "charging current alone reaches several mA and is identical for programmed and unprogrammed "
                "samples, so it says nothing about the programming current (README \"Current criterion\")")
    else:
        what = ("the **peak access-path current** over the pulse, max |i(VBL)| (this record predates the "
                "flat-top measurement; for this candidate the filament current dominates the charging "
                "current, so the value is the programming current)")
    P_(f"  2. {what}, is `<= {sci(ibound)} A`. "
       "This bound is an **ASSUMED campaign parameter, not a ratified one**: `spec/architecture.md` "
       "section 2 leaves `I_target_max` open and the cell model has no ballast resistor, so the current "
       "limit here is the access device alone. The current distribution is tabulated so any other "
       "bound can be applied to the saved data;")
    if cand.n == 3:
        P_("  3. **read decision: NOT EVALUATED for Candidate 3.** The #62 records show no `I_ref` window "
           "at the inherited placeholder read bias (I_prog_min below I_sneak_max; follow-up #75), so "
           "\"post-pulse read decision correct\" has no defined threshold. The Candidate 3 yields below "
           "are therefore **upper bounds** on a full read-decision yield (latch and current bound only).")
        read_defined = False
    else:
        read_defined = True
        P_("  3. the **post-pulse read decision is correct at the worst-case read corner**: the programmed "
           "cell's read current `I_read(z)` at that sample's filament draw `z` is `>= I_ref`, where "
           "`I_read(z)` is the pointwise minimum over the read corners "
           f"({READ_PROCESS}, {', '.join(f'{t:g}' for t in READ_TEMPS)} degC, BL = {READ_RAIL} V) of the "
           "programmed-read table below, interpolated log-linearly in z, and "
           "`I_ref = sqrt(I_sneak_max * I_prog_min,wc)` from the #62 record. **`I_ref` is a campaign "
           "choice** (geometric mean of the window, which `spec/architecture.md` section 4 does not "
           "ratify), not a spec value. The decision uses the programmed side only; the unprogrammed side "
           "is the #62 `I_sneak_max`, which the model makes independent of the pulse.")
    P_("")
    P_(f"- **Sample sizing**: n = {n} Monte Carlo samples per (sub-configuration, pulse condition, PVT "
       f"corner) cell. The 95 % Wilson interval half-width is at most {1.96 * math.sqrt(0.25 / n):.3f} "
       f"(p = 0.5, n = {n}) and narrower toward the ends; pooling the {len(C.MOSCAP_CORNERS)} x "
       f"{len(C.TEMPS_C)} PVT corners of a condition multiplies the sample by up to "
       f"{len(C.MOSCAP_CORNERS) * len(C.TEMPS_C)}. Chosen from that half-width, not from a yield target. "
       "A cell that needs a tighter interval is re-run with a larger n as a new record.")
    P_(f"- **Sampler**: `klt sim` `monte_carlo` {{n={n}, vary=\"{MC_VARY}\"}}; the draws are "
       f"`ubd = aunif(0.5, 0.5)` clamped to [{UB_FLOOR:g}, 1 - {UB_FLOOR:g}] (uniform Weibull quantile) and "
       "`zrf = agauss(0, 1, 1)` (standard-normal filament draw), evaluated once per run from the "
       "`.options seed=` klt writes, with a distinct `monte_carlo.seed` per process corner "
       f"(base {MC_SEED} + 1000 x process index). The draws are a function of (seed, temperature index, "
       "sample index), so the PVT corners of a condition are independent samples while the two access "
       "sizings and the five pulse conditions reuse the same draws at the same (process, temperature, "
       "sample) -- a paired design, README \"Draw reuse\".")
    P_("")
    P_("- **Corner matrix run**: " + str(sorted({k[1] for g in groups.values() for k in g.samples})) +
       " x temperatures " + str(sorted({k[2] for g in groups.values() for k in g.samples})) + " degC x pulse "
       "conditions below x access sizing " + ", ".join(SIZINGS) + f" (capacitor geometry fixed at `{GEOM}`). "
       "Programming transient only; the read-side PVT is the table below.")
    P_("- **Not run, and why**: the capacitor-geometry axis (`2x`). `af_breakdown` has **no area "
       "dependence** (its kinetics see tox only), so a larger capacitor changes the breakdown statistics "
       "of this model by construction -- it is *not resolvable* here and a run would only add the stock "
       "capacitor's different divider. The model must gain area scaling (Poisson-area Weibull) before "
       "that split axis can be read from a yield curve; running it now would manufacture a null result.")
    P_("")
    # ---- execution
    P_("- **Execution**: engine ngspice on the batch fleet; every request names `\"backend\": \"batch\"`; "
       "no local grid was run. Jobs:")
    listed: set = set()
    for (sz, tag), g in sorted(groups.items()):
        for j in g.jobs:
            r = j.get("remote") or {}
            key = (sz, r.get("job_id") or id(j))
            if key in listed:
                continue                  # first-run layout: one job covers several conditions
            listed.add(key)
            P_(f"  - access `{sz}`, `{tag}`: klt status `{j.get('status') or 'submit-error'}`, "
               f"job `{r.get('job_id', 'n/a')}`, runner klt {r.get('runner_klt_version', 'n/a')} "
               f"({r.get('runner_compatibility', 'n/a')}), {r.get('elapsed_seconds', 'n/a')} s"
               + (f" -- ERROR: {esc(j['error'][:300])}" if j.get("error") else ""))
    P_("")
    # ---- read table
    tabs = read_tables(readtab)
    iref = zc = None
    figs: dict[str, float] = {}
    zcrit: dict[str, float | None] = {}
    if read_defined:
        bdrid = stored_bd_record(cand)
        figs = parse_record_figs(bdrid) if bdrid else {}
        P_(f"- **Programmed-read table** (read side; request `readtab`, source of `I_read(z)`); "
           f"#62 record `{bdrid}`: I_sneak_max = {sci(figs.get('i_sneak_max'))} A, worst-corner "
           f"I_prog_min = {sci(figs.get('i_prog_min_wc'))} A:")
        if "i_sneak_max" in figs and "i_prog_min_wc" in figs:
            iref = math.sqrt(figs["i_sneak_max"] * figs["i_prog_min_wc"])
        P_(f"  - **I_ref (campaign choice) = {sci(iref)} A**")
        if rerr:
            P_(f"  - read table submit ERROR: {esc(rerr[:300])}")
        P_("")
        P_("  | Sizing | " + " | ".join(f"z={z:+d}" for z in Z_GRID) + " | z_crit |")
        P_("  |---|" + "---|" * (len(Z_GRID) + 1))
        for sz in SIZINGS:
            wt = worst_table(tabs.get(sz, {})) if tabs.get(sz) else {}
            zcrit[sz] = zcrit_from_table(wt, iref) if iref and wt else None
            P_(f"  | `{sz}` (min over read corners) | " + " | ".join(sci(wt.get(z)) for z in Z_GRID)
               + f" | {('%.2f' % zcrit[sz]) if zcrit[sz] is not None else 'n/a'} |")
        P_("")
        P_("  `z_crit` is the filament draw above which the read falls under `I_ref`; the assumed "
           "filament median/spread put it at "
           + ("; ".join(f"`{sz}`: P(z <= z_crit) = {0.5 * (1 + math.erf(zcrit[sz] / math.sqrt(2))):.4f}"
                        for sz in SIZINGS if zcrit.get(sz) is not None) or "n/a") + ".")
        P_("")
    # ---- yield tables
    P_("- **Result** -- success fraction vs pulse condition. One block per access sizing; rows are "
       "(condition, PVT corner). `succ/n` counts ok samples over **all** n drawn; `err` are inconclusive "
       "samples (klt error / non-converged / half-formed), so `yield` is a **lower bound** (errors counted "
       "as not-ok) and `yield_hi` counts them as ok. `yield, no I bound` drops criterion 2 (the unratified current "
       "bound) and keeps latch and read. CI is the 95 % Wilson interval on `succ/n`. "
       "`analytic` is the closed-form constant-field Weibull prediction, a sampler cross-check only.")
    P_("")
    ibsweep = (1e-5, 1e-4, 1e-3, 1e-2)
    cond_rows: dict = {}
    for sz in SIZINGS:
        P_(f"### Candidate {cand.n} / Region {cand.region}, access sizing `{sz}`")
        P_("")
        P_("| Condition | V_pulse [V] | tw [us] | Corner | n | succ | err | yield | CI95 | yield_hi | yield, no I bound | analytic |")
        P_("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cnd in conds:
            g = groups.get((sz, cnd["tag"]))
            if not g or not g.samples:
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | (no data) | | | | | | | | |")
                continue
            pooled = {"n": 0, "succ": 0, "err": 0}
            for key in sorted(k for k in g.samples if k[0] == cnd["frac"]):
                smp = g.samples[key]
                cl = [classify(x, zcrit.get(sz), read_defined, ibound) for x in smp]
                ok, er = cl.count("ok"), cl.count("inconclusive")
                lo, hi = wilson(ok, len(smp))
                cid = C.corner_id(key[1], key[2], "nosupply").replace("_nosupply", "")
                nb = [classify(x, zcrit.get(sz), read_defined, float("inf")) for x in smp].count("ok")
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | `{cid}` | {len(smp)} | "
                   f"{ok} | {er} | {ok / len(smp):.3f} | [{lo:.3f}, {hi:.3f}] | {(ok + er) / len(smp):.3f} | "
                   f"{nb / len(smp):.3f} | {analytic_yield(cand, params, cnd['frac'], cnd['tw']):.3f} |")
                pooled["n"] += len(smp); pooled["succ"] += ok; pooled["err"] += er; pooled["nb"] = pooled.get("nb", 0) + nb
            if pooled["n"]:
                lo, hi = wilson(pooled["succ"], pooled["n"])
                P_(f"| `{cnd['tag']}` | {cnd['frac'] * vbd:.3f} | {cnd['tw'] * 1e6:g} | **all PVT pooled** | "
                   f"{pooled['n']} | {pooled['succ']} | {pooled['err']} | **{pooled['succ'] / pooled['n']:.3f}** | "
                   f"[{lo:.3f}, {hi:.3f}] | {(pooled['succ'] + pooled['err']) / pooled['n']:.3f} | "
                   f"{pooled['nb'] / pooled['n']:.3f} | {analytic_yield(cand, params, cnd['frac'], cnd['tw']):.3f} |")
                cond_rows[(sz, cnd["tag"])] = pooled
        P_("")
    # ---- worst corner
    P_("- **Worst PVT corner per condition** (lowest yield among the corners of a cell; the "
       "yield-vs-condition claim for design purposes is this, not the pooled row):")
    P_("")
    P_("  | Sizing | Condition | Worst corner | yield | CI95 |")
    P_("  |---|---|---|---|---|")
    for sz in SIZINGS:
        for cnd in conds:
            g = groups.get((sz, cnd["tag"]))
            if not g:
                continue
            best = None
            for key, smp in g.samples.items():
                if key[0] != cnd["frac"]:
                    continue
                cl = [classify(x, zcrit.get(sz), read_defined, ibound) for x in smp]
                y = cl.count("ok") / len(smp)
                if best is None or y < best[0]:
                    best = (y, key, cl.count("ok"), len(smp))
            if best:
                lo, hi = wilson(best[2], best[3])
                cid = C.corner_id(best[1][1], best[1][2], "nosupply").replace("_nosupply", "")
                P_(f"  | `{sz}` | `{cnd['tag']}` | `{cid}` | {best[0]:.3f} | [{lo:.3f}, {hi:.3f}] |")
    P_("")
    # ---- sampler check
    seen: set = set()
    ub, zr = [], []
    total = 0
    for g in groups.values():
        for smp in g.samples.values():
            for x in smp:
                if x.ok:
                    total += 1
                    k = (round(x.ubd, 6), round(x.zrf, 6))
                    if k not in seen:
                        seen.add(k); ub.append(x.ubd); zr.append(x.zrf)
    if ub:
        mu, sd = sum(ub) / len(ub), math.sqrt(sum((x - sum(ub) / len(ub)) ** 2 for x in ub) / len(ub))
        zm, zs = sum(zr) / len(zr), math.sqrt(sum((x - sum(zr) / len(zr)) ** 2 for x in zr) / len(zr))
        P_(f"- **Sampler check** ({total} usable samples, {len(ub)} distinct (ubd, zrf) draws; the rest are "
           "deliberate repeats, see README \"Draw reuse\"), statistics over the distinct draws: "
           f"`ubd` mean {mu:.4f} (uniform: 0.5000, s.e. {math.sqrt(1 / 12 / len(ub)):.4f}), sd {sd:.4f} "
           f"(uniform: 0.2887), min {min(ub):.4f}, max {max(ub):.4f}; `zrf` mean {zm:+.4f} "
           f"(s.e. {1 / math.sqrt(len(zr)):.4f}), sd {zs:.4f} (target 1).")
        P_("")
    # ---- current
    P_(f"- **Access-path current of latched samples** ({'flat-top end' if kinds == {'flat-top'} else 'max over the pulse'}; "
       "the data behind criterion 2):")
    P_("")
    P_("  | Sizing | latched samples | median [A] | p95 [A] | max [A] | frac <= " +
       " | frac <= ".join(sci(b) for b in ibsweep) + " |")
    P_("  |---|---|---|---|---|" + "---|" * len(ibsweep))
    for sz in SIZINGS:
        ip = [x.ipk for (s_, _), g in groups.items() if s_ == sz for smp in g.samples.values() for x in smp
              if x.ok and x.st >= LATCHED]
        if ip:
            P_(f"  | `{sz}` | {len(ip)} | {sci(quantile(ip, .5))} | {sci(quantile(ip, .95))} | {sci(max(ip))} | " +
               " | ".join(f"{sum(1 for v in ip if v <= b) / len(ip):.3f}" for b in ibsweep) + " |")
    P_("")
    P_("- **What this does not show**: (i) any silicon yield; (ii) the capacitor-area axis (model has none); "
       "(iii) temperature or process dependence of breakdown itself (the model has none, so PVT enters "
       "only through the stock capacitor/access device); (iv) ballast sizing (no ballast in the cell "
       "model; the current bound is an assumed placeholder); (v) the program-path bias scheme (not "
       "ratified; the pulse is applied on PL with BL = 0 and the access device on, as in the #62 trigger "
       "bench); (vi) any difference between candidates beyond oxide thickness and the access device: the "
       "model gives all three the same kinetics and the same seeded draws, so candidates with equal relative "
       "pulse and comparable access devices reproduce each other's latch counts (e.g. Candidates 1 and 3 here). "
       "A cross-candidate yield comparison is a statement about this assumed model, not about the oxides.")
    P_("")
    P_("- **Links**:")
    P_(f"  - frozen netlist snapshot: `sim/programming-yield/netlist-snapshots/{rid}.spice`")
    P_(f"  - requests, decks and klt reports: `sim/programming-yield/corners/{rid}/`")
    P_(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} / Claude (loom sweep, issue #66)")
    P_(f"- **Supersedes**: {SUPERSEDES[0] or '(none)'}")
    return "\n".join(a) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def smoke(pdk, cand, params: dict) -> int:
    """ONE sample, ONE corner, locally -- a debug probe, not evidence."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}"
    work.mkdir(parents=True)
    tw = NOMINAL_TW
    body, ms = body_yield(pdk, cand, defaults, work, str(pdk.variant_dir), "min", tw)
    (work / "body.spice").write_text(body)
    req = make_request(cand, pdk, ms, tw, [NOMINAL_FRAC], 1, ["moscap_typical"], [27.0], MC_SEED)
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    t0 = time.time()
    report, err = BM.run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    print(f"smoke c{cand.n}: {c['corner_id']} status={c['status']} {time.time() - t0:.1f}s wall; work dir {work}")
    for m in c["measurements"]:
        print(f"   {m['name']} = {m['value']}")
    return 0 if c["status"] == "pass" else 1


def render_only(pdk, cand, rid: str, params: dict, ibound: float, n: int, note: str | None) -> int:
    groups, readtab, rerr = load_run(cand, rid)
    if not groups:
        print(f"ERROR: no saved reports under corners/{rid}/", file=sys.stderr)
        return 2
    pf = THIS_DIR / "corners" / rid / "run-provenance.json"
    dirty = json.loads(pf.read_text())["dirty"] if pf.is_file() else None
    snap = THIS_DIR / "netlist-snapshots" / f"{rid}.spice"
    if not snap.exists():
        R.write_once(snap, snapshot(cand))
    R.write_once(THIS_DIR / "records" / f"{rid}.md",
                 render_record(pdk, cand, rid, groups, readtab, rerr, params, dirty, ibound, n, note))
    print(f"record: records/{rid}.md (rendered from saved reports)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--n", type=int, default=100, help="Monte Carlo samples per cell")
    ap.add_argument("--processes", default=",".join(C.MOSCAP_CORNERS))
    ap.add_argument("--temps", default=",".join(str(t) for t in C.TEMPS_C))
    ap.add_argument("--ibound", type=float, default=I_BOUND_DEFAULT)
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--smoke", default=None, metavar="N")
    ap.add_argument("--render", default=None, metavar="RECORD_ID")
    ap.add_argument("--note", default=None)
    ap.add_argument("--conds", default="", help="comma list of condition tags to run (default: all 5)")
    ap.add_argument("--sizings", default=",".join(SIZINGS))
    ap.add_argument("--supersedes", default=None, help="record id this run supersedes (stated in the record)")
    ap.add_argument("--no-readtab", action="store_true", help="skip the programmed-read table request")
    ap.add_argument("--klt", default="klt")
    args = ap.parse_args(argv)
    KLT_CMD[:] = args.klt.split()
    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if not shutil.which(KLT_CMD[0]):
        print(f"ERROR: {KLT_CMD[0]} not on PATH", file=sys.stderr)
        return 3
    params, perr = CHECK.parse_params((BD_DIR / "breakdown_params.spice").read_text())
    if perr:
        print("ERROR: breakdown_params.spice fails provenance checks", file=sys.stderr)
        return 3
    PARAMS.update(params)
    SUPERSEDES[0] = args.supersedes
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK + parameter file OK.")
        return 0
    by_n = {c.n: c for c in CHAR.CANDIDATES}
    if args.render:
        return render_only(pdk, by_n[int(args.candidates)], args.render, params, args.ibound, args.n, args.note)
    if args.smoke:
        return smoke(pdk, by_n[int(args.smoke)], params)

    conds = {x for x in args.conds.split(",") if x}
    sizings = [x for x in args.sizings.split(",") if x]
    procs = [x for x in args.processes.split(",") if x]
    temps = [float(x) for x in args.temps.split(",") if x]
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n_c in [int(x) for x in args.candidates.split(",") if x.strip()]:
        cand = by_n[n_c]
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n_c} (Region {cand.region}) record {rid}")
        base = THIS_DIR / "corners" / rid
        R.write_once(base / "run-provenance.json",
                     json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty, "n": args.n,
                                 "processes": procs, "temps": temps, "ibound": args.ibound}) + "\n")
        jobs: list[tuple[str, Path, dict]] = []
        for sz in sizings:
            for cnd in conditions():
                if conds and cnd["tag"] not in conds:
                    continue
                for proc in procs:
                    gdir = base / gtag(sz, cnd, proc)
                    gdir.mkdir(parents=True)
                    body, ms = body_yield(pdk, cand, defaults, gdir, BM.FLEET_PDK_VARIANT_DIR, sz, cnd["tw"])
                    R.write_once(gdir / "body.spice", body)
                    jobs.append((f"{sz}/{cnd['tag']}/{proc}", gdir,
                                 make_request(cand, pdk, ms, cnd["tw"], [cnd["frac"]], args.n, [proc], temps, proc_seed(proc))))
        if cand.n != 3 and not args.no_readtab:
            gdir = base / "readtab"
            gdir.mkdir(parents=True)
            body, ms = body_readtab(pdk, cand, defaults, gdir, BM.FLEET_PDK_VARIANT_DIR)
            R.write_once(gdir / "body.spice", body)
            jobs.append(("readtab", gdir, make_readtab_request(cand, pdk, ms)))
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.time()

        def go(j):
            return j[0], run_group(j[1], j[2])
        with ThreadPoolExecutor(max_workers=2) as ex:      # fleet submits, not local simulation
            for label, (report, err) in ex.map(go, jobs):
                job = ((report or {}).get("environment", {}).get("remote") or {}).get("job_id")
                print(f"   {label}: {'ok ' + str(report.get('status')) if report else 'SUBMIT ERROR'} "
                      f"({time.time() - t0:.0f}s, job {job})" + (f" {err[:200]}" if err else ""), flush=True)
                if not report:
                    rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", snapshot(cand))
        groups, readtab, rerr = load_run(cand, rid)
        R.write_once(THIS_DIR / "records" / f"{rid}.md",
                     render_record(pdk, cand, rid, groups, readtab, rerr, params, dirty, args.ibound, args.n, args.note))
        print(f"   record: records/{rid}.md")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
