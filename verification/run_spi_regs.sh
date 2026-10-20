#!/usr/bin/env bash
# One-command cold start for the SPI register file bench.
#   verification/run_spi_regs.sh          run the bench for all configurations
#   verification/run_spi_regs.sh --lint   lint the RTL (verilator + iverilog) only
#   verification/run_spi_regs.sh --quick  N=32 configuration only (mutation runs)
# Exit status is nonzero if any check fails, any simulation does not report
# "ALL ... TESTS PASSED", or lint reports anything.
# RTL=<file> overrides the DUT source (used for the mutation demonstration).
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
rtl=${RTL:-$root/rtl/antifuse_spi_regs.v}
tb=$here/tb_antifuse_spi_regs.v

lint() {
    local rc=0
    verilator --lint-only -Wall "$rtl" || rc=1
    iverilog -g2005 -Wall -o /dev/null "$rtl" || rc=1
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

# name  N  READ_SETTLE  ARM_TIMEOUT
run_cfg() {
    local n=$1 settle=$2 to=$3
    echo "=== config N=$n READ_SETTLE=$settle ARM_TIMEOUT=$to ==="
    iverilog -g2005 -Wall -o "$work/sim_$n.vvp" \
        -Ptb_antifuse_spi_regs.TB_N="$n" \
        -Ptb_antifuse_spi_regs.TB_SETTLE="$settle" \
        -Ptb_antifuse_spi_regs.TB_TIMEOUT="$to" \
        "$tb" "$rtl" || { echo "compile failed" >&2; status=1; return; }
    vvp -n "$work/sim_$n.vvp" > "$work/out_$n.txt" 2>&1
    cat "$work/out_$n.txt"
    if ! grep -q '^RESULT: ALL .* PASSED' "$work/out_$n.txt" || grep -q 'FAIL' "$work/out_$n.txt"; then
        status=1
    fi
}

run_cfg 32 8 4096     # ratified grid size, default settle
[ "${1:-}" = "--quick" ] || run_cfg 20 200 2048   # second supported N (non power of two, 5-bit address), long settle for BUSY-write tests

if [ $status -eq 0 ]; then echo "ALL CONFIGURATIONS PASSED"; else echo "SUITE FAILED"; fi
exit $status
