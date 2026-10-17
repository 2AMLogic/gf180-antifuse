#!/usr/bin/env python3
"""sim/cell-breakdown-model -- single-cell bench for the behavioral
breakdown-augmented cell model (issue #62).

For each ratified cell candidate (spec/cell-candidates.md) this runs, as
`klt sim` corner requests (one request per bench -- see README for why):

  access_op   operating point, 5 MOS x 3 T x 3 read-rail corners (45):
              - regression: access-device OFF current through the stock cell,
                the wrapper with the element disabled (bden=0), and the
                wrapper enabled but unprogrammed (bden=1) -- same stimulus as
                sim/cell-device-characterization's tb_access_device.spice
              - programmed-cell read current at the median and worst-case
                filament resistance -> I_prog_min
  access_ac   AC at 10 MHz, same 45 corners: R_on regression (3 variants)
  cap_op      operating point, 3 moscap x 3 T (9): capacitor leakage regression
  cap_ac      AC at 1 kHz, same 9 corners: C-V regression
  trigger     .tran, 3 moscap x 3 T x 10 stress points (90): the breakdown
              trigger + latch check, one stressed instance per corner

and writes one append-only record per candidate under records/. Requests
use only features the fleet runner's klt has (README "Fleet klt version").

Issue #74 adds the transient-convergence campaign (`--campaign conv74`):
the trigger bench above re-run unchanged as a control, plus ONE-cell-per-deck
benches, each 3 moscap x 3 T x 5 levels (45):

  trig1_<v>   the trigger stimulus (PL driven, BL = 0)
  prog_<v>    a BL-driven program leg: VPP pulse -> ballast -> BL, PL = 0

with <v> = st (stock cell), b0 (element disabled), b1m / b1l (element
enabled, median / low Weibull quantile) -- decks identical but for the cell
line, so a non-converged corner can be attributed (README "Transient
convergence (#74)").

    python3 sim/run_corners.py cell-breakdown-model
    python3 sim/cell-breakdown-model/run_experiment.py --candidates 1
    python3 sim/cell-breakdown-model/run_experiment.py --campaign conv74 --candidates 1

The corner grids go to whatever backend the requests name -- `batch` (the
Spot fleet) by default. They are never run as a local ngspice grid. A
one-corner local pre-flight of a single bench is available for debugging:

    python3 sim/cell-breakdown-model/run_experiment.py --smoke 1:access_op

stdlib only; needs `klt` on PATH and a gf180mcuD install the PDK resolver
finds (sim/harness/pdk.py).
"""

from __future__ import annotations

import argparse
import hashlib
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
BD_DIR = REPO_ROOT / "design" / "breakdown"
WRAPPERS = BD_DIR / "cell_candidates_bd.spice"
CHAR_DIR = SIM_DIR / "cell-device-characterization"

sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness import klt as K  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# The existing characterization experiment is imported as a library, not
# copied: candidate definitions, OFF-bias levels, C-V bias points, the read
# rail, gmin and the geometry levels are therefore identical by construction.
CHAR = _load(CHAR_DIR / "run_experiment.py", "sim_char_lib")
CHECK = _load(BD_DIR / "check_params.py", "bd_check_params")

# --- bench constants (stimulus placeholders, documented in README) ---------
KLT_BACKEND = "batch"
# The fleet runner image currently ships an older klt than this host's client
# (README "Fleet klt version"). Every request below is restricted to features
# that runner has (.meas-only measurements, single-library process bundles),
# so the skew cannot silently drop an option; the version check is set to
# `warn` so the job runs, and environment.remote records both versions.
BATCH_OPTS = {"runner_version_check": "warn", "capacity_wait_s": 1800}
# The fleet's shared concurrency cap refuses a launch outright (klt does not
# retry it, unlike a Spot capacity refusal). Wait and resubmit the SAME
# request, bounded -- never fall back to a local run.
# The executing host's gf180mcuD variant directory, needed for the one model
# library Candidate 2 loads from the body (README "Two model libraries").
# Observed in fleet-generated corner decks: `.lib /opt/pdk/gf180mcuD/...`.
FLEET_PDK_VARIANT_DIR = "/opt/pdk/gf180mcuD"
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


def within_tol(q: str, x: float, ref: float) -> bool:
    if q in GMIN_FLOOR:
        return abs(x - ref) <= DEFAULT_RELTOL * abs(ref) + DEFAULT_ABSTOL
    return abs(x - ref) <= DEFAULT_RELTOL * abs(ref)


def rel_dev(x: float, ref: float) -> float:
    if ref == 0:
        return 0.0 if x == 0 else math.inf
    return abs(x - ref) / abs(ref)


def fmt(x: float) -> str:
    return f"{x:.6e}"


def sg_tag(sizing: str, geom: str) -> str:
    return f"s{1 if sizing == 'min' else 2}g{1 if geom == 'min' else 2}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel_from(base: Path, target: Path) -> str:
    """Relative path from directory base to target (for .include lines, so no
    committed deck carries this checkout's absolute path)."""
    import os
    return os.path.relpath(target, base)


def meas(analysis: str, name: str, quantity: str, at: float, unit: str) -> dict:
    return {"name": name, "spice": f".meas {analysis} {name} FIND {quantity} AT={fmt(at)}", "unit": unit}


# ---------------------------------------------------------------------------
# Deck bodies (klt sim "circuit body": no .control, no .end)
# ---------------------------------------------------------------------------


def design_param_block(pdk: P.PDKPaths) -> str:
    """design.ngspice's non-comment lines, inlined.

    klt emits the corner's .lib cards ahead of the body, and the fleet's PDK
    lives at a different absolute path than this host's, so a literal
    `.include <...>/design.ngspice` cannot travel. ngspice does not expand
    $PDK_ROOT in .include either. The global switches are therefore copied
    verbatim, at run time, out of the resolved PDK file (its sha256 is in the
    header), never hand-typed."""
    lines = [ln for ln in pdk.design_ngspice.read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith("*")]
    return (f"* --- inlined from {pdk.variant}/libs.tech/ngspice/design.ngspice "
            f"(sha256 {sha256(pdk.design_ngspice)}) ---\n" + "\n".join(lines) + "\n* --- end inline ---\n")


def second_lib(cand, bench: str, lib_root: str) -> str:
    """Candidate 2 needs two model files (smbb000149 for its access device,
    sm141064 for its capacitor). klt's process bundle reads every section from
    the request's one models.lib, so the library whose section is FIXED in this
    bench is loaded here instead, from the executing host's PDK."""
    if "smbb000149" not in cand.extra_mos_libs:
        return ""
    if bench.startswith("access"):     # access device corner swept; capacitor fixed typical
        return f".lib {lib_root}/libs.tech/ngspice/sm141064.ngspice moscap_typical\n"
    return f".lib {lib_root}/libs.tech/ngspice/smbb000149.ngspice typical\n"  # moscap swept; MOS fixed


def body_header(pdk: P.PDKPaths, body_dir: Path, title: str, cand, bench: str, lib_root: str) -> str:
    # the characterization experiment's options, unchanged (gmin only)
    opts = f".options gmin={fmt(CHAR.GMIN)}"
    return (
        f"* gf180-antifuse sim/cell-breakdown-model -- {title}\n"
        "* Generated by run_experiment.py; frozen here as evidence. See README.\n"
        + design_param_block(pdk)
        + second_lib(cand, bench, lib_root)
        + opts + "\n"
        + f".include {rel_from(body_dir, WRAPPERS)}\n"
    )


def geometry(cand, defaults: dict, sizing: str, geom: str) -> str:
    wacc = defaults["wacc"] * CHAR.sizing_multiplier(sizing)
    wcap = defaults["wcap"] * CHAR.sizing_multiplier(geom)
    return f"wcap={fmt(wcap)} lcap={fmt(defaults['lcap'])} wacc={fmt(wacc)} lacc={fmt(defaults['lacc'])}"


def dut(cand, variant: str, geo: str) -> str:
    if variant == "st":
        return f"{cand.subckt} {geo}"
    if variant == "b0":
        return f"{cand.subckt}_bd {geo} bden=0"
    if variant == "b1":
        return f"{cand.subckt}_bd {geo} bden=1 prog=0 dyn=0"
    if variant == "pm":
        return f"{cand.subckt}_bd {geo} bden=1 prog=1 dyn=0 zrf=0"
    if variant == "pw":
        return f"{cand.subckt}_bd {geo} bden=1 prog=1 dyn=0 zrf={{bd_zrf_wc}}"
    raise ValueError(variant)


def ac_probe(out: list[str], ms: list[dict], t: str, f: float) -> None:
    """A 1-ohm-transresistance CCVS reads the ammeter's complex AC current
    as a node voltage (ngspice .meas reads real/imag parts of voltages, vr/vi).
    It draws no current from the circuit."""
    out.append(f"H_{t} HP_{t} 0 VM_{t} 1")
    ms.append(meas("ac", f"hr_{t}", f"vr(hp_{t})", f, "A"))
    ms.append(meas("ac", f"hi_{t}", f"vi(hp_{t})", f, "A"))


