#!/usr/bin/env bash
#
# Regenerate the committed SPICE netlists in design/netlists/ from the xschem
# schematics in design/cells/.
#
#   design/regen-netlists.sh           regenerate in place
#   design/regen-netlists.sh --check   regenerate to a scratch dir and diff
#                                      against what is committed; non-zero exit
#                                      if they differ
#
# The --check mode is the T1 "regenerated on design change" pass condition:
# the committed netlist must be reproducible from the committed schematic, not
# a one-off drop.
#
# How the netlists are produced
# -----------------------------
# Every export goes through `klt netlist` (klayout-tools), which owns the
# xschem invocation: xschem's headless flags are always passed, the run is
# bounded by a wall-clock timeout with SIGTERM -> SIGKILL escalation over the
# whole process group, and the exit status is real. Raw `xschem -n -s -q -x`
# offers none of that (a GUI-initialised run can hang for hours, and xschem
# 3.4.7 exits 10 after netlisting any hierarchical schematic), and workers may
# not run raw xschem at all - the --check mode below is the worker-safe
# freshness check that constraint previously blocked.
#
# klt netlist is driven over design/cells/cell_library.sch with --output-dir,
# with split_files enabled by design/xschemrc, so each cell schematic lands in
# its own .spice file carrying a parameterized .subckt line. cell_library.sch
# is a netlist driver, not a circuit - see its header comment for why the cell
# schematics are not netlisted directly.
#
# The array and addressing stage (design/array/, design/mux/) are netlisted the
# same way from design/array/array_library.sch. Their schematics for the array
# and slices are emitted by design/gen_array.py, which this script runs first
# (or, under --check, runs in --check mode to prove the committed schematics
# are what the generator produces) - see that file's header. The program / read
# leg schematics in design/cells/ come from design/tools/gen_leg_schematics.py,
# which is run (or --check'd) the same way; both generators share
# design/tools/xschem_emit.py.
#
# The only transformations applied to xschem's output are path normalization
# and continuation-line unwrapping (see below):
# xschem stamps the absolute filesystem path of each schematic and symbol into
# two "** sym_path:" / "** sch_path:" comment lines, which would otherwise make
# the committed netlist depend on where the repository happens to be checked
# out. This script rewrites that prefix to a repo-relative path so the netlists
# are byte-identical from any checkout. No circuit content is touched.

set -euo pipefail

DESIGN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${DESIGN_DIR}/.." && pwd)"
CELLS_DIR="${DESIGN_DIR}/cells"
NETLIST_DIR="${DESIGN_DIR}/netlists"
DRIVERS=("${CELLS_DIR}/cell_library.sch" "${CELLS_DIR}/leg_library.sch")
ARRAY_DRIVER="${DESIGN_DIR}/array/array_library.sch"

CELLS=(cell_candidate1 cell_candidate2 cell_candidate3 leg_interlock program_leg read_leg)
# Netlists exported from ARRAY_DRIVER. array_32x32 and the slices are generated
# schematics; the ls_/pg_ cells are the addressing-stage building blocks.
ARRAY_NETLISTS=(ls_hv06 ls_hv10 pg_n06 pg_n10 array_32x32 slice_i_ii slice_ii_iii band_i band_ii band_iii)

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "")      ;;
  *)       echo "usage: $(basename "$0") [--check]" >&2; exit 2 ;;
esac

# PDK root resolution: $PDK_ROOT first, then ~/.ciel (pinned revision verified) - see
# design/lib-pdk-root.sh for the order and why it is shared with
# check-netlists.sh. This script drives xschem only through `klt netlist`,
# which resolves the PDK the same way and cross-checks it against
# design/xschemrc, so bare gf180mcuD is enough of a candidate root to require.
# shellcheck source=design/lib-pdk-root.sh
source "${DESIGN_DIR}/lib-pdk-root.sh"

PDK_ROOT="$(resolve_pdk_root gf180mcuD)" || exit 1
export PDK_ROOT
echo "using PDK_ROOT=${PDK_ROOT}"

if ! command -v klt >/dev/null 2>&1; then
  echo "ERROR: klt (klayout-tools) not found on PATH." >&2
  exit 1
fi

# Sources first: the array/slice schematics are generated, so the netlists can
# only be as current as they are. Under --check nothing is rewritten; the
# generator just has to reproduce the committed sources byte for byte.
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH (needed for design/gen_array.py)." >&2
  exit 1
fi
if [[ "${CHECK_ONLY}" -eq 1 ]]; then
  python3 -I "${DESIGN_DIR}/gen_array.py" --check >/dev/null || {
    python3 -I "${DESIGN_DIR}/gen_array.py" --check >&2 || true
    exit 1
  }
  echo "ok: generated array/mux schematics reproduce exactly"
  python3 -I "${DESIGN_DIR}/tools/gen_leg_schematics.py" --check >/dev/null || {
    python3 -I "${DESIGN_DIR}/tools/gen_leg_schematics.py" --check >&2 || true
    exit 1
  }
  echo "ok: generated leg schematics reproduce exactly"
else
  python3 -I "${DESIGN_DIR}/gen_array.py" >/dev/null
  echo "regenerated array/mux schematics (design/gen_array.py)"
  python3 -I "${DESIGN_DIR}/tools/gen_leg_schematics.py" >/dev/null
  echo "regenerated leg schematics (design/tools/gen_leg_schematics.py)"
