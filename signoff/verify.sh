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
# flipped met -> unmet), and it also fails when the *checklist* moved (the
# grading build ships a different design-evidence-tiers.md, changing
# source_doc_content_hash or the item set). Both are cases where the committed
# verdict has stopped being the truth, and both are fixed the same way: re-run
# the command below, read what changed, update the claim in signoff/README.md,
# and commit the new report.
#
# The grader is pinned: `klt` is invoked through KLT, by default the release
# that rendered the committed report (klayout-tools 0.8.0, the pin
# rtl/pnr/run_drc.sh uses), never whatever `klt` the host has on PATH. A newer
# host build bundles a different checklist and fails assertion 3 on a clean
# tree, hiding real drift behind a known-red check (issue #469). Set KLT_CMD to
# grade with another build (KLT_CMD=klt for the host install); a regrade at a
# newer release changes the verdict itself and is a decision recorded in
# signoff/README.md, not a refresh.
#
# Usage:  ./signoff/verify.sh                                  (from anywhere)
#         KLT_CMD=<klt launcher> ./signoff/verify.sh            override the pin
# Needs:  uv (for the pinned klt) and python3 on PATH.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$repo_root/signoff/manifest.json"
committed_report="$repo_root/signoff/report.json"
KLT=${KLT_CMD:-uvx --from klayout-tools==0.8.0 klt}

fail() { printf 'signoff/verify.sh: %s\n' "$1" >&2; exit 1; }

command -v "${KLT%% *}" >/dev/null 2>&1 \
    || fail "'${KLT%% *}' is not on PATH -- the pinned grader runs through uvx; install uv, or set KLT_CMD to the klt launcher to use (see signoff/README.md)"
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

# Item 11's compound citation is a list of {file, content_hash} parts (klt erc
# plus item 4's LVS report); check each part exactly as a single citation.
checks = []
for item, cited in (manifest.get("evidence") or {}).items():
    if isinstance(cited, list):
        checks.extend((item, f"evidence[{item!r}][{n}]", part) for n, part in enumerate(cited))
    else:
        checks.append((item, f"evidence[{item!r}]", cited))

for item, where, entry in checks:
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

# `supporting_evidence` is NOT read by `klt signoff` (an unknown top-level key
# is ignored), so it can never move a row. It records klt envelopes that back
# claims the grader has no row for; this script is the only thing that keeps it
# honest, so every entry must name a file that exists and whose sha256 matches.
import hashlib

for i, entry in enumerate(manifest.get("supporting_evidence") or []):
    where = f"supporting_evidence[{i}]"
    path = os.path.join(repo_root, str(entry.get("file", "")))
    if not os.path.isfile(path):
        problems.append(f"{where} cites {entry.get('file')!r}, which is not in the tree")
        continue
    digest = "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()
    if entry.get("content_hash") != digest:
        problems.append(f"{where} content_hash does not match {entry['file']} (now {digest})")

if problems:
    for problem in problems:
        print(f"signoff/verify.sh: {problem}", file=sys.stderr)
    sys.exit(1)
PY

# 2 + 3. Re-grade and compare against the committed verdict.
fresh_report="$(mktemp)"
trap 'rm -f "$fresh_report"' EXIT

rc=0
$KLT signoff --manifest "$manifest" --format json >"$fresh_report" || rc=$?
# 0 = tier T1 (every item met); 3 = tier null (at least one item unmet). Both
# are successful gradings and both are legitimate committed verdicts. 1 and 2
# mean the manifest or the tiers doc could not be read at all.
case "$rc" in
    0 | 3) ;;
    *) fail "klt signoff failed to render a report (exit $rc) -- see the error output above" ;;
esac

if ! diff -u "$committed_report" "$fresh_report"; then
    cat >&2 <<EOF

signoff/verify.sh: the committed verdict no longer matches a fresh grading run.

Either the cited evidence moved (an item's freshness/pass state changed) or the
T1 checklist itself moved (the grading build ships a different
design-evidence-tiers.md). Do not hand-edit signoff/report.json, and do not
re-render it with a host klt: re-run the grader this check used, then read the
diff, update the claim in signoff/README.md to match what actually changed, and
commit both.

    $KLT signoff --manifest signoff/manifest.json --format json > signoff/report.json
EOF
    exit 1
fi

echo "signoff/verify.sh: OK -- committed verdict matches a fresh klt signoff run"
