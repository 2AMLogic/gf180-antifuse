# Decision Record: Grid Size N and Split-Axis Plan

**Status**: Ratified (grid size N is a working target, explicitly subject to
revision — see "Open dependency" below)
**Date**: 2026-08-20
**Scope**: Sub-issue B of the decomposition of #1 — grid size and split-axis
plan only. This record maps grid size and split axes onto the candidate cell
set ratified in `spec/cell-candidates.md`. Program/read architecture
(row/column MUX, SPI addressing) and the on-die/off-die programming-supply
decision are separate decision records that this one has a two-way
dependency on (see below).

## Context

Per `CLAUDE.md`: "the grid is the experiment" — cell design, programming
conditions, and geometry must be deliberately varied across grid regions so
the array maps the antifuse design space rather than proving one operating
point. `spec/cell-candidates.md` (ratified 2026-08-20) selected three
candidate cells that already differ structurally (oxide flavor, device
polarity, access-device family). This record turns that candidate set,
together with the remaining device-physics split axes CLAUDE.md names
(capacitor W/L and geometry, access-device sizing, program pulse
voltage/width), into a concrete N×N grid layout with a stated rationale per
region.

## Grid size N

**N = 32** (a 32×32 array, 1,024 cells) is ratified as the working target.

Rationale:

- **Addressing cleanliness**: 32 = 2^5, so row and column addressing each
  fit a 5-bit field (10 bits total row+column), a clean binary decode with
  no wasted or irregular address space — a favorable starting point for the
  program/read architecture record (sub-issue C) rather than a constraint
  fighting it.
- **Statistical floor per split combination**: with 3 candidate regions
  (below) and 4 geometry sub-combinations per region, N=32 yields roughly
  80–90 cells per geometry sub-combination and, after a 5-point program-pulse
  condition sweep within each sub-combination, on the order of 15–20
  replicate cells per (candidate, geometry, pulse-condition) cell — enough
  for a first-order yield fraction per condition, though thin enough that
  tighter confidence intervals are flagged as a known limitation of this
  first test vehicle (see "Open questions" below) rather than glossed over.
- **Bounded, not fixed, per issue guidance**: the acceptable range considered
  was N between 16 and 64. N=16 (256 cells) was rejected as leaving too few
  cells per (candidate × geometry × pulse-condition) cell for even a crude
  yield fraction. N=64 (4,096 cells) was set aside for this first spin as
  adding array area and row/column decode complexity without a demonstrated
  need — it remains available if sub-issue C's addressing/fan-out analysis
  or early yield data (from this N=32 spin) show N=32's per-condition
  replication is too thin to draw useful yield-vs-condition curves.

### Open dependency: sub-issue C (program/read architecture)

N and the program/read architecture are acknowledged as **mutually
constraining**: row/column MUX fan-out and SPI address width bound how large
N can practically be driven and read, while N bounds how much per-region
yield data the architecture needs to support extracting. This record does
not block on sub-issue C — N=32 is chosen as a reasoned working target within
the independently-bounded 16–64 range — but sub-issue C should treat N=32 as
a proposal to confirm, not a constraint to design around unquestioned. If
sub-issue C's addressing scheme cannot cleanly support N=32 (e.g. row/column
driver fan-out or programming-current budget per column caps simultaneous
drive below what N=32 implies), N should be revisited here rather than
silently shrunk downstream.

## Region layout: contiguous candidate bands, interleaved sub-axes

The array is partitioned in two layers:

1. **Candidate regions — contiguous column bands.** The three candidates
   from `spec/cell-candidates.md` occupy three contiguous column bands
   spanning all 32 rows, rather than being interleaved cell-by-cell or
   row-by-row.
2. **Geometry and program-condition sub-axes — interleaved (checkerboard)
   within each candidate band.** Within a candidate's column band, the
   capacitor-W/L axis, access-device-sizing axis, and program-pulse
   condition axis are each assigned to cells in an interleaved pattern, not
   contiguous stripes.

**Rationale for the split between the two layers:**

