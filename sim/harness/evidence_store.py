"""Store a run's raw outputs in the fleet artifact store; keep only a manifest.

New evidence bytes do not go into git: they are staged in a git-ignored
scratch directory, stored with ``klt artifact put``, and only the resulting
manifest (``manifests/artifacts/<bench>-<run-id>.manifest.json``) plus the
Markdown record are committed. Entry names carry the ``<corner-id>`` (and any
region/sub-configuration path) so per-corner results stay separable.

Fails closed: no broker, a ``klt`` without ``artifact put``, or an unreachable
broker raises ``EvidenceStoreError`` and leaves nothing in the tracked tree.
There is no fallback that commits bytes. The broker URL is read from
``$KLT_ARTIFACT_BROKER`` by ``klt`` itself and is never recorded here.

Pre-adoption evidence keeps its committed bytes (manifest-forward only).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

BROKER_ENV = "KLT_ARTIFACT_BROKER"
SCRATCH_REL = Path("sim/.artifact-scratch")
MANIFEST_REL = Path("manifests/artifacts")


class EvidenceStoreError(RuntimeError):
    pass


def scratch_dir(repo_root: Path, bench: str, run_id: str) -> Path:
    return repo_root / SCRATCH_REL / f"{bench}-{run_id}"


def manifest_path(repo_root: Path, bench: str, run_id: str) -> Path:
    return repo_root / MANIFEST_REL / f"{bench}-{run_id}.manifest.json"


def preflight(klt_cmd=("klt",), env: dict[str, str] | None = None) -> None:
    """Raise unless a broker is configured and ``klt`` supports ``artifact put``."""
    env = os.environ if env is None else env
    if not env.get(BROKER_ENV):
        raise EvidenceStoreError(f"${BROKER_ENV} is unset; refusing to store evidence (no byte-committing fallback)")
    try:
        proc = subprocess.run([*klt_cmd, "artifact", "put", "--help"], capture_output=True, text=True,
                              timeout=60, env=dict(env))
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvidenceStoreError(f"klt unavailable: {exc}") from exc
    if proc.returncode != 0:
        raise EvidenceStoreError("this klt lacks `artifact put`; upgrade klt (no byte-committing fallback)")


def stage(files: dict[str, Path], scratch: Path) -> dict[str, Path]:
    """Copy ``{entry-name: source}`` into ``scratch`` under the entry name."""
    staged = {}
    for name, src in files.items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise EvidenceStoreError(f"unsafe entry name: {name!r}")
        dest = scratch / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        staged[name] = dest
    return staged


def store_run(bench: str, run_id: str, files: dict[str, Path], repo_root: Path, *,
              klt_cmd=("klt",), env: dict[str, str] | None = None) -> list[dict]:
    """Stage, store and manifest one run; return ``[{name, size, sha256}]``.

    The manifest is built outside the tracked tree and moved into place only
    after every object is stored, so a mid-run failure leaves no partial
    manifest. An existing manifest is never overwritten (append-only).
    """
    if not files:
        raise EvidenceStoreError("no files to store")
    preflight(klt_cmd, env)
    dest = manifest_path(repo_root, bench, run_id)
    if dest.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence file: {dest}")
    run_env = dict(os.environ if env is None else env)
    scratch = scratch_dir(repo_root, bench, run_id)
    staged = stage(files, scratch)
    with tempfile.TemporaryDirectory() as td:
        tmp_manifest = Path(td) / dest.name
        for name, path in staged.items():
            proc = subprocess.run([*klt_cmd, "artifact", "put", "--manifest", str(tmp_manifest), "--name", name,
                                   str(path)], capture_output=True, text=True, env=run_env)
            if proc.returncode != 0:
                raise EvidenceStoreError(f"klt artifact put failed for {name} (exit {proc.returncode}):\n"
                                         f"{(proc.stdout + proc.stderr)[-2000:]}")
        entries = json.loads(tmp_manifest.read_text())["entries"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_manifest), dest)
    return [{"name": e["name"], "size": e["size"], "sha256": e["sha256"]} for e in entries]
