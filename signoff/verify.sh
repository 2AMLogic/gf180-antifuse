#!/usr/bin/env bash
# Re-grade this block's T1 state and assert the committed verdict is still true.
#
# Three assertions, in order:
#   1. Every citation in signoff/manifest.json keys a real T1 item, pins a
#      content_hash, and (if file-backed) names a file that exists in the
#      tree. An unpinned citation cannot have its freshness checked by
#      `klt signoff` at all, and an evidence key the grader does not recognise
#      is ignored silently -- a typo would read as an honest gap. This script
#      refuses both outright.
#   2. `klt signoff --manifest signoff/manifest.json --format json` renders a
#      report (exit 0 = every T1 item met, exit 3 = at least one unmet -- both
#      are successful runs; 1 and 2 are tool/usage failures).
#   3. Its output is byte-identical to the committed signoff/report.json.
#
# Assertion 3 is the anti-rot gate: it fails when the evidence moved (a cited
# artifact was regenerated and no longer matches its pinned hash, so an item
# flipped met -> unmet), and it also fails when the *checklist* moved (a newer
# klayout-tools ships a different design-evidence-tiers.md, changing
# source_doc_content_hash or the item set). Both are cases where the committed
# verdict has stopped being the truth, and both are fixed the same way: re-run
# the command below, read what changed, update the claim in signoff/README.md,
# and commit the new report.
#
# Usage:  ./signoff/verify.sh          (from anywhere)
# Needs:  klt (klayout-tools) and python3 on PATH.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$repo_root/signoff/manifest.json"
committed_report="$repo_root/signoff/report.json"

fail() { printf 'signoff/verify.sh: %s\n' "$1" >&2; exit 1; }

command -v klt >/dev/null 2>&1 || fail "klt (klayout-tools) is not on PATH -- see signoff/README.md"
command -v python3 >/dev/null 2>&1 || fail "python3 is not on PATH"
[ -f "$manifest" ] || fail "missing $manifest"
[ -f "$committed_report" ] || fail "missing $committed_report"

# 1. Citation hygiene: every citation pinned, every cited file present.
python3 - "$manifest" "$repo_root" "$committed_report" <<'PY'
import json, os, re, sys

manifest_path, repo_root, report_path = sys.argv[1], sys.argv[2], sys.argv[3]
with open(manifest_path) as fh:
    manifest = json.load(fh)

problems = []
for key in ("block", "kind"):
    if not manifest.get(key):
        problems.append(f"manifest is missing required key {key!r}")
if manifest.get("kind") not in (None, "analog", "digital", "mixed-signal"):
    problems.append(f"kind {manifest['kind']!r} is not analog/digital/mixed-signal")

# `klt signoff` silently ignores an evidence key it does not recognise, so a
# typo ("3.anlaog", "12") reads as an honest gap rather than an error. Check
# every key against the item ids the committed report actually renders.
with open(report_path) as fh:
    known_ids = {
        str(item["id"]) for item in json.load(fh).get("items", [])
        if item.get("tier") == "T1" and item.get("id") is not None
    }

for item, entry in (manifest.get("evidence") or {}).items():
    where = f"evidence[{item!r}]"
    match = re.fullmatch(r"(\d+)(?:\.(analog|digital))?", str(item))
    if not match:
        problems.append(
            f"{where} is not a valid item key -- expected '<id>' or "
            "'<id>.analog' / '<id>.digital'"
        )
    elif known_ids and match.group(1) not in known_ids:
        problems.append(
            f"{where} names item {match.group(1)}, which is not a T1 item in "
            "the graded checklist -- klt signoff would ignore it silently"
        )
    if isinstance(entry, str):
        problems.append(
            f"{where} is a bare path with no pinned content_hash -- use "
            '{"file": ..., "content_hash": "sha256:..."} so freshness can be checked'
        )
        continue
    if not isinstance(entry, dict):
        problems.append(f"{where} is neither a path nor an object")
        continue
    if not str(entry.get("content_hash", "")).startswith("sha256:"):
        problems.append(f"{where} does not pin a sha256: content_hash")
    if "file" in entry:
        cited = os.path.join(repo_root, entry["file"])
        if not os.path.isfile(cited):
            problems.append(f"{where} cites {entry['file']!r}, which is not in the tree")
    elif "command" not in entry:
        problems.append(f"{where} has neither a 'file' nor a 'command'")

if problems:
    for problem in problems:
        print(f"signoff/verify.sh: {problem}", file=sys.stderr)
    sys.exit(1)
PY

# 2 + 3. Re-grade and compare against the committed verdict.
fresh_report="$(mktemp)"
trap 'rm -f "$fresh_report"' EXIT

rc=0
klt signoff --manifest "$manifest" --format json >"$fresh_report" || rc=$?
# 0 = tier T1 (every item met); 3 = tier null (at least one item unmet). Both
# are successful gradings and both are legitimate committed verdicts. 1 and 2
# mean the manifest or the tiers doc could not be read at all.
case "$rc" in
    0 | 3) ;;
    *) fail "klt signoff failed to render a report (exit $rc) -- see its error envelope above" ;;
esac

if ! diff -u "$committed_report" "$fresh_report"; then
    cat >&2 <<'EOF'

signoff/verify.sh: the committed verdict no longer matches a fresh grading run.

Either the cited evidence moved (an item's freshness/pass state changed) or the
T1 checklist itself moved (a newer klayout-tools ships a different
design-evidence-tiers.md). Do not hand-edit signoff/report.json. Re-run:

    klt signoff --manifest signoff/manifest.json --format json > signoff/report.json

then read the diff, update the claim in signoff/README.md to match what actually
changed, and commit both.
EOF
    exit 1
fi

echo "signoff/verify.sh: OK -- committed verdict matches a fresh klt signoff run"