def body_access(pdk, cand, defaults, body_dir: Path, bench: str, lib_root: str) -> tuple[str, list[dict]]:
    """access_op and access_ac. One shared VBL (the swept read rail),
    one 0 V ammeter per instance so each instance's BL current is separable."""
    lo, mid, hi = CHAR.off_levels(cand)
    analysis = "dc" if bench == "access_op" else "ac"
    out = [body_header(pdk, body_dir, f"Candidate {cand.n} access bench ({bench})", cand, bench, lib_root)]
    out.append(f"VBL BL 0 DC {fmt(CHAR.V_READ_NOM)} AC 1")
    out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
    out.append("VPL PL 0 DC 0")
    ms: list[dict] = []
    if analysis == "dc":
        out.append("VDMY DMY 0 DC 0")
        out += [f"VWLLO WLLO 0 DC {fmt(lo)}", f"VWLMID WLMID 0 DC {fmt(mid)}",
                f"VWLHI WLHI 0 DC {fmt(hi)}", f"VWLON WLON 0 DC {fmt(cand.wl_on)}"]
        for s in CHAR.SIZING_LEVELS:
            for g in CHAR.GEOM_LEVELS:
                geo = geometry(cand, defaults, s, g)
                sg = sg_tag(s, g)
                for b, wl in zip(BIAS_TAGS, ("WLLO", "WLMID", "WLHI")):
                    for v in REGRESSION_VARIANTS:
                        t = f"{v}_{sg}_{b}"
                        out.append(f"VM_{t} BL B_{t} 0")
                        out.append(f"X_{t} B_{t} {wl} PL VB {dut(cand, v, geo)}")
                        ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
                for v in ("pm", "pw"):
                    t = f"{v}_{sg}"
                    out.append(f"VM_{t} BL B_{t} 0")
                    out.append(f"X_{t} B_{t} WLON PL VB {dut(cand, v, geo)}")
                    ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
    else:
        out.append(f"VWLON WLON 0 DC {fmt(cand.wl_on)}")
        ms.append(meas("ac", "vr_bl", "vr(bl)", F_RON, "V"))
        ms.append(meas("ac", "vi_bl", "vi(bl)", F_RON, "V"))
        for s in CHAR.SIZING_LEVELS:
            for g in CHAR.GEOM_LEVELS:
                geo = geometry(cand, defaults, s, g)
                for v in REGRESSION_VARIANTS:
                    t = f"{v}_{sg_tag(s, g)}"
                    out.append(f"VM_{t} BL B_{t} 0")
                    out.append(f"X_{t} B_{t} WLON PL VB {dut(cand, v, geo)}")
                    ac_probe(out, ms, t, F_RON)
    return "\n".join(out) + "\n", ms


def body_cap(pdk, cand, defaults, body_dir: Path, bench: str, lib_root: str) -> tuple[str, list[dict]]:
    """cap_op and cap_ac: BL fixed at 0, WL fully on, the capacitor
    bias set on PL (tb_moscap_cv.spice's convention, incl. V(PL) = -bias)."""
    analysis = "dc" if bench == "cap_op" else "ac"
    out = [body_header(pdk, body_dir, f"Candidate {cand.n} capacitor bench ({bench})", cand, bench, lib_root)]
    out.append("VBL BL 0 DC 0")
    out.append(f"VWL WL 0 DC {fmt(cand.moscap_wl_on)}")
    out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
    if analysis == "dc":
        out.append("VDMY DMY 0 DC 0")
    subs = CHAR.moscap_substitutions(cand)
    for k in range(1, 6):
        out.append(f"VPL{k} PL{k} 0 DC {fmt(subs[f'VPL_{k}'])} AC 1")
    ms: list[dict] = []
    for s in CHAR.SIZING_LEVELS:
        for g in CHAR.GEOM_LEVELS:
            geo = geometry(cand, defaults, s, g)
            for k in range(1, 6):
                for v in REGRESSION_VARIANTS:
                    t = f"{v}_{sg_tag(s, g)}_{k}"
                    out.append(f"VM_{t} PL{k} P_{t} 0")
                    out.append(f"X_{t} BL WL P_{t} VB {dut(cand, v, geo)}")
                    if analysis == "dc":
                        ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
                    else:
                        ac_probe(out, ms, t, F_CV)
    return "\n".join(out) + "\n", ms


def vbd_ref(cand, params: dict) -> float:
    return params["bd_ebd"]["value"] * params[f"c{cand.n}_bd_tox"]["value"]


def trigger_levels(cand, params: dict) -> list[float]:
    sign = 1.0 if cand.polarity == "n" else -1.0
    vbd = vbd_ref(cand, params)
    return [sign * cand.cap_rated_v] + [sign * f * vbd for f in TRIG_FRACTIONS]


def body_trigger(pdk, cand, defaults, body_dir: Path, lib_root: str) -> tuple[str, list[dict]]:
    """Two dynamic instances (median and low Weibull quantile); each corner
    stresses exactly ONE of them via its own scalar amplitude source, so no
    deck ever contains two breakdown events (README: multi-event transients)."""
    out = [body_header(pdk, body_dir, f"Candidate {cand.n} trigger/latch bench (tran)", cand, "trigger", lib_root)]
    out.append(f".param t1={fmt(TRIG_T1)} tr={fmt(TRIG_TR)} tw={fmt(TRIG_TW)}")
    out.append("VBL BL 0 DC 0")
    out.append(f"VWL WL 0 DC {fmt(cand.moscap_wl_on)}")
    out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
    # raised-cosine edges: the stock moscap macro fails to converge at the
    # slope discontinuity of a PULSE corner at these voltages (README)
    out.append("BSH SH 0 V = '0.5*(1-cos(pi*min(max((time-t1)/tr,0),1)))"
               " - 0.5*(1-cos(pi*min(max((time-t1-tr-tw)/tr,0),1)))'")
    geo = geometry(cand, defaults, "min", "min")
    ms: list[dict] = []
    for inst, ubd in (("a", 0.5), ("b", UBD_LOW)):
        out.append(f"VAMP{inst.upper()} AMP{inst.upper()} 0 DC 0")
        out.append(f"BPL{inst.upper()} PL{inst.upper()} 0 V = 'v(amp{inst})*v(sh)'")
        out.append(f"X{inst.upper()} BL WL PL{inst.upper()} VB {cand.subckt}_bd {geo} bden=1 prog=0 dyn=1 ubd={ubd}")
        ms.append(meas("tran", f"st_{inst}", f"v(x{inst}.xbd.st)", TRIG_TMEAS, "1"))
        ms.append(meas("tran", f"dmg_{inst}", f"v(x{inst}.xbd.dmg)", TRIG_TMEAS, "1"))
        # oxide voltage mid-pulse = vcn - vpl (ngspice's .meas does not take
        # the two-node v(a,b) form on hierarchical names, so two FINDs)
        mid = TRIG_T1 + TRIG_TR + TRIG_TW / 2
        ms.append(meas("tran", f"vcn_{inst}", f"v(x{inst}.xc.cn)", mid, "V"))
        ms.append(meas("tran", f"vpl_{inst}", f"v(pl{inst})", mid, "V"))
    return "\n".join(out) + "\n", ms


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


def conv_dut(cand, variant: str, geo: str) -> str:
    if variant == "st":
        return f"{cand.subckt} {geo}"
    if variant == "b0":
        return f"{cand.subckt}_bd {geo} bden=0"
    ubd = 0.5 if variant == "b1m" else UBD_LOW
    return f"{cand.subckt}_bd {geo} bden=1 prog=0 dyn=1 ubd={ubd}"


def conv_cn(variant: str) -> str:
    """Hierarchical name of the capacitor node CN in this variant's deck."""
    return "xdut.cn" if variant == "st" else "xdut.xc.cn"


def prog_rballast(cand, params: dict) -> float:
    return vbd_ref(cand, params) / PROG_ILIM_PLACEHOLDER


def conv_levels(cand, params: dict, stim: str) -> list[float]:
    """PL-driven: the #62 trigger levels (signed V(PL)); BL-driven: the
    same magnitudes as a positive VPP (BL side) for every candidate."""
    lv = trigger_levels(cand, params)
    return lv if STIM_DRIVE[stim] == "pl" else [abs(x) for x in lv]


def edge_lines(edge: str) -> list[str]:
    """The unit pulse shape V(SH): 0 -> 1 over [t1, t1+tr], 1 -> 0 over
    [t1+tr+tw, t1+2tr+tw]."""
    if edge == "rc":
        return ["BSH SH 0 V = '0.5*(1-cos(pi*min(max((time-t1)/tr,0),1)))"
                " - 0.5*(1-cos(pi*min(max((time-t1-tr-tw)/tr,0),1)))'"]
    if edge == "cinf":
        # u clamped to [0,1]; exp(-1/max(u,1e-6)) underflows to exactly 0
        # at u <= 1e-6, and f(u) + f(1-u) > 0 everywhere
        return [".func af_fe(u) {exp(-1/max(u,1e-6))}",
                ".func af_edge(x) {af_fe(min(max(x,0),1))/(af_fe(min(max(x,0),1))+af_fe(1-min(max(x,0),1)))}",
                "BSH SH 0 V = 'af_edge((time-t1)/tr) - af_edge((time-t1-tr-tw)/tr)'"]
    raise ValueError(edge)


