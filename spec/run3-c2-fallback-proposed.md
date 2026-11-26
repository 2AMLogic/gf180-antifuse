# Decision Record: Run 3 Fallback Variant — Bare-Capacitor Candidate 2 (`2F`), Proposed

**Status**: Proposed. Records measured evidence and a recommendation only;
the operator chooses whether the fallback or the primary plan is submitted
(on #203), and this record ratifies nothing: it changes no spec target, no
floorplan row, no bench-plan target and no ratified text. If the operator
adopts the fallback for submission, that choice is recorded on #203 and the
downstream deltas listed under "Work left to GDS" become their own issues.
**Date**: 2026-11-17
**Scope**: Issue #372. Prepares the Run 3 fallback ruled on 2026-11-17
(operator, attended `/fleet:decide` round 20261116-r15, q119): a variant
that passes the PDK's native sign-off runset without any exception for
PCell-internal geometry, held ready in parallel with the wafer.space
conversation (#338). Evidence produced here: the scope of
`nfet_10v0_asym` use on the Run 3 chip, the drawn fallback cell
(`layout/cell_candidate2_fallback/`), its native-runset census, and the
cost comparison the ruling asks for. **Date basis**: 2026-12-01 is a
working decision date set against 2026-12-16 — which is Run 3's GDS date
**applicable only if space on that run is obtained**; no space has been
secured (operator correction, 2026-11-17). The decision date is re-set from
the real run and deadline once wafer.space names them; until then 2026-12-16
is the earliest possible date, not a known one.

## Problem

The primary Run 3 test chip carries Candidate 2: a 6.0 V thick-oxide
capacitor (`cap_nmos_06v0`) in series with the 10 V drain-extended access
device `nfet_10v0_asym`, drawn in `layout/cell_candidate2/` as the PDK's own
PCell. #338 step 1 found that wafer.space's Run 3 precheck would reject
candidate 2 as drawn: the 20 native-runset findings inside the unmodified
PCell (`CO.4` x16, `DF.6_MV` x2, `PL.4_MV` x2) are fatal there and no waiver
mechanism was found (#299 records the disposition: reported as measured,
never waived, hand-edited or substituted away). The operator is asking
wafer.space about the precheck (#338 step 2); the answer may be no, or may
come too late to rework. This issue prepares the fallback so the submission
does not depend on that reply.

## Scope of `nfet_10v0_asym` on the Run 3 chip (re-verified)

The filing session had not checked whether anything besides candidate 2
instantiates the device. Re-verified at the Builder's base commit
`1662d845` (2026-11-17, `git grep -n -E "10v0_asym"` over the tree;
`grep -n "10v0" layout/run3_top/run3_top.spice`):

| Where `nfet_10v0_asym` appears | On the Run 3 chip? |
|---|---|
| `layout/run3_top/run3_top.spice`: 2 hits, `XM1` in `cell_candidate2` and `cell_candidate2_Amin_G2x` (`nfet_10v0_asym L=0.60u W=8u nf=2`) | **Yes** — the C2-Amin group only: measurement cells M5/M6, 10 instances (5 Gmin + 5 G2x, `spec/run3-bench-plan.md` §1) |
| `pfet_10v0_asym` in `run3_top.spice` | No hit |
| `design/mux/ls_hv10`, `design/mux/pg_n10`, `design/gen_array.py` Region II band | **No** — these belong to the 32x32 array design; the floorplan states "No on-die mux" on the Run 3 chip |
| `layout/cell_candidate2_Amin_G2x/` | Not drawn (no such directory; `run3_top.spice` derives its literals from `cell_candidate2`) |

The fallback is therefore **candidate 2's 10 instances only**; no other
candidate or peripheral cell on this chip is affected. The array-level
(32x32) Region II exposure in `design/gen_array.py` is real but is a
later-run matter, out of scope here.

## Cost comparison (what the ruling asked to be worked out)

Three routes were compared. The ruling: "Work out which of these is cheaper
and say why."

| | Remove candidate 2 (reassign freed pads/area) | Bare-cap C2 (`2F`, this record) | Compliant access device |
|---|---|---|---|
| Native-runset exposure | none from C2 | the capacitor only: its own `DF.1c`/`PL.2_MV` clear with the ratified geometry (measured below); no PCell, so the 20 PCell-internal findings cannot fire | unknown — no drop-in exists in any ratified record |
| Layout work | none new, but 12 pads (10 PL + BL + WL) go to C1/C3 replicates | one bare-cap cell, two geometries, drawn and measured here; no PCell, no HV device | new device, new cell, new LVS reference, inside the same window |
| Silicon data lost | all thick-oxide (Region II) data | access-device and series-resistance term; on-die current limit (compliance moves to bench/pad resistor); C2 stops being the same experiment as full Candidate 2 | none if electrically equivalent — unproven |
| Verdict | floorplan: "not recommended" | **recommended** | not recommended |

- **Recommended: bare-cap C2 (`2F`)** — the variant `spec/run3-test-chip-floorplan.md`
  ("Variant C2-fallback") and `spec/run3-bench-plan.md` §9 already specify
  in prose. It keeps the one data set that cannot be recovered elsewhere on
  this chip (V_bd of the 6.0 V thick oxide at both capacitor-geometry
  levels), needs no device that is not already in a ratified spec, and its
  native-runset result is now measured (below). It is drawn as two bare
  `cap_nmos_06v0` blocks — one per ratified capacitor-geometry level
  (`spec/capacitor-geometry-decision.md` Region II: Gmin W 1.0 um x
  L 0.70 um, G2x W 2.0 um x L 0.70 um) — in
  `layout/cell_candidate2_fallback/`; the chip replicates each level five
  times (M5/M6, n = 5 each). The generator passes only literal parameters
  to the `klt gen mos_array` capacitor; the only hand-drawn shapes are the
  straps, labels and MOS-capacitor markers `klt` has no primitive for, as
  in every sibling cell. No PCell and no access device exists anywhere in
  the cell.
- **Rejected: remove candidate 2** — discards the thick-oxide point
  entirely for a layout saving not worth that loss (the floorplan already
  says "not recommended").
- **Rejected: compliant access device** —
  `spec/run3-test-chip-floorplan.md` states no 6 V device can stand the
  assumed Candidate 2 program voltage in series; a stacked/cascoded device
  or any other substitute is a new circuit whose program/read behaviour and
  native-runset cleanliness are not traced by any record here, and would
  need its own simulation and layout inside the window. Substituting the
  device is one of the three routes `spec/pdk-pcell-drc-exception-decision.md`
  forbids without an operator ruling; the operator asked for this
  comparison, so the electrical consequence is stated below, but no
  substitute is adopted by this record.

## Native-runset result (measured)

`layout/cell_candidate2_fallback/drc_crosscheck_report.json` —
`klt drc --engine both --deck gf180mcu --top cell_candidate2_fallback
--pdk gf180mcuA --deck-var decks=all,-mslot` at the pin used for
`layout/cell_candidate2/` (klayout-tools `0.9.2`, KLayout `0.30.13`
curated / `0.30.12` native, PDK `open_pdks f6eeac7…`, GDS
`sha256:92b431518b22a3c8067b31442b2c91792df72b9358bb5362b111121a994f7a16`,
regenerated byte-for-byte by `generate.py --check`). No waiver, no
`--deck-var` rule-off beyond the standard `-mslot` (the metal-slotting deck
aborts on this 3LM variant regardless of content, upstream
2AMLogic/klayout-tools#5091; the cell draws only Metal1/Metal2), no
hand-edited shape.

**Curated deck: `clean`, 0 violations.**

**Native runset: `violations`, 5 findings — all die-level, none in any cell
the repo drew.** Census by rule and by cell:

| Rule | Count | Where | Class |
|---|---|---|---|
| `DBU` | 1 | whole layout | the klt writer's 0.0005 um database unit against the runset's 0.001 requirement — every composed cell in this repo carries it (upstream 2AMLogic/klayout-tools#5721) |
| `M2.4`, `M3.4`, `MT30.7` | 1 each | whole die | metal/metaltop density ("coverage over the entire die") — any standalone cell trips these; they become meaningful at chip assembly (#211) with dummy fill |
| `PL.8` | 1 | whole die | Poly2 density, same class |

By cell: zero findings inside `cap_gmin`, `cap_g2x` or the straps; every
finding's bbox is the whole die. **The PCell-internal findings this variant
exists to escape — `CO.4`, `DF.6_MV`, `PL.4_MV` — are absent**, and so are
the capacitor findings the primary-plan cells carry at the old geometry
(`DF.1c`, `PL.2_MV`): W >= 1.0 um and L = 0.70 um clear them, as
`spec/capacitor-geometry-decision.md` derived from the deck. This is the
variant's whole point, measured.

Caveats, stated rather than smoothed over:

- klt's own cross-check `comparison.state` is `not_comparable` with
  `groups: []` (upstream 2AMLogic/klayout-tools#5720, same as
  `layout/cell_candidate2/`), so the census above is read off the two
  per-engine reports in the committed file, by rule — not from klt's
  comparison block.
- `M1.4` (metal1 density) did **not** fire on this cell, though it did on
  `cell_candidate2`; density rules sit near their thresholds at cell scale
  and their firing is a property of the whole-die area, not of the variant.
  The assembled chip is judged at #211, not here.
- LVS (`klt lvs`, same pin): **`match`, 0 errors** — 4 nets
  (`BL`, `PL_GMIN`, `PL_G2X`, `VB`), 2 `cap_nmos_06v0` devices. The
  capacitor's `A`/`P` are secondary parameters KLayout does not compare
  (`device.geometry_not_compared`, same bound as every sibling cell), so
  the drawn dimensions rest on the generator parameters and the committed
  `--check` hash, not on this LVS.

## What is given up against the primary plan (per measurement cell)

The fallback replaces M5 and M6 (`spec/run3-bench-plan.md` §1: C2-Amin,
Gmin and G2x, Amin sizing, n = 5 each) with bare capacitors. Per cell:

| Lost | Consequence |
|---|---|
| The access device (10 V drain-extended, 8 um) | M5/M6 no longer measure access-device-limited programming: the sizing/series-resistance contribution to programmed resistance is gone, and the cells no longer speak to the 10 V device's behaviour at all |
| On-die current limit | compliance during the program ramp is wholly bench-supplied (source compliance, OPEN-B1) or a pad-side series resistor; `spec/run3-bench-plan.md` §9 already states this and the `2F` candidate field |
| The candidate contrast | M5/M6 vs M1-M4 (thin oxide) and M7/M8 (PMOS polarity) stop being candidate comparisons of the kind §8 frames: with no access device, a `2F` row differs from its neighbours in more than oxide flavor/polarity, so cross-candidate reads are off; the within-group geometry comparison (M5 vs M6 Gmin-vs-G2x rank-sum, n = 5 vs 5) survives unchanged |
| Same-experiment status | the data are a different experiment from full Candidate 2; the record's Candidate field must say `2F` (bench-plan §9), and no pooled or cross-referenced yield claim may present `2F` rows as Candidate 2 |

What is **kept** is the point that cannot be recovered elsewhere on this
chip: the 6.0 V thick-oxide V_bd distribution at both ratified capacitor
areas (M5/M6), with private PL per instance and one ramp per instance, so
the yield-vs-condition curve and its exact binomial interval (n = 5:
two-sided 95 % lower bound 0.48 on a clean sweep) are produced as planned.

## Electrical consequence for the program/read path (qualitative, as scoped)

No SPICE was run for this record (single-corner assertion only; any
simulated claim would need a `klt sim` request with corners and is out of
scope here). The consequences below restate what the ratified floorplan and
the PROPOSED bench plan already say, made specific to `2F`:

- **Program path**: PL (private, HV) → gate oxide → S/D → BL. With no
  series device, nothing on die limits the breakdown current. Compliance
  must come from the bench source or a pad-side series resistor; if a
  resistor is used, its value is a known series element in the measured
  path: `R_total = V_read / I_post-read` (bench-plan §5) then includes it
  additively alongside the shared-BL route term (OPEN-B6), and its value
  is recorded so the R_prog correction interval can carry it. The
  access-device on-resistance term the §5 correction names for other
  candidates has no `2F` counterpart.
- **V_bd readout**: the ramp is still on the private PL and detection is
  still the PL current crossing `I_det` (bench-plan §4), so the V_bd
  extraction is unchanged in form; the distribution measured is the
  oxide's own, not an access-device/oxide composite.
- **Read path**: the off state is the capacitor (S/D shorted on BL, gate on
  its private PL), the on state the filament; both states now sit directly
  on the shared BL with no series device in either. The unprogrammed
  leakage term the group shares (bench-plan §5) is the same kind of
  term as before, but no longer bounded by an access device's
  subthreshold current — its magnitude is an OPEN bench quantity, not
  asserted here.

## Work left to GDS (if the operator adopts the fallback)

At minimum:

1. **`layout/run3_top/` generator variant**: the C2-Amin subcircuits lose
   `XM1` and the `WL` port (per-instance ports become `BL PL VB`), and the
   pad-table delta of the floorplan applies — `WL_C2_Amin` becomes unused
   (4 unused pads in total, 3 input-only); all other pads unchanged.
   `scripts/check_run3_pad_table.py` and `design/check-geometry-basis.py`
   re-own their halves.
2. **#211 assembly delta**: the 10 fallback instances placed from the drawn
   cell (both geometry levels, 5 each), dummy fill for the die-level
   density rules this census records as cell-scale artefacts, physical slot
   order, chip-level DRC/LVS through klt.
3. **Bench-plan `2F` fields**: §9 already carries the delta (no WL, bench
   compliance, `R_total` carries the pad-resistor value if used, Candidate
   field `2F`); the measurement-cell table and record template rows for
   M5/M6 follow from it.
4. The `2F` cell is a per-instance representative pair (one Gmin, one G2x
   block, shared BL strap) — the instance count, placement and routing
   duplication to 10 instances is assembly work (#211), not more cell
   drawing.

## Boundaries

- The primary plan is unchanged and keeps going: #207 (candidate 2 and 3
  layouts), #296 (capacitor geometry; its capacitor drawing supersedes the
  geometry code this cell used, not the variant's design — the levels are
  the ratified record's), #299 (the scoped exception record) and #338 (the
  foundry conversation this fallback runs beside).
- No spec target is changed here. Choosing the fallback for submission is
  an operator decision, recorded on #203.
- Agents do not contact wafer.space or the PDK maintainers.
- Array-level (32x32) Region II / peripheral `nfet_10v0_asym` cells are out
  of scope.

## References

- `spec/run3-test-chip-floorplan.md` ("Variant C2-fallback", pad table,
  shuttle-offering dependency) and `spec/run3-bench-plan.md` §1, §4, §5, §9.
- `spec/capacitor-geometry-decision.md` (Region II levels this cell draws),
  `spec/pdk-pcell-drc-exception-decision.md` (the forbidden routes that
  make a fallback necessary), `spec/measurement-matrix.md` §1 (one record
  per measurement cell, never pooled).
- `layout/cell_candidate2_fallback/` (generator with `--check`, GDS,
  `drc_crosscheck_report.json`, LVS request/reference/report) and
  `layout/README.md` section for it.
- #338 (precheck conversation, primary-plan track), #203 (run and
  submission decision), #299/#287 (PCell findings and the old-geometry
  capacitor findings this variant clears).
