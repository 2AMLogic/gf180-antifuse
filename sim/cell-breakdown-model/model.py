#!/usr/bin/env python3
"""sim/cell-breakdown-model model.py -- the experiment's shared library.

Bench constants, V_bd sensitivity overrides, SPICE deck and request builders,
report collection/grading, and the analysis helpers of the #62/#74/#75
campaigns. The CLI entry point is run_experiment.py, which loads this module
(and render.py) via harness.modload and re-exports this surface, so consumers
keep loading run_experiment.py as the library. render.py imports one-way from
this module; nothing here imports render.py or the CLI.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
BD_DIR = REPO_ROOT / "design" / "breakdown"
WRAPPERS = BD_DIR / "cell_candidates_bd.spice"
CHAR_DIR = SIM_DIR / "cell-device-characterization"

sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import numfmt as NF  # noqa: E402
from harness import pdk as P  # noqa: E402


# The existing characterization experiment is imported as a library, not
# copied: candidate definitions, OFF-bias levels, C-V bias points, the read
# rail, gmin and the geometry levels are therefore identical by construction.
CHAR = load_module(CHAR_DIR / "run_experiment.py", "sim_char_lib")
CHECK = load_module(BD_DIR / "check_params.py", "bd_check_params")

# --- bench constants (stimulus placeholders, documented in README) ---------
KLT_BACKEND = "batch"
# The fleet runner image currently ships an older klt than this host's client
# (README "Fleet klt version"). Every request below is restricted to features
# that runner has (.meas-only measurements, single-library process bundles),
# so the skew cannot silently drop an option; the version check is set to
# `warn` so the job runs, and environment.remote records both versions.
BATCH_OPTS = {"runner_version_check": "warn", "capacity_wait_s": 1800}
# capacity_wait_s makes klt wait and relaunch the SAME request on either
# refusal class (batch_no_capacity / batch_concurrency_cap, the fleet's
# shared concurrency cap), bounded by the value -- never fall back to a
# local run.
# The executing host's gf180mcuD variant directory, needed for the one model
# library Candidate 2 loads from the body (README "Two model libraries").
# Observed in fleet-generated corner decks: `.lib /opt/pdk/gf180mcuD/...`.
FLEET_PDK_VARIANT_DIR = "/opt/pdk/gf180mcuD"


def fleet_lib_root(pdk: P.PDKPaths) -> str:
    """The `.lib` root for a batch body. klt >= 0.8 refuses an absolute target outside this host's $PDK_ROOT
    (the old fixed /opt/pdk path) and rewrites one under it to $PDK_ROOT/<rel> for the runner, so a batch run
    names this host's own variant dir and exports PDK_ROOT to its parent (process environment only)."""
    import os
    os.environ.setdefault("PDK_ROOT", str(pdk.variant_dir.parent))
    return str(pdk.variant_dir)
DEFAULT_RELTOL = 1e-3          # ngspice default reltol
DEFAULT_ABSTOL = 1e-12         # ngspice default abstol (A)
# Quantity classes for the regression criterion (README "Regression
# criterion"): gmin-floor currents sit below abstol, where ngspice's own
# convergence test |di| <= reltol*|i| + abstol is the only resolution the
# solver promises; well-conditioned quantities are held to reltol alone.
GMIN_FLOOR = ("ioff", "ilk")
WELL_CONDITIONED = ("ron", "cval")
UBD_LOW = 0.01                 # Weibull quantile of the trigger bench's 2nd instance
TRIG_FRACTIONS = (0.9, 0.95, 1.0, 1.1)  # x V_bd(tref); the rated voltage is the 5th point
TRIG_T1, TRIG_TR, TRIG_TW = 1e-6, 100e-9, 10e-6
TRIG_TSTOP, TRIG_TSTEP, TRIG_TMEAS = 20e-6, 10e-9, 19.9e-6
# .op is expressed as a 3-point DC sweep of an unconnected dummy source, read
# at its interior point (.meas FIND needs an interval; klt's runner has no
# `expr` measurements, and ngspice has no `.meas op`). AC likewise uses a
# 3-point sweep centred on the characterization experiment's frequency.
DC_ARGS, DC_AT = "VDMY -1 1 1", 0.0
F_RON, F_CV = 1e7, 1e3

VARIANTS = {
    "st": "stock cell (design/netlists, unwrapped)",
    "b0": "wrapper, breakdown element disabled (bden=0)",
    "b1": "wrapper, element enabled, unprogrammed (bden=1 prog=0 dyn=0)",
}
REGRESSION_VARIANTS = ("st", "b0", "b1")
BIAS_TAGS = ("lo", "mid", "hi")

