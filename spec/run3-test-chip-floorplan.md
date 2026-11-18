# Decision Record: Run 3 Test Chip Floorplan, Instance Counts and Pad Budget

**Status**: Proposed for operator ratification. Adds a new chip-level floorplan
for the Run 3 test chip (quarter-slot target; space not yet secured);
relaxes and amends nothing in `spec/cell-candidates.md`,
`spec/split-axis-plan.md`, `spec/architecture.md` or any other ratified
record. Where this chip deliberately covers less than the
ratified 32x32 plan, that is stated as a chip-level scope cut (the array is out
of scope for this chip per #203), not as a change to the plan.
**Date**: 2026-10-29
**Scope**: Issue #206, part of #203. Per-candidate cell types and instance
counts, the split axes carried by which instances, the 48-I/O pad table, the
instance-to-pad wiring scheme and its measurement effects, the core-area
budget, and the shuttle-offering dependency. No layout, no HV pad or
protection design, no assembly, no bench plan (siblings of #203). Antifuse
physics, pad and addressing content only.

## Slot template read

Read 2026-10-29 from the public template page
(`https://mith.ro/gf180mcu-project-template/`, redirect target of the
`mithro.github.io` link in #203). The page is stamped "Generated: 24 Oct 2026
01:02 UTC" and shows **no version or revision number**, so the date stamp is
the only revision identifier. Facts used:

| Item | Value on the page |
|---|---|
| Die | 1.94 x 2.53 mm |
| Core | 1.05 x 1.65 mm = 1.73 mm^2 |
| Pads (standard quarter slot) | 56 = 48 signal I/O + 8 power (4 DVDD, 4 DVSS) |
| Signal I/O types | 38 bidirectional, 6 input-only, 4 analog |
| Pad voltage | not stated on the page |

The page also lists a 2-side "EXACT" variant (14 I/O); it is **not** used, #203
rules for the standard quarter slot. The pad voltage is not stated, so "standard"
below means the standard pad cell class (the 5 V class per #203), and "HV"
means a pad that must carry the program voltage (~8-16 V per #203). If the
template is revised, the slot-type counts above are the inputs to re-check.

## Cells and instance counts

Cell types are exactly Candidates 1, 2, 3 of `spec/cell-candidates.md`. An
**instance** is one cell with its own private plate pad. A **group** is a set
of instances sharing a bit-line pad and a word-line pad. Axis names follow
`spec/split-axis-plan.md` §2-3: capacitor geometry `Gmin`/`G2x`, access sizing
`Amin`/`A2x`.

| Group | Candidate | Cap | Access | Axes varied inside the group | Instances | Per (geometry) level |
|---|---|---|---|---|---|---|
| C1-Amin | 1 | `cap_nmos_03v3` | `nfet_06v0` min | cap geometry | 8 | 4 |
| C1-A2x | 1 | `cap_nmos_03v3` | `nfet_06v0` 2x width | cap geometry | 8 | 4 |
| C2-Amin | 2 | `cap_nmos_06v0` | `nfet_10v0_asym` min | cap geometry | 10 | 5 |
| C3-Amin | 3 | `cap_pmos_03v3` | `pfet_06v0` min | cap geometry | 10 | 5 |

36 instances. Every instance belongs to exactly one (candidate, geometry,
sizing) measurement cell of `spec/measurement-matrix.md` §1; there are eight
such cells: C1 x {Gmin, G2x} x {Amin, A2x}, C2 x {Gmin, G2x}, C3 x
{Gmin, G2x}. No instance is a duplicate of another region's: each measurement
cell differs from every other in at least one of oxide flavor, polarity,
access device, cap geometry or access sizing.

**Which axes vary where, and why**

- *Oxide flavor and polarity*: fixed by candidate (C1 thin NMOS, C2 thick
  NMOS, C3 thin PMOS), as in the plan. C1 vs C3 isolates polarity at equal
  oxide; C1 vs C2 isolates oxide thickness (with the access class changing
  with it, as the plan already accepts).
- *Cap geometry (2 levels)*: varied in every group, because area dependence
  of V_bd is the plan's central physics question and costs no extra pads
  (each level just takes more private plates).
- *Access sizing (2 levels)*: varied **only for C1**. C1 is the baseline whose
  sizing effect (series-resistance and compliance effect on programmed
  resistance) must be separated first; C2's sizing axis is width-only at a
  fixed HV-module length and C2 is also the offering-risk candidate, so its
  pads are spent on replicates instead. C3 is held at `Amin` so that C1-Amin vs
  C3-Amin is a like-for-like polarity comparison.
- *Program pulse voltage/width*: **not carried as a split on this chip.**
  A programmed cell cannot be reprogrammed, and 4-5 replicates per level leave
  none to divide among ~5 conditions. Each instance is instead taken through a
  voltage ramp, so every instance yields one V_bd sample and the
  yield-vs-condition curve is the empirical CDF of V_bd per measurement cell.
  The pulse-width axis of plan §4 is therefore uncovered here; that gap is
  stated, not closed.

**Count justification (statistics)**: the output per measurement cell is a
set of n V_bd values and n programmed-resistance values, n = 4 (C1) or 5
(C2, C3). With n samples, the chance that one further cell falls inside the
observed min-max range is (n-1)/(n+1): 60 % at n = 4, 67 % at n = 5. That
supports detecting a shift between levels that is large against the spread
and a first-order spread estimate; it does **not** support a Weibull-slope
claim per measurement cell, and no record may pool measurement cells to
raise n. The count is set by the pad budget (below), not by the statistics;
tighter statistics need an array (out of scope) or more pads. Reporting rule
from `spec/measurement-matrix.md` §1 applies unchanged: one record per
measurement cell, `n` in every record.

## Wiring scheme and its effect on measurement

**Chosen: private plate (PL) per instance, shared bit line (BL) and word line
(WL) per group.** Per-instance PL, shared BL/WL.

Why private PL, not shared PL with per-instance select (rejected): under the
PL-driven program scheme (VPP on PL, BL at 0 V; PROPOSED in
`spec/program-bias-scheme-proposed-decision.md`, not ratified) a programmed
cell's internal node follows PL. With a shared PL, every already-programmed
instance would keep its access device across the full VPP while the next
instance is programmed, against a 6 V/10 V rating that the proposed record
already finds marginal for a single selected cell. Private PL removes that
path: only the instance whose PL is driven sees VPP. If the operator ratifies
BL-driven programming for any candidate, the HV terminal moves to BL and the
private/shared roles of BL and PL swap for that candidate; pad **counts** are
unchanged, the slot types are not (HV on bidirectional, standard on analog),
which the HV-pad sibling must confirm.

Measurement effects of what is shared:

- **Shared BL (up to 10 instances)**: the read sense node is common. Reading
  instance k requires the other instances' PL to add no current. Two bench
  options, both leaving the chip unchanged: (a) leave unselected PL pads
  high-impedance, which puts the unselected instances' pad-leakage in the
  sense path; (b) drive unselected PL to the BL potential, which puts no
  voltage across them but needs one bench channel each. Either way the
  unprogrammed floor (`I_sneak_max` of `spec/architecture.md` §4) now includes
  a term that scales with group size minus one; it is not a per-cell number
  and must be measured, not assumed. Candidate 3's programmed read current is
  already near the fA scale in the proposed read-bias record, so that
  candidate is the most exposed; its group is therefore not enlarged beyond
  10.
- **Shared WL**: all instances of a group are gated together; selection is
  by PL only. Unselected instances have PL at 0 V, so they see no oxide
  stress with WL on.
- **Series resistance**: the program and read current return through the
  shared BL route (metal run of the order of 1 mm, pad and bond). There are
  no Kelvin pads (no spare budget). The route resistance is an *estimate*
  (tens of ohms; sheet resistance not looked up for this record) and adds to
  every programmed-resistance reading in a group equally. The proposed
  records use an assumed 10 kOhm filament, so the term is small but must be
  subtracted from, or bounded in, `measurements/` records.
- **No on-die mux**: no shared selection path exists on-die, so there is no
  switch leakage or on-resistance to de-embed. This is the reason for the
  all-passive scheme.
- **Body ties**: Candidates 1 and 2 bodies (p-substrate) are tied on-die to
  the substrate; there is no body-bias axis. Candidate 3's n-well tie is a pad
  (`VBW_C3`), because the proposed read-bias record sets it as a read-bias
  variable (`spec/candidate3-read-bias-decision.md`).

## Pad table

Pad IDs `L01`-`L48` are **logical** slots, one per signal I/O of the template,
grouped by slot type (the slot-type counts match the template exactly). The
mapping of logical slots to physical ring positions is part of full-chip
assembly (#211), because the physical order of slot types around the ring was
not read from the page. Direction is the bench's view of the signal. "HV"
means the pad must carry the program voltage; its structure and protection
are the HV-pad sibling issue's, and this record only reserves the slots. The
"Slot type" column is a request: HV pads occupy bidirectional-slot positions
(an assumption for that sibling to confirm or move to other slots).

| Pad | Signal | Direction | Slot type | Voltage class | Note |
|---|---|---|---|---|---|
| L01 | `PL_C1_Amin_Gmin_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L02 | `PL_C1_Amin_Gmin_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L03 | `PL_C1_Amin_Gmin_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L04 | `PL_C1_Amin_Gmin_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L05 | `PL_C1_Amin_G2x_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L06 | `PL_C1_Amin_G2x_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L07 | `PL_C1_Amin_G2x_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L08 | `PL_C1_Amin_G2x_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L09 | `PL_C1_A2x_Gmin_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L10 | `PL_C1_A2x_Gmin_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L11 | `PL_C1_A2x_Gmin_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L12 | `PL_C1_A2x_Gmin_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L13 | `PL_C1_A2x_G2x_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L14 | `PL_C1_A2x_G2x_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L15 | `PL_C1_A2x_G2x_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L16 | `PL_C1_A2x_G2x_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L17 | `PL_C2_Amin_Gmin_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L18 | `PL_C2_Amin_Gmin_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L19 | `PL_C2_Amin_Gmin_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L20 | `PL_C2_Amin_Gmin_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L21 | `PL_C2_Amin_Gmin_5` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L22 | `PL_C2_Amin_G2x_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L23 | `PL_C2_Amin_G2x_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L24 | `PL_C2_Amin_G2x_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L25 | `PL_C2_Amin_G2x_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L26 | `PL_C2_Amin_G2x_5` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L27 | `PL_C3_Amin_Gmin_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L28 | `PL_C3_Amin_Gmin_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L29 | `PL_C3_Amin_Gmin_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L30 | `PL_C3_Amin_Gmin_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L31 | `PL_C3_Amin_Gmin_5` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L32 | `PL_C3_Amin_G2x_1` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L33 | `PL_C3_Amin_G2x_2` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L34 | `PL_C3_Amin_G2x_3` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L35 | `PL_C3_Amin_G2x_4` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L36 | `PL_C3_Amin_G2x_5` | bidir (bench drives/senses) | bidir slot | HV | private plate of one instance |
| L37 | `BL_C1_Amin` | analog (bench sources/senses) | analog slot | standard | shared by the 8 instances of group C1-Amin |
| L38 | `BL_C1_A2x` | analog (bench sources/senses) | analog slot | standard | shared by the 8 instances of group C1-A2x |
| L39 | `BL_C2_Amin` | analog (bench sources/senses) | analog slot | standard | shared by the 10 instances of group C2-Amin |
| L40 | `BL_C3_Amin` | analog (bench sources/senses) | analog slot | standard | shared by the 10 instances of group C3-Amin |
| L41 | `WL_C1_Amin` | input (bench drives) | input-only slot | standard | shared gate of group C1-Amin |
| L42 | `WL_C1_A2x` | input (bench drives) | input-only slot | standard | shared gate of group C1-A2x |
| L43 | `WL_C2_Amin` | input (bench drives) | input-only slot | standard | shared gate of group C2-Amin |
| L44 | `WL_C3_Amin` | input (bench drives) | input-only slot | standard | shared gate of group C3-Amin |
| L45 | `VBW_C3` | bidir (bench drives) | bidir slot | standard | C3 n-well tie, shared |
| L46 | `UNUSED_1` | none | input-only slot | n/a | unused |
| L47 | `UNUSED_2` | none | input-only slot | n/a | unused |
| L48 | `UNUSED_3` | none | bidir slot | n/a | unused |

Totals: 36 HV (bidirectional slots), 9 standard (1 bidirectional, 4 analog,
4 input-only), 3 unused (2 input-only, 1 bidirectional). Slot type use:
bidirectional 38/38 (36 PL + `VBW_C3` + 1 unused), analog 4/4 (the four BL),
input-only 6/6 (4 WL + 2 unused). Sum 48. The 8 power pads (4 DVDD, 4 DVSS)
are separate from the signal I/O and carry no signal here. The three unused
pads are held for the sibling issues (e.g. an HV-pad reference structure
needed by the HV-pad sibling) and are not assigned design content.

Analog-slot assignment (BL on the analog pads) is a choice to put the
low-current sense nodes on the pads the template provides for analog use; it
is not a claim about that pad's leakage, which the template page does not
state.

## Core-area budget

Core = 1.73 mm^2 (1.05 x 1.65 mm). Every footprint below is **in um^2**.

| Item | Per-item footprint | Count | Subtotal | Basis |
|---|---|---|---|---|
| C1 `Gmin`/`Amin` instance | 35.9 (8.36 x 4.30) | 4 | 144 | **Measured**: `klt stats layout/cell_candidate1/cell_candidate1.gds` bbox (-1.23,-1.23)-(7.13,3.07), including both tap rings |
| C1 `G2x`/`A2x` instances | 72 | 12 | 864 | **Estimate**: upper bound of 2x the drawn cell for any doubled axis |
| C2 instance | 360 | 10 | 3,600 | **Estimate**: 10x C1 for the drain-extended LDNMOS and thick-oxide cap; not drawn |
| C3 `Gmin` instance | 59.5 (10.12 x 5.88) | 5 | 297.5 | **Measured**: `klt stats layout/cell_candidate3/cell_candidate3.gds` bbox (-2.02,-2.02)-(8.10,3.86), including both tap rings. The access block's tap ring is drawn at the raised generator padding 1.29 um (#297); the block offset grows with it |
| C3 `G2x` instance | 67.5 (10.12 x 6.67) | 5 | 337.5 | **Measured**: `klt stats layout/cell_candidate3_Amin_G2x/cell_candidate3_Amin_G2x.gds` bbox (-2.02,-2.02)-(8.10,4.65), including both tap rings. Same raised acc-ring padding as the `Gmin` cell (#297's parameter, re-bisected on this cell by #382); the grown bbox replaces the row the C3 budget used to share |
| Cell subtotal | | 36 | **5,243** (0.0052 mm^2) | |
| PL routes to pads | 5 um x ~800 um | 36 | 144,000 | **Estimate**: 5 um pitch (HV-spacing allowance) x ~0.8 mm mean run |
| BL/WL routes | 2 um x ~1.0 mm | 8 | 16,000 | **Estimate** |
| HV protection/clamp allowance | placeholder | | 500,000 | **Placeholder**: the HV-pad sibling sets the real figure |
| **Total** | | | **~665,240** (0.67 mm^2) | |

Margin: 0.67 mm^2 against 1.73 mm^2 core leaves 1.06 mm^2 (about 61 %) free.
Even if every estimate were doubled the total (1.33 mm^2) stays under the
core. The cells are a negligible fraction (about 0.30 % of the core); the
binding limit is the **pad count**, not area. Instance counts therefore
cannot be raised by area alone. Candidates 1 and 3 are drawn; candidate 1's
and candidate 3's drawn sizes are from the committed GDS. Candidate 2 is not
drawn (sibling issue), so its row is an estimate and must be replaced by its
drawn bounding box when that layout exists.

## Shuttle-offering dependency

Candidate 2's access device `nfet_10v0_asym` is not confirmed as offered
(#203). The 6.0 V thick-oxide capacitor `cap_nmos_06v0` is part of the same
3.3/6 V dual-oxide set as Candidate 1/3's access devices and is assumed
offered; that assumption is also unconfirmed.

**Variant C2-fallback (if `nfet_10v0_asym` is not offered)**: replace
Candidate 2 by 10 bare `cap_nmos_06v0` capacitor instances (`Gmin`/`G2x`,
5 each), PL private, BL shared, no access device (no 6 V device can stand
the assumed Candidate 2 program voltage in series). Pad table delta: `WL_C2_Amin`
becomes unused (4 unused pads in total, 3 input-only); all other pads
unchanged. Cost, stated plainly: with no series device the program current is
not limited on-die, so compliance must come from the bench or a pad-side
series resistor, the access-sizing and series-resistance contribution to
programmed resistance is gone for that group, and the C2 data are no longer
the same experiment as the full Candidate 2. Alternative: drop Candidate 2 and
move its 12 pads to extra replicates of Candidates 1 and 3; this loses the
thick-oxide point and is not recommended.

## References

- `spec/cell-candidates.md` (Candidates 1-3), `spec/split-axis-plan.md`
  (axes and measurement-cell definition), `spec/measurement-matrix.md` §1
  (one record per measurement cell, `n` in every record),
  `spec/architecture.md` §4 (`I_sneak_max`), `spec/supply-domains-decision.md`.
- `spec/program-bias-scheme-proposed-decision.md` and
  `spec/candidate3-read-bias-decision.md`: PROPOSED/unratified; this record
  depends on them only as stated above.
- `layout/cell_candidate1/cell_candidate1.gds`: footprint source.

## Decision

Propose: 36 instances (C1 16, C2 10, C3 10), private plate per instance and
shared BL/WL per group, the 48-slot pad table above, and the stated C2
fallback. Open items for the operator: ratification of the PL-driven program
scheme (which decides whether the HV terminals are PL or BL), the HV-pad
structure and slot type (sibling), the offering of `nfet_10v0_asym`, and the
physical slot order (assembly).
