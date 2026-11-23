#!/usr/bin/env bash
# Re-run place-and-route for antifuse_digital_top (N = 32, the RTL default) and
# refresh the committed artifacts. One local OpenROAD run; no grid.
#   rtl/pnr/run_pnr.sh          run and copy outputs next to this script
#   rtl/pnr/run_pnr.sh --check  cheap provenance check of the committed report
#   rtl/pnr/run_pnr.sh --rerun  full re-run diffed against the committed report
set -euo pipefail
# Run from the repo root: the dockerized openroad wrapper mounts only $PWD, and
# the netlist (rtl/synth) is outside rtl/pnr.
cd "$(dirname "$0")/../.."
KLT=${KLT_CMD:-uvx --from klayout-tools==0.8.0 klt}
D=rtl/pnr
REQ=$D/antifuse_digital_top.pnr.json
REPORT=$D/antifuse_digital_top.pnr.report.json
PDK_ARGS=(--pdk gf180mcuD)
case "${1:-}" in
  --check) exec $KLT place-and-route "$REQ" "${PDK_ARGS[@]}" --check "$REPORT" ;;
  --rerun) exec $KLT place-and-route "$REQ" "${PDK_ARGS[@]}" --check "$REPORT" --rerun ;;
  "") ;;
  *) echo "usage: $0 [--check|--rerun]" >&2; exit 2 ;;
esac
$KLT place-and-route "$REQ" "${PDK_ARGS[@]}" --format json > "$REPORT.tmp"
mv "$REPORT.tmp" "$REPORT"
python3 -I - "$REPORT" <<'PY'
import json, shutil, sys
r = json.load(open(sys.argv[1]))
for key, dst in (("gds_path", "rtl/pnr/antifuse_digital_top.gds"),
                 ("def_path", "rtl/pnr/antifuse_digital_top.def"),
                 ("verilog_path", "rtl/pnr/antifuse_digital_top_routed.v")):
    shutil.copyfile(r[key], dst)
PY
# PRESERVE_RAW=<path> copies the pre-scrub report aside first, for an evidence
# run that must show what klt actually emitted before scrubbing (issue #316).
[ -z "${PRESERVE_RAW:-}" ] || cp "$REPORT" "$PRESERVE_RAW"
python3 -I rtl/scrub_report_paths.py "$REPORT"
# Anything the scrubber could not collapse is an absolute host path; the lint
# stops the run here instead of letting it into the append-only committed
# report (issue #316). Exit 3 on findings, 0 clean.
$KLT env-provenance lint-envelope "$REPORT"
python3 -I rtl/pnr/attest.py
