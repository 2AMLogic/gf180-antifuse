# Decision Record (PROPOSED): Constant-Voltage Time-to-Breakdown (Weibull Slope, Voltage Acceleration) and Sub-Programming Soak

**Status**: PROPOSED -- nothing here is ratified, and nothing here amends or
relaxes a ratified spec. Ratified region map, replicate counts and split axes
(`spec/split-axis-plan.md`, `spec/measurement-matrix.md`) are unchanged; the cell
budget below is drawn from them and its cost is stated, not applied. Returns the
ratification decision to the operator.
**Date**: 2026-11-10
**Scope**: Issue #255. Antifuse physics, array and measurement-record content
only. States no measured or sourced breakdown, slope or acceleration value.
Every model number used is `assumed` as labelled in
`docs/breakdown-oxide-model.md`.

## 1. Gap

- `spec/run3-bench-plan.md` §8 measures breakdown by one voltage ramp per
  instance (n = 4 or 5 per measurement cell) and states the count "does not
  support per-cell tail or Weibull-slope claims".
- `spec/measurement-matrix.md` §1 gives about 16-18 replicates per pulse
  condition per sub-combination, one voltage per condition, one pulse per cell
  per record, and no time-to-breakdown record.
- `docs/breakdown-vbd-sources.md` §5 plans constant-voltage stress at 3 or more
  voltages, but only on pad-accessible shuttle structures; no spec says how the
  array does it. `bd_gam` and `bd_beta` are `assumed`.

## 2. Experiment definition (Wanted items 1 and 4)

**Stress by repeated fixed-width pulses.** The array has no DC hold: voltage is
`VPP` and duration is `PULSE_WIDTH` (`spec/architecture.md` §5), each pulse
needing a fresh arm/strobe. A "constant-voltage" run is therefore: at one `VPP`
level and one `PULSE_WIDTH` code, repeat {arm + strobe, read} on a cell until
the read returns 1 or `N_max` pulses have been applied. Per cell the outcome is
the pulse count `N` at first read = 1 (stress time `t = N x width`, rise/fall
ignored), or right-censored at `N_max`.

Assumptions this makes, each to be checked, none asserted:
- Pulsed stress with intervening reads is equivalent to continuous stress at the
  same voltage (no recovery or duty-cycle effect). Unverified; the Run 3 chip's
  pad structures (§5 of the sources note) are the place to compare.
- Detection is the comparator flipping (`I_cell > I_ref`), not first oxide
  damage. "Time to breakdown" here is time to a read-1 outcome. A soft
  breakdown that stays below `I_ref` is not seen. The threshold is recorded.
- Every read adds read-bias exposure (no certified safe read-disturb limit
  exists; `spec/run3-bench-plan.md` §3). The read count per cell is recorded.

**Voltage levels.** At least three stress voltages per candidate, chosen so the
assumed median times are about one decade apart inside an observation window of
about 4 decades (`N_max / N_min` about 1e4; the window is an open bench value,
OPEN-T1). At the assumed `gamma` that spacing is roughly 0.27 V (thin oxide) and
0.5 V (thick oxide). No voltage is set here; levels are chosen from the first
ramp data and must not exceed the `VPP` and access-device ratings of the HV pad
and program-bias records. Levels are assigned to cells by checkerboard /
round-robin within each stratum, as the ratified pulse-condition axis is.

**Record fields (additive to `spec/measurement-matrix.md` §5).** Quantity
`tddb`; one record = one candidate, one stress voltage, one stratum set
(never pooled across candidates or voltages). Per-cell rows keep the split tags
and add: `stress_V`, `width_code`, `pulses_to_bd` (or `N_max`), `censor`
(`exact` | `right` | `left_at_first_pulse` | `settling`), `reads_n`,
`temp`, `compliance` and `r_post`. In the array `r_post` is **not measurable**
(one-bit `RDATA`, OPEN-M1): the row carries `n/a_onebit`, and the
compliance column carries the design's on-die limit as a recorded value or
`design_fixed`. A cell that breaks during `VPP` settling or ramp-up is kept as
`settling` and treated as left-censored at the first pulse, never dropped
(OPEN-Y1). `scripts/check_measurements.py` does not yet know this quantity;
making the fields normative needs a follow-up there plus a
`measurements/TEMPLATE.md` section (OPEN-T5). Not done in this record.

## 3. Cell budget and cost (Wanted item 1)

No single sub-combination can hold 3 x 60 cells: sub-combinations have 88
(Regions I, II) and 80 (Region III) cells, and two sub-combinations give 176 /
176 / 160. Three voltages x 60 needs at least three sub-combinations of one
region, so the TDDB population is stratified (sub-combination = stratum, a
location term per stratum in the fit, slope and acceleration common). A
candidate's TDDB block is never pooled with another candidate's.

