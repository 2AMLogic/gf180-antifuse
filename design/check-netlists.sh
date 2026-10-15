#!/usr/bin/env bash
#
# Check the committed cell netlists in design/netlists/.
#
#   design/check-netlists.sh
#
# Four checks, all of which must pass:
#
#   4. Program leg / read leg - the three leg netlists elaborate (including the
#      ppolyf_u_2k_6p0 ballast), and the interlock block's truth table
#      (PON = PROG_EN & ~READ_EN, RON = READ_EN & ~PROG_EN) holds at the typical
#      corner. Structure only; the PVT bench is sim/program-read-legs/.
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

# PDK root resolution: $PDK_ROOT first, then ~/.volare - see
# design/lib-pdk-root.sh for the order and why it is shared with
# regen-netlists.sh. This script needs the ngspice model tree, so that is the
# subdirectory a candidate root has to actually hold.
# shellcheck source=design/lib-pdk-root.sh
source "${DESIGN_DIR}/lib-pdk-root.sh"

PDK_ROOT="$(resolve_pdk_root gf180mcuD/libs.tech/ngspice "gf180mcuD model directory")" || exit 1
export PDK_ROOT
MODELS="${PDK_ROOT}/gf180mcuD/libs.tech/ngspice"
echo "using PDK_ROOT=${PDK_ROOT} (models: ${MODELS})"

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
  if grep -qiE '^[[:space:]]*(error|fatal)' "${log}"; then
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
echo "== 4. program leg / read leg elaboration and interlock truth table =="
for nl in leg_interlock program_leg read_leg; do
  cp "${DESIGN_DIR}/netlists/${nl}.spice" "${SCRATCH}/"
done
cp "${DESIGN_DIR}/tb/tb_legs.spice" "${SCRATCH}/"
# The ballast needs the poly-resistor sheet-resistance parameters.
echo ".lib ${MODELS}/sm141064.ngspice res_typical" >> "${SCRATCH}/models.spice"
LEGS_LOG="${SCRATCH}/legs.log"
if ! ( cd "${SCRATCH}" && ngspice -b tb_legs.spice ) > "${LEGS_LOG}" 2>&1 \
   || grep -qiE '^[[:space:]]*(error|fatal)' "${LEGS_LOG}"; then
  echo "ERROR: leg netlists failed to elaborate:" >&2
  sed 's/^/    /' "${LEGS_LOG}" >&2
  exit 1
fi
# value of "<name> = <v>" from the ngspice log
val() { awk -v n="$1" '$1 == n { v = $3 } END { if (v == "") exit 1; print v }' "${LEGS_LOG}"; }
# (PROG_EN, READ_EN) tag: PON = PROG & ~READ, RON = READ & ~PROG
check_state() {
  local tag="$1" want_pon="$2" want_ron="$3" pon ron ok
  pon="$(val "v(pon${tag})")" || { echo "ERROR: no v(pon${tag}) in log" >&2; exit 1; }
  ron="$(val "v(ron${tag})")" || { echo "ERROR: no v(ron${tag}) in log" >&2; exit 1; }
  ok="$(awk -v p="${pon}" -v r="${ron}" -v wp="${want_pon}" -v wr="${want_ron}" \
    'BEGIN { print ((wp ? p > 3.0 : p < 0.3) && (wr ? r > 3.0 : r < 0.3)) ? "yes" : "no" }')"
  if [[ "${ok}" != "yes" ]]; then
    echo "FAIL: interlock state ${tag}: PON=${pon} RON=${ron}, expected PON=${want_pon} RON=${want_ron}" >&2
    exit 1
  fi
  printf 'ok: interlock PROG_EN,READ_EN=%s -> PON=%s RON=%s\n' "${tag}" "${want_pon}" "${want_ron}"
}
check_state 00 0 0
check_state 10 1 0
check_state 01 0 1
check_state 11 0 0
pg="$(val "v(xpg.pg)")"
awk -v v="${pg}" 'BEGIN { exit !(v < 0.5) }' || {
  echo "FAIL: program leg enabled but switch gate xpg.pg = ${pg} (expected ~0 V)" >&2; exit 1; }
echo "ok: program leg elaborates; switch gate at ${pg} V when enabled"

echo
echo "All checks passed."