def body_conv(pdk, cand, defaults, body_dir: Path, lib_root: str, bench: str,
              params: dict) -> tuple[str, list[dict]]:
    stim, var = conv_split(bench)
    out = [body_header(pdk, body_dir, f"Candidate {cand.n} {stim} bench, variant {var} (tran, #74)",
                       cand, "trigger", lib_root)]
    out.append(f".param t1={fmt(TRIG_T1)} tr={fmt(TRIG_TR)} tw={fmt(TRIG_TW)}")
    out += edge_lines(STIM_EDGE[stim])
    # klt's supply axis alters the DC value of VAMP (as in the #62 bench)
    out.append("VAMP AMP 0 DC 0")
    if STIM_DRIVE[stim] == "pl":
        out.append("VBL BL 0 DC 0")
        out.append(f"VWL WL 0 DC {fmt(cand.moscap_wl_on)}")
        out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
        out.append("BPL PL 0 V = 'v(amp)*v(sh)'")
    else:
        # VPP pulse -> ballast -> 0 V ammeter -> BL. The access device's gate
        # (and, for the PMOS candidate, its n-well) rides on VPP with the
        # static "on" bias of the #62 bench added, so its Vgs/Vsb before the
        # stress equal that bench's; Candidates 1/2's bulk is the p-substrate
        # tie (spec/supply-domains-decision.md row 14) and stays at VB.
        out.append("BVPP VPP 0 V = 'v(amp)*v(sh)'")
        out.append(f"RBAL VPP BLM {fmt(prog_rballast(cand, params))}")
        out.append("VBL BLM BL DC 0")
        out.append(f"BWL WL 0 V = '{fmt(cand.moscap_wl_on)} + v(vpp)'")
        if cand.polarity == "p":
            out.append(f"BVB VB 0 V = '{fmt(cand.vb)} + v(vpp)'")
        else:
            out.append(f"VVB VB 0 DC {fmt(cand.vb)}")
        out.append("VPL PL 0 DC 0")
    geo = geometry(cand, defaults, "min", "min")
    out.append(f"XDUT BL WL PL VB {conv_dut(cand, var, geo)}")
    cn = conv_cn(var)
    node = {"cn": cn, "pl": "pl", "wl": "wl", "bl": "bl", "vb": "vb"}
    ms: list[dict] = []
    # terminal differences as top-level nodes (ngspice .meas does not take
    # v(a,b) on hierarchical names); these B-sources load nothing
    for k, (p, n, _) in TERMINAL_PAIRS.items():
        out.append(f"BD{k.upper()} D{k.upper()} 0 V = 'v({node[p]})-v({node[n]})'")
        ms.append({"name": f"mx_{k}", "spice": f".meas tran mx_{k} MAX v(d{k})", "unit": "V"})
        ms.append({"name": f"mn_{k}", "spice": f".meas tran mn_{k} MIN v(d{k})", "unit": "V"})
    ms.append(meas("tran", "vox_mid", "v(dox)", TRIG_TMID, "V"))
    ms.append(meas("tran", "vcn_mid", f"v({cn})", TRIG_TMID, "V"))
    ms.append(meas("tran", "vbl_mid", "v(bl)", TRIG_TMID, "V"))
    ms.append(meas("tran", "vpl_mid", "v(pl)", TRIG_TMID, "V"))
    ms.append(meas("tran", "vcn_end", f"v({cn})", TRIG_TMEAS, "V"))
    ms.append(meas("tran", "ibl_mid", "i(vbl)", TRIG_TMID, "A"))
    ms.append({"name": "ibl_mx", "spice": ".meas tran ibl_mx MAX i(vbl)", "unit": "A"})
    ms.append({"name": "ibl_mn", "spice": ".meas tran ibl_mn MIN i(vbl)", "unit": "A"})
    if var.startswith("b1"):
        ms.append(meas("tran", "st", "v(xdut.xbd.st)", TRIG_TMEAS, "1"))
        ms.append(meas("tran", "dmg", "v(xdut.xbd.dmg)", TRIG_TMEAS, "1"))
        ms.append(meas("tran", "st_mid", "v(xdut.xbd.st)", TRIG_TMID, "1"))
    return "\n".join(out) + "\n", ms


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
    if bench in ("access_op", "cap_op"):
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
# Requests
# ---------------------------------------------------------------------------


def make_request(bench: str, cand, pdk: P.PDKPaths, measurements: list[dict], params: dict) -> dict:
    temps = [float(t) for t in C.TEMPS_C]
    two_lib = "smbb000149" in cand.extra_mos_libs
    lib = "libs.tech/ngspice/sm141064.ngspice"
    req: dict = {
        "netlist": "body.spice",
        "engine": "ngspice",
        "backend": KLT_BACKEND,
        "batch": dict(BATCH_OPTS),
        "measurements": measurements,
        "options": {"timeout_s": 300, "keep_artifacts": True},
    }
    if bench.startswith("access"):
        if two_lib:
            lib = "libs.tech/ngspice/smbb000149.ngspice"
            procs = [{"name": m, "sections": [m]} for m in C.MOS_CORNERS]
        else:
            procs = [{"name": m, "sections": [m, "moscap_typical"]} for m in C.MOS_CORNERS]
        req["corners"] = {
            "process": procs,
            "supply_v": {"vbl": [round(CHAR.V_READ_NOM * m, 6) for m in
                                  (1 - CHAR.SUPPLY_TOL, 1.0, 1 + CHAR.SUPPLY_TOL)]},
            "temperature_c": temps,
        }
    else:
        req["corners"] = {"process": [{"name": mc, "sections": ["typical", mc]} for mc in C.MOSCAP_CORNERS],
                          "temperature_c": temps}
    req["models"] = {"pdk": pdk.variant, "lib": lib}
    if bench == "trigger":
        lv = trigger_levels(cand, params)
        z = [0.0] * len(lv)
        req["corners"]["supply_v"] = {"vampa": [round(x, 6) for x in lv] + z,
                                      "vampb": z + [round(x, 6) for x in lv]}
    if bench in CONV_BENCHES:
        req["corners"]["supply_v"] = {"vamp": [round(x, 6) for x in conv_levels(cand, params, conv_split(bench)[0])]}
        req["analysis"] = {"kind": "tran", "args": f"{fmt(TRIG_TSTEP)} {fmt(TRIG_TSTOP)} uic"}
        return req
    if bench == OPSTART_BENCH:
        req["corners"]["supply_v"] = {"vamp": [round(conv_levels(cand, params, "trigc")[0], 6)]}
        req["analysis"] = {"kind": "tran", "args": f"{fmt(TRIG_TSTEP)} {fmt(TRIG_TSTOP)}"}  # no uic
        return req
    req["analysis"] = {
        "access_op": {"kind": "dc", "args": DC_ARGS},
        "access_ac": {"kind": "ac", "args": f"lin 3 {fmt(F_RON / 2)} {fmt(F_RON * 1.5)}"},
        "cap_op": {"kind": "dc", "args": DC_ARGS},
        "cap_ac": {"kind": "ac", "args": f"lin 3 {fmt(F_CV / 2)} {fmt(F_CV * 1.5)}"},
        # uic: start from zero initial conditions, not the computed operating
        # point -- the stock cells' transient fails to leave a DC-computed
        # start at temperature extremes (README "Transient start"). Every
        # stress source is 0 at t=0 and the pulse starts at TRIG_T1, so the
        # cell settles long before the stress; D(0) = 0 is then explicit.
        "trigger": {"kind": "tran", "args": f"{fmt(TRIG_TSTEP)} {fmt(TRIG_TSTOP)} uic"},
    }[bench]
    return req


BENCHES = ("access_op", "access_ac", "cap_op", "cap_ac", "trigger")
ALL_BENCHES = BENCHES + CONV_BENCHES + (OPSTART_BENCH,)


def build_body(bench: str, pdk, cand, defaults, body_dir: Path, lib_root: str,
               params: dict | None = None) -> tuple[str, list[dict]]:
    if bench in CONV_BENCHES or bench == OPSTART_BENCH:
        assert params is not None
        return body_conv(pdk, cand, defaults, body_dir, lib_root,
                         "trigc_st" if bench == OPSTART_BENCH else bench, params)
    if bench.startswith("access"):
        return body_access(pdk, cand, defaults, body_dir, bench, lib_root)
    if bench.startswith("cap"):
        return body_cap(pdk, cand, defaults, body_dir, bench, lib_root)
    return body_trigger(pdk, cand, defaults, body_dir, lib_root)


# ---------------------------------------------------------------------------
# klt invocation
# ---------------------------------------------------------------------------


KLT_CMD = ["klt"]


def run_klt(req_path: Path, outdir: Path, backend: str | None) -> tuple[dict | None, str]:
    return K.run_klt(req_path, outdir, backend, klt_cmd=KLT_CMD, retry=K.BACKOFF)


def corner_key(bench: str, corner: dict, cand, params: dict) -> str:
    proc = corner["process"]
    temp = int(round(corner["temperature_c"]))
    sv = corner.get("supply_v") or {}
    if bench.startswith("access"):
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


def collect(bench: str, report: dict | None, err: str, bench_dir: Path, cand, params: dict) -> BenchResult:
    if report is None or "corners" not in report:
        msg = err
        if report is not None and "error" in report:
            msg = json.dumps(report["error"])
        return BenchResult(bench=bench, status="submit-error", remote=None, error=msg)
    env = report.get("environment", {})
    res = BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"), klt_env=env)
    for c in report["corners"]:
        cid = corner_key(bench, c, cand, params)
        res.corner_status[cid] = c["status"]
        res.values[cid] = derive(bench, {m["name"].lower(): m["value"] for m in c["measurements"]})
        art = c.get("artifacts") or {}
        for kind, suffix in (("log", ".log"), ("deck", ".cir")):
            src = art.get(kind)
            if src and Path(src).is_file():
                R.write_once(bench_dir / f"{cid}{suffix}", Path(src).read_text(errors="replace"))
    fill_outcomes(res, report, bench_dir, cand, params)
    return res


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def stored_record_id(cand) -> str | None:
    hits = []
    for p in sorted((CHAR_DIR / "records").glob("*.md")):
        if re.search(rf"Candidate {cand.n}\b", p.read_text()):
            hits.append(p.stem)
    return hits[-1] if hits else None


def stored_value(rid: str, sizing: str, geom: str, cid: str, name: str) -> float | None:
    p = CHAR_DIR / "corners" / rid / f"access-{sizing}_cap-{geom}" / f"{cid}.log"
    if not p.is_file():
        return None
    return CHAR.parse_scalar(p.read_text(), name)


def stored_headline(rid: str) -> dict:
    text = (CHAR_DIR / "records" / f"{rid}.md").read_text()
    out = {}
    m = re.search(r"I_sneak_max = ([0-9.eE+-]+) A", text)
    out["i_sneak_max"] = float(m.group(1)) if m else None
    m = re.search(r"R_on = ([0-9.eE+-]+) ohm", text)
    out["r_on"] = float(m.group(1)) if m else None
    return out