- **Candidates are contiguous** because the three candidates use
  structurally different access-device families (`nfet_06v0`/`pfet_06v0`
  symmetric pass devices for Candidates 1 and 3, vs. the asymmetric
  drain-extended `nfet_10v0_asym` for Candidate 2 — see
  `spec/cell-candidates.md`'s note that the asymmetric device's
  source/drain assignment must be deliberate, not left to a symmetric
  pass-gate assumption). Interleaving three different access-device
  families cell-by-cell throughout the array would require every
  row/column driver segment to support all three pass-device electrical
  behaviors (including the asymmetric-terminal constraint) everywhere,
  multiplying row/column MUX design complexity roughly 3x across the whole
  array. Concentrating each access-device family in its own contiguous
  band instead confines that complexity to one band's driver design,
  which is the standard mixed-device-family layout practice this record
  adopts as the simpler, lower-risk option for a first test vehicle.
- **Geometry and pulse-condition sub-axes are interleaved (checkerboarded)**
  specifically to decouple each axis's yield/margin result from
  **systematic die-position gradients** — a real risk CLAUDE.md's "grid is
  the experiment" framing exists to guard against, since wafer-level
  process gradients (e.g. oxide-thickness or threshold-voltage drift
  across the die) can otherwise masquerade as a geometry or pulse-condition
  effect if a given split value is only ever tested in one physical corner
  of a candidate's band. Checkerboarding within the band means every
  geometry sub-combination and every pulse condition is sampled across the
  band's full row extent rather than clustered at one edge.

## Region map

| Region | Columns (of 32) | Rows | Cell count | Candidate (from `spec/cell-candidates.md`) | Oxide flavor | Access device |
|---|---|---|---|---|---|---|
| I | 0–10 (11 cols) | 0–31 | 352 | Candidate 1 — `cap_nmos_03v3` + `nfet_06v0` | 3.3 V thin (`toxe = 8 nm`) | `nfet_06v0` (6.0 V thick, symmetric) |
| II | 11–21 (11 cols) | 0–31 | 352 | Candidate 2 — `cap_nmos_06v0` + `nfet_10v0_asym` | 6.0 V thick (`toxe ≈ 15.2 nm`) | `nfet_10v0_asym` (10 V, asymmetric LDMOS) |
| III | 22–31 (10 cols) | 0–31 | 320 | Candidate 3 — `cap_pmos_03v3` + `pfet_06v0` | 3.3 V thin (`toxe = 8 nm`) | `pfet_06v0` (6.0 V thick, symmetric) |

Column counts are uneven (11/11/10) only because 32 does not divide evenly
by 3; the 10-column band (Region III) is the one region carrying one fewer
column of replication. This is accepted rather than adjusted, since Region
III's oxide flavor and access-device-sizing axis duplicate Region I's
structure (see the "Oxide flavor" axis below) — Region III's role is
isolating polarity, and a small replication difference does not compromise
that comparison.

Row/column orientation (which physical axis is "row" vs. "column" in the
final row/column MUX) is an array/layout-stage decision deferred to
sub-issue C, consistent with `spec/cell-candidates.md` deferring the
asymmetric-device source/drain assignment to the same stage. This record
fixes the band **partition** (three contiguous groups of 11/11/10 along one
grid axis) and the checkerboard sub-partitioning within each band; which
physical direction that axis maps to is not decided here.

## Split-axis mapping

### 1. Oxide flavor — mapped at the region (candidate-band) level

Oxide flavor is not an independently-interleavable axis: it is fixed by
which candidate cell is instantiated at a given grid location, so it is
exactly the Region I/II/III boundary, not a finer-grained split within a
region.

- **Region I & III**: 3.3 V thin oxide (`toxe = 8 nm`), via `cap_nmos_03v3`
  (Region I) and `cap_pmos_03v3` (Region III).
- **Region II**: 6.0 V thick oxide (`toxe ≈ 15.2 nm`), via `cap_nmos_06v0`
  — roughly 2x the Region I/III oxide thickness.

**Rationale**: this is the primary split axis `spec/cell-candidates.md`
ratified — thin vs. thick oxide is expected to require materially different
programming voltage regimes (oxide breakdown field scales primarily with
thickness), so putting the two oxide flavors in physically separate regions
with independently tunable program-pulse conditions (below) is required to
characterize each regime without one region's programming stimulus
compromising the other's cells electrically.

### 2. Capacitor W/L and geometry — interleaved within each region, 2 levels

Within each region, every cell is assigned one of two capacitor geometry
levels, checkerboarded across the region's row extent:

- **Minimum**: the process-minimum legal W/L for the region's moscap device
  (`cap_nmos_03v3` / `cap_nmos_06v0` / `cap_pmos_03v3` as applicable).
- **2x-area**: double the minimum capacitor area (via W and/or L scaling),
  same device and oxide flavor.