| Option | TDDB cells per candidate | Strata | Cost against the ratified plan | Slope interval (95 %, §4) |
|---|---|---|---|---|
| **S** | 3 x 28 = 84 | 1 sub-combination | uses almost one of four sub-combinations; no soak cells left in it | beta_hat/beta 0.86..1.21; g_hat/g 0.93..1.07 |
| **M** | 3 x 40 = 120 | 2 (same geometry, both sizings) | 2 of 4 sub-combinations | 0.89..1.18; 0.94..1.07 |
| **L** | 3 x 66 = 198 (22 per stratum per voltage) | 3 | 3 of 4 sub-combinations (264 of 352 / 264 of 352 / 240 of 320 cells) | 0.92..1.14; 0.95..1.04 |
| **D** | none now | -- | none; deferred, see §7 | -- |

Option L meets "at least 3 voltages, at least 60 per voltage" and leaves 66
cells of spare/excluded replacement. It consumes three quarters of a region, so
that candidate keeps one sub-combination of ~17.6 cells per pulse condition for
the ratified yield curve. Partial offset: the first-pulse outcome of the TDDB
cells is itself a yield outcome at (stress voltage, width) with n of 66 per
voltage, provided the stress levels coincide with ratified pulse-condition
voltages and widths; it would be a separate record, since one record is one
measurement cell.