# --- Candidate 3 read-bias study (issue #75) --------------------------------
# One scenario = one complete read-bias arrangement for the Candidate 3 cell:
# the read rail (BL = rail_scale x the swept VBL corner value), the selected
# word-line level, and how the access device's n-well (VB) is driven. The
# unselected word-line OFF levels are NOT a scenario axis: every scenario uses
# the characterization experiment's own three PMOS OFF levels (VDD -/0/+ 0.3 V
# with VDD = 3.3 V), so the leakage side is compared at identical WL stimulus.
# Programmed and unprogrammed cells are always simulated at the SAME scenario
# bias in the SAME deck (the issue's "same bias" requirement).
#   vb_mode "fixed": VB = vb_v volts      "track": VB = BL rail + vb_v volts
BIAS_BENCH = "bias_op"


@dataclass(frozen=True)
class ReadBias:
    name: str
    rail_scale: float
    wl_on: float
    vb_mode: str
    vb_v: float
    note: str


BIAS_SCENARIOS: tuple[ReadBias, ...] = (
    ReadBias("s0_placeholder", 1.0, 0.0, "fixed", 3.3,
             "inherited placeholder: WL on = 0 V, n-well 3.3 V (reproduces #75)"),
    ReadBias("s1_wl_neg1", 1.0, -1.0, "fixed", 3.3, "WL driven below ground (-1.0 V), n-well 3.3 V"),
    ReadBias("s2_wl_neg2", 1.0, -2.0, "fixed", 3.3, "WL driven below ground (-2.0 V), n-well 3.3 V"),
    ReadBias("s3_vb_track", 1.0, 0.0, "track", 0.0, "n-well lowered to the read rail (VB = BL), WL on = 0 V"),
    ReadBias("s4_vb_fix1v", 1.0, 0.0, "fixed", 1.0, "n-well lowered to the NOMINAL read rail (fixed 1.0 V), WL on = 0 V"),
    ReadBias("s5_rail1v8", 1.8, 0.0, "fixed", 3.3, "read rail raised to 1.8 V, WL on = 0 V, n-well 3.3 V"),
    ReadBias("s6_rail1v8_vb_track", 1.8, 0.0, "track", 0.0, "read rail 1.8 V, n-well tied to the rail, WL on = 0 V"),
    ReadBias("s7_vb_track_p0v3", 1.0, 0.0, "track", 0.3,
             "sensitivity: n-well 0.3 V ABOVE the read rail (well-supply offset), WL on = 0 V"),
    ReadBias("s8_vb_track_m0v3", 1.0, 0.0, "track", -0.3,
             "sensitivity: n-well 0.3 V BELOW the read rail (source junction forward-biased 0.3 V), WL on = 0 V"),
)
# the scenario the decision record (spec/candidate3-read-bias-decision.md) adopts
CHOSEN_C3_SCENARIO = "s3_vb_track"


def within_tol(q: str, x: float, ref: float) -> bool:
    if q in GMIN_FLOOR:
        return abs(x - ref) <= DEFAULT_RELTOL * abs(ref) + DEFAULT_ABSTOL
    return abs(x - ref) <= DEFAULT_RELTOL * abs(ref)


def rel_dev(x: float, ref: float) -> float:
    if ref == 0:
        return 0.0 if x == 0 else math.inf
    return abs(x - ref) / abs(ref)


fmt = NF.fmt

# --- V_bd sensitivity points (issue #130) -----------------------------------
# Primary-sourced |BVox| per candidate (docs/breakdown-vbd-sources.md section 2, source S1: GF180MCU PDK
# electrical specs 5.4): typical and spec floor [V]. The shared `bd_ebd` model parameter is NOT changed
# (operator ruling on #130); a sensitivity run overrides it PER CANDIDATE in the generated deck only, as
# bd_ebd = V_bd / tox. This reads the sourced BVox as the model's V_bd(t_ref): S1 states no ramp/current
# condition, so that identification is an ASSUMPTION, which is why every such record is a sensitivity
# point and not a parameter update.
SOURCED_VBD = {"typ": {1: 9.0, 2: 16.0, 3: 8.8}, "floor": {1: 7.0, 2: 12.0, 3: 7.0}}
# bd_ebd [V/m] the current run injects into every deck after the wrapper include; None = file value.
VBD_EBD_OVERRIDE: float | None = None


