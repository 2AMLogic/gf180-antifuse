#!/usr/bin/env bash
# Mutation evidence for the program interlock and the single-bit-fault claim.
#   verification/run_spi_mutations.sh
# Each mutant removes one protection from a temporary copy of the RTL; the
# bench (N=32, run_spi_regs.sh --quick) must FAIL on every one. The unmutated
# RTL must pass. Exit status is nonzero if any mutant survives, any mutation
# fails to apply, or the baseline fails.
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
rtl=$root/rtl/antifuse_spi_regs.v
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
status=0

run() { RTL=$1 "$here/run_spi_regs.sh" --quick >"$2" 2>&1; }

run "$rtl" "$work/base.txt" || { echo "BASELINE FAILED"; tail -5 "$work/base.txt"; exit 1; }
echo "baseline: pass"

# name | sed expression applied to the RTL
mutants=(
"arm_guard_removed|s|if (arm) do_fire = 1'b1; else err = 1'b1; // ARM-GUARD|do_fire = 1'b1;|"
"ctrl_strobe_code_restored|s|3'b100: if (arm) err = 1'b1; else do_read = 1'b1;|3'b011: if (arm) do_fire = 1'b1; else err = 1'b1;\n                            3'b100: if (arm) err = 1'b1; else do_read = 1'b1;|"
"fire_address_partial_decode_0x79|s|A_FIRE: begin  |A_FIRE, 7'h79: begin|"
"fire_address_partial_decode_0x7A|s|A_FIRE: begin  |A_FIRE, 7'h7A: begin|"
"row_write_3_while_armed_fires|s|if (in_range) wr_row = 1'b1; else err = 1'b1;|if (in_range) wr_row = 1'b1; else err = 1'b1; if (arm \&\& dat == 8'h03) do_fire = 1'b1;|"
"pw_write_3_while_armed_fires|s|if (dat != 8'h00) wr_pw = 1'b1; else err = 1'b1;|if (dat != 8'h00) wr_pw = 1'b1; else err = 1'b1; if (arm \&\& dat == 8'h03) do_fire = 1'b1;|"
"fire_on_read_command|s|if (a == 7'h04) clr_perr = 1'b1; |if (a == 7'h04) clr_perr = 1'b1; if (a == A_FIRE \&\& arm) do_fire = 1'b1; |"
"overlong_frame_accepted|s|wire        frame_ok  = (bitcnt == 5'd16);|wire        frame_ok  = (bitcnt >= 5'd16);|"
"truncated_frame_accepted|s|wire        frame_ok  = (bitcnt == 5'd16);|wire        frame_ok  = (bitcnt >= 5'd15);|"
)

for m in "${mutants[@]}"; do
    name=${m%%|*}; expr=${m#*|}
    sed -e "$expr" "$rtl" >"$work/$name.v"
    if cmp -s "$rtl" "$work/$name.v"; then echo "[ERROR] $name: mutation did not apply"; status=1; continue; fi
    if run "$work/$name.v" "$work/$name.txt"; then
        echo "[SURVIVED] $name"; status=1
    else
        echo "[killed]   $name ($(grep -c '^\[FAIL\]' "$work/$name.txt") failing tests)"
    fi
done

if [ $status -eq 0 ]; then echo "ALL MUTANTS KILLED"; else echo "MUTATION SUITE FAILED"; fi
exit $status
