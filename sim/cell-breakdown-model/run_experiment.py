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

    python3 sim/run_corners.py cell-breakdown-model
    python3 sim/cell-breakdown-model/run_experiment.py --candidates 1

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
import random
import re
import shutil
import subprocess
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
CAP_REFUSAL = "BATCH_MAX_CONCURRENT_INSTANCES"
CAP_RETRY_BUDGET_S, CAP_RETRY_BASE_S, CAP_RETRY_MAX_S = 5400, 60, 600
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
    req["analysis"] = {
        "access_op": {"kind": "dc", "args": DC_ARGS},
        "access_ac": {"kind": "ac", "args": f"lin 3 {fmt(F_RON / 2)} {fmt(F_RON * 1.5)}"},
        "cap_op": {"kind": "dc", "args": DC_ARGS},
        "cap_ac": {"kind": "ac", "args": f"lin 3 {fmt(F_CV / 2)} {fmt(F_CV * 1.5)}"},
        "trigger": {"kind": "tran", "args": f"{fmt(TRIG_TSTEP)} {fmt(TRIG_TSTOP)}"},
    }[bench]
    return req


BENCHES = ("access_op", "access_ac", "cap_op", "cap_ac", "trigger")


def build_body(bench: str, pdk, cand, defaults, body_dir: Path, lib_root: str) -> tuple[str, list[dict]]:
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
    # --outdir must be ABSOLUTE: klt runs ngspice with cwd set to the corner
    # directory but passes it deck/log paths relative to the invocation
    # directory, so a relative --outdir makes every corner fail to start
    # (2AMLogic/klayout-tools#2892).
    cmd = KLT_CMD + ["sim", str(req_path.resolve()), "-o", str(outdir.resolve()), "--format", "json"]
    if backend:
        cmd += ["--backend", backend]
    t0, delay, attempt = time.time(), CAP_RETRY_BASE_S, 0
    while True:
        attempt += 1
        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return json.loads(proc.stdout), proc.stderr
        except json.JSONDecodeError:
            err = f"exit {proc.returncode} (attempt {attempt})\nstdout:\n{proc.stdout[-4000:]}\nstderr:\n{proc.stderr[-4000:]}"
        if CAP_REFUSAL not in proc.stderr or time.time() - t0 + delay > CAP_RETRY_BUDGET_S:
            return None, err
        wait = delay * (0.5 + random.random() / 2)
        print(f"      fleet at its concurrency cap; retrying in {wait:.0f}s (attempt {attempt})", flush=True)
        time.sleep(wait)
        delay = min(delay * 2, CAP_RETRY_MAX_S)