def apply_vbd_case(params: dict, case: str | None, n: int) -> dict:
    """Params for a V_bd sensitivity point (a copy; the parsed file values are not touched). Also arms
    the deck override. case None = the assumed file values, no override."""
    global VBD_EBD_OVERRIDE
    if case is None:
        VBD_EBD_OVERRIDE = None
        return params
    ebd = SOURCED_VBD[case][n] / params[f"c{n}_bd_tox"]["value"]
    VBD_EBD_OVERRIDE = ebd
    out = {k: dict(v) for k, v in params.items()}
    out["bd_ebd"]["value"] = ebd
    out["bd_ebd"]["provenance"] = "sensitivity"
    return out


def sensitivity_block(case: str | None, n: int, params: dict) -> str:
    """Markdown bullet inserted into a record of a sensitivity run ('' for an assumed-V_bd run)."""
    if case is None:
        return ""
    tox = params[f"c{n}_bd_tox"]["value"]
    assumed = 1.0e9 * tox
    return (
        f"- **V_bd SENSITIVITY POINT (`{case}`), NOT a parameter update** (issue #130, operator ruling on "
        f"2AMLogic/gf180-antifuse#130): this record re-runs the bench with Candidate {n}'s gate-oxide V_bd(t_ref) set "
        f"to the primary-sourced BVox {case} value **{SOURCED_VBD[case][n]:g} V** "
        f"(`docs/breakdown-vbd-sources.md` section 2, S1), via a per-candidate `.param bd_ebd = "
        f"{VBD_EBD_OVERRIDE:.6g}` (= V_bd / tox, tox = {tox:.3g} m) injected into the generated deck after the wrapper "
        f"include. The shared `bd_ebd` in `design/breakdown/breakdown_params.spice` is unchanged (sha256 "
        f"`{sha256(BD_DIR / 'breakdown_params.spice')}`, still 1.0e9 V/m = {assumed:.2f} V for this candidate). The "
        "identification of sourced BVox with the model's V_bd at t_ref = 1 us is an ASSUMPTION (BVox has no stated "
        "ramp/current condition); every other breakdown and filament parameter stays `assumed`. Compare against "
        "the assumed-V_bd records per candidate and per stress level; levels are never merged.\n"
    )


def tag_record(text: str, block: str) -> str:
    """Insert the sensitivity block right after the record's `- **Record ID**` line."""
    if not block:
        return text
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("- **Record ID**"):
            return "\n".join(lines[:i + 1] + [block.rstrip("\n")] + lines[i + 1:])
    raise ValueError("record has no Record ID line to attach the sensitivity block to")


def sg_tag(sizing: str, geom: str) -> str:
    return f"s{1 if sizing == 'min' else 2}g{1 if geom == 'min' else 2}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Trigger levels (the deck bodies themselves live in benches.py)
# ---------------------------------------------------------------------------


def vbd_ref(cand, params: dict) -> float:
    return params["bd_ebd"]["value"] * params[f"c{cand.n}_bd_tox"]["value"]


def trigger_levels(cand, params: dict) -> list[float]:
    sign = 1.0 if cand.polarity == "n" else -1.0
    vbd = vbd_ref(cand, params)
    return [sign * cand.cap_rated_v] + [sign * f * vbd for f in TRIG_FRACTIONS]


# ---------------------------------------------------------------------------
# Issue #74: single-instance trigger and BL-driven program benches
# ---------------------------------------------------------------------------
#
# Each deck holds exactly ONE cell. The #62 trigger bench (body_trigger, kept
# unchanged above as the control) holds two, stressing one; the idle one is
# where most of its non-convergence was reported (README "Transient
# convergence (#74)"). The variant is the only difference between the four
# decks of a stimulus, so a corner that fails in the stock deck but not in
# the enabled one (or vice versa) is attributable.

