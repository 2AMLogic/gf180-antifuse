#!/usr/bin/env bash
# One-command cold start for the one-hot decoder bench.
#   verification/run_decode.sh          run the bench for all configurations
#   verification/run_decode.sh --lint   lint the RTL (verilator + iverilog) only
# Exit status is nonzero if any check fails, any simulation does not report
# "ALL ... TESTS PASSED", or lint reports anything.
# RTL=<file> overrides the decoder source (used for the mutation demonstration).
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
rtl=${RTL:-$root/rtl/antifuse_decode.v}
tb=$here/tb_antifuse_decode.v

lint() {
    local rc=0 top=$root/rtl/antifuse_digital_top.v regs=$root/rtl/antifuse_spi_regs.v
    verilator --lint-only -Wall "$rtl" || rc=1
    iverilog -g2005 -Wall -o /dev/null "$rtl" || rc=1
    verilator --lint-only -Wall --top-module antifuse_digital_top "$top" "$regs" "$rtl" || rc=1
    iverilog -g2005 -Wall -s antifuse_digital_top -o /dev/null "$top" "$regs" "$rtl" || rc=1
    return $rc
}

if [ "${1:-}" = "--lint" ]; then
    lint && echo "lint clean" ; exit $?
fi

for t in iverilog vvp; do
    command -v "$t" >/dev/null || { echo "missing tool: $t" >&2; exit 2; }
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
status=0

run_cfg() {
    local n=$1
    echo "=== config N=$n ==="
    iverilog -g2005 -Wall -o "$work/sim_$n.vvp" \
        -Ptb_antifuse_decode.TB_N="$n" "$tb" "$rtl" \
        || { echo "compile failed" >&2; status=1; return; }
    vvp -n "$work/sim_$n.vvp" > "$work/out_$n.txt" 2>&1
    cat "$work/out_$n.txt"
    if ! grep -q '^RESULT: ALL .* PASSED' "$work/out_$n.txt" || grep -q 'FAIL' "$work/out_$n.txt"; then
        status=1
    fi
}

run_cfg 32    # ratified grid size
run_cfg 20    # not a power of two: indices 20..31 fit in 5 bits but select nothing
run_cfg 2     # smallest supported N
run_cfg 256   # largest supported N

if [ $status -eq 0 ]; then echo "ALL CONFIGURATIONS PASSED"; else echo "SUITE FAILED"; fi
exit $status