SIZING_GEOM = [(s, g) for s in ("min", "2x") for g in ("min", "2x")]


def inertness(results: dict[str, BenchResult]) -> list[dict]:
    """Within one solve: does every regression quantity agree across the
    three variants? Exact equality of the printed values is required."""
    rows = []
    for bench in ("access_op", "access_ac", "cap_op", "cap_ac"):
        r = results.get(bench)
        if r is None or not r.values:
            continue
        for v in ("b0", "b1"):
            n = exact = ok = 0
            worst, worst_at, q = 0.0, "", ""
            for cid, vals in r.values.items():
                for name, x in vals.items():
                    m = re.match(rf"^(ioff|ron|ilk|cval)_{v}_(.*)$", name)
                    if not m:
                        continue
                    q = m.group(1)
                    ref = vals.get(f"{q}_st_{m.group(2)}")
                    if ref is None or x is None:
                        continue
                    n += 1
                    exact += x == ref
                    ok += within_tol(q, x, ref)
                    d = rel_dev(x, ref)
                    if d > worst:
                        worst, worst_at = d, f"{cid} {name}"
            rows.append({"bench": bench, "quantity": q, "variant": v, "n": n, "exact": exact, "ok": ok,
                         "worst_rel": worst, "worst_at": worst_at})
    return rows


def reproduction(results: dict[str, BenchResult], rid: str) -> list[dict]:
    """Default-tolerance benches vs the committed raw logs of `rid`."""
    rows = []
    spec = [
        ("access_op", "ioff", {"lo": "ioff_lo", "mid": "ioff_mid", "hi": "ioff_hi"}),
        ("access_ac", "ron", {None: "ron"}),
        ("cap_op", "ilk", {k: f"ilk_{k}" for k in range(1, 6)}),
        ("cap_ac", "cval", {k: f"cval_{k}" for k in range(1, 6)}),
    ]
    for bench, q, suffixes in spec:
        r = results.get(bench)
        if r is None or not r.values:
            continue
        for v in REGRESSION_VARIANTS:
            n = ok = exact = missing = 0
            worst, worst_at = 0.0, ""
            for cid, vals in r.values.items():
                for s, g in SIZING_GEOM:
                    for suf, stored_name in suffixes.items():
                        name = f"{q}_{v}_{sg_tag(s, g)}" + (f"_{suf}" if suf is not None else "")
                        x = vals.get(name)
                        ref = stored_value(rid, s, g, cid, stored_name)
                        if x is None or ref is None:
                            missing += 1
                            continue
                        n += 1
                        rel = rel_dev(x, ref)
                        ok += within_tol(q, x, ref)
                        exact += x == ref
                        if rel > worst:
                            worst, worst_at = rel, f"{cid} {name}"
            rows.append({"bench": bench, "quantity": q, "variant": v, "n": n, "ok": ok, "exact": exact,
                         "missing": missing, "worst_rel": worst, "worst_at": worst_at})
    return rows


def headline(results: dict[str, BenchResult], variant: str) -> dict:
    fh_c, fh_t, fh_dv = C.FAST_HOT_HIGH
    sc_c, sc_t, sc_dv = C.SLOW_COLD_LOW
    fh = C.corner_id(fh_c, fh_t, C.fmt_node_supply("bl", CHAR.V_READ_NOM * (1 + fh_dv)))
    sc = C.corner_id(sc_c, sc_t, C.fmt_node_supply("bl", CHAR.V_READ_NOM * (1 + sc_dv)))
    out = {"fh": fh, "sc": sc, "i_off": None, "i_sneak_max": None, "r_on": None}
    op = results.get("access_op")
    if op and fh in op.values:
        vals = [x for n, x in op.values[fh].items() if n.startswith(f"ioff_{variant}_") and x is not None]
        if vals:
            out["i_off"] = max(vals)
            out["i_sneak_max"] = (CHAR.N_GRID - 1) * max(vals)
    ac = results.get("access_ac")
    if ac and sc in ac.values:
        vals = [x for n, x in ac.values[sc].items() if n.startswith(f"ron_{variant}_") and x is not None]
        if vals:
            out["r_on"] = max(vals)
    return out


def iread_table(results: dict[str, BenchResult]) -> list[dict]:
    op = results.get("access_op")
    rows = []
    if not op:
        return rows
    for cid, vals in op.values.items():
        med = [x for n, x in vals.items() if n.startswith("iread_pm_") and x is not None]
        wc = {n: x for n, x in vals.items() if n.startswith("iread_pw_") and x is not None}
        if not wc:
            rows.append({"cid": cid, "med_min": None, "wc_min": None, "wc_at": "", "status": op.corner_status.get(cid)})
            continue
        at = min(wc, key=wc.get)
        rows.append({"cid": cid, "med_min": min(med) if med else None, "wc_min": wc[at],
                     "wc_at": at.replace("iread_pw_", ""), "status": op.corner_status.get(cid)})
    return rows


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------


def sci(x) -> str:
    return "n/a" if x is None else f"{x:.4e}"


def render_record(pdk, cand, rid: str, results: dict[str, BenchResult], params: dict,
                  dirty: bool | None, stored_rid: str | None, note: str | None = None) -> str:
    L: list[str] = []
    a = L.append
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    a("- **Claim**: issue #62 -- behavioral breakdown-augmented model for Candidate "
      f"{cand.n} / Region {cand.region} (`spec/cell-candidates.md` \"Post-breakdown model behavior\" gap; "
      "`spec/architecture.md#4-sense-scheme` `I_ref < I_prog_min`). (a) With the breakdown element disabled, "
      "or enabled but unprogrammed, the cell reproduces `sim/cell-device-characterization` "
      f"record `{stored_rid}`; (b) programmed-cell read current and `I_prog_min` per PVT corner under the "
      "ASSUMED parameters of `design/breakdown/breakdown_params.spice`; (c) the trigger/latch mechanism.")
    if dirty is None:
        state = (f"; working-tree state at run time not captured -- the run executed commit "
                 f"`{rid.rsplit('-', 1)[-1]}` (record id), and the exact decks are frozen under corners/{rid}/)")
    else:
        state = ", dirty tree at run time)" if dirty else ")"
    prov = f"schematic (design/netlists/{cand.netlist} wrapped by design/breakdown/cell_candidates_bd.spice" + state
    a(f"- **Netlist provenance**: {prov}")
    if note:
        a(f"- **Run note**: {note}")
    a("- **Model parameters** (sha256 of `design/breakdown/breakdown_params.spice`: "
      f"`{sha256(BD_DIR / 'breakdown_params.spice')}`):")
    a("")
    a("  | Parameter | Value | Unit | Provenance |")
    a("  |---|---|---|---|")
    for name, p in params.items():
        if name.startswith("c") and "_bd_tox" in name and not name.startswith(f"c{cand.n}_"):
            continue
        a(f"  | `{name}` | {p['value']:.4g} | {p['unit']} | {p['provenance']} |")
    a("")
    a(f"  Derived: V_bd(t_ref) = bd_ebd x c{cand.n}_bd_tox = **{vbd_ref(cand, params):.2f} V** (assumed, "
      "not a gf180 number); worst-case filament rf = bd_rf_med x exp(bd_zrf_wc x bd_rf_sig) = "
      f"{params['bd_rf_med']['value'] * math.exp(params['bd_zrf_wc']['value'] * params['bd_rf_sig']['value']):.4g} ohm.")
    a("- **Corner matrix run** (each bench one `klt sim` request; job ids below):")
    a(f"  - access benches: MOS process {', '.join(C.MOS_CORNERS)} (moscap_typical) x "
      f"{', '.join(str(t) for t in C.TEMPS_C)} degC x read rail {CHAR.V_READ_NOM*0.9:.2f}/{CHAR.V_READ_NOM:.2f}/"
      f"{CHAR.V_READ_NOM*1.1:.2f} V = 45 corners; x 4 (access-sizing x capacitor-geometry) sub-configurations "
      "as instances in the same deck")
    a(f"  - capacitor benches: {', '.join(C.MOSCAP_CORNERS)} (MOS typical) x 3 temperatures = 9 corners (`nosupply`), "
      "x 4 sub-configurations x 5 capacitor biases as instances")
    a(f"  - trigger bench: {', '.join(C.MOSCAP_CORNERS)} x 3 temperatures x 10 stress points "
      "(2 instances x 5 levels, one stressed per corner) = 90 corners, process-minimum (netlist-default) geometry")
    a("  - geometry/sizing levels are the committed netlists' placeholder defaults and their x2 widths, "
      "NOT `spec/split-axis-plan.md`'s ratified levels (same caveat as the characterization records)")
    envs = [r.klt_env for r in results.values() if r.klt_env]
    if envs:
        e0 = envs[0]
        rm = e0.get("remote") or {}
        a(f"- **Execution**: engine ngspice {e0.get('engine_version')} on the batch fleet "
          f"(runner klt {rm.get('runner_klt_version')}, submitting client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}` -- requests use only runner-supported "
          "features, README \"Fleet klt version\"); models_lib sha256 "
          f"`{e0.get('models_lib_sha256')}`. ngspice {e0.get('engine_version')} prints `.meas` results to 6 "
          "significant digits; the committed characterization logs carry 7, so exact digit matches against "
          "them are not expected and relative deviations of order 1e-6 are print precision.")
    a("- **Result**:")
    a("  - **Bench status**:")
    for b in BENCHES:
        r = results.get(b)
        if r is None:
            a(f"    - `{b}`: not run")
            continue
        job = (r.remote or {}).get("job_id", "local") if r.remote is not None else "local"
        nerr = sum(1 for s in r.corner_status.values() if s != "pass")
        a(f"    - `{b}`: klt status `{r.status}`, {len(r.corner_status)} corners, {nerr} not `pass`, job `{job}`"
          + (f" -- ERROR: {r.error[:400]}" if r.error else ""))
    a("  - **(a1) Element inertness, same deck** -- each regression quantity of the disabled (`b0`) and the "
      "enabled-unprogrammed (`b1`) wrapper vs the stock cell instance at the same bias in the same solve. "
      f"Criterion (README \"Regression criterion\"): well-conditioned {'/'.join(WELL_CONDITIONED)} within "
      f"reltol = {DEFAULT_RELTOL:g}; gmin-floor {'/'.join(GMIN_FLOOR)} within reltol*|ref| + abstol "
      f"({DEFAULT_ABSTOL:g} A), ngspice's own convergence bound for currents below abstol. Exact-match counts "
      "and the worst relative deviation are reported regardless:")
    if not inertness(results):
        a("    - (no regression bench in this run)")
    for row in inertness(results):
        a(f"    - `{row['bench']}` {row['quantity']} [{row['variant']}]: {row['ok']}/{row['n']} within criterion, "
          f"{row['exact']}/{row['n']} exactly equal; worst relative difference {row['worst_rel']:.2e}"
          + (f" at `{row['worst_at']}`" if row["worst_at"] else ""))
    if stored_rid and ("access_op" in results or "access_ac" in results or "cap_op" in results or "cap_ac" in results):
        a(f"  - **(a2) Reproduction of committed record `{stored_rid}`** (default tolerances, as that record ran) -- "
          "per corner and sub-configuration vs its raw logs; same class-based criterion as (a1):")
        for row in reproduction(results, stored_rid):
            a(f"    - `{row['bench']}` {row['quantity']} [{row['variant']}: {VARIANTS[row['variant']]}]: "
              f"{row['ok']}/{row['n']} within criterion, {row['exact']}/{row['n']} exactly equal, "
              f"worst relative deviation {row['worst_rel']:.2e}"
              + (f" at `{row['worst_at']}`" if row["worst_at"] else "")
              + (f", {row['missing']} not comparable" if row["missing"] else ""))
        sh = stored_headline(stored_rid)
        for v in REGRESSION_VARIANTS:
            h = headline(results, v)
            a(f"    - headline, {v}: I_sneak_max = {sci(h['i_sneak_max'])} A at `{h['fh']}` (record: "
              f"{sci(sh['i_sneak_max'])}); R_on = {sci(h['r_on'])} ohm at `{h['sc']}` (record: {sci(sh['r_on'])})")
    rows = iread_table(results)
    if rows:
        render_iread(a, rows, results, cand)
    tr = results.get("trigger")
    if tr and tr.values:
        render_trigger(a, tr, cand, params)
    render_links(a, rid, stored_rid, pdk)
    return "\n".join(L)