CONV_STIMULI = {
    "trig1": "PL-driven (the #62 trigger stimulus), one cell per deck, BL = 0; raised-cosine edges",
    "prog": "BL-driven through a ballast resistor from a VPP pulse, PL = 0 return (spec/architecture.md 1.2, 2); "
            "raised-cosine edges",
    "trigc": "as trig1, with C-infinity edges",
    "progc": "as prog, with C-infinity edges",
}
# PL-driven (signed level on PL) or BL-driven (positive VPP on the BL side)
STIM_DRIVE = {"trig1": "pl", "trigc": "pl", "prog": "bl", "progc": "bl"}
# Edge shape of the stress pulse, rise and fall both over TRIG_TR:
#   rc    raised cosine, 0.5*(1-cos(pi*u)): continuous slope, but its second
#         derivative jumps at both ends of each edge (the #62 shape)
#   cinf  f(u)/(f(u)+f(1-u)), f(u) = exp(-1/u): every derivative is
#         continuous and zero at both ends of each edge
STIM_EDGE = {"trig1": "rc", "prog": "rc", "trigc": "cinf", "progc": "cinf"}
# The stock cell in the trigc deck, started from ngspice's computed operating
# point instead of `uic` (README "Transient start"): a reproducer of the one
# known start-up failure, at the rated level only (no stress needed).
OPSTART_BENCH = "opstart"
CAMPAIGNS = {
    "conv74": ("trigger",) + tuple(f"{s}_{v}" for s in ("trig1", "prog") for v in ("st", "b0", "b1m", "b1l")),
    "conv74c": tuple(f"{s}_{v}" for s in ("trigc", "progc") for v in ("st", "b0", "b1m", "b1l")),
    "opstart": (OPSTART_BENCH,),
}
CONV_VARIANTS = {
    "st": "stock cell (design/netlists, unwrapped)",
    "b0": "wrapper, breakdown element disabled (bden=0)",
    "b1m": "wrapper, element enabled, dynamic, median quantile (ubd=0.5)",
    "b1l": f"wrapper, element enabled, dynamic, low quantile (ubd={UBD_LOW})",
}
CONV_BENCHES = tuple(f"{s}_{v}" for s in CONV_STIMULI for v in CONV_VARIANTS)
CONTROL_BENCH = "trigger"
TRIG_TMID = TRIG_T1 + TRIG_TR + TRIG_TW / 2
# Ratified access-device ratings (spec/cell-candidates.md device table;
# spec/supply-domains-decision.md rows 3-5, 14, 15). The spec states one
# rating per device; it is applied to every access-device terminal pair.
ACCESS_RATING_V = {1: 6.0, 2: 10.0, 3: 6.0}
# Program-leg ballast (spec/architecture.md 2 item 1): R >= (VPP - V_compliance)
# / I_target_max, and I_target_max is NOT fixed by the spec. PLACEHOLDER: a
# 500 uA compliance target at V_bd(t_ref), i.e. R = V_bd / 500 uA per
# candidate. An ideal resistor (no ppolyf corner/TC): this bench characterizes
# convergence of the topology, it does not size the ballast.
PROG_ILIM_PLACEHOLDER = 500e-6
# Terminal pairs logged over the whole transient (max and min of each
# difference). Names are cell ports plus CN, the internal capacitor node.
TERMINAL_PAIRS = {
    "ox": ("cn", "pl", "capacitor oxide (intended to exceed its rating)"),
    "wc": ("wl", "cn", "access gate to CN-side terminal"),
    "wb": ("wl", "bl", "access gate to BL-side terminal"),
    "bc": ("bl", "cn", "access BL-to-CN (drain-source)"),
    "cj": ("cn", "vb", "access CN-side junction to bulk"),
    "bj": ("bl", "vb", "access BL-side junction to bulk"),
    "gb": ("wl", "vb", "access gate to bulk"),
}
ACCESS_PAIRS = ("wc", "wb", "bc", "cj", "bj", "gb")


def conv_split(bench: str) -> tuple[str, str]:
    stim, var = bench.split("_", 1)
    if stim not in CONV_STIMULI or var not in CONV_VARIANTS:
        raise ValueError(bench)
    return stim, var


def prog_rballast(cand, params: dict) -> float:
    return vbd_ref(cand, params) / PROG_ILIM_PLACEHOLDER


def conv_levels(cand, params: dict, stim: str) -> list[float]:
    """PL-driven: the #62 trigger levels (signed V(PL)); BL-driven: the
    same magnitudes as a positive VPP (BL side) for every candidate."""
    lv = trigger_levels(cand, params)
    return lv if STIM_DRIVE[stim] == "pl" else [abs(x) for x in lv]


def damage_prediction(cand, params: dict, vox: float, ubd: float) -> tuple[float, float]:
    """Bounds on the damage the E-model accumulates over the pulse if the
    oxide held |vox| (the DISABLED deck's mid-pulse value at the same corner)
    for the flat top only (lower) or flat top plus both edges (upper)."""
    tox = params[f"c{cand.n}_bd_tox"]["value"]
    gam, ebd = params["bd_gam"]["value"], params["bd_ebd"]["value"]
    tref, beta = params["bd_tref"]["value"], params["bd_beta"]["value"]
    xmax = params["bd_num_xmax"]["value"]
    tq = (math.log(1 / (1 - ubd)) / math.log(2)) ** (1 / beta)
    rate = math.exp(min(gam * (abs(vox) / tox - ebd), xmax)) / (tq * tref)
    return TRIG_TW * rate, (TRIG_TW + 2 * TRIG_TR) * rate


