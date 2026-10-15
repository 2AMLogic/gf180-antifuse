# Decision Record: open_pdks Pin and Fail-Visible Revision Check

**Status**: Ratified for forward-looking use. Changes no design, result, or
tolerance.
**Date**: 2026-10-15
**Scope**: Which open_pdks revision the repo pins going forward, where the PDK
is looked up, and how a mismatching tree is refused. Existing `records/`,
`corners/`, `klt/runs/` and `bundles/` are append-only evidence and are not
edited; they keep the revision they were produced under.

## Decision

| Item | Before | After |
|---|---|---|
| Pinned open_pdks | `c6d73a35f524070e85faff4a6a9eef49553ebc2b` | `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` |
| Fetch tool | volare, `~/.volare` | ciel 2.6.1, `~/.ciel` (`ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`) |
| Revision check | none; a stray tree was used silently | `<variant>/SOURCES` must name the pin or the harness and `design/` scripts fail with found-vs-pinned hashes |

The pin has one definition per language: `PINNED_OPEN_PDKS` in
`sim/harness/pdk.py` and in `design/lib-pdk-root.sh`. A leftover `~/.volare`
tree at `c6d73a3…` is never selected, and a mismatching `PDK_ROOT` or
`GF180_PDK_PATH` fails rather than falling back.

## Spec text restating checked-on-date facts

`spec/cell-candidates.md` and `spec/leg-design-record.md` keep their original
check dates (2026-08-20 and earlier) and gain a dated re-pin line. The listed
device and model names were not re-verified against the new revision by this
change.

## Not changed

Records minted under `c6d73a3…` are not re-qualified here; re-running them as
new records is a separate piece of work. No result, margin, or tolerance is
relaxed.
