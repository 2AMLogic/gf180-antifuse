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
KLT=${KLT_CMD:-uvx --from klayout-tools==0.7.0 klt}
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

# Keep the committed report free of host paths: repo-relative, or ~ for the PDK.
import os
root, home = os.getcwd() + "/", os.path.expanduser("~") + "/"
def clean(v):
    if isinstance(v, str):
        return v.replace(root, "").replace(home, "~/")
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    return v
with open(sys.argv[1], "w") as f:
    json.dump(clean(r), f, indent=2)
    f.write("\n")
PY
python3 -I rtl/pnr/attest.py
