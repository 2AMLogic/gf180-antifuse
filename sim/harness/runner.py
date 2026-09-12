"""Run one ngspice deck and capture its raw output.

Deliberately thin: the corner grid, deck assembly and measurement parsing
are the experiment's job (see
``sim/cell-device-characterization/run_experiment.py``); this module only
knows how to invoke ngspice and report whether it succeeded.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class NgspiceNotFoundError(RuntimeError):
    pass


def check_ngspice() -> str:
    """Return the resolved ngspice binary path, or raise."""
    path = shutil.which("ngspice")
    if not path:
        raise NgspiceNotFoundError(
            "ngspice not found on PATH. Install it (e.g. `apt-get install "
            "ngspice` / `brew install ngspice`) before running this "
            "experiment."
        )
    return path


def run_deck(deck_path: Path, cwd: Path, timeout_s: float = 60.0) -> str:
    """Run `ngspice -b <deck_path>` from cwd, return combined stdout+stderr.

    Callers determine success from the deck's own expected measurement
    output (see ``run_experiment.py``), not from ngspice's exit status --
    ngspice sometimes exits 0 after printing an ERROR to stdout mid-
    ``.control`` block.
    """
    try:
        proc = subprocess.run(
            ["ngspice", "-b", str(deck_path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        combined = (exc.stdout or "") + (exc.stderr or "")
        return combined + "\n[harness] TIMEOUT\n"

    combined = proc.stdout + proc.stderr
    return combined