def predict_state(d_lo: float, d_hi: float) -> int | None:
    """1 = must break down (D passes 1 well inside the flat top), 0 = must
    not, None = within a factor of 2 of the threshold (not scored)."""
    if d_lo >= 2.0:
        return 1
    if d_hi <= 0.5:
        return 0
    return None


def latched_as_predicted(st: float, pred: int) -> bool:
    """The end-of-transient state matches the prediction AND is a settled
    0 or 1 (a half-formed filament counts as a miss either way)."""
    settled = st <= 1e-3 or st >= 1 - 1e-3
    return settled and (st > 0.5) == bool(pred)


TIMESTEP_RE = re.compile(r'Timestep too small; time = ([0-9.eE+-]+), timestep = [0-9.eE+-]+: '
                         r'trouble with node "([^"]+)"')


def classify_failure(status: str, diagnostics: list[dict], log_text: str | None,
                     values: dict[str, float | None]) -> dict:
    """One corner's outcome: `pass`, `timeout`, `timestep` (with the time
    and node ngspice named), `missing-measurement`, or `error` (anything
    else). A corner is only `pass` if klt passed it AND every requested
    measurement has a value."""
    codes = {d.get("code") for d in diagnostics or []}
    missing = sorted(k for k, v in values.items() if v is None)
    out = {"kind": "pass", "time": None, "node": None, "missing": missing, "where": None}
    m = TIMESTEP_RE.search(log_text or "")
    if "timeout" in codes:
        out["kind"] = "timeout"
    elif m:
        out.update(kind="timestep", time=float(m.group(1).rstrip(",")), node=m.group(2))
    elif status == "pass" and not missing:
        return out
    elif missing:
        out["kind"] = "missing-measurement"
    else:
        out["kind"] = "error"
    if out["node"]:
        out["where"] = "breakdown element" if ".xbd." in out["node"] else "stock cell / testbench"
    return out


def attribute_corner(ok: dict[str, bool | None]) -> str:
    """Attribute a corner's non-convergence by which of the otherwise
    identical decks (st, b0, b1m/b1l) failed. `ok[v]` is None when that
    variant was not run."""
    st, b0 = ok.get("st"), ok.get("b0")
    b1 = [ok[v] for v in ("b1m", "b1l") if ok.get(v) is not None]
    if st is False:
        return "stock-cell"
    if b0 is False:
        return "wrapper (element disabled)"
    if b1 and not all(b1):
        return "breakdown-element (enabled)" if st is not None else "enabled deck (stock deck not run)"
    return "converged"


def tally(kinds: list[str]) -> dict[str, int]:
    """Attempted/pass/failure counts; every attempted corner stays in the
    denominator whatever its failure kind."""
    out = {"attempted": len(kinds), "pass": 0, "timeout": 0, "timestep": 0, "missing-measurement": 0, "error": 0}
    for k in kinds:
        out[k] = out.get(k, 0) + 1
    return out


def derive(bench: str, raw: dict[str, float | None]) -> dict[str, float | None]:
    """Raw .meas values -> the quantities the characterization experiment
    reports (same definitions as its testbench templates)."""
    out: dict[str, float | None] = {}
    if bench == BIAS_BENCH:
        for name, x in raw.items():
            if name.startswith("i_"):
                kind, rest = name[2:].split("_", 1)
                key = {"off": "ioff", "offp": "ioffp", "un": "iun", "pm": "iread_pm", "pw": "iread_pw"}[kind] + "_" + rest
                out[key] = None if x is None else abs(x)
            else:
                out[name] = x
    elif bench in ("access_op", "cap_op"):
        q = "ioff" if bench == "access_op" else "ilk"
        for name, x in raw.items():
            if not name.startswith("i_"):
                continue
            t = name[2:]
            key = f"iread_{t}" if t.startswith(("pm_", "pw_")) else f"{q}_{t}"
            out[key] = None if x is None else abs(x)
    elif bench in ("access_ac", "cap_ac"):
        vbl = None
        if bench == "access_ac" and raw.get("vr_bl") is not None and raw.get("vi_bl") is not None:
            vbl = complex(raw["vr_bl"], raw["vi_bl"])
        for name, x in raw.items():
            if not name.startswith("hr_"):
                continue
            t = name[3:]
            xi = raw.get(f"hi_{t}")
            if x is None or xi is None:
                out[("ron_" if bench == "access_ac" else "cval_") + t] = None
                continue
            i = complex(x, xi)
            if bench == "access_ac":
                # tb_access_device.spice: real(v(bl)/(-i(vbl))); i(vm) is +INTO the cell
                out[f"ron_{t}"] = None if vbl is None or i == 0 else (vbl / i).real
            else:
                # tb_moscap_cv.spice: mag(i(vpl))/(2*pi*1e3)
                out[f"cval_{t}"] = abs(i) / (2 * math.pi * F_CV)
    else:
        out = dict(raw)
    return out