def render_iread(a, rows, results, cand) -> None:
    a("  - **(b) Programmed-cell read current** (BL = read rail, WL fully on, PL = 0, state forced programmed; "
      "minimum over the 4 sub-configurations at each corner). `rf_med` = median filament, `rf_wc` = "
      "+bd_zrf_wc sigma filament. CONDITIONAL ON THE ASSUMED FILAMENT PARAMETERS:")
    a("")
    a("    | Corner | I_read (rf_med) [A] | I_read (rf_wc) [A] | worst sub-config | klt |")
    a("    |---|---|---|---|---|")
    for row in rows:
        a(f"    | `{row['cid']}` | {sci(row['med_min'])} | {sci(row['wc_min'])} | {row['wc_at']} | {row['status']} |")
    a("")
    h1 = headline(results, "b1")
    sc_row = next((r for r in rows if r["cid"] == h1["sc"]), None)
    valid = [r for r in rows if r["wc_min"] is not None]
    glob = min(valid, key=lambda r: r["wc_min"]) if valid else None
    a(f"  - **I_prog_min (Candidate {cand.n})**, worst-case filament (rf_wc), worst sub-configuration:")
    a(f"    - at the corner `spec/architecture.md` Section 4 names for the selected cell (`{h1['sc']}`): "
      f"**{sci(sc_row['wc_min'] if sc_row else None)} A**")
    a(f"    - worst over all {len(valid)} resolved corners: **{sci(glob['wc_min'] if glob else None)} A** at "
      f"`{glob['cid'] if glob else 'n/a'}`" + (" -- a different corner than Section 4 names" if glob and sc_row
                                                  and glob["cid"] != sc_row["cid"] else ""))
    if h1["i_sneak_max"] is not None and glob is not None:
        ratio = glob["wc_min"] / h1["i_sneak_max"]
        if ratio > 1:
            a(f"    - against this run's unprogrammed-model `I_sneak_max` = {sci(h1['i_sneak_max'])} A (`{h1['fh']}`, "
              "gmin-floor upper bound): the `I_sneak_max < I_ref < I_prog_min` window spans a factor of "
              f"**{ratio:.3g}** (worst-corner I_prog_min). This sizes nothing -- it is conditional on the assumed "
              "filament distribution and the placeholder read/WL biases.")
        else:
            a(f"    - against this run's unprogrammed-model `I_sneak_max` = {sci(h1['i_sneak_max'])} A (`{h1['fh']}`): "
              f"the worst-corner I_prog_min is **below** it (ratio {ratio:.3g}). **No `I_ref` satisfies "
              "`I_sneak_max < I_ref < I_prog_min` at these placeholder read/WL biases, so a usable I_prog_min "
              "cannot be derived for this candidate until its read bias is set** -- see the run note.")


def render_trigger(a, tr: BenchResult, cand, params: dict) -> None:
    if tr.values:
        lv = trigger_levels(cand, params)
        a("  - **(c) Trigger/latch** -- PL stressed with a raised-cosine pulse "
          f"({TRIG_TW*1e6:g} us flat, {TRIG_TR*1e9:g} ns edges) with the access device on and BL = 0; state "
          f"`st` and damage `D` read at {TRIG_TMEAS*1e6:g} us, i.e. after the pulse has ended (a latched state "
          "must still read 1). Instance a: median Weibull quantile; instance b: ubd = "
          f"{UBD_LOW}. Model-mechanism check only, NOT a program-path claim:")
        a("")
        a("    | Corner | V(PL) [V] | inst | predicted st | st | D | V(CN,PL) mid-pulse [V] | klt |")
        a("    |---|---|---|---|---|---|---|---|")
        n_conv = n_ok = 0
        for cid in sorted(tr.values):
            vals = tr.values[cid]
            inst = "a" if "_pla" in cid else "b"
            vpl = cid.rsplit("_", 1)[1][3:-1].replace("p", ".")  # pla8p00v -> 8.00
            pred = trigger_prediction(cand, params, float(vpl), inst)
            st = vals.get(f"st_{inst}")
            if st is not None and tr.corner_status.get(cid) == "pass":
                n_conv += 1
                n_ok += int((st > 0.5) == bool(pred))
            a(f"    | `{cid}` | {vpl} | {inst} | {pred} | {sci(st)} | {sci(vals.get(f'dmg_{inst}'))} "
              f"| {vox(vals, inst)} | {tr.corner_status.get(cid)} |")
        a("")
        a(f"    **Converged corners: {n_conv}/{len(tr.corner_status)}; outcome as predicted at {n_ok}/{n_conv}.** "
          "Prediction (from the parameters alone): intact at the rated voltage and at 0.9 x V_bd; at 0.95 x V_bd "
          f"intact for the median instance a (D ~ 0.32) but broken down for instance b (ubd = {UBD_LOW}); broken "
          "down and latched at 1.0 and 1.1 x V_bd. Non-converged corners carry no state reading and are not "
          "counted either way (README \"Transient start\"; follow-up #74).")
        a(f"    Stress points: rated voltage {abs(lv[0]):.2f} V, then "
          + ", ".join(f"{f:g} x V_bd" for f in TRIG_FRACTIONS) + f" (V_bd = {vbd_ref(cand, params):.2f} V).")


def trigger_prediction(cand, params: dict, vpl: float, inst: str) -> int:
    """Expected latched state (0/1) at the end of the trigger bench, from the
    stress level alone (index into trigger_levels)."""
    lv = [abs(v) for v in trigger_levels(cand, params)]
    i = min(range(len(lv)), key=lambda k: abs(lv[k] - abs(vpl)))
    f = (None,) + TRIG_FRACTIONS
    if i == 0 or f[i] < 0.95:
        return 0
    if f[i] == 0.95:
        return 0 if inst == "a" else 1
    return 1


# --- issue #74 convergence record -------------------------------------------

# The #62 trigger records whose non-converged corners #74 is about; the
# control bench of a #74 run is compared corner by corner against them.
ORIGINAL_TRIGGER_RECORDS = {1: "20261009-023645-6eff628", 2: "20261009-023648-6eff628", 3: "20261009-023651-6eff628"}


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


def conv_ok(res: BenchResult | None, cid: str) -> bool | None:
    if res is None or cid not in res.outcome:
        return None
    return res.outcome[cid]["kind"] == "pass"


def abs_extreme(vals: dict, k: str) -> float | None:
    hi, lo = vals.get(f"mx_{k}"), vals.get(f"mn_{k}")
    if hi is None or lo is None:
        return None
    return max(abs(hi), abs(lo))


