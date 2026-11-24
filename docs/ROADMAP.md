# Roadmap

An antifuse characterization vehicle on gf180mcu: three cell candidates whose
breakdown, programmed resistance and read margin are to be measured per split,
first as direct-pad bitcells on a shuttle test chip, later as the 32x32 array.

Status as of 2026-11-15, `main` @ `0bb4ccfb`; issue and PR states as read that
day. `signoff/report.json` stays the T1 verdict of record.

## Where it stands

Two tracks: the Run 3 test chip (epic #203; quarter-slot target, space not
yet secured, GDS 2026-12-16 only if obtained) sets the order of work; the T1
ladder (tracker #10) is graded for the whole mixed-signal block and moves
when array-level evidence exists.

**Run 3 test chip (#203), by sub-issue**

| Piece | State | Evidence |
|---|---|---|
| Floorplan, counts, pad budget (#206) | merged, status Proposed | `spec/run3-test-chip-floorplan.md`: 36 instances, 48 slots, private PL, shared BL/WL |
| HV pad and protection (#210) | merged, status PROPOSED | `spec/hv-pad-protection-decision.md`, `sim/hv-pad-protection/`, `design/hv-pad/` |
| Bench plan (#212), fixture needs (#260) | merged, status Proposed | `spec/run3-bench-plan.md`, `spec/run3-bench-fixture-requirements.md` |
| Breakdown models (#204, #205, #208, #209) | merged; 12 of 15 parameters `assumed`, the three oxide thicknesses `literature` (PDK `toxe`) | `docs/breakdown-*.md`, `design/breakdown/breakdown_params.spice` |
| Candidate 1 bitcell | DRC: curated clean, native 5 findings; LVS match | `layout/cell_candidate1/` (Minimum x Minimum point only) |
| Candidate 3 bitcell | DRC: curated clean, native 6 findings (`DBU` x1 + die-level density; no cell-level finding since #297); LVS match | `layout/cell_candidate3/` (Minimum x Minimum point only) |
| Candidate 2 bitcell (#207) | drawn; DRC: curated 17 findings, native 25; LVS match | `layout/cell_candidate2/`, PRs #258 and #288 |
| Full-chip assembly (#211) | not started | reference netlist and pad table generated (`layout/run3_top/`, #275); no chip-level GDS or pad ring |

The floorplan needs eight measurement cells (C1 x {Gmin, G2x} x {Amin, A2x},
C2 x {Gmin, G2x}, C3 x {Gmin, G2x}). Seven are drawn: all four C1 points, the
C2 minimum point and both C3 points; C2's `G2x` is the one missing. On the
curated deck the C1 and C3 cells grade clean and C2 does not; on the native
runset every drawn cell carries violations (5 per C1 cell; 6 on C3 `Gmin`
and 5 on C3 `Amin_G2x` since #382 cleared its #297-family generator
findings; 25 on C2), so no drawn cell is native-clean. Cell-level fixes
are #287's. The floorplan's area table still carries estimates for
Candidates 2 and 3.

**T1 ladder (#10).** `signoff/report.json` (klt 0.8.0): `tier: null`, 8 of 22
rows met: `1.analog`, `1.digital`, `2.digital`, `3.digital`, `4.analog`,
`9.analog`, `9.digital`, `11.analog`. `3.analog` grades `unmet` /
`check_failed`: its DRC evidence is
now graded on the native runset, which reports violations on the Candidate 1
bitcell, superseding the curated-deck `clean` the row once rested on. The
remaining analog met rows (`4.analog`, `11.analog`) still rest on the
Candidate 1 bitcell only; `2.analog` stays uncited until array layout exists.

**Digital block.** `antifuse_digital_top` is routed (`rtl/pnr/`) and `klt drc`
clean; the 15-corner SPEF-annotated STA (PR #251) fails setup at two slow
corners, so `5.digital` is uncited. It is not on the Run 3 chip (no on-die mux).

**Repo checks.** No CI (#14). `npm run check:ci` fails on `main` twice:
`scripts/check_artifact_manifests.py` reports 15,713 "committed AND stored"
lines (the #225 condition; 4,401 when #225 was parked), and two `RequestBatchOpts`
shape assertions in `tests/test_program_read_legs_request.py` reject the
`remote` sharding key PR #326 added to `make_request` (#333). The HV-pad suite
itself runs stdlib-clean since PR #291 ported it off pytest.

## Now

Startable today, one PR each. The list has drained to one item: the Candidate 1
split variants, the Candidate 3 `G2x` cell, the chip-level reference netlist
and pad table (PR #329), and the HV-pad suite's unittest port (PR #291) have
all landed — see the floorplan table and Repo checks above. What remains is
parked on the runner question, not on a decision.

1. **CI bootstrap (#14, `loom:issue`).** Done: a PR-blocking workflow runs
   `npm run check:ci`, green on `main`. PR #15 wires the older
   `design/check-netlists.sh` (xschem and PDK), is conflicting, and was held
   on 2026-10-15 for a supported runner. `check:ci` is now Python only, so
   only the runner target and the two red checks above remain (#333, #225).

## Next

- **Candidate 2 clean-out (#207).** The 0.9.1 tool gap is closed: klayout-tools
  0.9.2 is released and in use (PR #288 bumped the pin, reached `klt lvs`
  match, and committed the PDK-runset cross-check). Done: `klt drc` clean on
  the curated deck (still 17 findings; 25 on the native runset); then its
  `G2x`.
- **Group macros.** One generated cell per group (shared BL/WL, private PL).
  Done: DRC clean, LVS match against the `layout/run3_top/` netlist.
- **Full-chip assembly (#211).** After #207, the group macros and the pad-ring
  answer below. Done: top-level generator with `--check`, full-chip `klt drc`
  clean and `klt lvs` match, reports committed.
- **Floorplan area table from drawn footprints.** An edit to a Proposed
  record, so it rides the floorplan ratification.
- **Bench record tooling.** After PR #256 merges: `scripts/check_measurements.py`
  and `measurements/TEMPLATE-run3.md` take the time-to-breakdown fields.
- **`9.analog` attestation (half of #117).** `design/run_analog_cold_start.sh`
  (PR #236) is the single-corner cold start the Builder lacked on 2026-10-17.
  Done: `signoff/attestations/item-9-analog.json` cited, row `met`. Needs #117
  re-curated; item 1 still lacks an xschem-free freshness check.

## Later

- **Array layout and analog T1 rows 2, 3, 4, 7, 11.** First: which candidate
  leads, and is N = 32 kept? Both wait on measured V_bd.
- **Analog items 5, 6, 8.** First: which read-margin, `I_ref` and yield rows
  get ratified limits? Item 6 needs measured breakdown data.
- **Digital timing (`5.digital`, `7.digital`).** First: is the 50 ns target a
  requirement (`rtl/README.md` calls it a P&R input)? Setup at the two `ss`
  corners is closed (issue #446: all 15 corners meet setup and hold on the
  re-routed geometry), and the routed zero-delay `klt functional-verification`
  run is done (issue #445). Remaining: the target question for `5.digital`,
  and klayout-tools#6991 for `7.digital`'s SDF-annotated leg.
- **Silicon measurements** in `measurements/run3/records/` (none today),
  replacing `assumed` breakdown parameters. First: is a slot secured?

## Blocked and waiting

Operator decisions:

- **Slot and offering (#203).** Slot purchase (deadline 2026-12-09, which
  applies only if space is obtained) and the `nfet_10v0_asym` offering are
  unconfirmed in the tracker.
- **Bare PL bond pad on the slot template** (`hv-pad-protection-decision.md`
  "Principal dependency", fixture note R1). If every pad must go through a
  ring pad cell, no program voltage above about 6.5 V reaches a cell.
- **Ratifications.** The floorplan, HV pad, bench plan, fixture note and
  `program-bias-scheme-proposed-decision.md` (PL-driven or BL-driven
  programming) are merged as Proposed. PR #256 is Judge-approved and held.
- **#99**: scope of the last item (characterization bundle); its body says
  `CommittedBundleTests` fails on `main`. **#97** is parked on #99.
- **#267** (remove or complete `sim/run_corners.py`), **#211**'s chip-level
  checklist, and the pre-submission firewall check named in #203.

Upstream or infrastructure: **#176, #177** (`4.digital`, `11.digital`) wait on
klayout-tools#4410 and a release carrying #4363; **#225** on a
`klt artifact verify` that finishes on the affected manifests; **#118** on
#14; **#12** is parked.

## Not planned

- A 32x32 array, on-die mux, SPI or sense path on the Run 3 chip (#203), or
  on-die program-voltage generation (`spec/program-voltage-decision.md`).
- Waivers, hand-edited PCell geometry or device swaps for Candidate 2 (#207).
- A visibility change, or application or use-case content (`CLAUDE.md`).
