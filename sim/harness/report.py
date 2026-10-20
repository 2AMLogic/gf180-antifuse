"""Record-id allocation, git provenance, and the append-only record writer.

Ports the shape of gf180-bandgap's ``sim/harness/report.py``: a
``<record-id>`` is ``<YYYYMMDD>-<HHMMSS>-<short-git-sha>``; nothing under
``records/``, ``netlist-snapshots/`` or ``corners/`` is ever overwritten.
"""

from __future__ import annotations

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