def corner_key(bench: str, corner: dict, cand, params: dict) -> str:
    proc = corner["process"]
    temp = int(round(corner["temperature_c"]))
    sv = corner.get("supply_v") or {}
    if bench.startswith("access"):
        tok = C.fmt_node_supply("bl", sv["vbl"])
    elif bench == "trigger":
        inst = "a" if abs(sv.get("vampa", 0.0)) > 0 else "b"
        tok = C.fmt_node_supply(f"pl{inst}", sv[f"vamp{inst}"])
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
                  dirty: bool, stored_rid: str | None) -> str:
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
    prov = f"schematic (design/netlists/{cand.netlist} wrapped by design/breakdown/cell_candidates_bd.spice" + \
        (", dirty tree at run time)" if dirty else ")")
    a(f"- **Netlist provenance**: {prov}")
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
    for row in inertness(results):
        a(f"    - `{row['bench']}` {row['quantity']} [{row['variant']}]: {row['ok']}/{row['n']} within criterion, "
          f"{row['exact']}/{row['n']} exactly equal; worst relative difference {row['worst_rel']:.2e}"
          + (f" at `{row['worst_at']}`" if row["worst_at"] else ""))
    if stored_rid:
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
    a("  - **(b) Programmed-cell read current** (BL = read rail, WL fully on, PL = 0, state forced programmed; "
      "minimum over the 4 sub-configurations at each corner). `rf_med` = median filament, `rf_wc` = "
      "+bd_zrf_wc sigma filament. CONDITIONAL ON THE ASSUMED FILAMENT PARAMETERS:")
    a("")
    a("    | Corner | I_read (rf_med) [A] | I_read (rf_wc) [A] | worst sub-config | klt |")
    a("    |---|---|---|---|---|")
    rows = iread_table(results)
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
        a(f"    - against this run's unprogrammed-model `I_sneak_max` = {sci(h1['i_sneak_max'])} A (`{h1['fh']}`, "
          "gmin-floor upper bound): the `I_sneak_max < I_ref < I_prog_min` window spans a factor of "
          f"**{glob['wc_min'] / h1['i_sneak_max']:.3g}** (worst-corner I_prog_min). This sizes nothing -- it is "
          "conditional on the assumed filament distribution and the placeholder read/WL biases.")
    tr = results.get("trigger")
    if tr and tr.values:
        lv = trigger_levels(cand, params)
        a("  - **(c) Trigger/latch** -- PL stressed with a raised-cosine pulse "
          f"({TRIG_TW*1e6:g} us flat, {TRIG_TR*1e9:g} ns edges) with the access device on and BL = 0; state "
          f"`st` and damage `D` read at {TRIG_TMEAS*1e6:g} us, i.e. after the pulse has ended (a latched state "
          "must still read 1). Instance a: median Weibull quantile; instance b: ubd = "
          f"{UBD_LOW}. Model-mechanism check only, NOT a program-path claim:")
        a("")
        a("    | Corner | V(PL) [V] | inst | st | D | V(CN,PL) mid-pulse [V] | klt |")
        a("    |---|---|---|---|---|---|---|")
        for cid in sorted(tr.values):
            vals = tr.values[cid]
            inst = "a" if "_pla" in cid else "b"
            vpl = cid.rsplit("_", 1)[1][3:-1].replace("p", ".")  # pla8p00v -> 8.00
            a(f"    | `{cid}` | {vpl} | {inst} | {sci(vals.get(f'st_{inst}'))} | {sci(vals.get(f'dmg_{inst}'))} "
              f"| {vox(vals, inst)} | {tr.corner_status.get(cid)} |")
        a("")
        a(f"    Stress points: rated voltage {abs(lv[0]):.2f} V, then "
          + ", ".join(f"{f:g} x V_bd" for f in TRIG_FRACTIONS) + f" (V_bd = {vbd_ref(cand, params):.2f} V).")
    a("- **Links**:")
    a(f"  - Model: `design/breakdown/` (element, wrappers, parameters, `check_params.py`)")
    a(f"  - Netlist snapshot: `sim/cell-breakdown-model/netlist-snapshots/{rid}.spice`")
    a(f"  - Requests, generated bodies, klt reports, per-corner decks and logs: `sim/cell-breakdown-model/corners/{rid}/<bench>/`")
    a(f"  - Regression reference: `sim/cell-device-characterization/records/{stored_rid}.md`")
    a(f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (submit host); fleet-side engine/model hashes in each `report.json` `environment`")
    a(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    a("- **Supersedes**: (none -- first record for this claim/region)")
    a("")
    return "\n".join(L)


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


def smoke(pdk, cand, bench: str, params: dict) -> int:
    """ONE corner of ONE bench, locally -- a debug probe, not evidence."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}-{bench}"
    work.mkdir(parents=True)
    body, ms = build_body(bench, pdk, cand, defaults, work, str(pdk.variant_dir))
    (work / "body.spice").write_text(body)
    req = make_request(bench, cand, pdk, ms, params)
    corners = req["corners"]
    corners["process"] = corners["process"][:1]
    corners["temperature_c"] = [27.0]
    if "supply_v" in corners:
        k = len(next(iter(corners["supply_v"].values())))
        idx = k - 2 if bench == "trigger" else k // 2   # trigger: inst b at 1.0 x V_bd; else nominal
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
    for k in list(derived)[:8]:
        print(f"   {k} = {derived[k]}")
    for d in c["diagnostics"][:3]:
        print(f"   diag: {d}")
    return 0 if c["status"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=",".join(BENCHES))
    ap.add_argument("--smoke", default=None, metavar="N:BENCH",
                    help="run ONE corner of ONE bench locally (debug probe; writes no record)")
    ap.add_argument("--check-env", action="store_true")
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
    if args.smoke:
        n, bench = args.smoke.split(":")
        return smoke(pdk, by_n[int(n)], bench, params)

    wanted = [int(x) for x in args.candidates.split(",") if x.strip()]
    benches = [b for b in args.benches.split(",") if b.strip()]
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand = by_n[n]
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n} (Region {cand.region}) record {rid}")
        results: dict[str, BenchResult] = {}
        for bench in benches:
            bdir = THIS_DIR / "corners" / rid / bench
            bdir.mkdir(parents=True, exist_ok=False)
            body, ms = build_body(bench, pdk, cand, defaults, bdir, FLEET_PDK_VARIANT_DIR)
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
                     render_record(pdk, cand, rid, results, params, dirty, stored_record_id(cand)))
        print(f"   record: records/{rid}.md")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
