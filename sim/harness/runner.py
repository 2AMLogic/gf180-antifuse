"""Run one ngspice deck and capture its raw output.

Deliberately thin: the corner grid, deck assembly and measurement parsing
are the experiment's job (see
``sim/cell-device-characterization/run_experiment.py``); this module only
knows how to invoke ngspice and report whether it succeeded.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
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


@dataclass(frozen=True)
class NgspiceRun:
    ok: bool
    returncode: int
    output: str


def run_deck(deck_path: Path, cwd: Path, timeout_s: float = 60.0) -> NgspiceRun:
    """Run `ngspice -b <deck_path>` from cwd, return combined stdout+stderr.

    A run is considered failed if ngspice exits non-zero OR its own output
    reports an error/fatal line -- ngspice sometimes exits 0 after printing
    an ERROR to stdout mid-``.control`` block.
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
        return NgspiceRun(ok=False, returncode=-1, output=combined + "\n[harness] TIMEOUT\n")

    combined = proc.stdout + proc.stderr
    lower = combined.lower()
    has_error = "fatal error" in lower or "\nerror" in lower or lower.startswith("error")
    return NgspiceRun(ok=(proc.returncode == 0 and not has_error), returncode=proc.returncode, output=combined)
