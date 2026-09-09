"""Corner grammar shared by every sim/ experiment in this repo.

Ports the naming *shape* of gf180-bandgap's ``sim/harness/corners.py`` and
``sim/README.md``:

- record-id: ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``
- corner-id: ``<process>_<temp>c_<supply>``, where ``<supply>`` is either
  ``<volts>v`` (a swept main supply), ``<node><volts>v`` (a swept rail that
  is not the main supply, e.g. this experiment's ``bl1p00v`` read-voltage
  node), or ``nosupply`` (no rail to sweep -- a device-level bench).

CLAUDE.md's mandated axis is -40/27/125 degC; gf180mcu's MOS process
sections are typical/ff/ss/fs/sf (Candidates 1/3's ``sm141064.ngspice`` and
Candidate 2's ``smbb000149.ngspice`` both define this same five-section
bundle); its moscap sections are moscap_typical/moscap_ff/moscap_ss.
"""

from __future__ import annotations

TEMPS_C: tuple[int, ...] = (-40, 27, 125)
MOS_CORNERS: tuple[str, ...] = ("typical", "ff", "ss", "fs", "sf")
MOSCAP_CORNERS: tuple[str, ...] = ("moscap_typical", "moscap_ff", "moscap_ss")

# Fast/hot/high-supply and slow/cold/low-supply are the two named worst-case
# corners spec/architecture.md Section 4 asks this experiment to bound.
FAST_HOT_HIGH = ("ff", 125, +0.10)
SLOW_COLD_LOW = ("ss", -40, -0.10)


def fmt_temp(temp_c: int) -> str:
    return f"{temp_c}c"


def fmt_node_supply(node: str, volts: float) -> str:
    """``<node><volts>v`` per sim/README.md, e.g. bl1p00v, bl0p90v."""
    return f"{node}{volts:.2f}".replace(".", "p") + "v"


def corner_id(process: str, temp_c: int, supply_token: str) -> str:
    """Assemble ``<process>_<temp>c_<supply>``."""
    return f"{process}_{fmt_temp(temp_c)}_{supply_token}"
