#!/usr/bin/env bash
#
# Check the committed cell netlists in design/netlists/.
#
#   design/check-netlists.sh [--skip-regen]
#
# --skip-regen skips step 1 (the reproducibility step, including the generator
# --check runs inside regen-netlists.sh) so the script needs no xschem; steps
# 2-7 are unchanged. design/run_analog_cold_start.sh uses it. Without the flag
# the behaviour is exactly as before.
#
# Seven checks, all of which must pass:
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
#   6. Program leg / read leg - the three leg netlists elaborate (including the
#      ppolyf_u_2k_6p0 ballast), and the interlock block's truth table
#      (PON = PROG_EN & ~READ_EN, RON = READ_EN & ~PROG_EN) holds at the typical
#      corner. Structure only; the PVT bench is sim/program-read-legs/.
#
# One further check closes the design/ <-> layout/ geometry boundary (issue #292):
#
#   7. Geometry basis - design/check-geometry-basis.py: the drawn bitcell
#      geometry (the XM1/XC1 literals in layout/cell_*/lvs_reference.spice)
#      against the geometry the committed SPICE evidence was run at (the
#      design/netlists/cell_candidateN.spice defaults and the 2x levels
#      derived from them the same way check 4 derives them). Every divergence
#      must be recorded in design/geometry-basis.json; a recorded entry whose
#      numbers no longer match the tree fails too, so the record cannot go
#      silently stale. Needs no ngspice, PDK or klt.
#
# The two geometry levels used here are a mechanism check, NOT the split-axis
# levels from spec/split-axis-plan.md. The capacitor half of that plan's
# "process-minimum" level is fixed by spec/capacitor-geometry-decision.md
# (Minimum wcap x lcap = 1.0 x 0.28 um for cap_nmos_03v3 / cap_pmos_03v3 and
# 1.0 x 0.70 um for cap_nmos_06v0; "2x" doubles wcap at fixed lcap), while the
# access half (wacc/lacc) - the plan's section-3 axis - is still a PDK
# design-rule lookup with no ratified record behind it. This script therefore
# still uses an arbitrary base geometry and doubles its width: what it proves
# is that the wcap/lcap parameters reach the device instance, not that the
# ratified levels are drawn.
# Nothing here is a device result: no corners are run, and results belong in
# sim/ per CLAUDE.md.

set -euo pipefail

SKIP_REGEN=0
for arg in "$@"; do
  case "${arg}" in
    --skip-regen) SKIP_REGEN=1 ;;
    *)
      echo "ERROR: unknown argument: ${arg}" >&2
      echo "usage: design/check-netlists.sh [--skip-regen]" >&2
      exit 2
      ;;
  esac
done

DESIGN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CELLS=(cell_candidate1 cell_candidate2 cell_candidate3)

# Arbitrary base geometry for the mechanism check only - see header.
BASE_W="1e-6"
BASE_L="1e-6"
DOUBLE_W="2e-6"

# PDK root resolution: $PDK_ROOT first, then ~/.ciel (pinned revision verified) - see
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

if [[ "${SKIP_REGEN}" -eq 0 ]]; then
  echo "== 1. netlist reproducibility =="
  "${DESIGN_DIR}/regen-netlists.sh" --check
else
  echo "== 1. netlist reproducibility == SKIPPED (--skip-regen)"
fi

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
echo "== 6. program leg / read leg elaboration and interlock truth table =="
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
echo "== 7. drawn vs simulated geometry basis (issue #292) =="
python3 -I "${DESIGN_DIR}/check-geometry-basis.py"

echo
echo "All checks passed."
