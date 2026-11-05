#!/usr/bin/env bash
# Worker-safe analog cold start: elaboration and mechanism checks only.
#   design/run_analog_cold_start.sh
# Runs design/check-netlists.sh --skip-regen: committed-netlist elaboration in
# ngspice, the geometry-parameter sweep, region-map drift, slice smoke and the
# program/read leg interlock truth table. Needs ngspice and the pinned PDK, but
# NOT xschem: the reproducibility step (and the generator checks inside it) is
# skipped. Single typical corner, no grid, no device evidence.
# Exit status is nonzero if any check fails.
set -u
here=$(cd "$(dirname "$0")" && pwd)

"$here/check-netlists.sh" --skip-regen
status=$?

if [ $status -eq 0 ]; then echo "ANALOG COLD START PASSED"; else echo "ANALOG COLD START FAILED"; fi
exit $status
