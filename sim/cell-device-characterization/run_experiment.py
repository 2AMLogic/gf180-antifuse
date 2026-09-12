#!/usr/bin/env python3
"""sim/cell-device-characterization -- the cold-start command.

Measures, per cell candidate (spec/cell-candidates.md), per PVT corner, at
both access-device sizing levels and both capacitor-geometry levels
(spec/split-axis-plan.md Sections 2-3, using this open_pdks revision's
model-file minimums as "values used" -- NOT the ratified split-axis
levels, see this directory's README):

  1. access-device OFF-state leakage I_off (spec/architecture.md Section 3
     item 2)
  2. access-device ON-state series resistance R_on (Section 4's slow/cold
     corner term)
  3. pre-breakdown capacitor C-V and leakage (Section 3 item 2's
     unprogrammed-cell current floor)

and derives, per candidate (= per spec/split-axis-plan.md region), the two
bounds spec/architecture.md Section 4 needs:

  - I_sneak_max = 31 x I_off at the fast/hot/high-supply corner
  - selected-cell R_on at the slow/cold/low-supply corner

stated as the I_ref > I_sneak_max lower bound only, per this issue's scope.

Usage:

    python3 sim/run_corners.py cell-device-characterization
    # equivalently, from this directory:
    python3 sim/cell-device-characterization/run_experiment.py

stdlib only, no venv. Needs PDK_ROOT (or GF180_PDK_PATH) set to a gf180mcu
install and ngspice on PATH -- see sim/README.md and this directory's
README for the full convention and methodology writeup.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

TB_ACCESS_TEMPLATE = (THIS_DIR / "testbench" / "tb_access_device.spice").read_text()
TB_MOSCAP_TEMPLATE = (THIS_DIR / "testbench" / "tb_moscap_cv.spice").read_text()
sys.path.insert(0, str(SIM_DIR))

from harness import corners as C  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402
from harness import runner as RUN  # noqa: E402

N_GRID = 32  # spec/split-axis-plan.md, ratified 2026-08-20
GMIN = 1e-13  # see README "Methodology note: gmin-floor-limited leakage"
V_READ_NOM = 1.0  # placeholder read-voltage rail -- not a ratified spec
                   # number (none exists yet); see README
SUPPLY_TOL = 0.10
WL_LOGIC_VDD = 3.3  # placeholder logic-rail level for the OFF-bias sweep


@dataclass(frozen=True)
class Candidate:
    n: int
    region: str
    netlist: str
    subckt: str
    access_model: str
    polarity: str  # "n" or "p"
    cap_model: str
    cap_rated_v: float
    extra_mos_libs: tuple[str, ...]  # additional .lib files needing the MOS corner
    wl_on: float  # WL "fully on" bias against BL=vread, matching
                  # design/tb/tb_cell_candidateN.spice's own convention
    moscap_wl_on: float  # WL "fully on" bias against tb_moscap_cv.spice's
                          # fixed BL=0 -- NOT always equal to wl_on: an
                          # access device's ON criterion is Vgs = V(WL) -
                          # V(source), and which terminal is the source
                          # differs by polarity (BL for Candidates 1/2's
                          # NMOS, the *other* terminal for Candidate 3's
                          # PMOS -- see design/README.md's source/drain
                          # assignment note), so "on" against a 0V BL is not
                          # the same WL value as "on" against a ~1V BL for
                          # every candidate. Confirmed during development by
                          # checking V(X1.CN) actually tracks V(BL): with
                          # wl_on reused unmodified for Candidate 3 here, WL
                          # (0V) - BL (0V) = 0V gate-source bias, leaving
                          # the PMOS access device barely conducting and
                          # X1.CN floating apart from BL instead.
    vb: float  # access-device bulk tie


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        n=1, region="I", netlist="cell_candidate1.spice", subckt="cell_candidate1",
        access_model="nfet_06v0", polarity="n", cap_model="cap_nmos_03v3",
        cap_rated_v=3.3, extra_mos_libs=(), wl_on=3.3, moscap_wl_on=3.3, vb=0.0,
    ),
    Candidate(
        n=2, region="II", netlist="cell_candidate2.spice", subckt="cell_candidate2",
        access_model="nfet_10v0_asym", polarity="n", cap_model="cap_nmos_06v0",
        cap_rated_v=6.0, extra_mos_libs=("smbb000149",), wl_on=5.0, moscap_wl_on=5.0, vb=0.0,
    ),
    Candidate(
        n=3, region="III", netlist="cell_candidate3.spice", subckt="cell_candidate3",
        access_model="pfet_06v0", polarity="p", cap_model="cap_pmos_03v3",
        cap_rated_v=3.3, extra_mos_libs=(), wl_on=0.0, moscap_wl_on=-3.3, vb=WL_LOGIC_VDD,
    ),
)

SIZING_LEVELS = ("min", "2x")   # access-device width multiplier
GEOM_LEVELS = ("min", "2x")     # capacitor width (-> area) multiplier

_SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}


def spice_num(token: str) -> float:
    """Parse a SPICE numeric literal with an optional unit suffix."""
    token = token.strip()
    m = re.match(r"^([0-9.eE+-]+)([a-zA-Z]*)$", token)
    if not m:
        raise ValueError(f"cannot parse SPICE numeric literal: {token!r}")
    mantissa, suffix = m.group(1), m.group(2).lower()
    value = float(mantissa)
    if suffix:
        if suffix not in _SUFFIX:
            raise ValueError(f"unknown SPICE unit suffix {suffix!r} in {token!r}")
        value *= _SUFFIX[suffix]
    return value


def parse_defaults(netlist_path: Path) -> dict[str, float]:
    """Pull wcap/lcap/wacc/lacc subcircuit-parameter defaults out of the
    committed netlist's `.subckt` line -- read, not hand-copied, so this
    never drifts from the actual committed geometry defaults."""
    text = netlist_path.read_text()
    m = re.search(
        r"\.subckt\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+"
        r"wcap=(?P<wcap>\S+)\s+lcap=(?P<lcap>\S+)\s+"
        r"wacc=(?P<wacc>\S+)\s+lacc=(?P<lacc>\S+)",
        text,
    )
    if not m:
        raise ValueError(f"could not find .subckt parameter defaults in {netlist_path}")
    return {k: spice_num(v) for k, v in m.groupdict().items()}


def fmt(value: float) -> str:
    return f"{value:.6e}"


def off_levels(candidate: Candidate) -> tuple[float, float, float]:
    """3-point OFF-gate-bias sweep per this issue's scope: 0V, +-0.3V for
    NMOS access devices around the logic rail; VDD, VDD+-0.3V for PMOS."""
    if candidate.polarity == "n":
        return (-0.3, 0.0, 0.3)
    return (WL_LOGIC_VDD - 0.3, WL_LOGIC_VDD, WL_LOGIC_VDD + 0.3)


def cv_bias_points(candidate: Candidate) -> tuple[float, float, float, float, float]:
    v = candidate.cap_rated_v
    return (-v, -v / 2, 0.0, v / 2, v)


# ---------------------------------------------------------------------------
# Deck assembly
# ---------------------------------------------------------------------------


def gen_models(pdk: P.PDKPaths, candidate: Candidate, mos_corner: str, temp_c: int) -> str:
    # gmin is a fixed constant for this whole experiment (see GMIN's module
    # docstring / README methodology note) -- written as a literal here
    # rather than routed through `.param`, since ngspice's `.options` card
    # does not reliably substitute a `.param`-declared name (confirmed
    # during development: it silently keeps the default gmin and reports
    # spurious "no such vector" errors after the .control block instead).
    lines = [f".include {pdk.design_ngspice}", f".lib {pdk.sm141064} {mos_corner}"]
    for extra in candidate.extra_mos_libs:
        extra_path = pdk.smbb000149 if extra == "smbb000149" else None
        if extra_path is None:
            raise ValueError(f"unknown extra MOS lib file: {extra}")
        lines.append(f".lib {extra_path} {mos_corner}")
    lines.append(f".lib {pdk.sm141064} moscap_typical")
    lines.append(f".temp {temp_c}")
    lines.append(f".options gmin={fmt(GMIN)}")
    return "\n".join(lines) + "\n"


def gen_models_moscap(pdk: P.PDKPaths, candidate: Candidate, moscap_corner: str, temp_c: int) -> str:
    # The cell subckt's access device still needs its MOS model resolved
    # here even though this bench isn't sweeping the MOS corner (it holds
    # WL fully ON and measures the capacitor branch only) -- fixed at
    # `typical` for every point, documented in the README.
    lines = [f".include {pdk.design_ngspice}", f".lib {pdk.sm141064} typical"]
    for extra in candidate.extra_mos_libs:
        extra_path = pdk.smbb000149 if extra == "smbb000149" else None
        if extra_path is None:
            raise ValueError(f"unknown extra MOS lib file: {extra}")
        lines.append(f".lib {extra_path} typical")
    lines.append(f".lib {pdk.sm141064} {moscap_corner}")
    lines.append(f".temp {temp_c}")
    lines.append(f".options gmin={fmt(GMIN)}")
    return "\n".join(lines) + "\n"


def gen_instantiate(candidate: Candidate, wcap: float, lcap: float, wacc: float, lacc: float) -> str:
    """The DUT instantiation only -- VBL/VWL/VPL are each testbench's own job
    (see testbench/*.spice), since what each of those sources does (fixed
    vs. swept, AC or not) differs between the two benches."""
    netlist_path = REPO_ROOT / "design" / "netlists" / candidate.netlist
    return (
        f".include {netlist_path}\n"
        f"X1 BL WL PL VB {candidate.subckt} "
        f"wcap={fmt(wcap)} lcap={fmt(lcap)} wacc={fmt(wacc)} lacc={fmt(lacc)}\n"
        f"VVB VB 0 DC {fmt(candidate.vb)}\n"
    )


def render_template(template_text: str, substitutions: dict[str, float]) -> str:
    """Replace @TOKEN@ placeholders with literal numeric values.

    Literal substitution, not ngspice `.param` + `alter`: `alter <element> =
    <param-name>` was confirmed during development to silently fail (keeps
    the prior value, then reports a spurious "no such vector <param-name>"
    after the run) where `alter <element> = <literal>` works correctly. See
    testbench/tb_access_device.spice's header.
    """
    text = template_text
    for name, value in substitutions.items():
        token = f"@{name}@"
        if token not in text:
            raise ValueError(f"template does not use placeholder {token}")
        text = text.replace(token, fmt(value))
    return text


def access_substitutions(candidate: Candidate, vread: float) -> dict[str, float]:
    lo, mid, hi = off_levels(candidate)
    return {"VREAD": vread, "VOFF_LO": lo, "VOFF_MID": mid, "VOFF_HI": hi, "VON": candidate.wl_on}


def moscap_substitutions(candidate: Candidate) -> dict[str, float]:
    b1, b2, b3, b4, b5 = cv_bias_points(candidate)
    # PL is the swept terminal (see tb_moscap_cv.spice's header for why):
    # V(CN)-V(PL) ~= V(BL)-V(PL) = 0 - V(PL), so V(PL) = -bias to hit `bias`.
    return {
        "VON": candidate.moscap_wl_on,
        "VPL_1": -b1, "VPL_2": -b2, "VPL_3": -b3, "VPL_4": -b4, "VPL_5": -b5,
    }


# ---------------------------------------------------------------------------
# Measurement parsing
# ---------------------------------------------------------------------------


def parse_scalar(output: str, name: str) -> float | None:
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*([0-9eE.+-]+)\s*$", output, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


@dataclass
class AccessResult:
    sizing: str
    geometry: str
    mos_corner: str
    temp_c: int
    supply_mult: float
    vread: float
    ioff_lo: float | None
    ioff_mid: float | None
    ioff_hi: float | None
    ron: float | None
    ok: bool


@dataclass
class CapResult:
    sizing: str
    geometry: str
    moscap_corner: str
    temp_c: int
    ilk: list[float | None]
    cval: list[float | None]
    ok: bool


@dataclass
class CandidateRun:
    candidate: Candidate
    record_id: str
    access_results: list[AccessResult] = field(default_factory=list)
    cap_results: list[CapResult] = field(default_factory=list)
    n_ngspice_runs: int = 0
    n_failed: int = 0


def sizing_multiplier(level: str) -> float:
    return 1.0 if level == "min" else 2.0


# ---------------------------------------------------------------------------
# One work item = one ngspice invocation writing one raw log
# ---------------------------------------------------------------------------


def run_access_corner(pdk: P.PDKPaths, candidate: Candidate, defaults: dict, sizing: str,
                       geometry: str, mos_corner: str, temp_c: int, supply_mult: float,
                       log_path: Path) -> AccessResult:
    wacc = defaults["wacc"] * sizing_multiplier(sizing)
    wcap = defaults["wcap"] * sizing_multiplier(geometry)
    vread = V_READ_NOM * supply_mult

    scratch = log_path.parent / ".work" / log_path.stem
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "models.spice").write_text(gen_models(pdk, candidate, mos_corner, temp_c))
    (scratch / "instantiate.spice").write_text(
        gen_instantiate(candidate, wcap, defaults["lcap"], wacc, defaults["lacc"])
    )
    tb_rendered = render_template(TB_ACCESS_TEMPLATE, access_substitutions(candidate, vread))
    (scratch / "tb.spice").write_text(tb_rendered)
    deck = scratch / "deck.spice"
    deck.write_text(".include models.spice\n.include instantiate.spice\n.include tb.spice\n")

    result = RUN.run_deck(deck, cwd=scratch)
    R.append_log(log_path, result.output)

    ioff_lo = parse_scalar(result.output, "ioff_lo")
    ioff_mid = parse_scalar(result.output, "ioff_mid")
    ioff_hi = parse_scalar(result.output, "ioff_hi")
    ron = parse_scalar(result.output, "ron")
    # A corner is "ok" when every expected scalar parsed to a real number.
    # Not gated on NgspiceRun.ok, which flags on any "error"/"fatal"
    # substring -- more conservative than needed here, since the ground
    # truth is whether the expected measurements actually printed.
    ok = None not in (ioff_lo, ioff_mid, ioff_hi, ron)

    return AccessResult(
        sizing=sizing, geometry=geometry, mos_corner=mos_corner, temp_c=temp_c,
        supply_mult=supply_mult, vread=vread, ioff_lo=ioff_lo, ioff_mid=ioff_mid,
        ioff_hi=ioff_hi, ron=ron, ok=ok,
    )


def run_cap_corner(pdk: P.PDKPaths, candidate: Candidate, defaults: dict, sizing: str,
                    geometry: str, moscap_corner: str, temp_c: int, log_path: Path) -> CapResult:
    wacc = defaults["wacc"] * sizing_multiplier(sizing)
    wcap = defaults["wcap"] * sizing_multiplier(geometry)

    scratch = log_path.parent / ".work" / log_path.stem
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "models.spice").write_text(gen_models_moscap(pdk, candidate, moscap_corner, temp_c))
    (scratch / "instantiate.spice").write_text(
        gen_instantiate(candidate, wcap, defaults["lcap"], wacc, defaults["lacc"])
    )
    tb_rendered = render_template(TB_MOSCAP_TEMPLATE, moscap_substitutions(candidate))
    (scratch / "tb.spice").write_text(tb_rendered)
    deck = scratch / "deck.spice"
    deck.write_text(".include models.spice\n.include instantiate.spice\n.include tb.spice\n")

    result = RUN.run_deck(deck, cwd=scratch)
    R.append_log(log_path, result.output)

    ilk = [parse_scalar(result.output, f"ilk_{i}") for i in range(1, 6)]
    cval = [parse_scalar(result.output, f"cval_{i}") for i in range(1, 6)]
    # See run_access_corner's comment: not gated on NgspiceRun.ok.
    ok = all(v is not None for v in ilk) and all(v is not None for v in cval)

    return CapResult(sizing=sizing, geometry=geometry, moscap_corner=moscap_corner,
                      temp_c=temp_c, ilk=ilk, cval=cval, ok=ok)


# ---------------------------------------------------------------------------
# Per-candidate orchestration
# ---------------------------------------------------------------------------


def run_candidate(pdk: P.PDKPaths, candidate: Candidate, experiment_dir: Path, workers: int) -> CandidateRun:
    defaults = parse_defaults(REPO_ROOT / "design" / "netlists" / candidate.netlist)
    record_id = R.allocate_record_id(experiment_dir, REPO_ROOT)
    corners_dir = experiment_dir / "corners" / record_id

    run = CandidateRun(candidate=candidate, record_id=record_id)

    jobs = []
    for sizing in SIZING_LEVELS:
        for geometry in GEOM_LEVELS:
            subdir = corners_dir / f"access-{sizing}_cap-{geometry}"
            for mos_corner in C.MOS_CORNERS:
                for temp_c in C.TEMPS_C:
                    for supply_mult in (1 - SUPPLY_TOL, 1.0, 1 + SUPPLY_TOL):
                        cid = C.corner_id(mos_corner, temp_c, C.fmt_node_supply("bl", V_READ_NOM * supply_mult))
                        log_path = subdir / f"{cid}.log"
                        jobs.append(("access", sizing, geometry, mos_corner, temp_c, supply_mult, log_path))
            for moscap_corner in C.MOSCAP_CORNERS:
                for temp_c in C.TEMPS_C:
                    cid = C.corner_id(moscap_corner, temp_c, "nosupply")
                    log_path = subdir / f"{cid}.log"
                    jobs.append(("cap", sizing, geometry, moscap_corner, temp_c, None, log_path))

    run.n_ngspice_runs = len(jobs)

    def do_job(job):
        kind, sizing, geometry, corner, temp_c, supply_mult, log_path = job
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "access":
            return "access", run_access_corner(pdk, candidate, defaults, sizing, geometry,
                                                corner, temp_c, supply_mult, log_path)
        return "cap", run_cap_corner(pdk, candidate, defaults, sizing, geometry, corner, temp_c, log_path)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(do_job, job) for job in jobs]
        for fut in as_completed(futures):
            kind, res = fut.result()
            if kind == "access":
                run.access_results.append(res)
            else:
                run.cap_results.append(res)
            if not res.ok:
                run.n_failed += 1

    # netlist snapshot: the frozen DUT this record measured.
    netlist_path = REPO_ROOT / "design" / "netlists" / candidate.netlist
    snapshot_path = experiment_dir / "netlist-snapshots" / f"{record_id}.spice"
    R.write_once(snapshot_path, netlist_path.read_text())

    return run


# ---------------------------------------------------------------------------
# Record writing
# ---------------------------------------------------------------------------


def derive_bounds(run: CandidateRun) -> dict:
    """I_sneak_max = 31 x I_off at fast/hot/high-supply; R_on at
    slow/cold/low-supply -- spec/architecture.md Section 4's two-sided
    corner, per this issue's scope."""
    fh_corner, fh_temp, fh_dv = C.FAST_HOT_HIGH
    sc_corner, sc_temp, sc_dv = C.SLOW_COLD_LOW
    fh_mult = 1.0 + fh_dv
    sc_mult = 1.0 + sc_dv

    fast_hot = [r for r in run.access_results
                if r.mos_corner == fh_corner and r.temp_c == fh_temp
                and abs(r.supply_mult - fh_mult) < 1e-9 and r.ok]
    slow_cold = [r for r in run.access_results
                 if r.mos_corner == sc_corner and r.temp_c == sc_temp
                 and abs(r.supply_mult - sc_mult) < 1e-9 and r.ok]

    i_off_worst = max((max(r.ioff_lo, r.ioff_mid, r.ioff_hi) for r in fast_hot), default=None)
    r_on_worst = max((r.ron for r in slow_cold if r.ron is not None), default=None)

    return {
        "fast_hot_corner": f"{fh_corner}_{fh_temp}c_{C.fmt_node_supply('bl', V_READ_NOM * fh_mult)}",
        "slow_cold_corner": f"{sc_corner}_{sc_temp}c_{C.fmt_node_supply('bl', V_READ_NOM * sc_mult)}",
        "i_off_worst": i_off_worst,
        "i_sneak_max": None if i_off_worst is None else (N_GRID - 1) * i_off_worst,
        "r_on_worst": r_on_worst,
        "n_fast_hot_samples": len(fast_hot),
        "n_slow_cold_samples": len(slow_cold),
    }


def sci(x: float | None) -> str:
    if x is None:
        return "N/A (corner not resolved -- see raw logs)"
    return f"{x:.4e}"


def render_record(pdk: P.PDKPaths, run: CandidateRun, dirty: bool, claim_extra: str = "") -> str:
    c = run.candidate
    bounds = derive_bounds(run)
    n_access = len(run.access_results)
    n_cap = len(run.cap_results)
    n_access_ok = sum(1 for r in run.access_results if r.ok)
    n_cap_ok = sum(1 for r in run.cap_results if r.ok)

    provenance = "schematic (design/netlists/{}, dirty tree at run time)".format(c.netlist) \
        if dirty else "schematic (design/netlists/{})".format(c.netlist)

    lines = []
    lines.append(f"# Record {run.record_id}")
    lines.append("")
    lines.append(f"- **Record ID**: {run.record_id}")
    lines.append(
        "- **Claim**: `spec/architecture.md#3-sneak-path-analysis-partially-programmed-array` "
        "(the `I_sneak_max ~= (N-1) x I_off` \"required design input\") and "
        "`spec/architecture.md#4-sense-scheme` (the slow/cold access-device series-resistance "
        "term of the sense path's worst-case corner). Region "
        f"{c.region} / Candidate {c.n} (`spec/split-axis-plan.md`, `spec/cell-candidates.md`)."
        f"{claim_extra}"
    )
    lines.append(f"- **Netlist provenance**: {provenance}")
    lines.append("- **Corner matrix run**:")
    lines.append(f"  - Access-device MOS process: {', '.join(C.MOS_CORNERS)} (5 sections)")
    lines.append(f"  - Capacitor moscap process: {', '.join(C.MOSCAP_CORNERS)} (3 sections)")
    lines.append(f"  - Temperature: {', '.join(str(t) for t in C.TEMPS_C)} degC (3 points)")
    lines.append(
        f"  - Read-voltage rail (access-device bench only): {V_READ_NOM*0.9:.2f}V / "
        f"{V_READ_NOM:.2f}V / {V_READ_NOM*1.1:.2f}V (nominal +-{SUPPLY_TOL*100:.0f}%, named "
        "`bl<v>v` in the corner-id) -- 15 process/temp points x 3 supply points = 45 access-"
        "device corners per (sizing, geometry) sub-configuration"
    )
    lines.append(
        "  - Capacitor bench: `nosupply` (no external supply rail; the swept quantity is the "
        "capacitor's own gate-to-plate bias, an internal DC sweep across the rated voltage "
        "range, not a rail -- 9 corners per sub-configuration)"
    )
    lines.append(
        f"  - Access-device sizing: {', '.join(SIZING_LEVELS)} (x{sizing_multiplier('min'):.0f}, "
        f"x{sizing_multiplier('2x'):.0f} the committed netlist's default `wacc`)"
    )
    lines.append(
        f"  - Capacitor geometry: {', '.join(GEOM_LEVELS)} (x{sizing_multiplier('min'):.0f}, "
        f"x{sizing_multiplier('2x'):.0f} the committed netlist's default `wcap`, same `lcap` "
        "-- doubles area, matching `design/check-netlists.sh`'s convention)"
    )
    lines.append(
        "  - **These geometry/sizing values are the values used for this run (this open_pdks "
        "revision's netlist-default / model-file numbers), NOT the ratified split-axis levels** "
        "-- `spec/split-axis-plan.md` names \"process-minimum\" and \"2x-area\"/\"2x-width\" as "
        "its two levels, but no ratified spec document fixes what the process-minimum legal "
        "geometry actually is (`design/README.md`: that PDK design-rule lookup is deliberately "
        "out of scope for this repo's sources so far). See this experiment's README."
    )
    lines.append(
        f"  - Full grid: {run.n_ngspice_runs} raw logs "
        f"({n_access} access-device + {n_cap} capacitor), {run.n_ngspice_runs - run.n_failed} resolved"
    )
    lines.append("- **Result**:")
    lines.append(
        f"  - Access-device corners resolved: {n_access_ok}/{n_access}; capacitor corners "
        f"resolved: {n_cap_ok}/{n_cap} (a corner is \"resolved\" when ngspice converged and every "
        "expected measurement parsed; see raw logs under `corners/{}/` for any that did not)".format(run.record_id)
    )
    lines.append(
        "  - **I_off methodology note (gmin-floor-limited upper bound)**: the stock `cap_*` "
        "models carry no DC branch (`spec/cell-candidates.md`), so the cell's internal node has "
        "no DC path except the access device's own OFF-state conduction and its source/body "
        "junction -- both verified during development to sit below ngspice's default gmin at "
        f"deep cutoff for this device family. `gmin={GMIN:.0e}` S was used uniformly; every "
        "`I_off` figure below is therefore an upper bound set jointly by the true device leakage "
        "and this numerical floor, not a fully resolved subthreshold current. This is the "
        "conservative direction for `I_ref > I_sneak_max`: an overestimate of sneak leakage only "
        "makes the derived bound safer. See this experiment's README for the derivation and the "
        "gmin sweep that established this."
    )
    lines.append(
        f"  - **I_sneak_max = (N-1) x I_off = {N_GRID-1} x I_off, evaluated at the fast/hot/"
        f"high-supply corner `{bounds['fast_hot_corner']}`** ({bounds['n_fast_hot_samples']} "
        f"matching sub-configuration samples): worst-case I_off = {sci(bounds['i_off_worst'])} A "
        f"-> **I_sneak_max = {sci(bounds['i_sneak_max'])} A** (N=32 per `spec/split-axis-plan.md`, "
        "ratified 2026-08-20). Stated as the `I_ref > I_sneak_max` **lower bound only** -- the "
        "`I_ref < I_prog_min` upper bound stays open pending the breakdown-augmented model "
        "(`spec/cell-candidates.md`), out of this issue's scope."
    )
    lines.append(
        f"  - **Selected-cell R_on at the slow/cold/low-supply corner `{bounds['slow_cold_corner']}`** "
        f"({bounds['n_slow_cold_samples']} matching sub-configuration samples): "
        f"**R_on = {sci(bounds['r_on_worst'])} ohm** (worst case across the sizing/geometry grid "
        "at that corner). This is the series-resistance term `spec/architecture.md` Section 4's "
        "sense-path worst-case corner needs; it is not itself a pass/fail against a ratified "
        "threshold (none is ratified yet)."
    )
    lines.append("- **Links**:")
    lines.append(f"  - Testbenches: `sim/cell-device-characterization/testbench/tb_access_device.spice`, "
                  "`sim/cell-device-characterization/testbench/tb_moscap_cv.spice`")
    lines.append(f"  - Netlist snapshot: `sim/cell-device-characterization/netlist-snapshots/{run.record_id}.spice`")
    lines.append(f"  - Raw logs: `sim/cell-device-characterization/corners/{run.record_id}/`")
    lines.append(
        f"  - PDK: `{pdk.variant}`, open_pdks `{pdk.revision}` (see this experiment's README for "
        "the comparison against `spec/cell-candidates.md`'s pinned revision)"
    )
    lines.append(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    lines.append("- **Supersedes**: (none -- first record for this claim/region)")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdk-root", default=None, help="override PDK_ROOT resolution")
    parser.add_argument("--candidates", default="1,2,3", help="comma-separated candidate numbers to run")
    parser.add_argument("-j", "--workers", type=int, default=8, help="parallel ngspice invocations")
    parser.add_argument("--check-env", action="store_true", help="verify ngspice + PDK are resolvable, then exit")
    args = parser.parse_args(argv)

    try:
        pdk = P.resolve_pdk(args.pdk_root)
        RUN.check_ngspice()
    except (P.PDKNotFoundError, RUN.NgspiceNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")

    if args.check_env:
        print("ngspice + PDK OK.")
        return 0

    wanted = {int(x) for x in args.candidates.split(",") if x.strip()}
    dirty = R.git_is_dirty(REPO_ROOT)
    if dirty:
        print("WARNING: working tree is dirty -- records will say so in Netlist provenance.")

    experiment_dir = THIS_DIR
    overall_rc = 0
    for candidate in CANDIDATES:
        if candidate.n not in wanted:
            continue
        t0 = time.time()
        print(f"== Candidate {candidate.n} (Region {candidate.region}, {candidate.access_model} / "
              f"{candidate.cap_model}) ==")
        run = run_candidate(pdk, candidate, experiment_dir, args.workers)
        elapsed = time.time() - t0
        print(f"   {run.n_ngspice_runs} ngspice runs, {run.n_failed} failed, {elapsed:.1f}s")

        record_md = render_record(pdk, run, dirty)
        record_path = experiment_dir / "records" / f"{run.record_id}.md"
        R.write_once(record_path, record_md)
        print(f"   record: {record_path.relative_to(REPO_ROOT)}")

        if run.n_failed:
            overall_rc = 1

    return overall_rc


if __name__ == "__main__":
    raise SystemExit(main())
