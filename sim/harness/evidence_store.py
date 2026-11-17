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

A successful store is also a cleanup point: the staged-from source files are
removed once the manifest has landed (empty directories pruned, never anything
at or above the repo root), so the store holds the only copy and nothing
committable remains under a run directory. A failure at any earlier point
writes no manifest and deletes nothing. Re-render paths recover a published
run's bytes with ``fetch_run`` / ``run_dir_for_reading``.

Not everything under a run directory is evidence: klt's git-ignored ``.work/``
scratch tree holds a second, internally-named copy of decks and logs the runner
already writes out under its ``<corner-id>`` name, plus a regenerated
``.spiceinit`` per corner. Those are skipped so the committed manifests index
the record and not the scratch (``collect_run_files`` / ``_skip_in_work``).
Skipping is forward-only: no existing manifest, record or stored object changes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BROKER_ENV = "KLT_ARTIFACT_BROKER"
SCRATCH_REL = Path("sim/.artifact-scratch")
MANIFEST_REL = Path("manifests/artifacts")

#: klt's per-corner working directory, git-ignored as disposable scratch
#: (``.gitignore``: ``**/.work/``). Only files *inside* such a directory are
#: ever eligible for the skips below.
WORK_DIR_NAME = ".work"
#: Basenames under ``.work/`` that are regenerated boilerplate, never evidence:
#: ngspice reads ``.spiceinit`` at startup and klt writes an identical copy into
#: every corner directory.
WORK_SKIP_BASENAMES = frozenset({".spiceinit"})
#: Basenames under ``.work/`` that are the only copy of something real and are
#: therefore kept unconditionally, duplicate bytes or not.
WORK_KEEP_BASENAMES = frozenset({"batch-receipt.json"})
#: Decided by basename alone, so never a de-duplication candidate.
_WORK_BY_BASENAME = WORK_SKIP_BASENAMES | WORK_KEEP_BASENAMES


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
    manifest. An existing manifest is never overwritten (append-only). Once
    the manifest has landed the staged-from source files are deleted — from
    that point the store holds the only copy — and directories the deletion
    emptied are pruned (never the repo root or anything outside it).
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
    _remove_stored_sources(files, repo_root)
    return [{"name": e["name"], "size": e["size"], "sha256": e["sha256"]} for e in entries]


def _remove_stored_sources(files: dict[str, Path], repo_root: Path) -> None:
    """Delete the just-stored sources; prune directories that become empty.

    Runs only after the manifest is in place, so a store that fails anywhere
    earlier leaves every source file untouched. Pruning never removes the
    repo root itself and never leaves it, so sources outside the repo are
    unlinked but their directories stay.
    """
    parents: set[Path] = set()
    for src in files.values():
        path = Path(src)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        parents.add(path.parent)
    _prune_empty_dirs(parents, repo_root)


def _prune_empty_dirs(starts: set[Path], stop: Path) -> None:
    """``rmdir`` upward from each start while the directory is empty.

    Stops at ``stop`` (exclusive), at the first non-empty directory, or as
    soon as a directory is outside ``stop`` — whichever comes first.
    """
    for start in starts:
        cur = start
        while cur != stop and stop in cur.parents:
            try:
                cur.rmdir()
            except OSError:
                break
            cur = cur.parent


def fetch_run(bench: str, run_id: str, repo_root: Path, *, dest: Path | None = None,
              klt_cmd=("klt",), env: dict[str, str] | None = None,
              names: set[str] | None = None) -> Path:
    """Fetch a published run's objects back from the store into ``dest``.

    Entry names are paths relative to the run directory, so the fetched tree
    reproduces the run directory's layout. ``klt artifact get`` verifies each
    object's sha256 before writing it. ``dest`` defaults to the run's
    git-ignored scratch directory plus ``fetched/``; ``names`` restricts the
    fetch to those entry names. Raises ``EvidenceStoreError`` when no
    manifest exists or a fetch fails.
    """
    m = manifest_path(repo_root, bench, run_id)
    if not m.is_file():
        raise EvidenceStoreError(f"no manifest for {bench}/{run_id}: {m} not found")
    entries = json.loads(m.read_text())["entries"]
    selected = [e for e in entries if names is None or e.get("name") in names]
    if not selected:
        raise EvidenceStoreError(f"{m.name}: no stored entries match the requested names")
    dest = Path(dest) if dest is not None else scratch_dir(repo_root, bench, run_id) / "fetched"
    run_env = dict(os.environ if env is None else env)
    for e in selected:
        key = e.get("name") or e["sha256"]
        out = dest / key
        out.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run([*klt_cmd, "artifact", "get", "--force", "-o", str(out), f"{m}#{key}"],
                              capture_output=True, text=True, env=run_env)
        if proc.returncode != 0:
            raise EvidenceStoreError(f"klt artifact get failed for {key} (exit {proc.returncode}):\n"
                                     f"{(proc.stdout + proc.stderr)[-2000:]}")
    return dest


