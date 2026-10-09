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
# Two further checks cover the array and addressing stage (issue #64):
#
#   4. Region-map drift - design/check-array.py: the generated per-cell
#      candidate type, wcap/lcap/wacc/lacc and the addressing-stage device
#      family match the region map RE-READ FROM spec/split-axis-plan.md, the
#      Candidate 2 drain-to-BL orientation holds, and the slices agree with the
#      full array. (Check 1 also covers the generated array schematics: it runs
#      design/gen_array.py --check.)
#
#   5. Slice function smoke - the committed slice netlists elaborate in ngspice
#      at the typical corner, and with one cell selected that cell conducts
#      while every other cell does not. A build-time check, not evidence: the
#      cornered, per-region record is sim/array-slice-bench/.
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
echo "== 4. array region-map drift =="
python3 -I "${DESIGN_DIR}/check-array.py"

echo
echo "== 5. slice elaboration and selected-cell smoke =="
REPO_ROOT="$(cd "${DESIGN_DIR}/.." && pwd)"
BENCH_TB="${REPO_ROOT}/sim/array-slice-bench/testbench"
if [[ ! -f "${BENCH_TB}/tb_slice_i_ii_typical.spice" ]]; then
  echo "ERROR: ${BENCH_TB}/tb_slice_i_ii_typical.spice missing (run sim/array-slice-bench/make_bench.py)." >&2
  exit 1
fi
# models.spice already carries design.ngspice and the typical sections; the
# bench decks also .include design.ngspice and .lib the 10 V section via $PDK_ROOT;
# models.spice already carries both, so drop those lines for this wrapper.
sed '/design.ngspice/d; /smbb000149/d' "${BENCH_TB}/tb_slice_i_ii_typical.spice" > "${SCRATCH}/tb_slice_i_ii.spice"
sed '/design.ngspice/d; /smbb000149/d' "${BENCH_TB}/tb_slice_ii_iii_typical.spice" > "${SCRATCH}/tb_slice_ii_iii.spice"
# the includes inside the bench decks are relative to the testbench dir
sed -i "s#\.\./\.\./\.\./design/netlists/#${DESIGN_DIR}/netlists/#" "${SCRATCH}"/tb_slice_*.spice

# slice_smoke <slice> <selected-row> <selected-col> <rows...> -- <cols...>
slice_smoke() {
  local sl="$1" sr="$2" sc="$3"; shift 3
  local rows=() cols=() seen=0
  for a in "$@"; do
    if [[ "$a" == "--" ]]; then seen=1; continue; fi
    if [[ "$seen" -eq 0 ]]; then rows+=("$a"); else cols+=("$a"); fi
  done
  local deck="${SCRATCH}/smoke_${sl}_${sr}_${sc}.spice" log="${SCRATCH}/smoke_${sl}_${sr}_${sc}.log"
  {
    echo "* slice smoke deck (generated by check-netlists.sh)"
    echo ".include ${SCRATCH}/models.spice"
    echo ".include ${SCRATCH}/tb_${sl}.spice"
    echo ".control"
    echo "alter vrsel${sr}=3.3"
    echo "alter vcsel${sc}=3.3"
    echo "op"
    for r in "${rows[@]}"; do for c in "${cols[@]}"; do echo "print i(vfil_${r}_${c})"; done; done
    echo ".endc"
    echo ".end"
  } > "${deck}"
  if ! ngspice -b "${deck}" > "${log}" 2>&1 || grep -qiE '^[[:space:]]*(error|fatal)' "${log}"; then
    echo "ERROR: ${sl} did not elaborate/solve with cell (${sr},${sc}) selected" >&2
    sed 's/^/    /' "${log}" | head -40 >&2
    exit 1
  fi
  # selected cell >= 1.5 uA (>=50% of the smallest ideal 3 V / 1 Mohm); every
  # other cell <= 3 nA (1e-3 of it). Typical corner only - not a corner result.
  awk -v sel="i(vfil_${sr}_${sc})" -v sl="${sl}" -v sr="${sr}" -v sc="${sc}" '
    /^i\(vfil_/ { n = $1; v = $NF + 0; if (v < 0) v = -v
                   if (n == sel) { s = v } else if (v > worst) worst = v }
    END { if (s < 1.5e-6) { printf "FAIL: %s selected (%d,%d) draws only %.3g A\n", sl, sr, sc, s > "/dev/stderr"; exit 1 }
          if (worst > 3e-9) { printf "FAIL: %s unselected cell leaks %.3g A with (%d,%d) selected\n", sl, worst, sr, sc > "/dev/stderr"; exit 1 }
          printf "ok: %s select (%d,%d): selected %.3g A, worst unselected %.3g A\n", sl, sr, sc, s, worst }' "${log}" || exit 1
}
slice_smoke slice_i_ii 1 10 0 1 2 3 -- 9 10 11 12
slice_smoke slice_i_ii 2 11 0 1 2 3 -- 9 10 11 12
slice_smoke slice_ii_iii 3 21 0 1 2 3 -- 20 21 22 23
slice_smoke slice_ii_iii 0 22 0 1 2 3 -- 20 21 22 23

echo
echo "All checks passed."
