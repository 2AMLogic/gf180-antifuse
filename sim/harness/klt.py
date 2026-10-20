"""Submit one ``klt sim`` request and return its JSON report.

The single shared wrapper for the experiments' ``klt sim`` calls. Policy it
owns, so no script re-derives it:

* ``-o`` is resolved to an ABSOLUTE path: klt runs ngspice with cwd set to the
  corner directory but hands it deck/log paths relative to the invocation
  directory, so a relative outdir makes every corner fail to start
  (2AMLogic/klayout-tools#2892).
* A fleet refusal (concurrency cap / no capacity) is transient and is retried
  as the SAME request after a pause, bounded by ``RetryPolicy``. Nothing else
  is retried, and a failed batch submit is NEVER replayed on a local backend.

What the caller does with the result (exit, record an error, ...) stays the
experiment's call; this module only reports ``(report | None, diagnostic)``.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

FLEET_REFUSALS = ("BATCH_MAX_CONCURRENT_INSTANCES", "batch_no_capacity")


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry of fleet refusals.

    ``max_submits`` caps the number of submissions, ``budget_s`` the total
    time spent (waits included; None = unbounded by time). The wait before
    retry n is ``base_s`` doubled each time up to ``max_s`` when ``backoff``
    (with 50-100% jitter), else a constant ``base_s``.
    """

    max_submits: int = 1
    base_s: float = 45.0
    max_s: float = 45.0
    budget_s: float | None = None
    backoff: bool = False


NO_RETRY = RetryPolicy()
FIXED_WAIT = RetryPolicy(max_submits=40, base_s=45)
BACKOFF = RetryPolicy(max_submits=10_000, base_s=60, max_s=600, budget_s=5400, backoff=True)


def run_klt(
    request: Path,
    outdir: Path,
    backend: str | None = None,
    *,
    klt_cmd: list[str] | tuple[str, ...] = ("klt",),
    retry: RetryPolicy = NO_RETRY,
    timeout_s: float | None = None,
    env: dict[str, str] | None = None,
) -> tuple[dict | None, str]:
    """Run ``klt sim`` on ``request``; return ``(report, diagnostic)``.

    ``report`` is the parsed JSON stdout (it may itself carry an ``error``
    key -- see ``error_of``); ``None`` means klt produced no JSON, and
    ``diagnostic`` is then the exit status plus the tail of its output. When
    a report was parsed ``diagnostic`` is klt's stderr.
    """
    cmd = [*klt_cmd, "sim", str(Path(request).resolve()), "-o", str(Path(outdir).resolve()), "--format", "json"]
    if backend:
        cmd += ["--backend", backend]
    t0, delay, attempt = time.time(), retry.base_s, 0
    while True:
        attempt += 1
        print(f"running (submit {attempt}):", " ".join(cmd), flush=True)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, env=env)
        except subprocess.TimeoutExpired:
            return None, "klt sim timed out"
        try:
            report = json.loads(proc.stdout)
        except json.JSONDecodeError:
            report = None
        if report is not None and "error" not in report:
            return report, proc.stderr
        blob = proc.stdout + proc.stderr
        refused = any(m in blob for m in FLEET_REFUSALS)
        out_of_budget = retry.budget_s is not None and time.time() - t0 + delay > retry.budget_s
        if not refused or attempt >= retry.max_submits or out_of_budget:
            if report is not None:
                return report, proc.stderr
            return None, (f"exit {proc.returncode} (attempt {attempt})\nstdout:\n{proc.stdout[-4000:]}\n"
                          f"stderr:\n{proc.stderr[-4000:]}")
        wait = delay * (0.5 + random.random() / 2) if retry.backoff else delay
        print(f"  fleet refusal; retrying in {wait:.0f}s (submit {attempt})", flush=True)
        time.sleep(wait)
        delay = min(delay * 2, retry.max_s) if retry.backoff else delay


def error_of(report: dict) -> dict | None:
    """The report's ``error`` object, if klt reported one."""
    return report.get("error")


def run_klt_or_exit(request: Path, outdir: Path, backend: str | None = None, **kw) -> dict:
    """``run_klt`` for scripts that treat any klt failure as fatal."""
    report, diag = run_klt(request, outdir, backend, **kw)
    if report is None:
        print(f"ERROR: klt sim produced no JSON.\n{diag}", file=sys.stderr)
        raise SystemExit(1)
    if error_of(report):
        print(f"ERROR: klt sim reported an error; NOT falling back to a local run:\n"
              f"{json.dumps(error_of(report), indent=2)}", file=sys.stderr)
        raise SystemExit(1)
    return report
