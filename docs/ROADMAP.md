# Roadmap

An antifuse characterization vehicle on gf180mcu: three cell candidates whose
breakdown, programmed resistance and read margin are to be measured per split,
first as direct-pad bitcells on a shuttle test chip, later as the 32x32 array.

Status as of 2026-11-13, `main` @ `7cb2d8ff`; issue and PR states as read that
day. `signoff/report.json` stays the T1 verdict of record.

## Where it stands

Two tracks: the Run 3 quarter-slot test chip (epic #203, GDS due 2026-12-16)
sets the order of work; the T1 ladder (tracker #10) is graded for the whole
mixed-signal block and moves when array-level evidence exists.

**Run 3 test chip (#203), by sub-issue**

| Piece | State | Evidence |
|---|---|---|
| Floorplan, counts, pad budget (#206) | merged, status Proposed | `spec/run3-test-chip-floorplan.md`: 36 instances, 48 slots, private PL, shared BL/WL |
| HV pad and protection (#210) | merged, status PROPOSED | `spec/hv-pad-protection-decision.md`, `sim/hv-pad-protection/`, `design/hv-pad/` |
| Bench plan (#212), fixture needs (#260) | merged, status Proposed | `spec/run3-bench-plan.md`, `spec/run3-bench-fixture-requirements.md` |
| Breakdown models (#204, #205, #208, #209) | merged; every parameter `assumed` | `docs/breakdown-*.md`, `design/breakdown/breakdown_params.spice` |
| Candidate 1 bitcell | DRC clean, LVS match | `layout/cell_candidate1/` (Minimum x Minimum point only) |
| Candidate 3 bitcell | DRC clean, LVS match | `layout/cell_candidate3/` (Minimum x Minimum point only) |
| Candidate 2 bitcell (#207) | drawn; DRC 17 violations, LVS mismatch | `layout/cell_candidate2/`, PR #258; gap filed as klayout-tools#5277 |
| Full-chip assembly (#211) | not started | no chip-level generator, netlist or pad ring in `layout/` |

The floorplan needs eight measurement cells (C1 x {Gmin, G2x} x {Amin, A2x},
C2 x {Gmin, G2x}, C3 x {Gmin, G2x}). Three are drawn, one of them not clean.
Its area table still carries estimates for Candidates 2 and 3.

**T1 ladder (#10).** `signoff/report.json` (klt 0.8.0): `tier: null`, 7 of 22
rows met: `1.digital`, `2.digital`, `3.digital`, `9.digital`, `3.analog`,
`4.analog`, `11.analog`. The analog rows rest on the Candidate 1 bitcell only;
`2.analog` stays uncited until array layout exists. (`signoff/README.md` still
says 6 of 22 above a table of seven met rows.)

**Digital block.** `antifuse_digital_top` is routed (`rtl/pnr/`) and `klt drc`
clean; the 15-corner SPEF-annotated STA (PR #251) fails setup at two slow
corners, so `5.digital` is uncited. It is not on the Run 3 chip (no on-die mux).

**Repo checks.** No CI (#14). `npm run check:ci` fails on `main`:
`scripts/check_artifact_manifests.py` reports 15,713 "committed AND stored"
lines (the #225 condition; 4,401 when #225 was parked), and
`tests/test_hv_pad_protection.py` imports `pytest`, which the stdlib runner
`check:ci` uses does not provide.

## Now

Startable today, one PR each. Items 1 to 4 are the only dispatchable work; the
rest is parked on the decisions and releases under "Blocked and waiting".

1. **Candidate 1 split-variant bitcells** (no issue yet, seed 1). Draw
   `G2x`/`Amin`, `Gmin`/`A2x` and `G2x`/`A2x` through `layout/bitcell_gen.py`.
   Done: three cell directories with the `cell_candidate1/` artifact set, DRC
   `clean`, LVS `match`, `generate.py --check` exits 0, drawn bounding boxes
   in `layout/README.md`. The levels are ratified (`spec/split-axis-plan.md`).
2. **Candidate 3 `G2x` bitcell** (no issue yet, seed 2). Same done-criterion
   for one cell, n-well connection stated as in `cell_candidate3/`.
3. **Run 3 chip-level reference netlist and pad table** (no issue yet, seed
   3). One generator emits the 36-instance netlist and the `L01`-`L48` table.
   Done: a stdlib check proves both agree with the floorplan record and fails
   on a seeded mismatch. #211's LVS needs it; Candidate 2 does not gate it.
4. **Run `tests/test_hv_pad_protection.py` under the repo's runner** (no issue
   yet, seed 4). Done: `python3 -I -m unittest discover -s tests -q` collects
   and passes it with no `pytest` installed.
5. **CI bootstrap (#14, `loom:issue`).** Done: a PR-blocking workflow runs
   `npm run check:ci`, green on `main`. PR #15 wires the older
   `design/check-netlists.sh` (xschem and PDK), is conflicting, and was held
   on 2026-10-15 for a supported runner. `check:ci` is now Python only, so
   only the runner target and the two red checks above remain (item 4, #225).

## Next

- **Candidate 2 clean-out (#207).** Needs a klayout-tools release newer than
  v0.9.1 (klayout-tools#5277 is closed, unreleased). Done: pin bumped,
  `klt drc` clean, `klt lvs` match, README section replaced; then its `G2x`.
- **Group macros.** After Now 1 and 2: one generated cell per group (shared
  BL/WL, private PL). Done: DRC clean, LVS match against the Now 3 netlist.
- **Full-chip assembly (#211).** After #207, the group macros and the pad-ring
  answer below. Done: top-level generator with `--check`, full-chip `klt drc`
  clean and `klt lvs` match, reports committed.
- **Floorplan area table from drawn footprints.** After Now 1 and 2; an edit
  to a Proposed record, so it rides the floorplan ratification.
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
  requirement (`rtl/README.md` calls it a P&R input)? Then close setup at the
  two `ss` corners and add a routed `klt functional-verification` run.
- **Silicon measurements** in `measurements/run3/records/` (none today),
  replacing `assumed` breakdown parameters. First: is a slot secured?

## Blocked and waiting

Operator decisions:

- **Slot and offering (#203).** Slot purchase (deadline 2026-12-09) and the
  `nfet_10v0_asym` offering are unconfirmed in the tracker.
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