# ---------------------------------------------------------------------------
# Bench names (requests and deck bodies live in benches.py)
# ---------------------------------------------------------------------------


BENCHES = ("access_op", "access_ac", "cap_op", "cap_ac", "trigger")   # the #62 benches (default run)
ALL_BENCHES = BENCHES + CONV_BENCHES + (OPSTART_BENCH, BIAS_BENCH)


def corner_key(bench: str, corner: dict, cand, params: dict) -> str:
    proc = corner["process"]
    temp = int(round(corner["temperature_c"]))
    sv = corner.get("supply_v") or {}
    if bench.startswith("access") or bench == BIAS_BENCH:
        tok = C.fmt_node_supply("bl", sv["vbl"])
    elif bench == "trigger":
        inst = "a" if abs(sv.get("vampa", 0.0)) > 0 else "b"
        tok = C.fmt_node_supply(f"pl{inst}", sv[f"vamp{inst}"])
    elif bench == OPSTART_BENCH:
        tok = C.fmt_node_supply("pl", sv["vamp"])
    elif bench in CONV_BENCHES:
        tok = C.fmt_node_supply("pl" if STIM_DRIVE[conv_split(bench)[0]] == "pl" else "vpp", sv["vamp"])
    else:
        tok = "nosupply"
    return C.corner_id(proc, temp, tok)


@dataclass
class BenchResult:
    bench: str
    status: str
    remote: dict | None
    values: dict[str, dict[str, float | None]] = field(default_factory=dict)  # corner-id -> name -> value
    corner_status: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    klt_env: dict | None = None
    outcome: dict[str, dict] = field(default_factory=dict)  # corner-id -> classify_failure()


def fill_outcomes(res: BenchResult, report: dict, bench_dir: Path, cand, params: dict) -> None:
    """Per-corner outcome from klt's status/diagnostics and the committed log."""
    for c in report["corners"]:
        cid = corner_key(res.bench, c, cand, params)
        log = bench_dir / f"{cid}.log"
        res.outcome[cid] = classify_failure(c["status"], c.get("diagnostics") or [],
                                            log.read_text(errors="replace") if log.is_file() else None,
                                            {m["name"].lower(): m["value"] for m in c["measurements"]})


def _decode_report(bench: str, report: dict, cand, params: dict) -> BenchResult:
    """BenchResult with environment, per-corner status and derived values filled
    from a klt report (shared by collect() and results_from_reports())."""
    env = report.get("environment", {})
    res = BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"), klt_env=env)
    for c in report["corners"]:
        cid = corner_key(bench, c, cand, params)
        res.corner_status[cid] = c["status"]
        res.values[cid] = derive(bench, {m["name"].lower(): m["value"] for m in c["measurements"]})
    return res


def collect(bench: str, report: dict | None, err: str, bench_dir: Path, cand, params: dict) -> BenchResult:
    if report is None or "corners" not in report:
        msg = err
        if report is not None and "error" in report:
            msg = json.dumps(report["error"])
        return BenchResult(bench=bench, status="submit-error", remote=None, error=msg)
    res = _decode_report(bench, report, cand, params)
    for c in report["corners"]:
        cid = corner_key(bench, c, cand, params)
        art = c.get("artifacts") or {}
        for kind, suffix in (("log", ".log"), ("deck", ".cir")):
            src = art.get(kind)
            if src and Path(src).is_file():
                R.write_once(bench_dir / f"{cid}{suffix}", Path(src).read_text(errors="replace"))
    fill_outcomes(res, report, bench_dir, cand, params)
    return res


# ---------------------------------------------------------------------------
# Candidate 3 read-bias analysis (issue #75)
# ---------------------------------------------------------------------------

PFET06_RATING_V = 6.0          # spec/cell-candidates.md: pfet_06v0 6.0 V thick oxide
JUNCTION_FWD_LIMIT_V = 0.4     # assumed: a p+/n-well junction forward-biased past this is not "reverse/zero bias"
CAP_RATING_C3_V = 3.3          # cap_pmos_03v3 rated voltage


