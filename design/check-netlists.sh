#!/usr/bin/env bash
#
# Check the committed cell netlists in design/netlists/.
#
#   design/check-netlists.sh
#
# Three checks, all of which must pass:
#
#   1. Reproducibility - design/regen-netlists.sh --check: a fresh xschem
#      export of every cell schematic is byte-identical to what is committed.
#
#   2. Elaboration - each committed netlist elaborates cleanly in ngspice
#      against the pinned PDK model files, driven by the matching deck in
#      design/tb/. sm141064.ngspice for Candidates 1 and 3; Candidate 2 also
#      needs smbb000149.ngspice for nfet_10v0_asym.
#
#   3. Geometry parameter sweep - each cell is elaborated twice, at a base
#      capacitor geometry and at 2x area, WITHOUT editing the schematic or the
#      netlist: only the generated geometry.spice changes. The capacitor branch
#      current at 2x area must be 2x the base current, which is what proves the
#      wcap/lcap subcircuit parameters actually reach the device instance.
#
# The two geometry levels used here are a mechanism check, NOT the split-axis
# levels from spec/split-axis-plan.md. That plan's "process-minimum" level is a
# PDK design-rule lookup that no ratified spec document fixes yet, so this
# script deliberately uses an arbitrary base geometry and doubles its width.
# Nothing here is a device result: no corners are run, and results belong in
# sim/ per CLAUDE.md.

set -euo pipefail

DESIGN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CELLS=(cell_candidate1 cell_candidate2 cell_candidate3)

# Arbitrary base geometry for the mechanism check only - see header.
BASE_W="1e-6"
BASE_L="1e-6"
DOUBLE_W="2e-6"

: "${PDK_ROOT:=${HOME}/.volare}"
export PDK_ROOT
MODELS="${PDK_ROOT}/gf180mcuD/libs.tech/ngspice"

if [[ ! -d "${MODELS}" ]]; then
  echo "ERROR: no gf180mcuD model directory at ${MODELS}" >&2
  exit 1
fi
if ! command -v ngspice >/dev/null 2>&1; then
  echo "ERROR: ngspice not found on PATH." >&2
  exit 1
fi

echo "== 1. netlist reproducibility =="
"${DESIGN_DIR}/regen-netlists.sh" --check

SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

cat > "${SCRATCH}/models.spice" <<EOF
* Pinned gf180mcuD model libraries, resolved from PDK_ROOT at check time.
.include ${MODELS}/design.ngspice
.lib ${MODELS}/sm141064.ngspice typical
.lib ${MODELS}/sm141064.ngspice moscap_typical
.lib ${MODELS}/smbb000149.ngspice typical
EOF

for cell in "${CELLS[@]}"; do
  cp "${DESIGN_DIR}/netlists/${cell}.spice" "${SCRATCH}/"
  cp "${DESIGN_DIR}/tb/tb_${cell}.spice" "${SCRATCH}/"
done

# Capacitor branch current magnitude for one cell at one geometry.
# Echoes the ngspice log to stderr on failure so the caller can see why.
run_cell() {
  local cell="$1" w="$2" l="$3"
  local log="${SCRATCH}/${cell}_${w}.log"

  cat > "${SCRATCH}/geometry.spice" <<EOF
.param wcell=${w}
.param lcell=${l}
EOF

  if ! ( cd "${SCRATCH}" && ngspice -b "tb_${cell}.spice" ) > "${log}" 2>&1; then
    echo "ERROR: ngspice exited non-zero for ${cell} at wcap=${w}" >&2
    sed 's/^/    /' "${log}" >&2
    return 1
  fi
  if grep -qiE '^\s*(error|fatal)' "${log}"; then
    echo "ERROR: ngspice reported an error for ${cell} at wcap=${w}" >&2
    sed 's/^/    /' "${log}" >&2
    return 1
  fi

  # "mag(i(vpl)) = <value>" from the single-point .ac sweep.
  local mag
  mag="$(awk '/mag\(i\(vpl\)\)/ { v = $NF } END { if (v == "") exit 1; print v }' "${log}")" || {
    echo "ERROR: could not read mag(i(vpl)) out of ${cell} at wcap=${w}" >&2
    sed 's/^/    /' "${log}" >&2
    return 1
  }
  printf '%s\n' "${mag}"
}

echo
echo "== 2/3. ngspice elaboration and capacitor geometry sweep =="
for cell in "${CELLS[@]}"; do
  i1="$(run_cell "${cell}" "${BASE_W}" "${BASE_L}")"
  i2="$(run_cell "${cell}" "${DOUBLE_W}" "${BASE_L}")"

  ratio="$(awk -v a="${i1}" -v b="${i2}" 'BEGIN { if (a+0 == 0) exit 1; printf "%.4f", b/a }')" || {
    echo "ERROR: ${cell} drew no capacitor current at the base geometry" >&2
    exit 1
  }

  ok="$(awk -v r="${ratio}" 'BEGIN { print (r > 1.99 && r < 2.01) ? "yes" : "no" }')"
  if [[ "${ok}" != "yes" ]]; then
    echo "FAIL: ${cell}: doubling wcap changed the capacitor branch current by" >&2
    echo "      ${ratio}x, expected 2x. The wcap parameter is not reaching the" >&2
    echo "      capacitor instance." >&2
    exit 1
  fi
  printf 'ok: %s elaborates; wcap %s -> %s scales i(vpl) by %sx\n' \
    "${cell}" "${BASE_W}" "${DOUBLE_W}" "${ratio}"
done

echo
echo "All checks passed."
