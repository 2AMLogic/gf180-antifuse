"""Record-id allocation, git provenance, the append-only record writer, and
the committed form of a klt report.

Ports the shape of gf180-bandgap's ``sim/harness/report.py``: a
``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``; nothing under
``records/``, ``netlist-snapshots/`` or ``corners/`` is ever overwritten.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def git_short_sha(repo_root: Path | None = None) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return out.stdout.strip() or "nogit"
    except (OSError, subprocess.SubprocessError):
        return "nogit"


def git_is_dirty(repo_root: Path | None = None) -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return bool(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def allocate_record_id(experiment_dir: Path, repo_root: Path | None = None) -> str:
    """Mint a `<YYYYMMDD>-<HHMMSS>-<sha>` id, unique within experiment_dir.

    Retries a second later on the (very unlikely) collision case rather than
    silently reusing an id -- records/netlist-snapshots/corners are
    append-only, so a re-used id would look like an edit-in-place.
    """
    sha = git_short_sha(repo_root)
    records_dir = experiment_dir / "records"
    for _ in range(5):
        now = datetime.now(timezone.utc)
        record_id = f"{now:%Y%m%d}-{now:%H%M%S}-{sha}"
        if not (records_dir / f"{record_id}.md").exists():
            return record_id
        time.sleep(1.1)
    raise RuntimeError("could not allocate a unique record-id after 5 attempts")


def write_once(path: Path, content: str) -> None:
    """Write content to path, refusing to overwrite an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence file: {path}")
    path.write_text(content)


def git_out(repo_root: Path, *args: str) -> str:
    """Stripped stdout of ``git -C repo_root <args>`` ("" on any failure)."""
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------------------
# The committed form of a klt report
# ---------------------------------------------------------------------------

#: The two `coverage` members that are per-measurement id lists rather than
#: results. Everything else under `coverage` (the counters, the booleans, the
#: short `skipped`/`unknown`/`nothing_checked_reasons` lists) is kept verbatim.
COVERAGE_ID_KEYS = ("checked", "inapplicable")

#: Marker left in place of an elided list. It names the count, so the committed
#: report still answers every question the list itself answered on these
#: characterization benches -- where `measurements_with_limits` is 0 and every
#: `inapplicable` entry carries the single reason `characterization_without_limits`.
ELISION_MARKER = "<{n} entries elided by sim/harness/report.py elide_coverage()>"


def elide_coverage(report: dict) -> dict:
    """Return a deep copy of a klt report with the coverage id lists elided.

    `coverage.checked` and `coverage.inapplicable` run to tens of thousands of
    entries per report -- one per (corner x declared measurement) -- and on a
    characterization bench they carry nothing the rest of the report does not:
    every `checked` id is a `.../observation` suffix over the measurements
    already in `measurements`, and with `measurements_with_limits: 0` every
    `inapplicable` entry carries the one reason `characterization_without_limits`.
    They are replaced by `ELISION_MARKER`, which keeps the count; every
    measurement value, corner status, diagnostic, `environment`, `provenance`
    and coverage counter is left untouched.

    `measurements_with_limits` stays in the committed report, so a bench that
    ever does declare limits -- where `inapplicable` would carry varied reasons
    worth keeping -- is visible in the evidence rather than silently elided.

    Pair this with the full report's sha256 (`klt_report_payload`) so the
    elision stays auditable.
    """
    r = json.loads(json.dumps(report))
    cov = r.get("coverage")
    if isinstance(cov, dict):
        for k in COVERAGE_ID_KEYS:
            v = cov.get(k)
            if isinstance(v, list):
                cov[k] = ELISION_MARKER.format(n=len(v))
    return r


def coverage_is_elided(report: dict) -> bool:
    """True when `report` is already in the committed, elided form.

    Decided structurally -- a present coverage id value that is not a list has
    been replaced by an elision marker -- never by matching the marker text:
    reports committed before the marker moved here carry an older
    `run_bench.py slim()` marker. A report with no `coverage` key, or with
    both id keys still lists (including empty ones), was not elided and a
    full-text digest of it is still attestable.
    """
    cov = report.get("coverage")
    return isinstance(cov, dict) and any(k in cov and not isinstance(cov[k], list) for k in COVERAGE_ID_KEYS)


def klt_report_payload(report: dict, *, indent: int | None = 2,
                       separators: tuple[str, str] | None = None) -> tuple[str, str]:
    """-> (text of the coverage-elided report to commit, sha256 of the full text).

    Both texts are serialised with the same options and a trailing newline, so
    the digest commits to exactly the bytes the runner would have written had
    it not elided -- that is what makes the elision auditable against a
    re-fetched report.
    """
    def dump(obj: dict) -> str:
        return json.dumps(obj, indent=indent, separators=separators) + "\n"

    return dump(elide_coverage(report)), hashlib.sha256(dump(report).encode()).hexdigest()