def bias_stats(vals_by_corner: dict[str, dict[str, float | None]], corner_status: dict[str, str],
               sc: ReadBias, n_grid: int = 32, floor: float = DEFAULT_ABSTOL) -> dict:
    """Per-scenario summary from derived bias_op values {corner-id: {name: value}}.

    Every corner that is not klt-`pass`, or lacks any of the scenario's current
    measurements, is a FAILED corner: it is listed and makes the scenario
    infeasible; it is never dropped from the verdict.
    Per corner (worst over the 4 access-sizing x capacitor-geometry
    sub-configurations, which are splits -- per-sub-config values are in `by_sg`):
      i_off      max over {unprogrammed, programmed} x 3 OFF levels of the OFF current
      i_sneak    (N-1) x i_off                      (spec/architecture.md Section 3 item 2)
      i_sneak_f  (N-1) x max(i_off, floor)          solver-floor-limited bound
      i_zero_f   i_sneak_f + max selected-unprogrammed current (floor-limited): the
                 current an UNPROGRAMMED selected cell reads together with N-1 unselected cells
      i_prog     min over sub-configs of the worst-filament programmed read current
    """
    n = n_grid - 1
    rows, failed = {}, []
    by_sg: dict[str, dict] = {}
    for cid, vals in sorted(vals_by_corner.items()):
        pref = (f"ioff_{sc.name}_", f"ioffp_{sc.name}_", f"iun_{sc.name}_", f"iread_pw_{sc.name}_", f"iread_pm_{sc.name}_")
        mine = {k: v for k, v in vals.items() if k.startswith(pref)}
        offs = [v for k, v in mine.items() if k.startswith((f"ioff_{sc.name}_", f"ioffp_{sc.name}_"))]
        uns = [v for k, v in mine.items() if k.startswith(f"iun_{sc.name}_")]
        pws = {k: v for k, v in mine.items() if k.startswith(f"iread_pw_{sc.name}_")}
        pms = [v for k, v in mine.items() if k.startswith(f"iread_pm_{sc.name}_")]
        st = corner_status.get(cid)
        expect = 4 * 3 * 2 + 4 + 4 + 4   # off+offp, un, pw, pm
        if st != "pass" or len(mine) != expect or any(v is None for v in mine.values()):
            failed.append((cid, st, f"{sum(v is not None for v in mine.values())}/{expect} values"))
            continue
        i_off = max(offs)
        un = max(max(uns), floor)
        rows[cid] = {"i_off": i_off, "i_sneak": n * i_off, "i_sneak_f": n * max(i_off, floor),
                     "i_zero_f": n * max(i_off, floor) + un, "i_un": max(uns),
                     "i_prog": min(pws.values()), "i_prog_at": min(pws, key=pws.get).rsplit("_", 1)[-1],
                     "i_prog_med": min(pms)}
        for k, v in pws.items():
            sg = k.rsplit("_", 1)[-1]
            d = by_sg.setdefault(sg, {"prog": (math.inf, ""), "off": (0.0, ""), "un": (0.0, "")})
            if v < d["prog"][0]:
                d["prog"] = (v, cid)
        for k, v in mine.items():
            sg = k.rsplit("_", 1)[-1] if not k.startswith(("ioff_", "ioffp_")) else k.rsplit("_", 2)[-2]
            d = by_sg.setdefault(sg, {"prog": (math.inf, ""), "off": (0.0, ""), "un": (0.0, "")})
            if k.startswith(("ioff_", "ioffp_")) and v > d["off"][0]:
                d["off"] = (v, cid)
            if k.startswith("iun_") and v > d["un"][0]:
                d["un"] = (v, cid)
    out = {"scenario": sc.name, "rows": rows, "failed": failed, "by_sg": by_sg, "n": n, "floor": floor}
    if rows:
        wp = min(rows, key=lambda c: rows[c]["i_prog"])
        ws = max(rows, key=lambda c: rows[c]["i_sneak"])
        wz = max(rows, key=lambda c: rows[c]["i_zero_f"])
        out.update({
            "prog_min": rows[wp]["i_prog"], "prog_min_at": wp,
            "sneak_max": rows[ws]["i_sneak"], "sneak_max_at": ws,
            "zero_f_max": rows[wz]["i_zero_f"], "zero_f_max_at": wz,
            "per_corner_ok": sum(r["i_prog"] > r["i_zero_f"] for r in rows.values()),
            "per_corner_ok_meas": sum(r["i_prog"] > r["i_sneak"] for r in rows.values()),
            "per_corner_bad": sorted(c for c, r in rows.items() if not r["i_prog"] > r["i_zero_f"]),
        })
        out["window"] = out["prog_min"] / out["zero_f_max"]
        out["window_meas"] = out["prog_min"] / out["sneak_max"] if out["sneak_max"] > 0 else math.inf
        out["common_iref"] = bool(out["prog_min"] > out["zero_f_max"] and not failed)
    else:
        out["common_iref"] = False
    return out