def render_conv_record(pdk, cand, rid: str, results: dict[str, BenchResult], params: dict,
                       dirty: bool | None, note: str | None = None) -> str:
    L: list[str] = []
    a = L.append
    vbd = vbd_ref(cand, params)
    rating = ACCESS_RATING_V[cand.n]
    orig_rid = ORIGINAL_TRIGGER_RECORDS.get(cand.n)
    a(f"# Record {rid}")
    a("")
    a(f"- **Record ID**: {rid}")
    stims = [s_ for s_ in CONV_STIMULI if any(f"{s_}_{v}" in results for v in CONV_VARIANTS)]
    a(f"- **Claim**: issue #74 -- does the breakdown-event transient of Candidate {cand.n} / Region {cand.region} "
      "converge at every corner of the full #62 trigger PVT grid on the fleet engine? Benches in this run: "
      + ("the #62 two-instance trigger bench re-run unchanged (control); " if CONTROL_BENCH in results else "")
      + "; ".join(f"`{s_}` = {CONV_STIMULI[s_]}" for s_ in stims)
      + ". Every single-instance stimulus is run as stock / element-disabled / element-enabled decks "
      "that differ only in the cell line; any non-convergence is attributed by that comparison. Trigger "
      "threshold, latch, program current and access-device terminal voltages (against the ratified "
      f"{rating:g} V rating of `{CHAR.CANDIDATES[cand.n - 1].access_model}`) are logged, CONDITIONAL ON THE "
      "ASSUMED breakdown parameters.")
    if dirty is None:
        state = f"; working-tree state at run time not captured, exact decks frozen under corners/{rid}/)"
    else:
        state = ", dirty tree at run time)" if dirty else ")"
    a(f"- **Netlist provenance**: schematic (design/netlists/{cand.netlist} wrapped by "
      "design/breakdown/cell_candidates_bd.spice" + state)
    if note:
        a(f"- **Run note**: {note}")
    a("- **Model parameters**: `design/breakdown/breakdown_params.spice` unchanged by #74 (sha256 "
      f"`{sha256(BD_DIR / 'breakdown_params.spice')}`); element `design/breakdown/af_breakdown.spice` sha256 "
      f"`{sha256(BD_DIR / 'af_breakdown.spice')}`. Derived V_bd(t_ref) = bd_ebd x c{cand.n}_bd_tox = "
      f"**{vbd:.2f} V** (assumed, not a gf180 number).")
    a("- **Corner matrix run** (each bench one `klt sim` request on the batch fleet; same grid as the #62 "
      f"trigger records): {', '.join(C.MOSCAP_CORNERS)} (MOS typical) x {', '.join(str(t) for t in C.TEMPS_C)} "
      f"degC x 5 stress levels = 45 corners per single-instance bench; the control is 90 corners "
      "(2 instances x 5 levels). Process-minimum (netlist-default) geometry. Levels: the capacitor's rated "
      f"voltage ({cand.cap_rated_v:g} V) and " + ", ".join(f"{f:g}" for f in TRIG_FRACTIONS) +
      f" x V_bd. Pulse: edges {TRIG_TR*1e9:g} ns (shape per bench, `edge_lines()`), flat {TRIG_TW*1e6:g} us from t = "
      f"{TRIG_T1*1e6:g} us; `tran {fmt(TRIG_TSTEP)} {fmt(TRIG_TSTOP)} uic`; default ngspice tolerances, "
      f"gmin = {fmt(CHAR.GMIN)}; per-corner timeout 300 s.")
    a("  - PL-driven (`trig1`, `trigc`): PL driven to the signed level, BL = 0 V, WL = "
      f"{cand.moscap_wl_on:g} V, VB = {cand.vb:g} V (the #62 stimulus, one cell).")
    a(f"  - BL-driven (`prog`, `progc`): VPP pulse (positive level) -> ballast {prog_rballast(cand, params)/1e3:.4g} kOhm (PLACEHOLDER: "
      f"V_bd / {PROG_ILIM_PLACEHOLDER*1e6:g} uA; `I_target_max` is unresolved in `spec/architecture.md` 2) -> BL; "
      f"PL = 0 V return; WL = {cand.moscap_wl_on:g} V + VPP(t)"
      + (f"; n-well VB = {cand.vb:g} V + VPP(t)" if cand.polarity == "p" else f"; VB = {cand.vb:g} V (p-substrate tie)")
      + ". Gate (and well) drive riding on VPP is a bench choice: the gate-drive and well levels are "
      "unresolved in `spec/supply-domains-decision.md` rows 8, 9, 15.")
    envs = [r.klt_env for r in results.values() if r.klt_env]
    if envs:
        e0 = envs[0]
        rm = e0.get("remote") or {}
        a(f"- **Execution**: engine ngspice {e0.get('engine_version')} on the batch fleet (runner klt "
          f"{rm.get('runner_klt_version')}, submitting client {rm.get('client_klt_version')}, "
          f"`runner_compatibility: {rm.get('runner_compatibility')}`); models_lib sha256 "
          f"`{e0.get('models_lib_sha256')}`.")
    a("- **Result**:")
    render_conv_matrix(a, cand, params, results)
    render_control(a, cand, params, results, orig_rid)
    render_attribution(a, rid, results)
    render_opstart(a, rid, results)
    for stim in CONV_STIMULI:
        render_conv_trigger(a, cand, params, results, stim)
    if any(b in results for b in CONV_BENCHES):
        render_conv_regression(a, results)
        render_device_limits(a, cand, params, results)
        render_prog_current(a, cand, params, results)
    a("- **Links**:")
    a("  - Model: `design/breakdown/` (unchanged by this run)")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Requests, bodies, klt reports, per-corner decks and logs: `sim/cell-breakdown-model/corners/{rid}/<bench>/`")
    if orig_rid:
        a(f"  - Original trigger record: `sim/cell-breakdown-model/records/{orig_rid}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host); fleet-side hashes in each `report.json`")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a(f"- **Supersedes**: (none -- the #62 trigger record `{orig_rid}` stays as evidence; this record adds "
      "the #74 convergence campaign)")
    a("")
    return "\n".join(L)


def render_conv_matrix(a, cand, params, results) -> None:
    a("  - **(1) Convergence, every attempted corner counted** (`pass` = klt pass AND every measurement has a "
      "value; failures by kind: `timeout` = 300 s per-corner limit, `timestep` = ngspice \"timestep too "
      "small\", `missing` = ran to the end but a measurement has no value):")
    a("")
    a("    | Bench | Stimulus / variant | Attempted | Pass | Timeout | Timestep | Missing | Other | klt | Job |")
    a("    |---|---|---|---|---|---|---|---|---|---|")
    for b in (CONTROL_BENCH,) + CONV_BENCHES + (OPSTART_BENCH,):
        r = results.get(b)
        if r is None:
            continue
        if b == OPSTART_BENCH:
            desc = "stock cell, trigc deck, rated level, operating-point start (no `uic`)"
        else:
            desc = "control: #62 two-instance bench, unchanged" if b == CONTROL_BENCH else \
            f"{b.split('_')[0]} / {CONV_VARIANTS[conv_split(b)[1]]}"
        job = (r.remote or {}).get("job_id", "?") if r.remote else ("submit-error" if r.error else "?")
        t = tally([o["kind"] for o in r.outcome.values()])
        a(f"    | `{b}` | {desc} | {t['attempted']} | {t['pass']} | {t['timeout']} | {t['timestep']} | "
          f"{t['missing-measurement']} | {t['error']} | `{r.status}` | `{job}` |")
        if r.error:
            a(f"    | | ERROR: {r.error[:300]!r} | | | | | | | | |")
    a("")
    a("    Per stress level (pass / attempted), each level over 3 moscap corners x 3 temperatures:")
    a("")
    head = ["rated"] + [f"{f:g}x" for f in TRIG_FRACTIONS]
    a("    | Bench | " + " | ".join(head) + " |")
    a("    |---|" + "---|" * len(head))
    for b in (CONTROL_BENCH,) + CONV_BENCHES:
        r = results.get(b)
        if r is None or not r.outcome:
            continue
        stim = "trig1" if b == CONTROL_BENCH else conv_split(b)[0]  # control: same levels as trig1
        cnt = {h: [0, 0] for h in head}
        for cid, o in r.outcome.items():
            h = level_label(cand, params, stim, corner_level(cid))
            cnt[h][1] += 1
            cnt[h][0] += o["kind"] == "pass"
        a(f"    | `{b}` | " + " | ".join(f"{cnt[h][0]}/{cnt[h][1]}" for h in head) + " |")
    a("")


def render_control(a, cand, params, results, orig_rid) -> None:
    r = results.get(CONTROL_BENCH)
    if r is None or not orig_rid:
        return
    orig = results_from_reports(cand, orig_rid, params, benches=(CONTROL_BENCH,)).get(CONTROL_BENCH)
    if orig is None:
        return
    now_bad = {c for c, o in r.outcome.items() if o["kind"] != "pass"}
    old_bad = {c for c, o in orig.outcome.items() if o["kind"] != "pass"}
    a(f"  - **(2) Control reproduction** -- the #62 two-instance deck, re-submitted unchanged, vs record "
      f"`{orig_rid}`: {len(now_bad)}/{len(r.outcome)} not converged now, {len(old_bad)}/{len(orig.outcome)} "
      f"then; same corners: **{'yes' if now_bad == old_bad else 'no'}**"
      + ("" if now_bad == old_bad else
         f" (only now: {', '.join(f'`{c}`' for c in sorted(now_bad - old_bad)) or 'none'}; only then: "
         f"{', '.join(f'`{c}`' for c in sorted(old_bad - now_bad)) or 'none'})") + ".")
    where: dict[str, int] = {}
    for c in sorted(now_bad):
        o = r.outcome[c]
        k = o["kind"] if o["kind"] != "timestep" else f"timestep in {o['node']} ({control_role(c, o['node'])})"
        where[k] = where.get(k, 0) + 1
    if where:
        a("    Where ngspice reported the failure: " + "; ".join(f"{k}: {n}" for k, n in sorted(where.items())) + ".")


def control_role(cid: str, node: str) -> str:
    """In the two-instance control deck: was the failing node in the stressed
    cell, the idle one, or a testbench source?"""
    m = re.match(r"^(?:e\.)?x([ab])\.", node)
    if not m:
        return "testbench source"
    stressed = "a" if "_pla" in cid else "b"
    return "stressed instance" if m.group(1) == stressed else "idle instance"


