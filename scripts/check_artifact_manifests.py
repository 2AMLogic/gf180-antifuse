#!/usr/bin/env python3
"""Check manifests/artifacts/*.manifest.json (fleet artifact store manifests).

Fails on a malformed manifest, any `uri` not starting with `artifact:`, a
storage locator (`s3://`, `arn:aws:`) anywhere in the file, and any stored
object whose sha256 matches the bytes of a tracked file (bytes committed as
well as stored). Stdlib only.

Usage:
    scripts/check_artifact_manifests.py [PATH ...]

PATH may be manifest files or directories (default: manifests/artifacts).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY_KEYS = {"sha256", "size", "kind", "producer", "uri"}
OPTIONAL_KEYS = {"name", "media_type"}
PRODUCER_KEYS = {"tool", "version", "loom.repo", "commit"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LOCATOR_RE = re.compile(r"s3://|arn:aws:")


def check_text(text: str) -> list[str]:
    errs = []
    if LOCATOR_RE.search(text):
        errs.append("names a storage locator (s3:// or arn:aws:)")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return errs + [f"invalid JSON: {exc}"]
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "entries"}:
        return errs + ["top level must be exactly {schema_version, entries}"]
    if doc["schema_version"] != 1:
        errs.append(f"unsupported schema_version {doc['schema_version']!r}")
    if not isinstance(doc["entries"], list) or not doc["entries"]:
        return errs + ["entries must be a non-empty list"]
    for i, e in enumerate(doc["entries"]):
        where = f"entries[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{where}: not an object")
            continue
        keys = set(e)
        if not ENTRY_KEYS <= keys <= ENTRY_KEYS | OPTIONAL_KEYS:
            errs.append(f"{where}: bad field set {sorted(keys)}")
            continue
        if not (isinstance(e["sha256"], str) and SHA_RE.match(e["sha256"])):
            errs.append(f"{where}: sha256 must be 64 lowercase hex")
        if not (isinstance(e["size"], int) and not isinstance(e["size"], bool) and e["size"] >= 0):
            errs.append(f"{where}: size must be a non-negative integer")
        if e["kind"] != "evidence":
            errs.append(f"{where}: kind must be 'evidence'")
        if not (isinstance(e["uri"], str) and e["uri"].startswith("artifact:") and len(e["uri"]) > 9):
            errs.append(f"{where}: uri must start with 'artifact:'")
        p = e["producer"]
        if not isinstance(p, dict) or set(p) != PRODUCER_KEYS:
            errs.append(f"{where}: producer must have exactly {sorted(PRODUCER_KEYS)}")
        name = e.get("name")
        if name is not None and (not isinstance(name, str) or name.startswith("/") or ".." in Path(name).parts):
            errs.append(f"{where}: name must be a relative path")
    return errs


def tracked_files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [root / p for p in out.decode().split("\0") if p]


def check_no_tracked_bytes(manifests: dict[Path, str], root: Path) -> list[str]:
    """Error for each stored object whose bytes are also a tracked file."""
    wanted: dict[int, dict[str, Path]] = {}
    for mpath, text in manifests.items():
        try:
            entries = json.loads(text)["entries"]
            for e in entries:
                wanted.setdefault(e["size"], {})[e["sha256"]] = mpath
        except (ValueError, KeyError, TypeError):
            continue  # reported by check_text
    errs = []
    for f in tracked_files(root):
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size in wanted:
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
            if digest in wanted[size]:
                errs.append(f"{f.relative_to(root)}: bytes are committed AND stored "
                            f"(manifest {wanted[size][digest].name})")
    return errs


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv] or [ROOT / "manifests" / "artifacts"]
    files: list[Path] = []
    for t in targets:
        files += sorted(t.glob("*.manifest.json")) if t.is_dir() else [t]
    texts = {f: f.read_text() for f in files}
    failed = False
    for f, text in texts.items():
        for e in check_text(text):
            print(f"{f}: {e}", file=sys.stderr)
            failed = True
    if not failed and texts:
        for e in check_no_tracked_bytes(texts, ROOT):
            print(e, file=sys.stderr)
            failed = True
    print(f"checked {len(files)} manifest(s): {'FAIL' if failed else 'ok'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
