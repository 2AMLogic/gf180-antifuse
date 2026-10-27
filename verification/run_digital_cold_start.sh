#!/usr/bin/env bash
# Single cold-start command for the digital-partition attestation
# (signoff/inventories/item-9-digital.json lists exactly one `cold_start`).
#   verification/run_digital_cold_start.sh
# Runs, in order: the SPI register file bench, the one-hot decoder bench, and
# the port-only cocotb suite (request_spi_regs.json). Exit status is nonzero if
# any of them fails; a missing cocotb fails the run rather than skipping it.
# The mutation runs (run_spi_mutations.sh) are not part of this: they are
# expected to fail by design.
set -u
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/.." && pwd)
cd "$root" || exit 2
KLT_PIN=${KLT_PIN:-0.8.0}
status=0

"$here/run_spi_regs.sh" || status=1
"$here/run_decode.sh" || status=1

out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
uvx --from "klayout-tools[functional-verification]==$KLT_PIN" klt \
    functional-verification verification/cocotb/request_spi_regs.json \
    -o "$out" --format json >"$out/envelope.json" || status=1
cat "$out/envelope.json"

if [ $status -eq 0 ]; then echo "DIGITAL COLD START PASSED"; else echo "DIGITAL COLD START FAILED"; fi
exit $status