fi

SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

# klt netlist reports a real exit status, so a failed export aborts right here
# with klt's own diagnostics (raw xschem's was useless: 3.4.7 exits 10 after
# netlisting ANY hierarchical schematic, including the PDK's own
# libs.tech/xschem/tests/0_top.sch). Generation is still judged by the stem
# netlist, though, so the emitted files are validated by name below: a
# silently missing split_files output must be caught even when the driver
# export itself succeeds. The log is kept for those by-name error paths.
KLT_LOG="${SCRATCH}/klt.log"
: >"${KLT_LOG}"
for DRIVER in "${DRIVERS[@]}"; do
  if ! klt netlist "${DRIVER}" \
      --output-dir "${SCRATCH}" \
      --rcfile "${DESIGN_DIR}/xschemrc" \
      --pdk gf180mcuD \
      --backend local \
      --timeout-s 120 \
      --no-provenance-header \
      >>"${KLT_LOG}" 2>&1; then
    echo "ERROR: klt netlist failed for $(basename "${DRIVER}")." >&2
    sed 's/^/    /' "${KLT_LOG}" >&2
    exit 1
  fi
done

ARRAY_SCRATCH="${SCRATCH}/array"
mkdir -p "${ARRAY_SCRATCH}"
if ! klt netlist "${ARRAY_DRIVER}" \
    --output-dir "${ARRAY_SCRATCH}" \
    --rcfile "${DESIGN_DIR}/xschemrc" \
    --pdk gf180mcuD \
    --backend local \
    --timeout-s 120 \
    --no-provenance-header \
    >>"${KLT_LOG}" 2>&1; then
  echo "ERROR: klt netlist failed for $(basename "${ARRAY_DRIVER}")." >&2
  sed 's/^/    /' "${KLT_LOG}" >&2
  exit 1
fi
for nl in "${ARRAY_NETLISTS[@]}"; do
  if [[ ! -f "${ARRAY_SCRATCH}/${nl}.spice" ]]; then
    echo "ERROR: klt netlist did not emit ${nl}.spice from $(basename "${ARRAY_DRIVER}")." >&2
    sed 's/^/    /' "${KLT_LOG}" >&2
    exit 1
  fi
  sed "s#${REPO_ROOT}/##g" "${ARRAY_SCRATCH}/${nl}.spice" >"${SCRATCH}/${nl}.spice"
done

# Normalize the absolute paths xschem stamps into the block header comments.
for cell in "${CELLS[@]}" "${ARRAY_NETLISTS[@]}"; do
  src="${SCRATCH}/${cell}.spice"
  if [[ ! -f "${src}" ]]; then
    echo "ERROR: klt netlist did not emit ${cell}.spice." >&2
    echo "       Is ${cell}.sym instantiated in a driver schematic (cell_library.sch / leg_library.sch)," >&2
    echo "       and is split_files set in design/xschemrc?" >&2
    echo "--- klt netlist output ---" >&2
    sed 's/^/    /' "${KLT_LOG}" >&2
    exit 1
  fi
  # Portable in-place edit: GNU sed's bare `-i` and BSD/macOS sed's
  # `-i <suffix>` are mutually incompatible spellings, so neither form runs on
  # both hosts. Substituting through a temp file and moving it back is the one
  # spelling that is identical on both, and leaves no stray backup file behind
  # if sed fails (set -e aborts before the mv).
  #
  # Second normalization: xschem's line-wrapping of long device lines differs
  # between versions (3.4.4 wraps at a different column than 3.4.7), which is
  # pure formatting. Continuation lines ("+ ...") are joined onto their parent
  # line so the committed netlist does not depend on the xschem version.
  sed "s#${REPO_ROOT}/##g" "${src}" \
    | awk '/^\+/ { sub(/^\+ */, " "); buf = buf $0; next }
           { if (buf != "") print buf; buf = $0 }
           END { if (buf != "") print buf }' >"${src}.tmp"
  mv "${src}.tmp" "${src}"
done

status=0
mkdir -p "${NETLIST_DIR}"
for cell in "${CELLS[@]}" "${ARRAY_NETLISTS[@]}"; do
  src="${SCRATCH}/${cell}.spice"
  dst="${NETLIST_DIR}/${cell}.spice"
  if [[ "${CHECK_ONLY}" -eq 1 ]]; then
    if [[ ! -f "${dst}" ]]; then
      echo "DRIFT: ${dst#"${REPO_ROOT}"/} is missing" >&2
      status=1
    elif ! diff -u "${dst}" "${src}" >/dev/null; then
      echo "DRIFT: ${dst#"${REPO_ROOT}"/} differs from a fresh klt netlist export:" >&2
      diff -u --label "committed" --label "regenerated" "${dst}" "${src}" >&2 || true
      status=1
    else
      echo "ok: ${dst#"${REPO_ROOT}"/} reproduces exactly"
    fi
  else
    cp "${src}" "${dst}"
    echo "wrote: ${dst#"${REPO_ROOT}"/}"
  fi
done

if [[ "${CHECK_ONLY}" -eq 1 && "${status}" -ne 0 ]]; then
  echo >&2
  echo "Committed netlists are out of date. Run design/regen-netlists.sh." >&2
fi
exit "${status}"
