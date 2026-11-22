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
        + (f"* V_bd sensitivity point (issue #130): per-candidate override of the shared bd_ebd\n"
           f".param bd_ebd = {VBD_EBD_OVERRIDE:.9g}\n" if VBD_EBD_OVERRIDE is not None else "")
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


def body_bias(pdk, cand, defaults, body_dir: Path, lib_root: str,
              scenarios: tuple[ReadBias, ...] = BIAS_SCENARIOS) -> tuple[str, list[dict]]:
    """bias_op (Candidate 3 only): per scenario and per access-sizing x
    capacitor-geometry sub-configuration, at the swept corner:
      off_*  unprogrammed cell, WL at an OFF level           -> I_off
      offp_* PROGRAMMED cell (median filament), WL at an OFF level -> I_off,prog
      un_*   unprogrammed cell, WL at the scenario ON level  -> selected-unprogrammed current
      pm_*/pw_*  programmed cell (median / worst filament), WL at ON -> I_read
    plus the selected-device terminal voltages (CN, BL rail, VB) of pm/pw."""
    if cand.n != 3:
        raise ValueError("bias_op is the Candidate 3 read-bias study (#75)")
    lo, mid, hi = CHAR.off_levels(cand)
    out = [body_header(pdk, body_dir, "Candidate 3 read-bias bench (bias_op)", cand, "bias_op", lib_root)]
    out.append(f"VBL BL 0 DC {fmt(CHAR.V_READ_NOM)}")
    out.append("VPL PL 0 DC 0")
    out.append("VDMY DMY 0 DC 0")
    out += [f"VWLLO WLLO 0 DC {fmt(lo)}", f"VWLMID WLMID 0 DC {fmt(mid)}", f"VWLHI WLHI 0 DC {fmt(hi)}"]
    ms: list[dict] = []
    for sc in scenarios:
        n = sc.name
        out.append(f"EBL_{n} BLS_{n} 0 BL 0 {fmt(sc.rail_scale)}")
        if sc.vb_mode == "fixed":
            out.append(f"VVB_{n} VB_{n} 0 DC {fmt(sc.vb_v)}")
        elif sc.vb_mode == "track":
            out.append(f"BVB_{n} VB_{n} 0 V = 'v(bls_{n}) + {fmt(sc.vb_v)}'")
        else:
            raise ValueError(sc.vb_mode)
        out.append(f"VWLON_{n} WLON_{n} 0 DC {fmt(sc.wl_on)}")
        ms.append(meas("dc", f"vbl_{n}", f"v(bls_{n})", DC_AT, "V"))
        ms.append(meas("dc", f"vvb_{n}", f"v(vb_{n})", DC_AT, "V"))
        for s_ in CHAR.SIZING_LEVELS:
            for g in CHAR.GEOM_LEVELS:
                geo = geometry(cand, defaults, s_, g)
                sg = sg_tag(s_, g)
                for b, wl in zip(BIAS_TAGS, ("WLLO", "WLMID", "WLHI")):
                    t = f"off_{n}_{sg}_{b}"
                    out.append(f"VM_{t} BLS_{n} B_{t} 0")
                    out.append(f"X_{t} B_{t} {wl} PL VB_{n} {dut(cand, 'b1', geo)}")
                    ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
                for b, wl in zip(BIAS_TAGS, ("WLLO", "WLMID", "WLHI")):
                    # the same OFF levels with the cell PROGRAMMED (CN pulled to PL by the
                    # filament): the unselected-programmed-cell leakage, the worst sneak case
                    t = f"offp_{n}_{sg}_{b}"
                    out.append(f"VM_{t} BLS_{n} B_{t} 0")
                    out.append(f"X_{t} B_{t} {wl} PL VB_{n} {dut(cand, 'pm', geo)}")
                    ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
                for v, kind in (("b1", "un"), ("pm", "pm"), ("pw", "pw")):
                    t = f"{kind}_{n}_{sg}"
                    out.append(f"VM_{t} BLS_{n} B_{t} 0")
                    out.append(f"X_{t} B_{t} WLON_{n} PL VB_{n} {dut(cand, v, geo)}")
                    ms.append(meas("dc", f"i_{t}", f"i(vm_{t})", DC_AT, "A"))
                    if kind in ("pm", "pw"):
                        ms.append(meas("dc", f"vcn_{t}", f"v(x_{t}.xc.cn)", DC_AT, "V"))
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
    if bench.startswith("access") or bench == BIAS_BENCH:
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
        BIAS_BENCH: {"kind": "dc", "args": DC_ARGS},
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


BENCHES = ("access_op", "access_ac", "cap_op", "cap_ac", "trigger")   # the #62 benches (default run)
ALL_BENCHES = BENCHES + CONV_BENCHES + (OPSTART_BENCH, BIAS_BENCH)


def build_body(bench: str, pdk, cand, defaults, body_dir: Path, lib_root: str,
               params: dict | None = None) -> tuple[str, list[dict]]:
    if bench == BIAS_BENCH:
        return body_bias(pdk, cand, defaults, body_dir, lib_root)
    if bench in CONV_BENCHES or bench == OPSTART_BENCH:
        assert params is not None
        return body_conv(pdk, cand, defaults, body_dir, lib_root,
                         "trigc_st" if bench == OPSTART_BENCH else bench, params)
    if bench.startswith("access"):
        return body_access(pdk, cand, defaults, body_dir, bench, lib_root)
    if bench.startswith("cap"):
        return body_cap(pdk, cand, defaults, body_dir, bench, lib_root)
    return body_trigger(pdk, cand, defaults, body_dir, lib_root)


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


def snapshot(cand) -> str:
    parts = []
    for p in (REPO_ROOT / "design" / "netlists" / cand.netlist, WRAPPERS,
              BD_DIR / "af_breakdown.spice", BD_DIR / "breakdown_params.spice"):
        parts.append(f"* ===== {p.relative_to(REPO_ROOT)} =====\n{p.read_text()}")
    return "\n".join(parts)


def results_from_reports(cand, rid: str, params: dict, benches=None,
                         base_dir: Path | None = None) -> dict[str, BenchResult]:
    results: dict[str, BenchResult] = {}
    base = Path(base_dir) if base_dir is not None else THIS_DIR / "corners" / rid
    for bench in benches or ALL_BENCHES:
        bdir = base / bench
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
