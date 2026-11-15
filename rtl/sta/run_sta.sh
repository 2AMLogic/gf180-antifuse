#!/usr/bin/env bash
# Post-route, SPEF-annotated, multi-corner STA of the routed antifuse_digital_top.
# Two local steps, no grid: `klt extract --parasitics` writes the SPEF from the
# routed GDS, then ONE `klt sta` request times that fixed geometry at every
# corner listed in rtl/pnr/antifuse_digital_top.pnr.report.json.
#   rtl/sta/run_sta.sh          run both steps, refresh the report + inputs.sha256
#   rtl/sta/run_sta.sh --check  verify input hashes and report shape; no OpenROAD
set -euo pipefail
cd "$(dirname "$0")/../.."
KLT=${KLT_CMD:-uvx --from klayout-tools==0.8.0 klt}
D=rtl/sta
P=rtl/pnr
EXTRACT_REQ=$D/antifuse_digital_top.extract.json
STA_REQ=$D/antifuse_digital_top.sta.json
REPORT=$D/antifuse_digital_top.sta.report.json
SPEF=$D/antifuse_digital_top.spef
SUMS=$D/inputs.sha256
INPUTS=($P/antifuse_digital_top.gds $P/antifuse_digital_top.def
        $P/antifuse_digital_top_routed.v $SPEF $EXTRACT_REQ $STA_REQ)

check_report() {
python3 -I - "$P/antifuse_digital_top.pnr.report.json" "$REPORT" "$STA_REQ" <<'PY'
import json, sys
pnr, rep, req = (json.load(open(p)) for p in sys.argv[1:4])
want = [c["name"] for c in pnr["corners"]]
got = [c["corner"] for c in rep["corners"]]
assert got == want, f"corner list drifted: {got} != {want}"
assert req["pdk"]["corners"] == want, "sta request does not name every P&R corner"
assert req["constraints"] == {"clock_port": "clk", "clock_period_ns": 50}
assert rep["geometry_source"] == "routed" and rep["status"] == "ok"
assert rep["spef_path"]["path"] == "rtl/sta/antifuse_digital_top.spef"
for c in rep["corners"]:
    a = c["spef_annotation"]
    assert a["annotation_complete"] and a["design_nets_annotated"] == a["design_nets_total"], c["corner"]
print(f"report ok: {len(got)} corners, all SPEF-annotated")
PY
}

case "${1:-}" in
  --check)
    sha256sum --check --strict "$SUMS"
    check_report
    exit 0 ;;
  "") ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

$KLT extract "$EXTRACT_REQ" --format json > /dev/null
$KLT sta "$STA_REQ" --pdk gf180mcuD --format json > "$REPORT.tmp"
python3 -I rtl/scrub_report_paths.py "$REPORT.tmp" "$REPORT"
rm -f "$REPORT.tmp"
sha256sum "${INPUTS[@]}" > "$SUMS"
check_report