def bias_voltages(vals_by_corner: dict[str, dict[str, float | None]], sc: ReadBias,
                  wl_off_levels: tuple[float, float, float]) -> dict:
    """Selected-device terminal voltages and junction/oxide checks for one scenario,
    from the measured rail/well/CN voltages (worst over corners and sub-configs)."""
    vb_m, vd_m, vg_wl, vg_bl, stress = [], [], [], [], []
    for vals in vals_by_corner.values():
        vbl, vvb = vals.get(f"vbl_{sc.name}"), vals.get(f"vvb_{sc.name}")
        cns = [v for k, v in vals.items() if k.startswith(f"vcn_pw_{sc.name}_") or k.startswith(f"vcn_pm_{sc.name}_")]
        if vbl is None or vvb is None or not cns or any(c is None for c in cns):
            continue
        vb_m.append(vvb - vbl)                       # source (BL) -> well margin; < 0 = forward-biased
        vd_m.append(vvb - max(cns))                  # drain (CN) -> well margin
        wls = (sc.wl_on,) + tuple(wl_off_levels)
        vg_wl.append(max(abs(w - vvb) for w in wls))  # gate-to-well
        vg_bl.append(max(abs(w - vbl) for w in wls))  # gate-to-source/drain(BL)
        stress.append(vbl)                           # oxide of the unprogrammed selected cell sees BL - PL(0)
    if not vb_m:
        return {}
    return {"src_well_min": min(vb_m), "drn_well_min": min(vd_m), "gate_well_max": max(vg_wl),
            "gate_bl_max": max(vg_bl), "cap_v_max": max(stress),
            "fwd_ok": min(min(vb_m), min(vd_m)) > -JUNCTION_FWD_LIMIT_V,
            "gate_ok": max(max(vg_wl), max(vg_bl)) <= PFET06_RATING_V,
            "cap_ok": max(stress) <= CAP_RATING_C3_V}


def level_label(cand, params: dict, stim: str, v: float) -> str:
    lv = [abs(x) for x in conv_levels(cand, params, stim)]
    i = min(range(len(lv)), key=lambda k: abs(lv[k] - abs(v)))
    return "rated" if i == 0 else f"{TRIG_FRACTIONS[i - 1]:g}x"


def corner_level(cid: str) -> float:
    """Signed stress level from a corner id's supply token (pl-7p90v -> -7.9)."""
    tok = cid.rsplit("_", 1)[1]
    m = re.match(r"^(?:pl[ab]?|vpp)(-?[0-9]+p[0-9]+)v$", tok)
    if not m:
        raise ValueError(cid)
    return float(m.group(1).replace("p", "."))


def corner_temp(cid: str) -> int:
    m = re.search(r"_(-?\d+)c_", cid)
    return int(m.group(1)) if m else 0


def abs_extreme(vals: dict, k: str) -> float | None:
    hi, lo = vals.get(f"mx_{k}"), vals.get(f"mn_{k}")
    if hi is None or lo is None:
        return None
    return max(abs(hi), abs(lo))


def vox(vals: dict, inst: str) -> str:
    cn, pl = vals.get(f"vcn_{inst}"), vals.get(f"vpl_{inst}")
    return "n/a" if cn is None or pl is None else f"{cn - pl:.4e}"


def results_from_reports(cand, rid: str, params: dict, benches=None,
                         base_dir: Path | None = None) -> dict[str, BenchResult]:
    results: dict[str, BenchResult] = {}
    base = Path(base_dir) if base_dir is not None else THIS_DIR / "corners" / rid
    for bench in benches or ALL_BENCHES:
        bdir = base / bench
        rp = bdir / "report.json"
        if rp.is_file():
            report = json.loads(rp.read_text())
            res = _decode_report(bench, report, cand, params)
            fill_outcomes(res, report, bdir, cand, params)
        elif (bdir / "submit-error.txt").is_file():
            res = BenchResult(bench=bench, status="submit-error", remote=None,
                              error=(bdir / "submit-error.txt").read_text())
        else:
            continue
        results[bench] = res
    return results
