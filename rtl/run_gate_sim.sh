#!/usr/bin/env bash
# Gate-level functional verification of the routed antifuse_digital_top.
# No arguments refresh the zero-delay evidence. --sdf regenerates the
# post-route SDF and its annotated report. --check verifies both locally.
# Pinned to klayout-tools git rev 6bd18bbc8637 (unreleased; the `pdk` request
# block it carries is what keeps host PDK paths out of the committed request --
# klayout-tools#6977 -- and its report envelope emits checkout-free artifact
# paths). KLT_CMD overrides the klt invocation (e.g. the host dev install of
# the same rev, which already has cocotb).
set -euo pipefail
cd "$(dirname "$0")/.."
KLT=${KLT_CMD:-uvx --python 3.12 --from "klayout-tools[functional-verification]@git+https://github.com/2AMLogic/klayout-tools.git@6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe" klt}
PIN=6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe
D=verification/cocotb
NET=rtl/pnr/antifuse_digital_top_routed.v
REQ=$D/request_digital_top.json
REPORT=$D/report_digital_top.json
SUMS=$D/inputs_digital_top.sha256
SDF_STA_REQ=rtl/sta/antifuse_digital_top.sdf.json
SDF_REQ=$D/request_digital_top_sdf.json
SDF_REPORT=$D/report_digital_top_sdf.json
SDF=rtl/sta/.klt/sta/antifuse_digital_top.tt_025C_1v80.sdf
INPUTS=("$NET" "$D/test_antifuse_digital_top.py" "$REQ")
SDF_SUMS=$D/inputs_digital_top_sdf.sha256
FV_ARGS=(--format json)
if [[ -n "${PDK_ROOT:-}" ]]; then FV_ARGS+=(--pdk-root "$PDK_ROOT"); fi

check_report() {
python3 -I - "$1" "$2" "$3" "$NET" "$PIN" "$D/test_antifuse_digital_top.py" "$SDF_STA_REQ" "$SDF" "${4:-}" <<'PY'
import hashlib, json, re, sys
from pathlib import Path
rep, request, mode, net, pin, suite, sta_request, sdf_path, live_sdf = sys.argv[1:]
r = json.load(open(rep))
assert r["schema_version"] == 2, r["schema_version"]
assert r["engine"] == "icarus" and r["hdl_toplevel"] == "antifuse_digital_top"
assert r["testbench"] == "test_antifuse_digital_top"
assert r["status"] == "pass", r["status"]
assert r["failed_count"] == 0 and r["skipped_count"] == 0 and r["passed_count"] == r["test_count"] > 0
e = r["environment"]
assert e["engine_version"] == "13.0", "iverilog drift"  # -ginterconnect floor
assert e["cocotb_version"] and e["random_seed"] == 1
req = json.loads(Path(request).read_text())
canonical = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
assert hashlib.sha256(canonical).hexdigest() == r["provenance"]["request_sha256"]
assert e["env"] == req.get("env", {})
if mode == "sdf":
    period = json.loads(Path(sta_request).read_text())["constraints"]["clock_period_ns"]
    assert int(e["env"]["ANTIFUSE_GATE_CLOCK_NS"]) == period
    assert e["sdf"]["annotated"] is True and e["sdf"]["corner"] == "typ"
    assert e["sdf"]["file"] == sdf_path
    sys.path.insert(0, str(Path("scripts").resolve()))
    from check_signoff_pins import verify_routed_sdf
    citation = json.loads(Path("signoff/manifest.json").read_text())["evidence"]["7.digital"]
    verify_routed_sdf(citation, r, Path(live_sdf) if live_sdf else None)
else:
    assert e["sdf"] is None
assert e["initial_state"] is None
assert r["provenance"]["klt_git_commit"] == pin, r["provenance"]["klt_git_commit"]
srcs = e["sources"]
netrel = "rtl/pnr/antifuse_digital_top_routed.v"
assert any(s["path"] == netrel and s["scope"] == "repo" and
           s["sha256"] == hashlib.sha256(Path(net).read_bytes()).hexdigest()
           for s in srcs), srcs
ext = [s for s in srcs if s["scope"] == "external"]
assert len(ext) == 2 and all(s["path"] is None and s["sha256"] for s in ext), \
    "PDK cell models (primitives + library) must be the two external sources"
names = {t["name"] for t in r["tests"]}
for want in ("reset_values_and_idle_outputs", "program_full_sequence",
             "decoder_onehot_all_indices", "read_settle_cycle_count_and_data",
             "arm_timeout_expires", "arm_timeout_boundary"):
    assert want in names, want
# port-only discipline: no hierarchical reference into the netlist beyond
# <dut>.<port>.value / <dut>._log, whichever way the suite spells the receiver
# (dut, self.dut, b.dut or any attribute chain ending in dut, or the d = self.dut
# alias); matches are a failure
hier_re = re.compile(
    r"(?<![A-Za-z_0-9.])(?:(?:[A-Za-z_0-9]+\.)*dut|d)\.(?!_log\b)[A-Za-z_0-9]+\.(?!value\b)")
with open(suite) as fh:
    hier = [f"{n}:{line.rstrip()}" for n, line in enumerate(fh, 1) if hier_re.search(line)]
assert not hier, "hierarchical reference(s) in the suite:\n" + "\n".join(hier)
print(f"report ok: {r['passed_count']}/{r['test_count']} tests, "
      f"{mode} gate-level, {len(srcs)} sources incl. PDK models")
PY
}

live_sdf=
case "${1:-}" in
  --check)
    sha256sum --check --strict "$SUMS" "$SDF_SUMS"
    check_report "$REPORT" "$REQ" zero-delay
    check_report "$SDF_REPORT" "$SDF_REQ" sdf
    exit 0 ;;
  "") mode=zero-delay ;;
  --sdf)
    mode=sdf
    live_sdf=$SDF
    REPORT=$SDF_REPORT
    REQ=$SDF_REQ
    FV_ARGS+=(-o "$D/.klt/sdf")
    SUMS=$SDF_SUMS
    INPUTS=("$NET" "$D/test_antifuse_digital_top.py" "$REQ" "$SDF_STA_REQ"
            rtl/pnr/antifuse_digital_top.def rtl/sta/antifuse_digital_top.spef)
    $KLT sta "$SDF_STA_REQ" --pdk gf180mcuD --format json > /dev/null
    # OpenSTA writes a wall-clock DATE into every generated SDF. This optional
    # header has no timing content. Omit it for a stable provenance digest.
    sed '/^ (DATE "/d' "$SDF" > "$SDF.tmp"
    mv "$SDF.tmp" "$SDF"
    ;;
  *) echo "usage: $0 [--check|--sdf]" >&2; exit 2 ;;
esac

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
$KLT functional-verification "$REQ" "${FV_ARGS[@]}" > "$tmp/raw.json"
python3 -I rtl/scrub_report_paths.py "$tmp/raw.json" "$tmp/report.json"
$KLT env-provenance lint-envelope "$tmp/report.json"
check_report "$tmp/report.json" "$REQ" "$mode" "$live_sdf"
mv "$tmp/report.json" "$REPORT"
sha256sum "${INPUTS[@]}" > "$SUMS"