The concrete levels are pinned by
[`capacitor-geometry-decision.md`](capacitor-geometry-decision.md): Minimum
W x L is 1.0 x 0.28 um (`cap_nmos_03v3`, `cap_pmos_03v3`) and 1.0 x 0.70 um
(`cap_nmos_06v0`); "2x-area" doubles W at that fixed L (exactly 2.000x C at
fixed bias). The pair the generator drew before that record (0.42 / 0.84 um)
was its enclosed-contact floor, not the process minimum.

**Rationale**: gate-oxide breakdown is commonly modeled with area-dependent
(Weibull-type) statistics — more oxide area under stress has a higher
probability of containing the defect that nucleates breakdown at a given
field, which should show up as a lower programming voltage (or higher yield
at a fixed voltage) for the 2x-area cells relative to minimum-area cells at
the same oxide flavor and pulse condition. This is precisely the
device-physics question CLAUDE.md frames the grid to answer, and it is kept
orthogonal to oxide flavor by testing it within each region rather than only
at one oxide thickness. Two levels (not three or more) were chosen to keep
each sub-combination's cell population, and therefore each pulse-condition
replicate count, above the statistical floor discussed under "Grid size N".

### 3. Access-device sizing — interleaved within each region, 2 levels, orthogonal to the W/L axis

Independently of the capacitor W/L axis, every cell is also assigned one of
two access-device sizing levels, checkerboarded orthogonally to the
capacitor-geometry checkerboard (so all four combinations of {capacitor
geometry} × {access sizing} occur, each roughly evenly across the region):

- **Minimum**: process-minimum channel width for the region's access device
  (`nfet_06v0` / `nfet_10v0_asym` / `pfet_06v0`), at that device's
  design-rule-set minimum drawn length.
- **2x-width**: double the minimum channel width, same drawn length.

Region II's access device (`nfet_10v0_asym`) differs structurally from
Regions I and III's: as an LDMOS device from the dedicated `SM-BB-000149`
high-voltage process module, its minimum drawn length is fixed by the HV
process module's design rules rather than by the standard logic device
rules that set Region I/III's minimum length. Region II's sizing axis
therefore varies channel width only, at that fixed HV-module minimum length
— the same two-level width scaling as Regions I/III, but without a
comparable length-scaling degree of freedom.