def render_attribution(a, rid, results) -> None:
    if not any(b in results for b in CONV_BENCHES):
        return
    a("  - **(3) Attribution of non-converged single-instance corners** (stock / disabled / enabled decks of "
      "the same stimulus at the same corner; the committed `.cir` is the minimal reproducer, one cell, one "
      "corner):")
    any_bad = False
    for stim in CONV_STIMULI:
        rs = {v: results.get(f"{stim}_{v}") for v in CONV_VARIANTS}
        cids = sorted(set().union(*[set(r.outcome) for r in rs.values() if r]))
        for cid in cids:
            ok = {v: conv_ok(rs[v], cid) for v in CONV_VARIANTS}
            if all(x is not False for x in ok.values()):
                continue
            any_bad = True
            fails = []
            for v, x in ok.items():
                if x is False:
                    o = rs[v].outcome[cid]
                    det = o["kind"] + (f" at t = {o['time']:.4e} s in `{o['node']}` ({o['where']})"
                                       if o["kind"] == "timestep" else "")
                    fails.append(f"{v}: {det}; reproducer `corners/{rid}/{stim}_{v}/{cid}.cir`")
            a(f"    - `{stim}` `{cid}`: **{attribute_corner(ok)}** -- " + "; ".join(fails))
    if not any_bad:
        a("    - none: every corner of every single-instance bench converged.")


def render_opstart(a, rid, results) -> None:
    r = results.get(OPSTART_BENCH)
    if r is None:
        return
    t = tally([o["kind"] for o in r.outcome.values()])
    job = (r.remote or {}).get("job_id", "?") if r.remote else "?"
    a(f"  - **(3b) Operating-point start, stock cell** (`{OPSTART_BENCH}`: the `trigc_st` deck at the rated level, "
      "`tran` WITHOUT `uic`, job "
      f"`{job}`): {t['pass']}/{t['attempted']} converged (timeout {t['timeout']}, timestep {t['timestep']}, "
      f"missing {t['missing-measurement']}, other {t['error']}). No breakdown element is in this deck, so any "
      "failure here is **stock-cell**; reproducers `corners/" + rid + f"/{OPSTART_BENCH}/<corner>.cir`:")
    for cid in sorted(r.outcome, key=lambda c: (c.split("_")[1], corner_temp(c))):
        o = r.outcome[cid]
        a(f"    - `{cid}`: {o['kind']}" + (f" at t = {o['time']:.4e} s in `{o['node']}`" if o["kind"] == "timestep" else ""))


def render_conv_trigger(a, cand, params, results, stim) -> None:
    b0 = results.get(f"{stim}_b0")
    rows = []
    for var, ubd in (("b1m", 0.5), ("b1l", UBD_LOW)):
        r = results.get(f"{stim}_{var}")
        if r is None:
            continue
        for cid in sorted(r.values, key=lambda c: (c.split("_")[1], corner_temp(c), abs(corner_level(c)))):
            vals = r.values[cid]
            vox = (b0.values.get(cid) or {}).get("vox_mid") if b0 else None
            d_lo = d_hi = pred = None
            if vox is not None:
                d_lo, d_hi = damage_prediction(cand, params, vox, ubd)
                pred = predict_state(d_lo, d_hi)
            rows.append((var, cid, vox, d_lo, pred, vals, r.outcome[cid]["kind"]))
    if not rows:
        return
    title = (f"(4) Trigger/latch, `{stim}`: "
             + ("PL-driven, one cell per deck" if STIM_DRIVE[stim] == "pl" else "BL-driven program leg")
             + (", raised-cosine edges" if STIM_EDGE[stim] == "rc" else ", C-infinity edges"))
    a(f"  - **{title}** -- predicted state from the E-model applied to the DISABLED deck's mid-pulse oxide "
      "voltage at the same corner (damage over the flat top >= 2: must break down; flat top plus edges <= 0.5: "
      "must not; in between: threshold boundary, not scored). `st` read at "
      f"{TRIG_TMID*1e6:g} us (mid-pulse) and {TRIG_TMEAS*1e6:g} us (after the pulse: latch):")
    a("")
    a("    | Variant | Corner | Level | V(CN,PL) disabled [V] | D_pred (flat) | predicted | st mid | st end | D end | outcome |")
    a("    |---|---|---|---|---|---|---|---|---|---|")
    n_conv = n_scored = n_ok = n_bound = n_nopred = 0
    for var, cid, vox, d_lo, pred, vals, kind in rows:
        st = vals.get("st")
        conv = kind == "pass"
        n_conv += conv
        if conv and pred is not None and st is not None:
            n_scored += 1
            n_ok += int(latched_as_predicted(st, pred))
        n_bound += pred is None and vox is not None
        n_nopred += vox is None
        ptxt = "no prediction" if vox is None else ("boundary" if pred is None else str(pred))
        a(f"    | {var} | `{cid}` | {level_label(cand, params, stim, corner_level(cid))} | "
          f"{'n/a' if vox is None else f'{vox:.4f}'} | {sci(d_lo)} | {ptxt} | "
          f"{sci(vals.get('st_mid'))} | {sci(st)} | {sci(vals.get('dmg'))} | {kind} |")
    a("")
    a(f"    **Converged {n_conv}/{len(rows)}; outcome as predicted (and fully latched, st = 0 or 1) at "
      f"{n_ok}/{n_scored} scored corners; {n_bound} at the threshold boundary and {n_nopred} without a "
      "prediction because the disabled deck did not converge there (neither scored).**")


CELL_QUANTITIES = tuple(f"{p}_{k}" for k in TERMINAL_PAIRS for p in ("mx", "mn")) + \
    ("vox_mid", "vcn_mid", "vbl_mid", "vpl_mid", "vcn_end", "ibl_mid", "ibl_mx", "ibl_mn")


def compare_decks(ra: BenchResult | None, rb: BenchResult | None, cids=None) -> dict:
    """Exact-equality count and worst relative deviation of every cell
    quantity between two decks, over corners where both converged."""
    out = {"n": 0, "exact": 0, "worst": 0.0, "at": "", "corners": 0}
    if ra is None or rb is None:
        return out
    for cid in sorted(set(ra.values) & set(rb.values)):
        if cids is not None and cid not in cids:
            continue
        if ra.outcome[cid]["kind"] != "pass" or rb.outcome[cid]["kind"] != "pass":
            continue
        out["corners"] += 1
        for q in CELL_QUANTITIES:
            x, y = rb.values[cid].get(q), ra.values[cid].get(q)
            if x is None or y is None:
                continue
            out["n"] += 1
            out["exact"] += x == y
            d = rel_dev(x, y) if abs(y) > 1e-9 else abs(x - y)
            if d > out["worst"]:
                out["worst"], out["at"] = d, f"{cid} {q}"
    return out


def render_conv_regression(a, results) -> None:
    a("  - **(5) Element inertness in transient** -- every logged cell quantity (terminal-difference extremes, "
      "mid-pulse and end voltages, BL current), same corner, decks differing only in the cell line. "
      "Relative deviation (absolute below 1 nV/nA):")
    for stim in CONV_STIMULI:
        st = results.get(f"{stim}_st")
        if st is None:
            continue
        c = compare_decks(st, results.get(f"{stim}_b0"))
        a(f"    - `{stim}` disabled (`b0`) vs stock: {c['exact']}/{c['n']} exactly equal over {c['corners']} "
          f"corners; worst deviation {c['worst']:.2e}" + (f" at `{c['at']}`" if c["at"] else ""))
        for v in ("b1m", "b1l"):
            r = results.get(f"{stim}_{v}")
            if r is None:
                continue
            intact = {cid for cid, vals in r.values.items() if vals.get("st") == 0.0}
            c = compare_decks(st, r, intact)
            a(f"    - `{stim}` enabled (`{v}`) vs stock where the enabled cell stayed intact (st = 0 exactly): "
              f"{c['exact']}/{c['n']} exactly equal over {c['corners']} corners; worst deviation {c['worst']:.2e}"
              + (f" at `{c['at']}`" if c["at"] else ""))


def render_device_limits(a, cand, params, results) -> None:
    rating = ACCESS_RATING_V[cand.n]
    a(f"  - **(6) Terminal voltages vs ratings** -- largest |V| of each pair over the WHOLE transient, worst "
      f"PVT corner per stress level (converged corners only). Access-device rating {rating:g} V "
      f"(`{CHAR.CANDIDATES[cand.n - 1].access_model}`); **bold** = exceeds it. The capacitor column is the "
      f"stressed oxide (rated {cand.cap_rated_v:g} V; exceeding it is the point of the bench):")
    head = ["rated"] + [f"{f:g}x" for f in TRIG_FRACTIONS]
    for stim in CONV_STIMULI:
        for var in ("st", "b1m", "b1l"):
            r = results.get(f"{stim}_{var}")
            if r is None or not r.values:
                continue
            a("")
            a(f"    `{stim}_{var}`:")
            a("")
            a("    | Level | " + " | ".join(f"{k}: {TERMINAL_PAIRS[k][0].upper()}-{TERMINAL_PAIRS[k][1].upper()}"
                                         for k in TERMINAL_PAIRS) + " | over rating |")
            a("    |---|" + "---|" * (len(TERMINAL_PAIRS) + 1))
            for h in head:
                cells, over = [], 0
                cids = [c for c in r.values if level_label(cand, params, stim, corner_level(c)) == h
                        and r.outcome[c]["kind"] == "pass"]
                for k in TERMINAL_PAIRS:
                    best, at = None, ""
                    for c in cids:
                        x = abs_extreme(r.values[c], k)
                        if x is not None and (best is None or x > best):
                            best, at = x, c
                    if best is None:
                        cells.append("n/a")
                        continue
                    if k in ACCESS_PAIRS and best > rating:
                        over += 1
                        cells.append(f"**{best:.2f}**")
                    else:
                        cells.append(f"{best:.2f}")
                a(f"    | {h} ({len(cids)} corners) | " + " | ".join(cells) + f" | {over} pair(s) |")
    a("")


