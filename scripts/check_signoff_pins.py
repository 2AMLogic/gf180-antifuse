#!/usr/bin/env python3
"""Check signoff/manifest.json pins against the cited files' bytes.

For every `evidence` citation part, three hashes must agree (issue #443):
  1. the manifest's pinned `content_hash`,
  2. the cited envelope's recorded `provenance.input.content_hash`,
  3. the sha256 of the input bytes the envelope names.

For every `supporting_evidence` entry, the pinned `content_hash` must equal
the sha256 of the entry's own `file` bytes (issue #453) -- the exact check
`signoff/verify.sh` performs on that block, minus its `klt` dependency, so
`npm run check:ci` catches a regenerated report drifting from its pin on
hosts where verify.sh cannot run.

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
is resolved from the repository root. Functional reports combine Verilog source
digests in path order. Their manifest source_hash_order indexes the recorded
source list because KLT redacts the two external PDK paths. The repo netlist
is rehashed locally. The declared PDK pins come from the actual simulator run.
Stdlib only.

Usage:
    scripts/check_signoff_pins.py [MANIFEST]

MANIFEST defaults to signoff/manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "signoff" / "manifest.json"

PIN_RE = re.compile(r"sha256:[0-9a-f]{64}")


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


def verify_routed_sdf(citation: dict, report: dict, sdf: Path | None = None) -> None:
    """Bind the simulator's normalized SDF to the reviewed STA output digest."""
    expected = citation.get("sdf_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("missing or malformed SDF pin in signoff/manifest.json")
    reported = report.get("provenance", {}).get("sdf_sha256")
    if reported != expected:
        raise ValueError(f"reported SDF digest {reported} differs from the pin {expected}")
    if sdf is not None:
        actual = hashlib.sha256(sdf.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"normalized SDF {sdf} hashes to {actual}, expected {expected}")


def _functional_source_hash(root: Path, envelope: dict, order: list) -> str:
    """Replay the producer's path-sorted multi-source hash, including PDK model pins."""
    sources = envelope.get("environment", {}).get("sources", [])
    if (not isinstance(sources, list) or not sources or not isinstance(order, list)
            or any(type(i) is not int for i in order)
            or sorted(order) != list(range(len(sources)))):
        raise ValueError("source_hash_order must name every source exactly once")
    digests = []
    repo_sources = 0
    for i in order:
        source = sources[i]
        if not isinstance(source, dict):
            raise ValueError(f"source {i} is not an object")
        digest = source.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"source {i} has no sha256")
        if source.get("scope") == "repo" and isinstance(source.get("path"), str):
            repo_sources += 1
            actual = hashlib.sha256((root / source["path"]).read_bytes()).hexdigest()
            if actual != digest:
                raise ValueError(f"{source['path']} differs from its recorded source sha256")
        elif source.get("scope") != "external" or source.get("path") is not None:
            raise ValueError(f"source {i} has an invalid scope or path")
        digests.append(digest)
    if not repo_sources:
        raise ValueError("functional report names no repo source")
    return "sha256:" + hashlib.sha256("".join(digests).encode("ascii")).hexdigest()


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


def _load_manifest(manifest_path: Path) -> tuple[dict | None, list[str]]:
    """(manifest, []) on success, or (None, [one clean diagnostic])."""
    try:
        manifest = json.loads(manifest_path.read_text())
    except OSError as exc:
        return None, [f"{manifest_path}: unreadable ({exc})"]
    except json.JSONDecodeError as exc:
        return None, [f"{manifest_path}: invalid JSON ({exc})"]
    if not isinstance(manifest, dict):
        return None, [f"{manifest_path}: manifest is not a JSON object"]
    return manifest, []


def _check_evidence(root: Path, manifest: dict,
                    manifest_path: Path) -> tuple[list[str], int]:
    """(errors, citation-part count) for the 'evidence' block (#443)."""
    evidence = manifest.get("evidence")
    if not isinstance(evidence, dict):
        return [f"{manifest_path}: no 'evidence' object to check"], 0

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
        if row == "7.digital":
            try:
                verify_routed_sdf(part, envelope)
            except ValueError as exc:
                errs.append(f"{where}: {exc}")
        if "source_hash_order" in part:
            if envelope.get("engine") != "icarus" or not envelope.get("testbench"):
                errs.append(f"{where}: source_hash_order requires a functional report")
                continue
            try:
                digest = _functional_source_hash(root, envelope, part["source_hash_order"])
            except (OSError, ValueError) as exc:
                errs.append(f"{where}: {exc}")
                continue
            if not pin == recorded == digest:
                errs.append(f"{where}: pin {pin}, recorded {recorded}, combined sources {digest}")
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
    return errs, rows


def _check_supporting(root: Path, manifest: dict) -> list[str]:
    """Errors for the 'supporting_evidence' block (#453).

    Each entry pins its own file's bytes -- a single sha256 per entry, no
    envelope parsing. An absent or empty list passes, exactly as in
    verify.sh; a present non-list value is malformed and fails closed.
    """
    supporting = manifest.get("supporting_evidence")
    if supporting is None:
        return []
    if not isinstance(supporting, list):
        return ["'supporting_evidence' is not a list"]
    errs: list[str] = []
    for i, entry in enumerate(supporting):
        where = f"supporting_evidence[{i}]"
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            errs.append(f"{where}: missing 'file'")
            continue
        ref = entry["file"]
        pin = entry.get("content_hash")
        if not isinstance(pin, str) or not PIN_RE.fullmatch(pin):
            errs.append(f"{where}: pin {pin!r} is not 'sha256:' + 64 hex")
            continue
        try:
            digest = "sha256:" + hashlib.sha256((root / ref).read_bytes()).hexdigest()
        except OSError as exc:
            errs.append(f"{where}: {ref} unreadable ({exc})")
            continue
        if pin != digest:
            errs.append(f"{where}: pin {pin} != {ref} bytes (now {digest}) "
                        "-- re-pin or regenerate")
    return errs


def _audit(root: Path, manifest_path: Path) -> tuple[list[str], int, int]:
    """(errors, evidence-part count, supporting-entry count); one manifest load."""
    manifest, errs = _load_manifest(manifest_path)
    if errs:
        return errs, 0, 0
    ev_errs, n_evidence = _check_evidence(root, manifest, manifest_path)
    supporting = manifest.get("supporting_evidence")
    n_supporting = len(supporting) if isinstance(supporting, list) else 0
    return ev_errs + _check_supporting(root, manifest), n_evidence, n_supporting


def check_pins(root: Path, manifest_path: Path | None = None) -> list[str]:
    """One error string per evidence part or supporting_evidence entry that
    fails its pin check."""
    return _audit(root, manifest_path or root / "signoff" / "manifest.json")[0]


def main(argv: list[str]) -> int:
    manifest_arg = Path(argv[0]) if argv else DEFAULT_MANIFEST
    root = manifest_arg.resolve().parent.parent
    errs, n_evidence, n_supporting = _audit(root, manifest_arg)
    for e in errs:
        print(f"check_signoff_pins: {e}", file=sys.stderr)
    print(f"checked {n_evidence} evidence part(s) and {n_supporting} "
          f"supporting_evidence part(s) in {manifest_arg}: "
          f"{'FAIL' if errs else 'ok'}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
