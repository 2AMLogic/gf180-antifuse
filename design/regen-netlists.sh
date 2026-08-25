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
# xschem is driven in batch (-n -s -q -x) over design/cells/cell_library.sch,
# with split_files enabled by design/xschemrc, so each cell schematic lands in
# its own .spice file carrying a parameterized .subckt line. cell_library.sch
# is a netlist driver, not a circuit - see its header comment for why the cell
# schematics are not netlisted directly.
#
# The only transformation applied to xschem's output is path normalization:
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
DRIVER="${CELLS_DIR}/cell_library.sch"

CELLS=(cell_candidate1 cell_candidate2 cell_candidate3)

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "")      ;;
  *)       echo "usage: $(basename "$0") [--check]" >&2; exit 2 ;;
esac

: "${PDK_ROOT:=${HOME}/.volare}"
export PDK_ROOT

if [[ ! -d "${PDK_ROOT}/gf180mcuD" ]]; then
  echo "ERROR: no gf180mcuD under PDK_ROOT=${PDK_ROOT}" >&2
  echo "       Set PDK_ROOT to the open_pdks/volare install root." >&2
  exit 1
fi

if ! command -v xschem >/dev/null 2>&1; then
  echo "ERROR: xschem not found on PATH." >&2
  exit 1
fi

SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

# xschem's batch exit status is not a success/failure signal: xschem 3.4.7
# exits 10 after netlisting ANY hierarchical schematic, including the PDK's own
# libs.tech/xschem/tests/0_top.sch. So the log is kept and the emitted files are
# what this script actually validates.
XSCHEM_LOG="${SCRATCH}/xschem.log"
set +e
xschem -n -s -q -x -o "${SCRATCH}" --rcfile "${DESIGN_DIR}/xschemrc" "${DRIVER}" \
  >"${XSCHEM_LOG}" 2>&1
set -e

# Normalize the absolute paths xschem stamps into the block header comments.
for cell in "${CELLS[@]}"; do
  src="${SCRATCH}/${cell}.spice"
  if [[ ! -f "${src}" ]]; then
    echo "ERROR: xschem did not emit ${cell}.spice." >&2
    echo "       Is ${cell}.sym instantiated in $(basename "${DRIVER}")," >&2
    echo "       and is split_files set in design/xschemrc?" >&2
    echo "--- xschem output ---" >&2
    sed 's/^/    /' "${XSCHEM_LOG}" >&2
    exit 1
  fi
  sed -i "s#${REPO_ROOT}/##g" "${src}"
done

status=0
mkdir -p "${NETLIST_DIR}"
for cell in "${CELLS[@]}"; do
  src="${SCRATCH}/${cell}.spice"
  dst="${NETLIST_DIR}/${cell}.spice"
  if [[ "${CHECK_ONLY}" -eq 1 ]]; then
    if [[ ! -f "${dst}" ]]; then
      echo "DRIFT: ${dst#"${REPO_ROOT}"/} is missing" >&2
      status=1
    elif ! diff -u "${dst}" "${src}" >/dev/null; then
      echo "DRIFT: ${dst#"${REPO_ROOT}"/} differs from a fresh xschem export:" >&2
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
