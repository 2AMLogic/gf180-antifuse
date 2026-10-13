# Decision Record: Measurement Matrix and Extraction Protocol (Yield, Read Margin, Retention)

**Status**: Ratified, with explicit OPEN items (the retention stress points —
see "Open items"). Adds definitions only; relaxes nothing in
`spec/architecture.md`, `spec/split-axis-plan.md` or `spec/cell-candidates.md`.
**Date**: 2026-10-09
**Scope**: Issue #78. Defines, for the three quantities the die exists to
measure (programming yield, read margin, retention), the quantity and unit,
the unit of replication, the pass/fail criterion, the SPI command sequence
that produces it, and the required record fields for `measurements/`. Does
**not** assert any breakdown voltage, `I_prog_min`, `I_sneak_max`, `I_ref`,
read voltage or stress number: those are measurement outputs or open items.

## Context

`spec/split-axis-plan.md` ("Open questions", last bullet) says the
`measurements/` per-region matrix "should report replicate counts alongside
yield fractions"; `CLAUDE.md` says an aggregate across splits is a bug, not a
result. Until this record, `measurements/README.md` was a stub and no
`spec/` record defined how any of the three quantities is extracted (no
retention definition existed at all). The same definition of "programmed" is
intended to be shared by `sim/` yield work (#66) and the bench.

Terminology reused from the ratified records: Regions I/II/III and
Candidates 1/2/3 (`spec/split-axis-plan.md` region map); capacitor geometry
`min`/`2x`; access sizing `min`/`2x`; pulse condition (one of the ~5 voltage
and width sweep points per sub-combination).

## 1. Unit of replication (common to all three quantities)

A **measurement cell** (not to be confused with a grid cell) is one
(candidate region x capacitor geometry x access sizing x pulse condition)
combination, per `spec/split-axis-plan.md` "Split-axis mapping" §4. Its
replicates are the grid cells assigned to it by the checkerboard/round-robin
assignment. Counts, from the ratified plan:

| Region | Cells | Per (geometry x sizing) sub-combination (4 per region) | Per pulse condition (~5 per sub-combination) |
|---|---|---|---|
| I | 352 | 88 | about 17.6 |
| II | 352 | 88 | about 17.6 |
| III | 320 | 80 | 16 |

This is the plan's "roughly 80-90 cells" and "on the order of 15-20
replicate cells"; actual per-record counts are whatever the assignment map
gives and are recorded, not assumed. The plan already flags this as thin for
tight confidence intervals; this record does not close that gap, it makes the
count visible in every record.

Rules that follow from the plan and `CLAUDE.md`:

- **A record covers exactly one measurement cell.** Its replicates share one
  region, candidate, geometry, sizing and pulse condition. No record, row or
  summary line may pool across regions, candidates, geometries, sizings or
  pulse conditions. A cross-split comparison is a report built from several
  records, never a record.
- Read margin and retention records additionally fix one read condition
  (read margin) or one stress point (retention) and one expected state
  (programmed or unprogrammed), so the programmed and unprogrammed
  distributions are never merged.
- Every record carries the replicate count `n`, the per-cell raw outcomes
  (every replicate, including excluded ones), and the confidence-interval
  method. Default method: exact (Clopper-Pearson) two-sided binomial interval,
  confidence level stated in the record. It is chosen because the replicate
  counts are small (about 16-18) and observed fractions near 0 or 1 are
  expected; a normal-approximation interval is not acceptable at these counts.

## 2. Programming yield

- **Quantity and unit**: programming yield `Y = k / n_eff`, a dimensionless
  fraction with its confidence interval. `k` = replicates with outcome
  `programmed`; `n_eff` = `programmed` + `not_programmed`. Excluded
  replicates (below) stay in the raw table and in `n`, not in `n_eff`.
- **Unit of replication**: the measurement cell of §1 (one pulse condition).
  One program pulse per grid cell per record; the program sequence's
  arm is single-use (`spec/architecture.md` §5 step 5), and retrying a cell
  would confound the condition with the number of attempts. A retry campaign
  is a different pulse condition, recorded separately.
- **Pass/fail criterion** (`spec/architecture.md` §4): a cell is
  `programmed` iff the post-program read returns `RDATA` = 1, with the sense
  reference satisfying `I_sneak_max < I_ref < I_prog_min`. Because those
  bounds are measurement outputs and `I_ref` is set on-die, the record states
  only the outcome of the comparator; it does not claim the inequality was
  verified. A record may cite the `sim/` record or bench evidence that bounds
  `I_sneak_max`, but a yield record without it is still valid as a raw
  outcome table.
- **Exclusions** (never silently dropped): `excluded_preread_high` (the
  pre-program read returned `RDATA` = 1, so the cell was not a valid
  unprogrammed starting point); `excluded_protocol_error` (`STATUS.PROTOCOL_ERROR`
  set during the sequence, or `PROG_DONE` never observed).
- **SPI sequence** (register map of `spec/architecture.md` §5), per grid cell:
  1. Pre-read: write `ADDR_ROW`, `ADDR_COL`; write `CTRL` = `READ_STROBE`;
     wait `BUSY` clear and `READ_VALID` set; read `RDATA`. Expect 0.
  2. Write `PULSE_WIDTH` to the pulse-condition's width code. The pulse
     voltage is the bench `VPP` level for the condition (not a register;
     `spec/program-voltage-decision.md`). Record both.
  3. Write `ADDR_ROW`, `ADDR_COL` again (after `PULSE_WIDTH`, since §5 step 6
     clears an armed state on any of those writes).
  4. Write `CTRL` with `PROG_ARM`=1, `PROG_STROBE`=0; then, in a separate
     transaction within the arm timeout, `CTRL` with `PROG_STROBE`=1.
  5. Poll `STATUS` until `PROG_DONE`=1 and `BUSY`=0; check `PROTOCOL_ERROR`=0.
  6. Post-read as in step 1; `RDATA` = 1 gives `programmed`.
  Cell ordering within a record must not follow the pulse-condition
  assignment (the plan's checkerboard exists to avoid position confounding);
  record the program order if it is not row-major.

## 3. Read margin

- **Quantity and unit**: read agreement `A = agree / n_eff` (dimensionless
  fraction with interval) at one read condition, separately for the
  `programmed` and `unprogrammed` expected states. For `programmed` cells a
  flip is a false 0; for `unprogrammed` cells it is a false 1 (a sneak or
  leakage failure, `spec/architecture.md` §3). A cell margin in amperes
  (`I_cell / I_ref`) is **not** defined here: `RDATA` is one bit and bits
  [7:1] are reserved (`spec/architecture.md` §5), and no ratified
  pad exposes the bit-line current. See OPEN-M1.
- **Unit of replication**: the programmed (or unprogrammed) cells of one
  measurement cell, taken from the yield record that produced them (cite its
  record id), at one read condition. Programmed-state replicates are therefore
  `k` from the yield record, not `n`; the record states this count.
- **Pass/fail criterion** (`spec/architecture.md` §4): for an expected state
  `programmed`, outcome `read_agree` iff `RDATA` = 1; for `unprogrammed`,
  `read_agree` iff `RDATA` = 0; otherwise `read_flip`. This is the current-threshold
  comparator outcome, i.e. whether the cell current lies on the correct side
  of `I_ref` given `I_sneak_max < I_ref < I_prog_min`.
- **Read-condition matrix**: the worst case in §4 is two different corners on
  two different device sets (slow/cold for the selected access device,
  fast/hot for the `N-1` unselected ones). A packaged die at one
  temperature cannot apply both at once, so measured agreement at a
  temperature extreme **bounds** one side only; the record states the
  temperature and does not claim to be the §4 worst case. The read-voltage
  and temperature values are OPEN-M2 (no read voltage is ratified).
- **Sneak requirement**: unprogrammed-expected reads are made after the array
  is in its partially-programmed state (all yield records of the campaign
  complete), because that is the condition `spec/architecture.md` §3 targets.
  The record states what fraction of the array was programmed at read time.
- **SPI sequence**: the read sequence of `spec/architecture.md` §5 (write
  `ADDR_ROW`, `ADDR_COL`; `CTRL` = `READ_STROBE`; wait `READ_VALID`; read
  `RDATA`), repeated once per grid cell per read condition. No `CTRL`
  program bits are written.

## 4. Retention

- **Quantity and unit**: retention fraction `R = retained / n_eff`
  (dimensionless, with interval) after one stress point, separately for the
  `programmed` expected state (programmed cells still reading 1) and the
  `unprogrammed` expected state (control cells still reading 0, i.e. no
  spontaneous programming or disturb during stress).
- **Defined as a matrix**: stress condition x duration. A **stress point** is
  one (stress condition, duration) pair with an identifier; a record covers
  exactly one stress point and one measurement cell. The matrix axes and every
  numeric value on them are OPEN (OPEN-R1 to OPEN-R5). No number is invented
  here.
- **Unit of replication**: cells of one measurement cell that were
  `programmed` in the cited yield record (for the programmed state) or that
  stayed unprogrammed (control state), subjected to the stress point.
  Because these are subsets of an already thin population, splitting one
  measurement cell across several stress points divides `k` further; the
  split is OPEN-R4 and every record states its `n_eff`.
- **Pass/fail criterion** (`spec/architecture.md` §4): a cell is `retained`
  iff the post-stress read, made at the same read condition as the pre-stress
  read, returns the same `RDATA` as its pre-stress read (1 for programmed, 0
  for control); else `lost`. Pre-stress and post-stress reads at one fixed
  read condition keep the criterion on the same `I_ref` bound.
  Pre-stress `RDATA` of programmed cells must be 1; a programmed cell that
  already reads 0 before stress is a read-margin finding and is excluded
  (`excluded_pre_stress_mismatch`).
- **SPI sequence**: pre-stress read (§5 read sequence) -> stress (no SPI
  traffic is required; whether the die is powered during stress is OPEN-R2)
  -> post-stress read (same sequence, same address order). No program
  sequence is issued.

## 5. Record fields (required in every `measurements/` record)

Format and example in `measurements/TEMPLATE.md`; enforced by
`scripts/check_measurements.py`. Required: record id; quantity; claim (cited
`spec/` section); region; candidate; capacitor geometry; access sizing; pulse
condition; read condition (read margin and retention); stress point
(retention); expected state (read margin, retention); die identifier;
temperature; `VPP` and `PULSE_WIDTH` code used to program; replicate count
`n`; confidence-interval method and level; declared outcome counts; the
fraction and interval; the full per-cell outcome table (one row per replicate,
each row restating its own region, candidate, geometry, sizing, pulse
condition, and the read condition / stress point / expected state where
applicable); `Supersedes`; timestamp and author. Each per-cell row repeats the
split tags so that a row pooled from another split is detectable on its own.

The shape follows the per-region records documented in
`sim/cell-device-characterization/README.md` (record id, claim, conditions,
result, links, timestamp/author, supersedes).

## 6. Append-only discipline

Same as `sim/`: a record, once committed, is never edited or deleted. A
re-measurement, a correction or an exclusion revision is a new record whose
`Supersedes` names the earlier record id. `scripts/check_measurements.py
--base <ref>` fails if any file under `measurements/records/` that exists at
`<ref>` is modified, renamed or deleted.

## Open items (explicit; no numbers invented)

- **OPEN-R1: stress temperatures.** Which temperature(s), and whether any is
  above the die's rated range. Unset.
- **OPEN-R2: stress bias and power state.** Read-level bias held across the
  cell, unbiased storage, or a bias above read level; die powered or
  unpowered during stress. Unset.
- **OPEN-R3: durations and checkpoints.** The durations and whether
  checkpoints are cumulative on the same cells. Unset.
- **OPEN-R4: replicate allocation.** How the programmed population of one
  measurement cell is divided across stress points, given the thin
  per-condition counts in `spec/split-axis-plan.md`; whether retention runs on
  a subset of conditions only. Unset.
- **OPEN-R5: retention pass threshold for a campaign.** The per-cell
  criterion is fixed above (same `RDATA` before and after); any acceptance
  threshold on `R` is a decision for after data exists. Unset.
- **OPEN-M1: analog margin readout.** Whether a bench-accessible measurement
  of bit-line current exists. It is not in the ratified register map or pad
  list; adding one needs a `spec/` change outside this record.
- **OPEN-M2: read-voltage and temperature matrix.** No read voltage is
  ratified (`spec/architecture.md` §4 only requires sub-disturb); the `sim/`
  value is a placeholder. Unset.
- **OPEN-Y1: ordering and `VPP` settling.** The program order across cells
  and the bench `VPP` settling criterion between conditions. Recorded per
  record, not fixed here.

## References

- `spec/architecture.md` §3 (sneak paths), §4 (sense scheme and the `I_ref`
  bounds), §5 (register map, program and read sequences).
- `spec/split-axis-plan.md` (region map, split axes, replicate counts).
- `spec/cell-candidates.md` (candidates; post-breakdown model gap).
- `spec/program-voltage-decision.md` (`VPP` is bench-supplied, so pulse
  voltage is a recorded condition, not a register).
- `sim/README.md`, `sim/cell-device-characterization/README.md` (append-only
  rule; per-region record shape).

## Decision

Ratify the extraction definitions of §2-§4, the record fields of §5 and the
append-only rule of §6, with the OPEN items above left open. A record covers
exactly one measurement cell and always reports its replicate count and raw
per-cell outcomes; rows pooled across candidate regions or split axes are
rejected by the format check.
