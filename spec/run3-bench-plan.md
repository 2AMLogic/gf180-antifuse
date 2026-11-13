# Decision Record: Run 3 Test Chip Bench Plan (Direct-Pad Cells)

**Status**: Proposed for operator ratification. Adds a bench and extraction
plan for the Run 3 quarter-slot test chip; relaxes and amends nothing in
`spec/measurement-matrix.md` (ratified, tied to the SPI path of the 32x32
array), `spec/run3-test-chip-floorplan.md`, `spec/cell-candidates.md` or any
other record. Numeric values not derived from a model, a ratified record or a
measurement are **OPEN items**; none is invented here.
**Date**: 2026-10-29
**Scope**: Issue #212, part of #203. For the direct-pad cells of the floorplan
record: instrument list and limits, stimulus, what is recorded per instance,
the extraction of V_bd, programmed and unprogrammed resistance and read
margin, per-measurement-cell sample sizes and minimum detectable effect, the
physical-programming safety statement, and the `measurements/` layout. Does
**not** run any measurement, set pad/HV structure (#210) or change the
floorplan (#206). Silicon is not expected before Q2 2027 at the earliest.

## Context

The chip has no SPI path, no on-die sense amplifier and no on-die `I_ref`
(`spec/run3-test-chip-floorplan.md`): every instance is reached by pad. The
questions the silicon must answer are, per candidate and per split, the V_bd
distribution, the programmed resistance and the read margin.
`spec/measurement-matrix.md` §2-§3 define "programmed" and "read margin" from
the one-bit `RDATA` comparator; that path does not exist here, so those two
definitions are re-derived from bench-measured pad current in §4-§6 below.
What is reused unchanged from the matrix record: one record = one measurement
cell; Clopper-Pearson exact intervals; programmed and unprogrammed
distributions never merged; raw per-instance outcomes listed, exclusions never
dropped; append-only records. Extending `measurement-matrix.md` in place was
rejected (it is ratified and SPI-specific); it receives a cross-reference only.

## 1. Unit of replication and the eight measurement cells

An **instance** is one cell with a private plate pad (PL); a **group** is the
set of instances sharing one BL and one WL pad (floorplan). A **measurement
cell** is one (candidate x capacitor geometry x access sizing) combination.
There is **no pulse-condition axis** on this chip: each instance gets exactly
one voltage ramp, so one instance gives one V_bd sample (floorplan, "Program
pulse voltage/width"). Result tables are per measurement cell:

| Measurement cell | Group (shared BL/WL) | Geometry | Sizing | n | PL pads |
|---|---|---|---|---|---|
| M1 | C1-Amin | Gmin | Amin | 4 | L01-L04 |
| M2 | C1-Amin | G2x | Amin | 4 | L05-L08 |
| M3 | C1-A2x | Gmin | A2x | 4 | L09-L12 |
| M4 | C1-A2x | G2x | A2x | 4 | L13-L16 |
| M5 | C2-Amin | Gmin | Amin | 5 | L17-L21 |
| M6 | C2-Amin | G2x | Amin | 5 | L22-L26 |
| M7 | C3-Amin | Gmin | Amin | 5 | L27-L31 |
| M8 | C3-Amin | G2x | Amin | 5 | L32-L36 |

Rules (inherited from `spec/measurement-matrix.md` §1 and `CLAUDE.md`): a
record covers exactly one row of this table; no record, table or summary line
pools rows (not Gmin with G2x, not Amin with A2x, not candidates), and no
pooling is allowed to raise n. A cross-split comparison is a report built from
several records. The wiring caveat of the floorplan applies: M1 and M2 share a
BL and a sense path, as do M3/M4, M5/M6 and M7/M8; they are separate records
but not electrically independent (see §5 leakage term).

If the operator ratifies BL-driven programming for any candidate, the HV
terminal moves from PL to BL and the private/shared roles swap for that
candidate; this plan assumes **PL-driven** (the PROPOSED scheme of
`spec/program-bias-scheme-proposed-decision.md`, not ratified). Under the swap,
the per-instance ramp channel would be the BL of a group, which breaks
one-ramp-per-instance independence for a shared BL; that case needs its own
plan revision, not a silent reinterpretation of this one.

## 2. Instruments, channels and limits

| Function | Needed capability | Limit / value |
|---|---|---|
| PL ramp source (36 pads) | Voltage source with current compliance and current readback, reaching the program voltage | Maximum voltage and rated compliance: **OPEN-B1** (depends on #210, the HV pad and protection record; the floorplan only reserves HV slots, ~8-16 V per #203) |
| BL sense (4 pads) | Pad current measurement at read bias, resolution below the lowest expected programmed read current | Candidate 3 programmed read current is near fA scale in the proposed read-bias record (conditional on assumed filament parameters); the instrument floor must be **measured** (§5), not assumed. Required resolution: **OPEN-B2** |
| WL drive (4 pads) | DC supply | WL on/off levels per candidate: **OPEN-B3** (proposed bias records, unratified) |
| `VBW_C3` (1 pad) | DC supply tied to the read rail for C3 (`spec/candidate3-read-bias-decision.md`, PROPOSED) | Must track the C3 read rail; value follows that record's status |
| Channel multiplexing | One ramp/sense channel per PL, or a switch matrix | Matrix leakage and offset are in the sense path and are measured as part of the floor (§5). Channel count vs matrix: **OPEN-B4** |
| Environment | Guarded fixture, temperature control with measured (not set-point) temperature | Temperature points: reuse **OPEN-M2** of the matrix record |

Limits that are fixed regardless of the OPEN values:

- One ramp rate and one compliance setting apply to **every** instance of
  every measurement cell, so ramp rate and compliance are controlled, not
  split axes. Both are recorded per instance. Whether V_bd depends on ramp
  rate is **not measured on this chip** and is not assumed either way; the
  plan states this gap rather than closing it.
- Compliance is set on the source, not left to the on-die access device
  alone, because the post-breakdown filament current must be bounded on every
  candidate (C2-fallback has no access device at all, §9).
- Unselected PL pads are at 0 V during any program ramp (floorplan: no oxide
  stress with the shared WL on); the group BL is at 0 V.
- No instance receives voltage above the OPEN-B1 maximum, and no value of
  OPEN-B1 may exceed what the HV pad record (#210) establishes for the pad.

## 3. Procedure per instance

Within a group, the instance order is randomized and the order is recorded;
geometry levels must be interleaved (not all Gmin then all G2x) so position and
session drift are not confounded with the level. For each instance:

1. **Floor reading** (once per group per session): WL off, BL read at the read
   bias; this is the bench and fixture floor `I_floor`, not a cell property.
2. **Pre-read** at the read condition (§7) under *both* unselected-PL policies
   (a) unselected PL high-impedance and (b) unselected PL driven to the BL
   potential. Both are non-destructive at the read bias. The difference of the
   two readings estimates the unselected-pad leakage in the sense path under
   policy (a). The policy used for all recorded margins and R_prog values is
   stated per record (policy (b) when the channel count allows).
3. **Ramp**: PL swept from 0 V upward at the single bench ramp rate, to the
   OPEN-B1 maximum or until compliance, current read back throughout (the full
   I-V trace is kept as raw data).
4. **Post-read** at the same read condition and policy as the pre-read, then a
   second post-read after a stated settle interval, to detect drift.
5. **Group sneak stages**: for each group, unprogrammed-instance reads are
   repeated after one-third and two-thirds of the group's instances are
   programmed (the sneak-relevant condition of `spec/architecture.md` §3), and
   the fraction programmed at read time is recorded.

Every read adds to a cumulative exposure that is not a certified safe
read-disturb limit (the proposed read-bias record states none exists); the
number of reads and the exposure time per instance are recorded.

## 4. V_bd distribution

- **Per-instance V_bd**: the PL voltage at which the PL current first exceeds
  the breakdown-detection current `I_det` (an OPEN value, **OPEN-B5**, to be
  fixed from the first unprogrammed I-V traces before any instance is ramped,
  and recorded per record). An instance whose ramp reaches the maximum with no
  detection has `V_bd > V_max`: a **right-censored** sample, kept in the table
  as `no_breakdown_at_vmax` and handled as censored in the distribution.
- **Per-measurement-cell result**: the empirical CDF of V_bd over the n
  instances (this is the yield-vs-condition curve of `CLAUDE.md`, with the
  ramp voltage as the condition), plus the exact binomial interval on
  "broke down below V_max" (`k/n_eff`). With n = 4 or 5 only the median, the
  range and a first-order spread are reported; no Weibull slope, no
  percentile below the sample resolution, and no curve fitted across cells.
- All 4 of 4 (or 5 of 5) successes give, with the matrix record's two-sided
  95 % exact interval, a lower bound of 0.40 (n = 4) and 0.48 (n = 5) on the
  yield; that is the strongest yield statement these counts allow.

## 5. Programmed and unprogrammed resistance, leakage term

Both distributions are recorded for every measurement cell and are never
merged.

- **Unprogrammed**: the pre-read current of each instance, minus `I_floor`,
  at the read condition. The group-size leakage term (the other group
  members' pad leakage, scaling with group size minus one) is the difference
  between policy (a) and policy (b) readings of the same instance, and is
  **measured at the three sneak stages of §3.5**, not assumed. Candidate 3 is
  the most exposed (floorplan, shared-BL section).
- **Programmed**: the post-read current of each programmed instance, minus
  `I_floor`, at the same read condition; `R_total = V_read / I`.
- **R_prog** is reported as `R_total` **minus a stated correction interval**
  for the shared-BL route resistance (floorplan estimate: tens of ohms, sheet
  resistance not looked up, **OPEN-B6**) and for the access device on-resistance
  (a model value from `sim/` records, labelled model-derived). There are no
  Kelvin pads, so the route term cannot be measured on this chip. The record
  carries `R_total`, the correction interval, its source, and the resulting
  R_prog interval. If `R_total` is large against the correction the record
  says so; if not, R_prog is reported as the interval, never as a point.
- The correction applies equally within a group, so within-group comparisons
  (the geometry comparison M1 vs M2, etc.) are insensitive to it; comparisons
  across groups (e.g. M1 vs M3, sizing) are not, and use the interval.

## 6. Outcome classes (neither silently programmed nor unprogrammed)

An instance gets exactly one outcome:

| Outcome | Definition |
|---|---|
| `programmed` | Breakdown detected in the ramp and both post-reads, floor-subtracted, at or above the programmed threshold `I_prog_thr` and agree within the drift criterion |
| `not_programmed` | No breakdown detected up to V_max (V_bd censored) and post-read consistent with the pre-read within the drift criterion |
| `partial_conduction` | Anything between: a breakdown event was detected but the post-read current is below `I_prog_thr`; **or** the post-read lies above the instance's own pre-read and below `I_prog_thr`; **or** the two post-reads disagree beyond the drift criterion (a cell that conducts after partial breakdown) |
| `excluded_preread_high` | Pre-read above `I_unprog_hi` before the ramp; not a valid unprogrammed start |
| `excluded_setup_error` | Compliance, channel or fixture fault during the sequence |

`I_prog_thr`, `I_unprog_hi` and the drift criterion are **OPEN-B7**. They must
be set before the first ramp from the measured unprogrammed distribution of the
same chip (the pre-read data of all 36 instances is non-destructive), and
`I_prog_thr` must exceed the largest unprogrammed pre-read (plus the measured
group leakage term) of that measurement cell's *group* by a factor the
operator fixes. A cell with `partial_conduction` counts in `n_eff` and in
neither the numerator of programming yield nor `not_programmed`; the record
reports the bracket `k/n_eff` and `(k + partial)/n_eff`, so partial breakdown
is visible in every yield statement. Its post-read current still enters the
read-margin table as a third, separate population.

## 7. Read margin extraction

`spec/measurement-matrix.md` §3 defines margin as one-bit agreement at an
on-die `I_ref`; here the pad current is observable (the matrix's OPEN-M1 is
closed for this chip by construction). Per measurement cell:

- `I_prog,min` = the smallest floor-subtracted post-read current among
  `programmed` instances; `I_unprog,max` = the largest floor-subtracted
  current among all unprogrammed reads of the cell's *group* (all sneak
  stages, both policies stated), including the group leakage term.
- **Window** `W = I_prog,min / I_unprog,max` for that measurement cell. The
  full per-instance currents (both populations, and the `partial_conduction`
  population separately) are the primary result; `W` is a summary of two
  distributions, never a substitute for them. `W > 1` is the necessary
  condition `I_sneak_max < I_ref < I_prog_min` of `spec/architecture.md` §4,
  stated as an observation, not as verification of a chosen `I_ref`.
- **Read condition**: one bias and temperature per record. A packaged die at
  one temperature bounds only one side of the §4 worst case (slow/cold for the
  selected device, fast/hot for the unselected ones); the record states the
  temperature and does not claim to be the worst case. The read bias values
  and the temperature matrix remain **OPEN-M2** (matrix record) and the
  C3 well tracking follows the status of its proposed record.
- A read-margin claim for a measurement cell also requires the group sneak
  stage at which `I_unprog,max` was taken to be stated, because the number
  depends on how many neighbours are programmed.

## 8. Sample sizes and minimum detectable effect

n is 4 (M1-M4) or 5 (M5-M8), set by the pad budget, not by a power target
(floorplan). There is no spread estimate before data exists, so the minimum
detectable effect is stated as a **criterion on the observed samples**, not as
a standard-deviation multiple that would assume a spread:

A shift between two levels of one split axis is called detected, for V_bd or
for programmed current, only when it passes an exact two-sided rank test at the
5 % level on the two n-instance samples. The attainable cases, by exact
enumeration of the rank-sum distribution:

| Comparison (levels never pooled) | Sample sizes | Detected at two-sided 5 % only if |
|---|---|---|
| Gmin vs G2x within M1/M2, within M3/M4 | 4 vs 4 | complete separation (every instance of one level beyond every instance of the other); next-best case has p = 0.057 |
| Gmin vs G2x within M5/M6, within M7/M8 | 5 vs 5 | exact rank-sum statistic U <= 2, i.e. at most two instance pairs out of order (p = 0.032); U = 3 gives 0.056 |
| Amin vs A2x at fixed geometry (M1 vs M3, M2 vs M4) | 4 vs 4 | complete separation |
| C1-Amin vs C3-Amin at fixed geometry (M1 vs M7, M2 vs M8) | 4 vs 5 | U <= 1 (p = 0.032); U = 2 gives 0.063 |

Stated minimum detectable effect, per comparison: the shift that moves one
level's samples entirely beyond (4 vs 4) or, for 5 vs 5 and 4 vs 5, almost
entirely beyond the range of the other level's samples. Any smaller shift is
**not detectable on this chip**. A shift beyond the other level's observed
range is reported as a range separation with its p-value; the effect size in
volts or amperes is the observed gap, with no interval claimed beyond the
sample. The test needs no distribution assumption, which matters because the
shape is unknown at these counts. C2 and C3 comparisons are never made on
pooled instances, and no comparison across oxide flavors is described as an
isolated effect of oxide thickness, because the access class changes with the
oxide (floorplan, "Which axes vary where").

Yield: with all n of n instances programmed the two-sided 95 % exact lower
bound is 0.40 (n = 4) and 0.48 (n = 5); anything weaker than a clean sweep
widens the interval correspondingly (the interval is computed per record, not
looked up). The count does not support per-cell tail or Weibull-slope claims;
tighter statistics need an array or more pads (out of scope).

## 9. Variant deltas

- **C2-fallback** (no `nfet_10v0_asym`; floorplan): M5/M6 become bare
  `cap_nmos_06v0` instances with no access device and no WL. The series
  device no longer limits current, so compliance is wholly bench-supplied (or
  a pad-side series resistor, whose value then enters `R_total` and is
  recorded); the R_prog correction loses the access-device term; the data are
  a different experiment from the full Candidate 2 and the record's Candidate
  field must say so (`2F`).
- **BL-driven programming**: see §1; a plan revision, not a silent swap.

## 10. Safety and physical-programming limits

- **Every physical programming run requires its own operator go-ahead**, per
  the standing ruling in #127 (programming of carried candidates is
  conditional on a measured V_bd; Candidates 2 and 3 are both carried until
  then). Approval of this plan is not that go-ahead.
- Unprogrammed characterization (floor and pre-reads, §3.1-§3.2) involves no
  breakdown stimulus and may precede any program ramp; it is also the input
  that sets the OPEN-B5 and OPEN-B7 thresholds, so it is done first and
  recorded.
- No ramp above the OPEN-B1 maximum, no compliance above the OPEN-B1 rating;
  both are bounded by the HV pad record (#210) and the proposed program-bias
  record, whose findings (marginal access-device ratings on a selected cell)
  are the reason the ramp is stopped at compliance and the full trace kept.
- Programming is irreversible and each instance has exactly one ramp: a failed
  or aborted ramp on an instance is recorded and the instance is not retried
  (a retry is a different, separately recorded experiment).
- The bench never places two instances on the same group at program voltage
  at once; unselected PL stay at 0 V.

## 11. Records and layout

Direct-pad records use `measurements/TEMPLATE-run3.md` and live under
`measurements/run3/records/`, one file per measurement cell (M1-M8) per
quantity (yield/V_bd, resistance and read margin), keyed by PL pad name.
`scripts/check_measurements.py` reads only `measurements/records/` and is
SPI-specific (row/col 0..31, regions I-III); it is left unchanged. Extending it
to the Run 3 directory is out of scope for this record. Records are
append-only (matrix record §6); a re-measurement is a new record whose
`Supersedes` names the earlier one.

## Open items (explicit; no numbers invented)

- **OPEN-B1**: maximum ramp voltage and rated compliance current; set by the
  HV pad/protection record (#210) and the program-bias scheme.
- **OPEN-B2**: required BL current resolution and floor; set after the first
  measured `I_floor`.
- **OPEN-B3**: WL on/off levels per candidate; depends on the proposed bias
  records.
- **OPEN-B4**: channel count versus switch matrix, and which unselected-PL
  policy is used.
- **OPEN-B5**: breakdown-detection current `I_det`.
- **OPEN-B6**: shared-BL route resistance (needs layout-derived length and a
  looked-up sheet resistance).
- **OPEN-B7**: `I_prog_thr`, `I_unprog_hi` and the drift criterion.
- **OPEN-B8**: the single ramp rate and settle intervals. The dependence of
  V_bd on ramp rate is unmeasured here.
- Inherited from the matrix record: OPEN-M2 (read bias and temperature
  matrix); retention (OPEN-R1 to R5) is not part of this chip's questions.

## References

- `spec/run3-test-chip-floorplan.md` (instances, pad table, wiring scheme,
  C2-fallback).
- `spec/measurement-matrix.md` (§1 unit of replication, §5 record fields,
  §6 append-only; cross-reference only).
- `spec/architecture.md` §3-§4 (sneak paths, `I_sneak_max < I_ref < I_prog_min`).
- `spec/program-bias-scheme-proposed-decision.md`,
  `spec/candidate3-read-bias-decision.md`: PROPOSED, unratified.
- `spec/vbd-sensitivity-comparison-proposed.md` (conditional on assumed V_bd).
- `spec/run3-bench-fixture-requirements.md` (pad-ring needs of the bench fixture, delivery form and measurement route; cross-reference only).

## Decision

Propose: the eight measurement cells of §1 with one record each per quantity;
the procedure of §3; the V_bd, resistance and margin extraction of §4-§7 with
the outcome classes of §6 (partial conduction is a separate outcome);
the exact-rank-test detection criterion of §8 as the stated minimum
detectable effect, per comparison and unpooled; and the safety statement of
§10. Numeric limits stay OPEN (B1-B8) until the HV pad record, the first
unprogrammed characterization and the operator's go-ahead provide them.