Which candidate gets a block, and whether more than one does, is the operator's
decision; this record does not rank the candidates (open lead question, #127).
Each additional candidate costs the same again.

## 4. Expected interval width (method and assumptions)

Method: Monte Carlo of the maximum-likelihood fit, `scripts/tddb_ci_width.py`
(`python3 -I scripts/tddb_ci_width.py --reps 200`, seed 255, about 16 s). Model:
`ln t = mu_stratum - g*k + (1/beta) w`, `w` smallest-extreme-value, with
left/right censoring at the window edges. The table gives the central 95 % range
of the estimator over 200 simulated experiments, as a ratio to the true value.
That is a **finite-sample sampling range, not an asymptotic figure and not a
confidence interval from real data**; 200 repetitions leave the endpoints about
+-0.02 uncertain. The expected-information (asymptotic) half-width, one
stratum, is printed as a cross-check: beta +-0.17 / +-0.11 / +-0.06 and g
+-0.08 / +-0.05 / +-0.03 at 28 / 60 / 200 cells per level, in line with the MC
ranges. For comparison, the ~30 structures per cell with ~25 % relative
uncertainty in `docs/breakdown-vbd-sources.md` §5 is the complete-sample
order of magnitude; a 3 x 28 array block reaches about +-17 % and 3 x 66 about
+-12 % on beta.

Assumed inputs (all `assumed`, none sourced): beta = 1.5 (`bd_beta`; 3.2 and
6.08 are the `beta_i` values), levels 1 decade apart at the design point,
4-decade window, identical cells within a stratum, voltages known exactly,
no cell-to-cell variation beyond the Weibull shape, no recovery.

Sensitivity of Option L (3 x 66, 3 strata), same method:

| Departure from assumption | Censored fraction | beta_hat/beta | g_hat/g |
|---|---|---|---|
| none (beta 1.5) | 0.01 | 0.91..1.12 | 0.95..1.05 |
| beta 3.2 / 6.08 | 0.00 | 0.90..1.13 / 0.93..1.12 | 0.98..1.02 / 0.99..1.01 |
| true acceleration half the assumed (levels 0.5 decade apart) | 0.00 | 0.92..1.10 | 0.92..1.09 |
| true acceleration double (levels 2 decades apart) | 0.33 | 0.89..1.13 | 0.97..1.03 |
| median time 1 decade longer than centre | 0.12 | 0.92..1.15 | 0.95..1.07 |
| median time 2 decades longer than centre | 0.44 | 0.89..1.19 | 0.90..1.11 |
| median time 2 decades shorter than centre | 0.56 | 0.88..1.21 | 0.91..1.10 |

Reading: precision degrades slowly with censoring up to about half the cells
censored, because the window is wide; the larger risk is a window that does not
bracket the data at all, which a pilot of a few cells per voltage before the
full run would catch (OPEN-T1). The interval says nothing about bias from the
equivalence assumptions of §2, which a sampling simulation cannot bound.

## 5. Sub-programming soak (Wanted item 2)

On unprogrammed cells, hold `VPP` at fractions **1/2 and 1/3** of the
programming voltage of the region's nominal pulse condition, for **m times the
programming pulse time** (m as repeated pulses of the nominal width; `m = 100`
is a placeholder, OPEN-T2), then read. Two populations per fraction and per
candidate: cells with no programmed line-sharing/physical neighbour
(*isolated*) and cells next to programmed ones (*adjacent*; TDDB cells that have
already broken down supply those neighbours). The neighbour definition
(shared row/column vs physical) and the placement map are layout-stage items
(OPEN-T4). Each soak record fixes one fraction, one `m` and one neighbour class.

Result per record: `k` failures of `n` with the exact two-sided 95 %
Clopper-Pearson interval, computed per record as in `spec/run3-bench-plan.md`.
Zero-failure upper bounds (same script): n = 15: 0.218; 22: 0.154; 30: 0.116;
60: 0.060; 100: 0.036. With the Option L spare sub-combination (88 cells) split
into 4 classes the bound is 0.154 at best.

Limit stated plainly: under the assumed E-model (`gamma` = 3 decades per MV/cm,
`assumed`) halving the voltage lengthens the time by many orders of magnitude,
so a failure is not expected. A zero-failure soak at these n bounds the
probability only to about 5-20 %; it checks that the extrapolation is not
grossly wrong (e.g. a non-exponential voltage law or a defect tail). It cannot
measure a small disturb probability. That quantity comes from the fitted slope
and acceleration of §4, which is why §4 matters.

## 6. Area and edge (Wanted item 3)

From `spec/split-axis-plan.md` §2, geometry has two levels per region: minimum
and 2x-area, "via W and/or L scaling", same device and oxide. Within one region
the two geometries share oxide and differ in area, but the ratified plan does
not fix how the 2x is reached, so the perimeter ratio is unspecified and the
2-level plan **cannot separate area from perimeter**. The ladder and the
perimeter-heavy/area-heavy pair that can are in the probed structures of
`docs/breakdown-vbd-sources.md` §5, not in the array.

What Option L can do: strata with the same access sizing and different geometry
(Gmin/Amin vs G2x/Amin) are compared by their fitted location difference.
Simulated sampling sd of that difference, ln-time units: 0.12 (beta 1.5), 0.05
(beta 3.2), 0.03 (beta 6.08). Weakest-link scaling for 2x area predicts a shift
of `ln2/beta` = 0.46 / 0.22 / 0.11. The area effect at 2x is then about 4 sd at
beta 1.5, 4 sd at 3.2 and 3-4 sd at 6.08 under the assumptions of §4; a
perimeter-dominated effect gives a different ratio and is not separated.
Options S and M have no geometry contrast of this kind (S has one sub-combination;
M's strata differ in sizing, not geometry).

## 7. Run 3 direct-pad chip (Wanted item 5) -- Decision

**Decision: no constant-voltage hold on the Run 3 instances; the ramp stays as
the only stimulus.** Reasons: every instance is destroyed by its single ramp, so
a hold can only replace a ramp, and the ramp comparisons are already at the edge
of detectability (4 vs 4 needs complete separation; 5 vs 5 needs U <= 2,
`spec/run3-bench-plan.md` §8). Moving even one instance per measurement cell
from ramp to hold drops n to 3 or 4, which removes the 4 vs 4 case (3 vs 4 can
reach p = 0.057 at best), and a hold at 3 voltages on 4-5 instances yields no
slope. Cost to the ramp statistics if done anyway: loss of the geometry and
sizing comparisons at 5 % two-sided. Instances reporting `no_breakdown_at_vmax`
are survivors but a selected population; a hold on them is allowed only as a
separate, unpooled, right-censored record and needs its own operator go-ahead
(§10 of that plan). This does not change the Run 3 deadline.

Count needed for a slope from a pad-limited chip: about 180 instances per
candidate (3 voltages x 60) for the intervals of §4; the Run 3 pad budget gives
36 in all. That is why the array is the venue.

## 8. Option D (defer) -- count that would be needed

If the operator prefers not to spend ratified cells on N = 32: the ratified plan
already names N = 64 as available if replication is too thin (`spec/split-axis-plan.md`,
"Grid size N"). At N = 64 (4096 cells, about 1365 per region, about 340 per
sub-combination) the Option L block (198 cells) is under 15 % of a region and
leaves each yield pulse-condition replicate count about 4 times the N = 32 figure
before the block is taken. Required counts for a deferred run: 3 voltages x 60
cells per candidate for the intervals above, plus 4 soak classes x 30 cells
per fraction pair per candidate for a 0.116 zero-failure bound.

## 9. Open items

- **OPEN-T1: observation window and pilot.** `N_max`, minimum pulse width and
  the 4-decade window are assumed; a pilot of a few cells per voltage fixes the
  stress levels. Unset.
- **OPEN-T2: soak multiple `m` and fractions.** 100 and 1/2, 1/3 are placeholders.
- **OPEN-T3: which candidate(s) and which option (S/M/L/D).** Operator decision;
  nothing here picks a candidate.
- **OPEN-T4: neighbour class and placement map** for the *adjacent* soak cells
  (layout-stage).
- **OPEN-T5: record-format extension.** Add `tddb` quantity and the §2 fields to
  `measurements/TEMPLATE.md` and `scripts/check_measurements.py` (follow-up,
  not in this record).
- **OPEN-T6: pulsed-vs-continuous equivalence** (§2), checkable only on pad
  structures.

## References

- `spec/split-axis-plan.md`, `spec/measurement-matrix.md` (ratified; unchanged).
- `spec/run3-bench-plan.md` §8, §10; `spec/architecture.md` §5.
- `docs/breakdown-oxide-model.md`, `docs/breakdown-vbd-sources.md` §4-§5.
- `scripts/tddb_ci_width.py` (reproduces every interval in §4-§6).

## Decision requested

Choose option S, M, L or D (§3) and the candidate(s) for any block, and rule on
OPEN-T1 to OPEN-T6. Until then nothing in the ratified plan changes. The Run 3
decision of §7 is proposed as stated.
