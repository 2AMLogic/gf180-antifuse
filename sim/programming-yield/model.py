#!/usr/bin/env python3
"""sim/programming-yield model.py -- the experiment's shared library.

Campaign constants, SPICE deck and `klt sim` request builders, the
statistical analysis helpers (Wilson interval, analytic Weibull yield,
z_crit interpolation, quantiles), the per-sample/per-group data model and
classification, and the saved-report loaders. The CLI entry point is
run_experiment.py, which loads this module (and render.py) via
harness.modload and re-exports this surface, so consumers keep loading
run_experiment.py as the library. render.py imports one-way from this
module; nothing here imports render.py or the CLI.
"""

from __future__ import annotations

import gzip
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import numfmt as NF  # noqa: E402


# The bench library of sim/cell-breakdown-model is imported, not copied, so
# the candidates, bias placeholders, geometry levels and fleet workarounds
# are identical by construction.
BM = load_module(SIM_DIR / "cell-breakdown-model" / "run_experiment.py", "sim_bdmodel_lib")
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


fmt = NF.fmt


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


PARAMS: dict = {}

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


# ---------------------------------------------------------------------------
# Loading saved results (the record is always rendered from the saved reports)
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


def merge_into(dst: Group, src: Group) -> None:
    dst.request_ok = dst.request_ok or src.request_ok
    for k, v in src.samples.items():
        dst.samples.setdefault(k, []).extend(v)
    dst.jobs.extend(src.jobs)
    if dst.status in ("", "pass") or src.status not in ("", "pass"):
        dst.status = src.status or dst.status


def load_run(cand, rid: str, base_dir: Path | None = None) -> tuple[dict[tuple[str, str], Group], dict | None, str | None]:
    groups: dict[tuple[str, str], Group] = {}
    base = Path(base_dir) if base_dir is not None else THIS_DIR / "corners" / rid

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
