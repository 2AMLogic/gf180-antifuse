#!/usr/bin/env bash
# Gate-level functional verification of the routed antifuse_digital_top.
# One `klt functional-verification` request whose source is the routed netlist
# rtl/pnr/antifuse_digital_top_routed.v (N = 32 baked in) with the
# gf180mcu_fd_sc_mcu7t5v0 behavioural cell models resolved from the PDK by the
# request's `pdk` block (zero-delay FUNCTIONAL branch; no SDF -- see the
# --sdf leg and rtl/README.md "Gate-level functional verification").
#   rtl/run_gate_sim.sh          run the suite, refresh the report + input hashes
#   rtl/run_gate_sim.sh --check  verify input hashes and report shape; no simulator
#   rtl/run_gate_sim.sh --sdf    re-attempt the SDF-annotated leg (issue #445
#                                records it failing: klayout-tools#6991; exit is
#                                nonzero while that stands -- that nonzero IS the
#                                recorded outcome, the zero-delay report above
#                                stays the committed evidence)
# Pinned to klayout-tools git rev 6bd18bbc8637 (unreleased; the `pdk` request
# block it carries is what keeps host PDK paths out of the committed request --
# klayout-tools#6977 -- and its report envelope emits checkout-free artifact
# paths). KLT_CMD overrides the klt invocation (e.g. the host dev install of
# the same rev, which already has cocotb).
set -euo pipefail
cd "$(dirname "$0")/.."
KLT=${KLT_CMD:-uvx --from "klayout-tools[functional-verification]@git+https://github.com/2AMLogic/klayout-tools.git@6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe" klt}
PIN=6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe
D=verification/cocotb
NET=rtl/pnr/antifuse_digital_top_routed.v
REQ=$D/request_digital_top.json
REPORT=$D/report_digital_top.json
SUMS=$D/inputs_digital_top.sha256
SDF_STA_REQ=rtl/sta/antifuse_digital_top.sdf.json
SDF_REQ=$D/request_digital_top_sdf.json
INPUTS=($NET $D/test_antifuse_digital_top.py $REQ $SDF_STA_REQ $SDF_REQ)

check_report() {
python3 -I - "$REPORT" "$NET" "$PIN" "$D/test_antifuse_digital_top.py" <<'PY'
import json, re, subprocess, sys
rep, net, pin, suite = sys.argv[1:5]
r = json.load(open(rep))
assert r["schema_version"] == 2, r["schema_version"]
assert r["engine"] == "icarus" and r["hdl_toplevel"] == "antifuse_digital_top"
assert r["testbench"] == "test_antifuse_digital_top"
assert r["status"] == "pass", r["status"]
assert r["failed_count"] == 0 and r["skipped_count"] == 0 and r["passed_count"] == r["test_count"] > 0
e = r["environment"]
assert e["engine_version"] == "13.0", "iverilog drift"  # -ginterconnect floor
assert e["cocotb_version"] and e["random_seed"] == 1
assert e["sdf"] is None, "committed evidence must be the unannotated run"
assert e["initial_state"] is None
assert r["provenance"]["klt_git_commit"] == pin, r["provenance"]["klt_git_commit"]
srcs = e["sources"]
netrel = "rtl/pnr/antifuse_digital_top_routed.v"
assert any(s["path"] == netrel and s["scope"] == "repo" for s in srcs), srcs
ext = [s for s in srcs if s["scope"] == "external"]
assert len(ext) == 2 and all(s["path"] is None and s["sha256"] for s in ext), \
    "PDK cell models (primitives + library) must be the two external sources"
names = {t["name"] for t in r["tests"]}
for want in ("reset_values_and_idle_outputs", "program_full_sequence",
             "decoder_onehot_all_indices", "read_settle_cycle_count_and_data",
             "arm_timeout_expires", "arm_timeout_boundary"):
    assert want in names, want
# port-only discipline: no hierarchical reference into the netlist beyond
# dut.<port>.value / dut._log (grep -P; matches are a failure)
hier = subprocess.run(
    ["grep", "-nP", r"dut\.(?!_log\b)[A-Za-z_0-9]+\.(?!value\b)", suite],
    capture_output=True, text=True)
assert hier.returncode == 1, f"hierarchical reference(s) in the suite:\n{hier.stdout}"
print(f"report ok: {r['passed_count']}/{r['test_count']} tests, "
      f"zero-delay gate-level, {len(srcs)} sources incl. PDK models")
PY
}

case "${1:-}" in
  --check)
    sha256sum --check --strict "$SUMS"
    check_report
    exit 0 ;;
  "") ;;
  --sdf)
    # 1. one SDF per corner from the same committed DEF + SPEF the STA flow
    #    uses (write_sdf -divider . -include_typ), tt_025C_1v80 only.
    $KLT sta "$SDF_STA_REQ" --pdk gf180mcuD --format json > /dev/null
    # 2. the same suite, SDF-annotated (timing-branch models, corner typ).
    set +e
    $KLT functional-verification "$SDF_REQ" --format json -o verification/cocotb/.klt/sdf_attempt > /tmp/gate_sim_sdf.json
    rc=$?
    set -e
    if [ "$rc" -ne 0 ]; then
      echo "SDF leg FAILED (exit $rc) -- the outcome issue #445 records:"
      echo "  partial annotation drops state-dependent and ifnone-edge arcs"
      echo "  (klayout-tools#6991) and the run fails functionally."
      echo "  The unannotated report stays the committed evidence; 7.digital stays unmet."
    else
      echo "SDF leg PASSED -- rtl/README.md and issue #445 need updating:"
      echo "  the SDF run becomes citable evidence for 7.digital."
    fi
    exit "$rc" ;;
  *) echo "usage: $0 [--check|--sdf]" >&2; exit 2 ;;
esac

$KLT functional-verification "$REQ" --format json > "$REPORT.tmp"
python3 -I rtl/scrub_report_paths.py "$REPORT.tmp" "$REPORT"
# Anything the scrubber could not collapse is an absolute host path; the lint
# stops the run here instead of letting it into the committed report
# (issue #316), as in rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh.
$KLT env-provenance lint-envelope "$REPORT"
rm -f "$REPORT.tmp"
sha256sum "${INPUTS[@]}" > "$SUMS"
check_report
