#!/usr/bin/env bash
# Re-run the digital gate-level LVS (abstract-cell extraction, then klt lvs
# against the routed gate-level Verilog with power_connectivity). Single local
# units; no grid. Needs a klt with the upstream abstract-cell fixes: pass
# KLT_CMD="uvx --from git+https://github.com/2AMLogic/klayout-tools@<sha> klt".
#   rtl/pnr/run_lvs.sh          extract + compare, rewrite the committed report
#   rtl/pnr/run_lvs.sh --check  cheap freshness check of the committed report
set -euo pipefail
cd "$(dirname "$0")/../.."
KLT=${KLT_CMD:?set KLT_CMD to the klt launcher (see header)}
D=rtl/pnr
REQ=$D/antifuse_digital_top.lvs.json
REPORT=$D/antifuse_digital_top.lvs.report.json
[ "${1:-}" != --check ] || exec $KLT lvs --check "$REPORT"
$KLT extract $D/antifuse_digital_top.gds --deck gf180mcu --pdk gf180mcuD \
  --abstract-cells 'gf180mcu_fd_sc_mcu7t5v0__*' --def-net-names \
  --top antifuse_digital_top -o $D/antifuse_digital_top.gate.spice --format json >/dev/null
$KLT lvs "$REQ" --format json > "$REPORT.tmp"
mv "$REPORT.tmp" "$REPORT"
