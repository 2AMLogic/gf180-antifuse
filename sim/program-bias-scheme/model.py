#!/usr/bin/env python3
"""sim/program-bias-scheme model.py -- the experiment's shared library.

Bench and drive constants (the legacy PL-driven benches, the Candidate 3
gate/well-drive schemes), the SPICE deck-body and ``klt sim`` request
builders, and the saved-report loaders (collect / fill / load_saved),
everything reusing sim/cell-breakdown-model as a library so the stimulus
levels, the 45-corner grid and the assumed breakdown parameters are
identical by construction. The CLI entry point is run_experiment.py, which
loads this module (and render.py) via harness.modload and re-exports this
surface, so consumers keep loading run_experiment.py as the library.
render.py imports one-way from this module; nothing here imports render.py
or the CLI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
CB_DIR = SIM_DIR / "cell-breakdown-model"

sys.path.insert(0, str(SIM_DIR))
from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402

# sim/cell-breakdown-model's CLI facade, loaded under the fixed unique name
# every downstream driver of it in sim/ uses (never a bare `import`, which
# under python3 -I has no script dir on sys.path and would collide in
# sys.modules between experiments).
CB = load_module(CB_DIR / "run_experiment.py", "sim_cb_lib")
CHAR = CB.CHAR

# Existing BL-driven fleet records (cell-breakdown-model, C-infinity edges,
# "progc" = BL-driven program leg), per candidate.
EXISTING_PROGC = {1: "20261014-001717-86afd07", 2: "20261014-001720-86afd07", 3: "20261014-001723-86afd07"}

LEGACY_BENCHES = ("plb_st", "plb_b1m", "plb_b1l", "plu_st")
# Candidate 3 gate/well-drive benches (#129): the PL-driven leg of `plb`, with the access device's
# gate (WL) and n-well tie (VB) levels set per scheme instead of the #62 "on" bias. Static levels
# [V], Candidate 3 only (PMOS access, rating 6 V); the pulse is the same signed PL level.
GWD_DRIVE = {
    "gwa": {"wl": -3.3, "vb": 0.0, "desc": "WL -3.3 V (the #62 on level), n-well tie lowered from +3.3 V to 0 V (the BL return level)"},
    "gwb": {"wl": -6.0, "vb": 0.0, "desc": "WL -6.0 V (stronger gate drive), n-well tie 0 V (the BL return level)"},
}
GWD_VARIANTS = ("st", "b1m", "b1l")
GWD_BENCHES = tuple(f"{s}_{v}" for s in GWD_DRIVE for v in GWD_VARIANTS)
BENCHES = LEGACY_BENCHES + GWD_BENCHES
BENCH_DESC = {
    "plb_st": "PL-driven through ballast, selected cell, stock cell (no breakdown element)",
    "plb_b1m": "PL-driven through ballast, selected cell, element enabled, median quantile (ubd=0.5)",
    "plb_b1l": f"PL-driven through ballast, selected cell, element enabled, low quantile (ubd={CB.UBD_LOW})",
    "plu_st": "PL pulse on an UNSELECTED stock cell (WL at OFF level, BL = 0 V, CN floating)",
}
_VAR_DESC = {"st": "stock cell (no breakdown element)", "b1m": "element enabled, median quantile (ubd=0.5)",
             "b1l": f"element enabled, low quantile (ubd={CB.UBD_LOW})"}
for _s, _d in GWD_DRIVE.items():
    for _v in GWD_VARIANTS:
        BENCH_DESC[f"{_s}_{_v}"] = f"gate/well drive `{_s}` ({_d['desc']}), {_VAR_DESC[_v]}"
ACCESS_PAIRS = CB.ACCESS_PAIRS
PAIR_LABEL = {k: f"{k}: {CB.TERMINAL_PAIRS[k][0].upper()}-{CB.TERMINAL_PAIRS[k][1].upper()}" for k in CB.TERMINAL_PAIRS}
TRIGC_KEY = "trigc_st"   # corner-id/level convention shared with the PL-driven #74 benches


def off_level(cand) -> float:
    """WL level that holds the access device OFF with BL = 0 V: the bulk
    level (0 V for the NMOS candidates, the n-well tie for the PMOS one)."""
    return cand.vb


# ---------------------------------------------------------------------------
# Deck bodies
# ---------------------------------------------------------------------------


C_PL_SHUNT = 100e-15   # PLACEHOLDER plate-line shunt capacitance [F]


def body_pl(pdk, cand, defaults, body_dir: Path, lib_root: str, bench: str, params: dict):
    scheme, var = bench.split("_", 1)
    out = [CB.body_header(pdk, body_dir, f"Candidate {cand.n} {bench} (tran, #90)", cand, "trigger", lib_root)]
    out.append(f".param t1={CB.fmt(CB.TRIG_T1)} tr={CB.fmt(CB.TRIG_TR)} tw={CB.fmt(CB.TRIG_TW)}")
    out += CB.edge_lines("cinf")
    out.append("VAMP AMP 0 DC 0")                      # klt's supply axis sets this (signed level)
    out.append("BVPP VPP 0 V = 'v(amp)*v(sh)'")
    out.append(f"RBAL VPP PLM {CB.fmt(CB.prog_rballast(cand, params))}")
    out.append("VPLM PLM PL DC 0")                     # ammeter: program (return-side) current
    out.append("VBL BL 0 DC 0")                        # bit line at the 0 V return, through an ammeter
    if scheme in GWD_DRIVE:
        if cand.n != 3:
            raise ValueError(f"bench {bench} is defined for Candidate 3 only")
        wl, vb = GWD_DRIVE[scheme]["wl"], GWD_DRIVE[scheme]["vb"]
    else:
        wl = cand.moscap_wl_on if scheme == "plb" else off_level(cand)
        vb = cand.vb
    out.append(f"VWL WL 0 DC {CB.fmt(wl)}")
    out.append(f"VVB VB 0 DC {CB.fmt(vb)}")
    # Plate-line (pad / routing) shunt capacitance. Without it the ballasted PL node is a
    # high-impedance node that stalls the `uic` start of the moscap macro (timestep collapse at
    # -40 C and at the slow corner on the fleet; found in #90). 100 fF is a PLACEHOLDER.
    out.append(f"CPL PL 0 {CB.fmt(C_PL_SHUNT)}")
    geo = CB.geometry(cand, defaults, "min", "min")
    out.append(f"XDUT BL WL PL VB {CB.conv_dut(cand, var, geo)}")
    cn = CB.conv_cn(var)
    node = {"cn": cn, "pl": "pl", "wl": "wl", "bl": "bl", "vb": "vb"}
    ms: list[dict] = []
    for k, (p, n, _) in CB.TERMINAL_PAIRS.items():
        out.append(f"BD{k.upper()} D{k.upper()} 0 V = 'v({node[p]})-v({node[n]})'")
        ms.append({"name": f"mx_{k}", "spice": f".meas tran mx_{k} MAX v(d{k})", "unit": "V"})
        ms.append({"name": f"mn_{k}", "spice": f".meas tran mn_{k} MIN v(d{k})", "unit": "V"})
    ms.append(CB.meas("tran", "vox_mid", "v(dox)", CB.TRIG_TMID, "V"))
    ms.append(CB.meas("tran", "vcn_mid", f"v({cn})", CB.TRIG_TMID, "V"))
    ms.append(CB.meas("tran", "vcn_end", f"v({cn})", CB.TRIG_TMEAS, "V"))
    ms.append(CB.meas("tran", "ipl_mid", "i(vplm)", CB.TRIG_TMID, "A"))
    ms.append({"name": "ipl_mx", "spice": ".meas tran ipl_mx MAX i(vplm)", "unit": "A"})
    ms.append({"name": "ipl_mn", "spice": ".meas tran ipl_mn MIN i(vplm)", "unit": "A"})
    if var.startswith("b1"):
        ms.append(CB.meas("tran", "st", "v(xdut.xbd.st)", CB.TRIG_TMEAS, "1"))
        ms.append(CB.meas("tran", "st_mid", "v(xdut.xbd.st)", CB.TRIG_TMID, "1"))
    return "\n".join(out) + "\n", ms


def make_request(bench: str, cand, pdk, ms: list[dict], params: dict) -> dict:
    # the PL-driven #74 request (signed level on VAMP, 45 corners, tran uic)
    req = CB.make_request(TRIGC_KEY, cand, pdk, ms, params)
    return req


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def collect(bench: str, report: dict | None, err: str, bdir: Path, cand, params: dict):
    if report is None or "corners" not in report:
        msg = err if report is None or "error" not in report else json.dumps(report["error"])
        return CB.BenchResult(bench=bench, status="submit-error", remote=None, error=msg)
    env = report.get("environment", {})
    res = CB.BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"), klt_env=env)
    fill(res, report, bdir, cand, params, write=True)
    return res


def fill(res, report: dict, bdir: Path, cand, params: dict, write: bool) -> None:
    for c in report["corners"]:
        cid = CB.corner_key(TRIGC_KEY, c, cand, params)
        res.corner_status[cid] = c["status"]
        res.values[cid] = {m["name"].lower(): m["value"] for m in c["measurements"]}
        if write:
            art = c.get("artifacts") or {}
            for kind, suffix in (("log", ".log"), ("deck", ".cir")):
                src = art.get(kind)
                if src and Path(src).is_file():
                    R.write_once(bdir / f"{cid}{suffix}", Path(src).read_text(errors="replace"))
        log = bdir / f"{cid}.log"
        res.outcome[cid] = CB.classify_failure(c["status"], c.get("diagnostics") or [],
                                               log.read_text(errors="replace") if log.is_file() else None,
                                               res.values[cid])


def load_saved(cand, rid: str, params: dict, base_dir: Path | None = None) -> dict:
    out = {}
    base = Path(base_dir) if base_dir is not None else THIS_DIR / "corners" / rid
    for bench in BENCHES:
        bdir = base / bench
        if (bdir / "report.json").is_file():
            report = json.loads((bdir / "report.json").read_text())
            env = report.get("environment", {})
            res = CB.BenchResult(bench=bench, status=report.get("status", "?"), remote=env.get("remote"),
                                 klt_env=env)
            fill(res, report, bdir, cand, params, write=False)
            out[bench] = res
        elif (bdir / "submit-error.txt").is_file():
            out[bench] = CB.BenchResult(bench=bench, status="submit-error", remote=None,
                                        error=(bdir / "submit-error.txt").read_text())
    return out
