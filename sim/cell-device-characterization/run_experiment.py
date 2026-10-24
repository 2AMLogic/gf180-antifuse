#!/usr/bin/env python3
"""sim/cell-device-characterization -- shared parameter/parse library.

The legacy local-ngspice grid driver that used to live here was retired
(operator ruling, #158); the PVT grid now runs as checked-in `klt sim`
requests via `klt/run_klt_campaign.py`. What remains is the library that
`sim/cell-breakdown-model/run_experiment.py` loads as `CHAR`: the candidate
table, grid constants, bias-level helpers and the log-scalar parser. The
committed `corners/` logs and `records/` stay as append-only evidence.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent

sys.path.insert(0, str(SIM_DIR))

from harness import numfmt as NF  # noqa: E402

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

spice_num = NF.spice_num


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


def sizing_multiplier(level: str) -> float:
    return 1.0 if level == "min" else 2.0
