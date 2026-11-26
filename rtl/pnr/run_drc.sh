#!/usr/bin/env bash
# Re-run klt drc on the routed GDS and refresh the committed report. One local
# klt drc run (a single unit); no grid.
#   rtl/pnr/run_drc.sh          run and rewrite the report next to this script
#   rtl/pnr/run_drc.sh --check  cheap freshness check of the committed report
#   rtl/pnr/run_drc.sh --rerun  full re-run diffed against the committed report
set -euo pipefail
cd "$(dirname "$0")/../.."
KLT=${KLT_CMD:-uvx --from klayout-tools==0.8.0 klt}
D=rtl/pnr
GDS=$D/antifuse_digital_top.gds
REPORT=$D/antifuse_digital_top.drc.json
ARGS=(--deck gf180mcu --top antifuse_digital_top --pdk gf180mcuD)
case "${1:-}" in
  --check) exec $KLT drc "$GDS" "${ARGS[@]}" --check "$REPORT" ;;
  --rerun) exec $KLT drc "$GDS" "${ARGS[@]}" --check "$REPORT" --rerun ;;
  "") ;;
  *) echo "usage: $0 [--check|--rerun]" >&2; exit 2 ;;
esac
# Exit 3 = violations found; the report is still written so it can be read.
rc=0
$KLT drc "$GDS" "${ARGS[@]}" --format json > "$REPORT.tmp" || rc=$?
[ "$rc" -le 3 ] || { rm -f "$REPORT.tmp"; exit "$rc"; }
mv "$REPORT.tmp" "$REPORT"
exit "$rc"
