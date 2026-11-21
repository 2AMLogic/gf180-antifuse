#!/usr/bin/env python3
"""Check signoff/manifest.json evidence pins against the cited envelopes.

For every `evidence` citation part, three hashes must agree (issue #443):
  1. the manifest's pinned `content_hash`,
  2. the cited envelope's recorded `provenance.input.content_hash`,
  3. the sha256 of the input bytes the envelope names.

The grader's own freshness check only runs for rows it grades on their
envelope, and `klt signoff --check REPORT` compares verdicts, not pins -- a
stale pin on a row that already grades `check_failed` (3.analog after #296
moved the GDS) is invisible to both, and `verify.sh` byte-compares a report
that renders no citation for such a row. This script is the offline guard:
run as part of `npm run check:ci`, it fails before a stale pin can drift a
graded row silently.

The input each envelope names is found the way the klt envelope families
record it: generic attestations put a repo-scoped path object in
`provenance.input.path`, DRC and ERC envelopes use the top-level `file`, and
LVS envelopes use the top-level `layout`. The first present wins; the path
is resolved from the repository root. Stdlib only.

Usage:
    scripts/check_signoff_pins.py [MANIFEST]

MANIFEST defaults to signoff/manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "signoff" / "manifest.json"


def _input_ref(envelope: dict) -> str | None:
    """The repo-relative path of the input the envelope hashed, or None."""
    for probe in (
        (envelope.get("provenance") or {}).get("input", {}).get("path"),
        envelope.get("file"),
        envelope.get("layout"),
    ):
        if isinstance(probe, str):
            return probe
        if isinstance(probe, dict) and isinstance(probe.get("path"), str):
            return probe["path"]
    return None


def _parts(evidence: dict) -> list[tuple[str, str, dict]]:
    """Expand compound (list) citations into (row, where, part) triples."""
    out = []
    for item, cited in evidence.items():
        if isinstance(cited, list):
            out.extend((item, f"evidence[{item!r}][{n}]", part)
                       for n, part in enumerate(cited))
        else:
            out.append((item, f"evidence[{item!r}]", cited))
    return out


def check_pins(root: Path, manifest_path: Path | None = None) -> list[str]:
    """Return one error string per citation part whose three hashes disagree."""
    manifest_path = manifest_path or root / "signoff" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except OSError as exc:
        return [f"{manifest_path}: unreadable ({exc})"]
    except json.JSONDecodeError as exc:
        return [f"{manifest_path}: invalid JSON ({exc})"]

    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        return [f"{manifest_path}: no 'evidence' object to check"]

    errs: list[str] = []
    rows = 0
    for row, where, part in _parts(evidence):
        rows += 1
        if not isinstance(part, dict) or "file" not in part:
            continue  # command-backed citation; verify.sh governs hygiene
        pin = part.get("content_hash")
        envelope_path = root / part["file"]
        try:
            envelope = json.loads(envelope_path.read_text())
        except OSError as exc:
            errs.append(f"{where}: cited envelope {part['file']} unreadable ({exc})")
            continue
        except json.JSONDecodeError as exc:
            errs.append(f"{where}: cited envelope {part['file']} is invalid JSON ({exc})")
            continue
        recorded = (envelope.get("provenance") or {}).get("input", {}).get("content_hash")
        if not isinstance(recorded, str):
            errs.append(f"{where}: {part['file']} records no provenance.input.content_hash")
            continue
        ref = _input_ref(envelope)
        if ref is None:
            errs.append(f"{where}: {part['file']} names no input path "
                        "(provenance.input.path / file / layout)")
            continue
        input_path = root / ref
        try:
            digest = "sha256:" + hashlib.sha256(input_path.read_bytes()).hexdigest()
        except OSError as exc:
            errs.append(f"{where}: input {ref} named by {part['file']} unreadable ({exc})")
            continue
        if len({pin, recorded, digest}) != 1:
            errs.append(
                f"{where}: pin {pin} != envelope {part['file']} recorded {recorded} "
                f"!= input {ref} bytes (now {digest}) -- re-pin or regenerate"
            )
    if rows == 0:
        errs.append(f"{manifest_path}: 'evidence' has no citation parts")
    return errs


def main(argv: list[str]) -> int:
    manifest_arg = Path(argv[0]) if argv else DEFAULT_MANIFEST
    root = manifest_arg.resolve().parent.parent
    errs = check_pins(root, manifest_arg)
    for e in errs:
        print(f"check_signoff_pins: {e}", file=sys.stderr)
    n = len(_parts(json.loads(manifest_arg.read_text()).get("evidence") or {}))
    print(f"checked {n} evidence part(s) in {manifest_arg}: "
          f"{'FAIL' if errs else 'ok'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