**Rationale**: access-device sizing sets the on-resistance and current
capacity of the programming path in series with the capacitor being broken
down. A too-narrow access device can current-limit the programming pulse
(under-delivering the energy needed for a clean breakdown, or extending the
effective pulse width needed to reach it) and can also degrade post-program
read margin by adding series resistance that the sense path must
distinguish from the programmed-cell resistance itself
(`CLAUDE.md`: "Read-margin claims need the sense path's worst-case corner,
programmed and unprogrammed resistance distributions both"). Sizing is kept
orthogonal to capacitor geometry (four combinations per region, not treated
as a single combined axis) because it is a distinct physical mechanism —
current delivery / series resistance, not oxide breakdown statistics — and
conflating the two would prevent isolating which one drives a given yield or
margin shift.

### 4. Program pulse voltage/width — a test-campaign axis applied within each geometry×sizing sub-combination

Program pulse voltage and width are not baked into the silicon at any
grid location — they are stimuli applied externally through the SPI
program path at test/characterization time, identical hardware regardless
of pulse recipe. The "region mapping" for this axis is therefore about
**which cell population each pulse condition is measured against**, not a
layout choice:

- Within each of a region's four (capacitor-geometry × access-sizing)
  sub-combinations (roughly 80–90 cells each, per the Region I/II/III
  populations above), the sub-combination's cell population is further
  divided, again by checkerboard/round-robin cell assignment (not
  contiguous clustering), across a multi-point program-pulse condition
  sweep: at minimum, a voltage sweep at a fixed nominal pulse width and a
  width sweep at a fixed nominal voltage, for roughly 5 conditions total per
  sub-combination.
- This produces, per (candidate region, capacitor geometry, access sizing,
  pulse condition) cell, a replicate population on the order of 15–20 cells
  — the yield-fraction sample `sim/README.md` and `measurements/README.md`
  require to report "yield-vs-condition distributions, per grid region"
  rather than a single transient that happened to program.
- The nominal center point of the voltage/width sweep differs by region,
  because the two oxide flavors are expected to require different absolute
  programming voltages (see "Oxide flavor" above and
  `spec/cell-candidates.md`'s programming-voltage-regime notes per
  candidate); the sweep's *relative* structure (a voltage sweep and a width
  sweep of comparable shape around each region's own nominal point) is kept
  consistent across regions so yield curves are comparable in relative,
  not absolute, terms.

**Rationale**: mapping program-pulse condition to specific replicate
sub-populations, rather than applying one fixed condition array-wide, is
what turns "programming worked on this die" into a yield-vs-condition curve
per region — directly serving `CLAUDE.md`'s requirement that "claims about
programming need yield-vs-condition curves … not a single transient that
happened to pop." Checkerboarding the condition assignment within a
sub-combination (rather than clustering, e.g., the highest-voltage
condition at one edge of the region) avoids confounding a condition's yield
with the same die-position-gradient risk the geometry/sizing checkerboard
guards against.

## Summary: axis-to-region mapping

| Split axis | Region-level or sub-region-level | Levels | Where it is set |
|---|---|---|---|
| Oxide flavor | Region (candidate band) | 2 flavors across 3 regions (I/III thin, II thick) | Fixed by which candidate cell occupies the region |
| Capacitor W/L / geometry | Sub-region, interleaved within each region | 2 (minimum, 2x-area) | Checkerboard across each region's row extent |
| Access-device sizing | Sub-region, interleaved within each region, orthogonal to W/L | 2 (minimum, 2x-width) | Checkerboard, orthogonal to the W/L checkerboard |
| Program pulse voltage/width | Test-campaign axis within each (region, geometry, sizing) sub-combination | ~5 conditions (voltage sweep + width sweep around region's nominal point) | Checkerboard/round-robin cell assignment within each sub-combination's replicate population |

Every axis named in the issue — capacitor W/L and geometry, oxide flavor,
access-device sizing, program pulse voltage/width — is accounted for above;
none is dropped.

## Open questions carried forward (not resolved here)

- **N is a working target, not final** — see "Open dependency: sub-issue C"
  above. If sub-issue C's addressing/fan-out analysis or early yield data
  from an N=32 spin show the ~15–20-cell-per-condition replication is too
  thin for useful confidence intervals, N should be revisited (most likely
  upward, within the 16–64 bound already considered) rather than silently
  accepted as adequate.
- **Row/column physical orientation** of the band partition (which grid
  axis carries the 11/11/10 candidate split vs. which is addressed within a
  band) is deferred to sub-issue C, consistent with
  `spec/cell-candidates.md` deferring the Candidate 2 access device's
  source/drain assignment to the same array/layout stage.
- **`_b` (body-tap) moscap variants** flagged as an open question in
  `spec/cell-candidates.md` are not included as a fifth region or
  additional split axis here — they were left as a candidate-set
  refinement question in that record, not part of the ratified candidate
  set this plan maps regions against. If a future decision record adds
  them to the candidate set, this plan's region map would need revisiting.
- **Statistical power at N=32** (roughly 15–20 replicate cells per fully
  crossed condition) is workable for a first-order yield fraction but thin
  for tight confidence intervals; this is accepted as a known limitation of
  a first test vehicle rather than a gap to close in this record — the
  `measurements/` per-region matrix should report replicate counts alongside
  yield fractions so downstream consumers can judge the sample size
  themselves.

## References

- `spec/cell-candidates.md` — the ratified candidate cell set (Candidates
  1, 2, 3) this record maps onto grid regions I, II, III respectively.
- `CLAUDE.md` — "the grid is the experiment" (split-axis requirement),
  "programming is an analog event, not a digital write" (yield-vs-condition
  requirement), and the read-margin corner requirement.
- `measurements/README.md`, `sim/README.md` — the per-region result and
  yield-curve conventions this plan's region map is designed to key.

## Decision

Ratify N=32 (32×32, 1,024 cells) as the working grid size, subject to
revision once sub-issue C's program/read architecture is ratified. Ratify
the two-layer region structure: three contiguous candidate column bands
(Regions I, II, III, mapped to Candidates 1, 2, 3 of
`spec/cell-candidates.md`) each carrying an interleaved (checkerboarded)
2-level capacitor-W/L axis and 2-level access-device-sizing axis, with
program-pulse voltage/width applied as a test-campaign axis (~5 conditions)
checkerboarded within each resulting sub-combination. Sub-issue C (program/
read architecture) and sub-issue D (on-die/off-die programming-supply
decision) build on this plan.
