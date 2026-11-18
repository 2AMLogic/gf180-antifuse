# Requirements Note (Proposed): Bench Fixture Needs on the Run 3 Pad Ring

**Status**: Proposed. **Needs an operator read before the 2026-12-16 GDS
submission** (a date that holds only if shuttle space is obtained), because
pad order, grouping and spacing are frozen at that point.
Relaxes and amends nothing in `spec/run3-test-chip-floorplan.md`,
`spec/hv-pad-protection-decision.md`, `spec/run3-bench-plan.md` or any other
record. Anything not fixed by one of those records is **OPEN**, with who
supplies the answer; no value is invented here.
**Date**: 2026-11-13
**Scope**: Issue #260, part of #203. What the bench fixture needs from the pad
ring of the Run 3 test chip (quarter-slot target, space not yet secured;
order, grouping, spacing, spare pads), the delivery form and package/pinout
(OPEN), and the measurement route per delivery form with the instrument
classes each needs. Does not change the
layout, the measurement plan (#255) or the pad table, and does not cover
ordering or fixture hardware design.

## Sources

Every constraint below cites one of: **[FP]** `spec/run3-test-chip-floorplan.md`,
**[HV]** `spec/hv-pad-protection-decision.md`, **[BP]**
`spec/run3-bench-plan.md`. A requirement with no source is marked **derived**
and is a request for the operator, not a ratified constraint.

## 1. Pad groups and what the fixture needs from each

Pad IDs are the logical slots `L01`-`L48` of [FP] "Pad table". The physical
position of each logical slot around the ring is not fixed by [FP]; it is
assigned in full-chip assembly (#211) ([FP], pad-table preamble). Section 2
lists what the fixture asks of that assignment.

| Group | Pads | Count | Fixture needs | Source |
|---|---|---|---|---|
| HV plate (PL) | L01-L36 | 36 | Bare pad, no pad-cell diodes or clamp, so the fixture sees the plate directly. Bench-side series resistor and source compliance (placeholder 10 kOhm, OPEN-B1). Unselected PL driven to 0 V during any ramp: one channel each, or a matrix (OPEN-B4). No ESD structure on the die, so handling discipline is a fixture requirement. | [HV] Answer 1-3, 5; [BP] §2 |
| Bit line (BL) | L37-L40 | 4 | Low-current sense. C3 programmed read current is near fA scale in the proposed read-bias record, so leakage on the BL path is the dominant fixture risk. The instrument floor is measured, not assumed (OPEN-B2). | [BP] §2 BL row, §3.1 |
| Word line (WL) | L41-L44 | 4 | DC drive per group; levels OPEN-B3. | [BP] §2 WL row |
| C3 well tie (`VBW_C3`) | L45 | 1 | DC supply that tracks the C3 read rail. | [BP] §2 `VBW_C3` row |
| Unused | L46-L48 | 3 | None required. Held for sibling issues (an HV-pad reference structure). | [FP] pad-table totals |
| Power | 4 DVDD, 4 DVSS (outside L01-L48) | 8 | Carry no signal on this chip; whether the fixture bonds, probes or leaves them floating is OPEN (§4). | [FP] pad-table totals |

Wiring facts the fixture inherits: 4 BL pads are shared by 8 / 8 / 10 / 10
instances, so reading one instance needs the other plates either high-impedance
or driven to the BL potential ([FP] "Shared BL"; [BP] §3.2). Groups of PL pads
map to measurement cells M1-M8 as in [BP] §1 (L01-L04 M1 ... L32-L36 M8).

## 2. Constraints on pad order, grouping and spacing

| # | Requirement | Pad IDs | Status | Source |
|---|---|---|---|---|
| R1 | The 36 PL pads reach a bare bond pad with no pad cell on the route. This is an open dependency on the shuttle template, not something the fixture can fix. If the ring's pad cells cannot be bypassed, no program voltage above about 6.5 V reaches a cell and this note's HV route is moot. | L01-L36 | OPEN (operator / shuttle offering) | [HV] "Principal dependency" |
| R2 | Order PL pads so each measurement cell's pads (M1-M8) are contiguous and the group boundaries fall on measurement-cell boundaries, so one probe-card or socket bank corresponds to one record. | L01-L36 | Derived (request to #211); pad IDs already follow this order logically | [FP] pad table; [BP] §1 |
| R3 | Keep the four BL pads (analog-slot pads) physically away from HV PL pads, or separated by a pad at a fixed bias, so the fA-scale sense path is not adjacent to a pad ramped to the program voltage. | L37-L40 vs L01-L36 | Derived (request to #211). The template does not state analog-pad leakage ([FP] "Analog-slot assignment"); the fixture cannot assume a value. | [BP] §2, §5; [FP] |
| R4 | HV pad pitch and pad-to-pad spacing the fixture can stand off at the program voltage (about 8-16 V per #203; maximum is OPEN-B1). The template page does not state HV pad pitch or spacing, and neither [FP] nor [HV] sets one. | L01-L36 | OPEN (operator / shuttle offering; ring geometry) | [FP] slot template table; [HV] scope |
| R5 | The fixture must not require the physical slot order to differ from what #211 produces beyond R2-R3; a mismatch is handled in the fixture channel map, not the die. | all | Derived | [FP] pad-table preamble |

## 3. Pad-ring changes asked for

**None is asked for in this note.** Reasons: all 48 signal slots are assigned
and the slot-type counts are exactly used (bidirectional 38/38, analog 4/4,
input-only 6/6) ([FP] pad-table totals); R2-R3 are ordering requests to
assembly (#211) and do not change which signal sits in which slot type.

**The one place a change could be requested, and what it would cost.** The
floorplan states there are no Kelvin pads ("no spare budget"), and the
shared-BL route resistance is estimated, not measured (OPEN-B6) ([FP] "Series
resistance"; [BP] §5). If the operator decides the bench needs a Kelvin sense
or a guard pad, the only candidates are the three unused pads, **L46
(input-only), L47 (input-only), L48 (bidirectional)**, which are already held
for the HV-pad sibling ([FP] pad-table totals). Using them would conflict
with that hold, and the slot type of each limits what it can be: the analog
slots are all consumed. This is an **operator decision**; it is not made here.
Not requested: any change to L01-L45.

## 4. Delivery form and package / pinout: OPEN

| Item | Value | Who supplies the answer |
|---|---|---|
| Delivery form: bare die, packaged, or both | **OPEN** | Operator (shuttle offering and what is received). Nothing in [FP], [HV] or [BP] records it. |
| Package type and pinout (pin-to-pad map) | **OPEN** | Operator, once the delivery form is known. Applies only to the packaged form. |
| Probe vs socket | **OPEN** | Follows the delivery form; see §5. |
| Power pads (4 DVDD, 4 DVSS): bonded, probed or floating | **OPEN** | Operator; [FP] says they carry no signal on this chip. |

No default is assumed for any row. Packaged form also depends on whether the
package can keep the PL pads free of internal clamps or shared rails, which is
the same open point as R1.

## 5. Measurement route per delivery form

Instrument classes come from [BP] §2; "OPEN" items stay open.

| Function | Class | Bare die (probe card) | Packaged (socket) |
|---|---|---|---|
| PL ramp (36 pads) | Source with current compliance and readback, reaching the OPEN-B1 maximum; series resistor on the bench side ([HV]) | Probe card with HV-rated needles and standoff (rating OPEN-B1/R4). Hot-chuck compatibility with the card is OPEN. | Socket and board traces rated for the same voltage (OPEN-B1); series resistor off-die on the board. |
| BL sense (4 pads) | Pad-current meter with resolution below the lowest programmed read current; floor measured ([BP] §3.1); resolution OPEN-B2 | Guarded needles; probe-card leakage enters `I_floor` and is measured with WL off. | Guarded socket/board path; socket and board leakage enter `I_floor` the same way. |
| WL drive (4), `VBW_C3` (1) | DC supplies; levels OPEN-B3 and C3 record status | Same. | Same. |
| Channel multiplexing | One channel per PL or a switch matrix; matrix leakage is part of the floor ([BP] §2); OPEN-B4 | Same | Same |
| Environment | Guarded fixture; temperature control with measured temperature; points OPEN-M2 ([BP] §2) | Chuck temperature at the die; reach vs the program voltage standoff is OPEN. | Package temperature is not die temperature; the record states what was measured ([BP] §7 on read condition). |

A packaged die at one temperature bounds only one side of the worst-case read
margin and the record must say so ([BP] §7). Which route supplies which
temperature points is OPEN until the delivery form is known.

## 6. Open items needing the operator before 2026-12-16 (if space is obtained)

1. Delivery form (bare die / packaged / both) and package/pinout (§4).
2. R1: whether a bare PL pad is available on the slot template (the same open
   dependency as in [HV]).
3. R4: HV pad pitch and spacing the ring allows.
4. R2-R3 accepted as requests to #211.
5. Whether any of L46-L48 is to be released for a Kelvin or guard function
   (§3); the default in this note is no.

## References

- `spec/run3-test-chip-floorplan.md`, `spec/hv-pad-protection-decision.md`,
  `spec/run3-bench-plan.md` (sources above).
- `spec/measurement-matrix.md` (inherited OPEN-M2; cross-reference only).