def run_dir_for_reading(bench: str, run_id: str, repo_root: Path, run_dir: Path, *,
                        klt_cmd=("klt",), env: dict[str, str] | None = None) -> Path:
    """Where a reader should look for a run's files: the run dir, or the store.

    The run directory itself while it still holds named (non-``.work``) files
    — pre-adoption runs whose bytes are committed keep working from disk. A
    published-and-consumed run (only git-ignored ``.work`` scratch left, or
    nothing at all) is fetched back into scratch with ``fetch_run``. A run
    with no manifest was never stored — its run dir answer is returned
    unchanged so callers report their usual missing-files error.
    """
    run_dir = Path(run_dir)
    if not manifest_path(repo_root, bench, run_id).is_file():
        return run_dir
    for p in run_dir.rglob("*"):
        if p.is_file() and WORK_DIR_NAME not in p.relative_to(run_dir).parts:
            return run_dir
    return fetch_run(bench, run_id, repo_root, klt_cmd=klt_cmd, env=env)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _skip_in_work(path: Path, basename: str, twin_shas_by_size: dict[int, set[str]]) -> bool:
    """Is this file under ``.work/`` disposable scratch rather than evidence?

    Two narrow cases, both of which leave the evidence record complete:

    * a regenerated ``.spiceinit`` (``WORK_SKIP_BASENAMES``);
    * a file whose bytes are already published under a non-``.work`` name in the
      same run, i.e. klt's internally-named copy of a deck or log the runner also
      wrote out under its ``<corner-id>`` name. The corner-id-named copy is the
      one records cite, so the ``.work`` twin is a pure double-store.

    Everything else under ``.work/`` is kept: ``WORK_KEEP_BASENAMES`` provenance,
    and any file with no non-``.work`` twin — which is what preserves the
    simulator logs of a bench that never copies them out under a corner-id name.
    """
    if basename in WORK_SKIP_BASENAMES:
        return True
    if basename in WORK_KEEP_BASENAMES:
        return False
    twins = twin_shas_by_size.get(path.stat().st_size)
    return bool(twins) and _sha256(path) in twins


def collect_run_files(run_dir: Path, prefix: str = "") -> dict[str, Path]:
    """Map the regular files under ``run_dir`` to entry names relative to it.

    Keeps the ``<corner-id>`` / region path components in the name so stored
    objects stay separable per corner and per region.

    Files outside klt's git-ignored ``.work/`` scratch tree are always published.
    Inside it, the disposable ones are skipped so the committed manifests stop
    indexing regenerable scratch — see ``_skip_in_work`` for exactly which, and
    note that no file outside a ``.work/`` directory is ever skipped.
    """
    run_dir = Path(run_dir)
    files = [p for p in sorted(run_dir.rglob("*")) if p.is_file()]
    rels = {p: p.relative_to(run_dir) for p in files}
    in_work = {p: WORK_DIR_NAME in rels[p].parts for p in files}

    # Byte-identical implies equal size, so only a size held by BOTH a .work/
    # de-duplication candidate and a published file can ever match; hash just
    # those. A run with no .work/ tree reads no file content at all.
    twin_paths_by_size: dict[int, list[Path]] = {}
    candidate_sizes: set[int] = set()
    for p in files:
        if not in_work[p]:
            twin_paths_by_size.setdefault(p.stat().st_size, []).append(p)
        elif rels[p].name not in _WORK_BY_BASENAME:
            candidate_sizes.add(p.stat().st_size)
    twin_shas_by_size = {size: {_sha256(q) for q in twin_paths_by_size[size]}
                         for size in candidate_sizes & twin_paths_by_size.keys()}

    out: dict[str, Path] = {}
    for p in files:
        if in_work[p] and _skip_in_work(p, rels[p].name, twin_shas_by_size):
            continue
        out[f"{prefix}{rels[p].as_posix()}"] = p
    return out


def publish_run(bench: str, run_id: str, run_dir: Path, repo_root: Path, *,
                klt_cmd=("klt",), env: dict[str, str] | None = None) -> list[dict]:
    """Store everything under ``run_dir`` for one run; return the record's object rows."""
    return store_run(bench, run_id, collect_run_files(run_dir), repo_root, klt_cmd=klt_cmd, env=env)


def publish_for_runner(bench: str, run_id: str, run_dir: Path, repo_root: Path, *,
                       klt_cmd=("klt",), env: dict[str, str] | None = None) -> int:
    """Runner entry point: publish ``run_dir`` and return a process exit code.

    Prints the manifest path on success (the run dir's stored copies are
    removed — the store holds the only copy); on ``EvidenceStoreError``
    prints the reason and returns 1 (nothing is written, no bytes are
    committed, the run dir is left untouched).
    """
    try:
        rows = publish_run(bench, run_id, run_dir, repo_root, klt_cmd=klt_cmd, env=env)
    except EvidenceStoreError as exc:
        print(f"ERROR: evidence not stored: {exc}", file=sys.stderr)
        return 1
    print(f"   manifest: {manifest_path(repo_root, bench, run_id).relative_to(repo_root)} "
          f"({len(rows)} objects, run-dir copies removed)")
    return 0
