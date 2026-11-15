# Decision Record: Capacitor-Geometry Split Levels

**Status**: Implements the ratified wording of `spec/split-axis-plan.md`
section 2 — "the process-minimum **legal** W/L for the region's moscap
device" — by writing down the concrete numbers that sentence already demands.
It departs from no ratified text, so it is not a `-proposed` record and needs
no separate operator ratification; it binds when this PR is merged by the
operator's normal review path. It changes no layout file, no netlist, and no
simulation result.
**Date**: 2026-11-15
**Scope**: The capacitor-geometry split axis only (`spec/split-axis-plan.md`
section 2), for all three moscap devices that plan's region map names:
Region I `cap_nmos_03v3`, Region II `cap_nmos_06v0`, Region III
`cap_pmos_03v3`. It fixes the **Minimum** and **2x-area** drawn W/L and the
meaning of "2x-area". It does not touch the access-device sizing axis
(section 3, including the `wacc`/`lacc` half of `design/README.md` open item
1(a)), and it does not settle #292 (drawn vs. simulated geometry).
**Evidence**: every geometric fact below was measured with released
`klayout-tools==0.9.2` against PDK `gf180mcuA` (`--engine klayout
--deck-var decks=all,-mslot`), first at `origin/main` @ `ab8dd5cf` (#287),
re-verified at `feb788e1` and again at the base `af86a376` — the tree
immediately before this record — where `layout/bitcell_gen.py` still
carries `W_MIN = 0.42` / `L_CAP = 0.28` and
`git grep -nE '0\.42|0\.84' -- spec/` returns no matches, so no ratified
document quoted the old figures before this record. At this record's own
commit the same grep instead matches this record itself plus the one
citation sentence `spec/split-axis-plan.md` adds — both deliberate.
Generatability of every level below is measured, not assumed — see
"Generatability and rule clearance".

## Problem

`spec/split-axis-plan.md` section 2 defines the capacitor-geometry split
axis as a **Minimum** level ("the process-minimum legal W/L") and a
**2x-area** level ("double the minimum capacitor area (via W and/or L
scaling)"). The drawn grid never implemented those words: the generator's
enclosed-contact floor (`layout/bitcell_gen.py` `W_MIN = 0.42`, "generator
floor (== Minimum level for both devices)") was adopted as the spec's
"Minimum", and the PDK's own sign-off runset rejects both drawn levels —
`DF.1c`, "Min. COMP Width for MOSCAP: 1 um" (PDK rule `comp AND mos_cap_mk`
width >= 1 um), fires on all six drawn cells, at Gmin = 0.42 um and
G2x = 0.84 um alike.

So **no ratified sub-minimum point exists to preserve**: the spec's own text
calls for the process-minimum *legal* dimension, and 0.42 um is not legal for
a MOSCAP. Conforming the drawn geometry to >= 1 um is therefore
**implementing** the ratified spec, not relaxing it — under CLAUDE.md's rule
that agents never relax a ratified spec to make results pass, the old numbers
were the defect, and this record is the correction. But the concrete level
numbers were never written down, and "2x-area" must now double a *different*
(legal) minimum area, which changes C for every cell in the grid at once.
That is why the numbers go through a decision record before any geometry
moves.

## Decision

| Region | moscap device | Minimum W x L (um) | Min area (um^2) | 2x-area W x L (um) | 2x area (um^2) | C(2x)/C(Min) |
|---|---|---|---|---|---|---|
| I | `cap_nmos_03v3` | 1.0 x 0.28 | 0.28 | 2.0 x 0.28 | 0.56 | 2.000 |
| II | `cap_nmos_06v0` | 1.0 x 0.70 | 0.70 | 2.0 x 0.70 | 1.40 | 2.000 |
| III | `cap_pmos_03v3` | 1.0 x 0.28 | 0.28 | 2.0 x 0.28 | 0.56 | 2.000 |

- **Minimum** is the process-minimum *legal* W/L, exactly as the ratified
  wording requires: **W = 1.0 um** is the `DF.1c` COMP-width floor for a
  MOSCAP; **L** is each device's process-minimum drawn gate length — 0.28 um
  for the thin-oxide devices and 0.70 um for the 6 V thick-oxide device.
  Each length minimum is read from the PDK's native sign-off runset, not
  from a generator constant: `PL.2_LV` ("Gate Width (Channel Length).
  : 0.28µm") sets the thin-oxide minimum, and the `ngate_6v` edge of
  `PL.2_MV` (width 0.7 um) sets the thick-oxide one; both rules live in
  `~/.ciel/gf180mcuA/libs.tech/klayout/tech/drc/rule_decks/poly2.rb`.
  #287's rule text quotes the 0.70 um minimum and records candidate 2's
  drawn `L_CAP = 0.56` as violating it independently of width; it quotes
  no rule for 0.28 um, so that minimum is cited here from the runset
  directly. (`layout/bitcell_gen.py`'s
  `L_CAP = 0.28 # um, thin-oxide minimum drawn length` comment agrees,
  but it is the same evidence class this issue family found wrong and is
  not relied on.) `DF.1c` constrains the W dimension only — the orthogonal
  COMP extent is already 1.28 um in the drawn cells (#287 marker
  geometry), so raising W alone clears the rule without touching L.
- **2x-area doubles W at fixed L**: 1.0 -> 2.0 um. This implements the
  ratified "via W and/or L scaling" as W-only. One realisation constraint
  is measured and accepted with it: at W_CAP = 2.0 um with the access
  device at its own Minimum width, no single-rectangle `CN` strap clears
  `metal1.space.1` through both tap-ring gaps, so the 2x level's `CN`
  strap is drawn as a doglegged (multi-segment) metal1 shape. That
  constrains the strap drawing, not the level — the measured spans,
  windows and disposition are under "Generatability and rule clearance"
  below, and the drawing itself is #296's.

### Why W-only doubling

1. **It is already the committed convention on the schematic side.**
   `design/README.md` defines capacitor "2x" as "2x `wcap` at the same
   `lcap` (2x area)", and `design/array/array_32x32.sch` instantiates
   `wcap=1e-6, lcap=1e-6` (Minimum) against `wcap=2e-6, lcap=1e-6` (2x).
   Choosing L-doubling here would put the drawn axis out of alignment with
   the simulated axis and make #292 strictly worse.
2. **It is the cleaner experiment.** Section 2's rationale is area-dependent
   (Weibull-type) breakdown statistics, so the axis should vary oxide *area*
   with as little else co-varying as possible. W-only holds L at the process
   minimum on both levels; L-doubling would co-vary channel length with
   area, and for Region II would push L to 1.40 um, well off the `PL.2_MV`
   minimum this record pins to.
3. **It is measured to work**: all six points of the table generate at
   released klt 0.9.2 (see below).

The one consideration that argues for L-scaling instead — strap
buildability at the 2x level — was measured rather than assumed, and does
not carry: the tap-ring exit gaps rise with device width, so at
W = 2.0 um a single-rectangle `CN` strap has no legal position, but a
doglegged strap through the two gaps does, and L-scaling would still
break reasons 1 and 2. The measured spans and the disposition are in
"Generatability and rule clearance"; the constraint is discharged inside
this W-only choice, not by re-leveling the axis.

Rejected alternatives, for the record:

- *L-doubling, or W+L both*: breaks (1) and (2) above.
- *Pin Minimum to the simulated basis (W 1.0 x L 1.0 um) to close #292's
  capacitor gap*: L = 1.0 um is far above the 0.28 um process minimum, so it
  **changes** the ratified wording rather than implementing it — that is the
  departure case, needing operator ratification, which this record does not
  invoke. It is also the weaker case now that `design/README.md` item 1(a)
  records `wcap = lcap = 1e-6` as a PDK symbol-template **placeholder**,
  not a considered design point.
- *Retain a deliberate sub-minimum point for comparison*: same departure
  problem, plus it keeps a cell in the grid that the foundry runset rejects —
  the condition this record exists to end.

### Capacitance consequences

The stock moscap subcircuit (`spec/cell-candidates.md`) computes
`c = <corner>*c_length*c_width*(cvar1+cvar2*tanh(cvar3*v(1,2)+cvar4))`, so C
is **strictly proportional to `c_length*c_width`**. The within-region
2x/Minimum C ratio is therefore exactly **2.000 at any fixed bias**,
independent of the `cvar` coefficients — this is the model's own algebra, not
a parallel-plate estimate. The **absolute** C remains bias-dependent through
the `tanh` term, so the ratio is stated at fixed bias only; per-region
absolute C values come from the PDK model, not from this record.

### What this is, and is not, relative to the ratified text

This record **implements** the ratified definition literally: Minimum = the
process-minimum legal W/L (W at the `DF.1c` floor, L at the drawn gate-length
minimum), 2x-area = double that legal minimum area via W only. No level
falls below a foundry minimum and no level is pinned above the process
minimum for external reasons, so the departure case — a retained
sub-minimum point or a supra-minimum one, either of which needs **operator
ratification, not an agent's call** — does **not** apply, and none is taken.
Had it applied, this file would have been named
`capacitor-geometry-proposed-decision.md` and carried a `(proposed)` marker
in `spec/README.md`.

## Generatability and rule clearance

All six table points generate cleanly (`rc=0`) with
`klt gen mos_array --pdk gf180mcuA` at
`gate_contact: true, add_guard_ring: true, rows=1, cols=1, dummy=0`:

| Point | params | rc | provenance |
|---|---|---|---|
| I Minimum | nfet, w_um 1.0, l_um 0.28 | 0 | #287 |
| I 2x | nfet, w_um 2.0, l_um 0.28 | 0 | #287 |
| II Minimum | nfet medium_voltage, w_um 1.0, l_um 0.70 | 0 | #287 |
| II 2x | nfet medium_voltage, w_um 2.0, l_um 0.70 | 0 | #294 curator probe, 2026-11-14 |
| III Minimum | pfet, w_um 1.0, l_um 0.28 | 0 | #287 |
| III 2x | pfet, w_um 2.0, l_um 0.28 | 0 | #294 curator probe, 2026-11-14 |

`DF.1c` clearance follows on every point from W >= 1.0 um (the rule
constrains the MOSCAP COMP width only, per #287's marker measurements);
`PL.2_MV` is cleared in Region II by L = 0.70 um. This is rule arithmetic on
the drawn dimensions, **not** a DRC run of this record's own: composed-cell
DRC proof is #296's job, and the die-level density rules (`M1.4`/`M2.4`/
`M3.4`/`MT30.7`/`PL.8`) and `DBU` remain out of scope for a standalone cell,
as #287 records.

### CN strap clearance through the tap-ring gaps (measured)

`CN` leaves each block through that block's tap-ring metal1 exit gap
(`ring_gap_um 1.0`, `ring_gap_offset_um -0.7`; cap side `E`, access side
`W`), so it must sit in the intersection of both gaps with >= 0.23 um
(`metal1.space.1`) clearance from each gap edge. Each gap is centred on
its device and rises with the device's width. Measured spans at released
`klayout-tools==0.9.2` (PDK `gf180mcuA`, `klt gen mos_array` port
reports; probes ran with output outside the repo and left it clean):

| block | W (um) | gap span (um, y) |
|---|---|---|
| access (`W_ACC`, not set by this axis) | 0.42 | -0.28..0.72 |
| capacitor, Minimum | 1.0 | 0.01..1.01 |
| capacitor, 2x | 2.0 | 0.51..1.51 |

consistent with the committed `klt gen mos_array` measurements at
W = 0.42 and 0.84 um recorded in
`layout/cell_candidate1_Amin_G2x/generate.py` and
`layout/cell_candidate3_Amin_G2x/generate.py` (-0.28..0.72 and
-0.07..0.93): the gap centre is W/2 + 0.01 um at all four measured
widths, and the span depends on width, not flavor — the committed pair
is identical across thin-oxide nfet/pfet capacitors and medium-voltage
nfet/pfet access devices.

At **Minimum** (W_CAP = 1.0 um) the cap/access gap intersection is
0.01..0.72 um: a single-rectangle `CN` fits, inside a 0.25 um-tall
window (0.24..0.49 um) — tighter than the 0.30 um band the G2x variant
cells draw, so that band does not carry over unshrunk even at Minimum.
At **2x** (W_CAP = 2.0 um) the intersection is 0.51..0.72 um, 0.21 um —
below the 0.46 um two-sided clearance — so **no single-rectangle `CN`
clears `metal1.space.1` at the 2x level** while the access device stays
at Minimum width. The 2x level's `CN` strap is therefore a doglegged
(multi-segment) metal1 shape: each segment passes its gap inside that
gap's window (both windows are 0.54 um tall — -0.05..0.49 um at the
access gap, 0.74..1.28 um at the 2x capacitor gap) and the segments
join over the inter-ring field between the rings. This is a measured
constraint on the strap drawing, not on the level, and it discharges
the question routed here from #296 (Curator flag on #294,
2026-11-15): 2x-area stays W = 2.0 um; that flag's derived
no-single-rectangle conclusion is confirmed by measurement, and the
realisation it forces is the doglegged strap above. Drawing that strap
and DRC-proving it on composed cells is #296's, like every other
composed-cell consequence.

## What this record does not settle

- **#292 (drawn vs. simulated geometry) stays open, and #292 owns it.** The
  gap narrows but does not close: with this table, the drawn Minimum area is
  0.28 um^2 (Regions I/III) and 0.70 um^2 (Region II) against the simulated
  basis `wcap = lcap = 1e-6` (1.00 um^2) — residuals of 3.57x and 1.43x,
  against 8.50x (candidates 1/3) and 4.25x (candidate 2, 0.2352 um^2)
  before. Whether to re-run the SPICE campaigns, revise the schematic
  defaults, or re-draw is #292's decision, and the `design/array/` +
  `design/mux/` regeneration that `design/README.md` item 1(a) describes
  follows from it. **This record authorises that regeneration; it does not
  perform it** — no `.spice`/`.sch` content changes here, and no new issue
  is filed for the follow-through.
- **The committed `sim/array-slice-bench/` bench numbers (path efficiency,
  isolation, leakage) were taken at the placeholder geometry and remain
  valid as structure evidence only.** They say nothing about the
  process-minimum device, and this record does not re-run them; a re-run
  mints a new append-only record under `sim/array-slice-bench/records/`.
- **`spec/run3-test-chip-floorplan.md`'s measured per-instance area goes
  stale.** Its core-area budget cites, as **Measured**,
  `C1 Gmin/Amin instance | 35.9 (8.36 x 4.30)` um^2 from
  `klt stats layout/cell_candidate1/cell_candidate1.gds` bbox
  (-1.23,-1.23)-(7.13,3.07) — taken at the 0.42 um floor. With W = 1.0 um
  and the measured "+y only, by exactly (W - 0.42)" growth law (#296's law,
  independently confirmed at the 2x level by both curator probes), the cell
  height becomes 4.88 um at Minimum and 5.88 um at 2x, so the per-instance
  area is ~40.8 um^2 at Minimum. **That figure is derived, not re-measured
  on a composed cell.** Re-measuring on the composed cell and re-budgeting
  the floorplan is #296's, once it implements this record in `layout/`.
- **The 2x level's doglegged `CN` strap is required here but not drawn
  here.** The measurement above fixes the constraint (no single
  rectangle at W_CAP = 2.0 um with `W_ACC` = 0.42 um) and the realisation
  (multi-segment metal1 through the two ring gaps); the drawing, its pad
  overlaps and its DRC proof on composed cells are #296's, on the same
  standing as the `layout/README.md` reconciliation this record leads.
  The constraint is width-arithmetic on the access side — the gap
  intersection height is exactly W_ACC/2 um — so a single-rectangle
  strap reopens only if section 3 ever raises `W_ACC` above ~0.92 um
  (more, for a realistic strap height); that would be a re-measure at
  the new width, not a re-level of this axis.
- **The `layout/README.md` contradiction is expected.** Until #296 lands,
  `layout/README.md`'s 0.42 / 0.84 narrative (notably its "2x the drawn
  Minimum ... not 2x a process minimum" passage) contradicts this record;
  **this record leads**, and #296 brings `layout/` in line. The matching
  sentence in `design/README.md` ("no ratified spec document fixes what the
  process-minimum legal geometry actually is") is narrowed in the same PR
  that lands this record: its capacitor half now points to this record, and
  only the access half remains a design-rule lookup.
- **The access-device sizing axis is untouched.** Section 3's levels, and
  the access half (`wacc`/`lacc`) of `design/README.md` item 1(a), remain
  provisional; `W_ACC` is not under a MOSCAP rule and is not implicated by
  `DF.1c`.

## Downstream

- **#296** (layout geometry child, "Depends on #294") implements these
  levels in `layout/`: retires the `W_MIN = 0.42` generator floor, updates
  `layout/README.md`'s 0.42 / 0.84 narrative, re-fits the MOSCAP marker,
  proves `DF.1c` clearance and the cell-growth law on composed cells, and
  draws the 2x level's `CN` strap as the doglegged multi-segment metal1
  shape this record measures (no single rectangle fits at W = 2.0 um with
  the access device at Minimum width), DRC-proving it on the composed
  cell.
- **#292** owns the drawn-vs-simulated reconciliation and the `design/`
  regeneration follow-through this record authorises.
- **#287** is the evidence source this record cites rather than re-derives;
  #295 (native-deck DRC reports) is independent recording discipline and
  will be the artefact that shows this record's effect once #296 lands.

## Provenance

- Measurements: 2026-11-14, released `klayout-tools==0.9.2` (the host
  `klt` was a dev build, so the pinned release was used), PDK `gf180mcuA`;
  probes ran with output outside the repo and left it clean.
- Ring-gap spans for the CN-strap clearance table: measured 2026-11-15,
  released `klayout-tools==0.9.2`, PDK `gf180mcuA`, `klt gen mos_array`
  port reports (three probes: capacitor widths 1.0 and 2.0 um at
  `ring_gap_side E`, access width 0.42 um at `ring_gap_side W`); probes
  ran with output outside the repo and left it clean.
- First measured at `origin/main` @ `ab8dd5cf` (#287); the only intervening
  change to `layout/` before re-verification (PR #288) touched
  `cell_candidate2` comment text and `layout/README.md` only —
  `L_CAP = 0.56` and the 0.42 um width were byte-identical at `feb788e1`.
- Re-verified at the base `af86a376` — the tree immediately before this
  record (see Evidence).
- Rule text (`DF.1c` >= 1 um; `PL.2_MV` 6 V n-gate >= 0.7 um) is quoted and
  provenance-stamped in #287. The thin-oxide minimum (`PL.2_LV`, gate
  length 0.28 um) is cited from the native runset deck directly
  (`poly2.rb` of PDK `gf180mcuA`), since #287 quotes no rule for it.
