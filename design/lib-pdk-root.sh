#!/usr/bin/env bash
#
# lib-pdk-root.sh - shared gf180mcu PDK root resolution for design/'s shell
# entry points. Sourced, never executed:
#
#   source "${DESIGN_DIR}/lib-pdk-root.sh"
#   PDK_ROOT="$(resolve_pdk_root gf180mcuD)" || exit 1
#   export PDK_ROOT
#
# WHY THIS EXISTS
#
# design/check-netlists.sh and design/regen-netlists.sh both have to find the
# same PDK install before they can run, and both need the same resolution order
# (see resolve_pdk_root below). That order was a bug once already: #49 fixed
# $PDK_ROOT being ignored in favour of ~/.volare, and had to land the identical
# fix twice, in lockstep, because the logic was copied into both scripts. One
# sourced implementation means the next change to it - a third fallback
# location, a `klt pdk`-backed lookup - lands once.
#
# The Python side of the tree resolves the same convention independently in
# sim/harness/pdk.py (resolve_pdk()); that is a different runtime with its own
# return contract and is deliberately not consolidated here.

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "ERROR: lib-pdk-root.sh is a sourced helper, not an executable script." >&2
  echo "       source it from design/check-netlists.sh-style callers instead." >&2
  exit 1
fi

# resolve_pdk_root <required-relative-subdir> [<what>]
#
# Honour $PDK_ROOT (open_pdks'/volare's own variable, and what an
# openlane-shaped toolchain already exports) when it actually holds
# <required-relative-subdir>, and only then fall back to ~/.volare, which is
# one deployment's convention rather than the portable contract.
#
# On success: exports PDK_ROOT as the matched root and echoes it on stdout, for
# `PDK_ROOT="$(resolve_pdk_root ...)"` capture (the export matters only for a
# direct, non-subshell call - a command substitution runs in a subshell, so
# such callers must re-export the captured value themselves).
#
# On failure: prints "ERROR: no <what> found. Looked under: ..." to stderr,
# naming every candidate that was probed, and returns 1. <what> defaults to
# "gf180mcuD"; pass it when the caller needs a more specific noun (e.g.
# "gf180mcuD model directory").
resolve_pdk_root() {
  local required="$1"
  local what="${2:-gf180mcuD}"
  local candidates=()
  local root

  if [[ -n "${PDK_ROOT:-}" ]]; then
    candidates+=("${PDK_ROOT}")
  fi
  if [[ "${PDK_ROOT:-}" != "${HOME}/.volare" ]]; then
    candidates+=("${HOME}/.volare")
  fi

  for root in "${candidates[@]}"; do
    if [[ -d "${root}/${required}" ]]; then
      PDK_ROOT="${root}"
      export PDK_ROOT
      printf '%s\n' "${root}"
      return 0
    fi
  done

  echo "ERROR: no ${what} found. Looked under:" >&2
  for root in "${candidates[@]}"; do
    echo "         ${root}/${required}" >&2
  done
  echo "       Set PDK_ROOT to the open_pdks/volare install root." >&2
  return 1
}