def render_prog_current(a, cand, params, results) -> None:
    rb = prog_rballast(cand, params)
    a(f"  - **(7) Program current, BL-driven leg** -- I(BL) at mid-pulse and its peak over the transient; the "
      f"ballast alone allows VPP / {rb/1e3:.4g} kOhm:")
    a("")
    a("    | Variant | Corner | VPP [V] | ballast-only limit [A] | I(BL) mid [A] | I(BL) peak [A] | st end | outcome |")
    a("    |---|---|---|---|---|---|---|---|")
    for var in ("b1m", "b1l"):
        r = results.get(f"prog_{var}")
        if r is None:
            continue
        for cid in sorted(r.values, key=lambda c: (c.split("_")[1], corner_temp(c), corner_level(c))):
            v = r.values[cid]
            vpp = corner_level(cid)
            a(f"    | {var} | `{cid}` | {vpp:.2f} | {sci(vpp / rb)} | {sci(v.get('ibl_mid'))} | "
              f"{sci(v.get('ibl_mx'))} | {sci(v.get('st'))} | {r.outcome[cid]['kind']} |")
    a("")


def render_links(a, rid: str, stored_rid: str | None, pdk) -> None:
    a("- **Links**:")
    a("  - Model: `design/breakdown/` (element, wrappers, parameters, `check_params.py`)")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Requests, generated bodies, klt reports, per-corner decks and logs: `sim/cell-breakdown-model/corners/{rid}/<bench>/`")
    a(f"  - Regression reference: `sim/cell-device-characterization/records/{stored_rid}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host); fleet-side engine/model hashes in each `report.json` `environment`")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("- **Supersedes**: (none -- first record for this claim/region)")
    a("")


def vox(vals: dict, inst: str) -> str:
    cn, pl = vals.get(f"vcn_{inst}"), vals.get(f"vpl_{inst}")
    return "n/a" if cn is None or pl is None else f"{cn - pl:.4e}"


def snapshot(cand) -> str:
    parts = []
    for p in (REPO_ROOT / "design" / "netlists" / cand.netlist, WRAPPERS,
              BD_DIR / "af_breakdown.spice", BD_DIR / "breakdown_params.spice"):
        parts.append(f"* ===== {p.relative_to(REPO_ROOT)} =====\n{p.read_text()}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def smoke(pdk, cand, bench: str, params: dict, pick: list[str] | None = None) -> int:
    """ONE corner of ONE bench, locally -- a debug probe, not evidence.
    `pick` = [process, temperature, supply-index] selects the corner
    (default: the first process, 27 degC, a bench-specific level)."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}-{bench}"
    work.mkdir(parents=True)
    body, ms = build_body(bench, pdk, cand, defaults, work, str(pdk.variant_dir), params)
    (work / "body.spice").write_text(body)
    req = make_request(bench, cand, pdk, ms, params)
    corners = req["corners"]
    proc = [p for p in corners["process"] if pick and p["name"] == pick[0]]
    corners["process"] = proc or corners["process"][:1]
    corners["temperature_c"] = [float(pick[1]) if pick else 27.0]
    if "supply_v" in corners:
        k = len(next(iter(corners["supply_v"].values())))
        idx = k - 2 if bench == "trigger" else k // 2   # trigger: inst b at 1.0 x V_bd; else nominal
        if pick:
            idx = int(pick[2])
        corners["supply_v"] = {key: [vals[idx]] for key, vals in corners["supply_v"].items()}
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    report, err = run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke {bench}: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    bad = [m for m in c["measurements"] if m["value"] is None]
    print(f"smoke c{cand.n} {bench}: {c['corner_id']} status={c['status']} "
          f"{len(c['measurements']) - len(bad)}/{len(c['measurements'])} measurements; work dir {work}")
    derived = derive(bench, {m["name"].lower(): m["value"] for m in c["measurements"]})
    for k in list(derived)[:40]:
        print(f"   {k} = {derived[k]}")
    for d in c["diagnostics"][:3]:
        print(f"   diag: {d}")
    return 0 if c["status"] == "pass" else 1


def results_from_reports(cand, rid: str, params: dict, benches=None) -> dict[str, BenchResult]:
    results: dict[str, BenchResult] = {}
    for bench in benches or ALL_BENCHES:
        bdir = THIS_DIR / "corners" / rid / bench
        rp = bdir / "report.json"
        if rp.is_file():
            report = json.loads(rp.read_text())
            env = report.get("environment", {})
            res = BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"), klt_env=env)
            for c in report["corners"]:
                cid = corner_key(bench, c, cand, params)
                res.corner_status[cid] = c["status"]
                res.values[cid] = derive(bench, {m["name"].lower(): m["value"] for m in c["measurements"]})
            fill_outcomes(res, report, bdir, cand, params)
        elif (bdir / "submit-error.txt").is_file():
            res = BenchResult(bench=bench, status="submit-error", remote=None,
                              error=(bdir / "submit-error.txt").read_text())
        else:
            continue
        results[bench] = res
    return results


def render_any(pdk, cand, rid: str, results: dict[str, BenchResult], params: dict, dirty, note) -> str:
    """A run that includes any #74 bench gets the convergence record."""
    if any(b in CONV_BENCHES or b == OPSTART_BENCH for b in results):
        return render_conv_record(pdk, cand, rid, results, params, dirty, note)
    return render_record(pdk, cand, rid, results, params, dirty, stored_record_id(cand), note)


def render_only(pdk, cand, rid: str, params: dict, note: str | None = None) -> int:
    results = results_from_reports(cand, rid, params)
    if not results:
        print(f"ERROR: no saved reports under corners/{rid}/", file=sys.stderr)
        return 2
    prov_file = THIS_DIR / "corners" / rid / "run-provenance.json"
    dirty = json.loads(prov_file.read_text())["dirty"] if prov_file.is_file() else None
    R.write_once(THIS_DIR / "records" / f"{rid}.md", render_any(pdk, cand, rid, results, params, dirty, note))
    print(f"record: records/{rid}.md (rendered from saved reports)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=",".join(BENCHES),
                    help=f"comma-separated; #62 benches {', '.join(BENCHES)}; #74 benches {', '.join(CONV_BENCHES)}")
    ap.add_argument("--campaign", choices=tuple(CAMPAIGNS), default=None,
                    help="conv74: the #62 trigger bench (control) + the single-instance trig1/prog benches "
                         "(raised-cosine edges); conv74c: the trigc/progc benches (C-infinity edges). "
                         "Overrides --benches")
    ap.add_argument("--smoke", default=None, metavar="N:BENCH[:PROCESS:TEMP:LEVEL_INDEX]",
                    help="run ONE corner of ONE bench locally (debug probe; writes no record)")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--note", default=None, help="free-text run note carried into the record(s)")
    ap.add_argument("--render", default=None, metavar="RECORD_ID",
                    help="(re)write records/RECORD_ID.md from the saved corners/RECORD_ID/*/report.json "
                         "of ONE candidate (--candidates N); runs no simulation. Refuses to overwrite.")
    ap.add_argument("--klt", default="klt",
                    help="klt command (space-separated), e.g. a version-pinned `uvx --from ... klt` to "
                         "pre-flight a request against the fleet runner's klt with --smoke")
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
        print("ERROR: breakdown_params.spice fails provenance checks; run design/breakdown/check_params.py",
              file=sys.stderr)
        return 3
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK + parameter file OK.")
        return 0

    by_n = {c.n: c for c in CHAR.CANDIDATES}
    if args.render:
        return render_only(pdk, by_n[int(args.candidates)], args.render, params, args.note)
    if args.smoke:
        n, bench, *pick = args.smoke.split(":")
        return smoke(pdk, by_n[int(n)], bench, params, pick or None)

    wanted = [int(x) for x in args.candidates.split(",") if x.strip()]
    benches = [b for b in args.benches.split(",") if b.strip()]
    if args.campaign:
        benches = list(CAMPAIGNS[args.campaign])
    unknown = [b for b in benches if b not in ALL_BENCHES]
    if unknown:
        print(f"ERROR: unknown bench(es) {unknown}", file=sys.stderr)
        return 2
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand = by_n[n]
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n} (Region {cand.region}) record {rid}")
        R.write_once(THIS_DIR / "corners" / rid / "run-provenance.json",
                     json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty}) + "\n")
        results: dict[str, BenchResult] = {}
        for bench in benches:
            bdir = THIS_DIR / "corners" / rid / bench
            bdir.mkdir(parents=True, exist_ok=False)  # corners/<rid>/ itself exists (run-provenance.json)
            body, ms = build_body(bench, pdk, cand, defaults, bdir, FLEET_PDK_VARIANT_DIR, params)
            R.write_once(bdir / "body.spice", body)
            req = make_request(bench, cand, pdk, ms, params)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
            if report is not None:
                R.write_once(bdir / "report.json", json.dumps(report, indent=2) + "\n")
            res = collect(bench, report, err, bdir, cand, params)
            if res.error:
                R.write_once(bdir / "submit-error.txt", res.error + "\n")
            results[bench] = res
            job = (res.remote or {}).get("job_id") if res.remote else None
            print(f"   {bench}: {res.status} ({len(res.corner_status)} corners, {time.time()-t0:.0f}s, job {job})"
                  + (f" ERROR {res.error[:300]}" if res.error else ""))
            if res.status not in ("pass", "pass_partial"):
                rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", snapshot(cand))
        R.write_once(THIS_DIR / "records" / f"{rid}.md",
                     render_any(pdk, cand, rid, results, params, dirty, args.note))
        print(f"   record: records/{rid}.md")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
