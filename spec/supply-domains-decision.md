# Decision Record: Supply-Domain Inventory

**Status**: Ratified as an inventory only — it tabulates supply and return
nets already stated in ratified records; it chooses no voltage and changes no
design. Everything unresolved is carried as a named OPEN ITEM (OI-n) below.
**Date**: 2026-10-09
**Scope**: One table of every supply and return net the block needs: name,
voltage class, which candidate regions it serves, the device rating that
bounds it, bench-supplied vs. on-die, owning partition, and the existing spec
section each row derives from. Also states the domain-crossing rule. It does
**not** draft the `klt erc` supply spec file (that follows once this net list
is ratified and layout exists), and it does **not** relax or reopen
`spec/architecture.md`, `spec/program-voltage-decision.md`,
`spec/split-axis-plan.md`, or `spec/cell-candidates.md`.

## Conventions

- **Regions** are those of `spec/split-axis-plan.md` "Region map": **I** =
  Candidate 1 (`cap_nmos_03v3` + `nfet_06v0`), **II** = Candidate 2
  (`cap_nmos_06v0` + `nfet_10v0_asym`), **III** = Candidate 3
  (`cap_pmos_03v3` + `pfet_06v0`). No row below averages across regions; where
  regions differ they get separate rows or separate cells in the row.
- **Device rating** is the rating stated in `spec/cell-candidates.md`
  ("Verified access/isolation (series-device) candidates" and "Candidates").
  A rating bounds what a net may carry; it is not a chosen voltage.
- **Bench / on-die** follows `spec/program-voltage-decision.md` "Answer":
  `VPP` generation is off-die (bench, dedicated pad); switching and routing
  are on-die. That record says nothing about the other supplies, so for them
  the column says "not decided" rather than inferring.
- **Partition** (digital / analog) is classified here from the block roles in
  `spec/architecture.md`: the logic-voltage decode, control logic and SPI slave
  (§1.1, §5) are digital; the high-voltage pass-gates, level shifters, program
  path, cell array and sense path (§1–§4) are analog. The level shifters are
  listed as analog (thick-oxide, program-rail referenced) with the partition
  boundary at their logic-side inputs. See OI-9: no earlier record defines
  this split, so it is this record's classification.
- Voltages are never asserted. "Voltage class" means the class named in the
  cited text, or "unresolved".

## Supply and return nets

| # | Net | Voltage class | Regions served | Bounding device rating | Bench / on-die | Partition | Derives from |
|---|---|---|---|---|---|---|---|
| 1 | Logic rail (`VDD_LOGIC`, placeholder name) | 3.3 V-class, stated as an assumption ("assumed 3.3 V-class") | I, II, III (global decode and SPI are not region-specific) | Rating of the `gf180mcu_fd_sc_mcu7t5v0` standard cells and `gf180mcu_fd_io` pads is not stated in `spec/cell-candidates.md`; see OI-1 | Not decided by `spec/program-voltage-decision.md` (OI-2) | digital | `spec/architecture.md` §1.1 (global decode, "never at the programming voltage"), §5 "Physical/protocol layer" |
| 2 | Logic ground / return (`VSS_LOGIC`, placeholder name) | 0 V reference of the logic rail | I, II, III | As row 1 | Not decided (OI-2) | digital | `spec/architecture.md` §1.1, §5; relationship to rows 12 and 13 is OI-6 |
| 3 | `VPP`, Region I program rail | Unresolved. Thin-oxide regime, "expected to be several times the 3.3 V rated voltage", "not asserted here as a specific number" | I | `nfet_06v0`, 6.0 V (access and pass-gate); `ppolyf_u_2k_6p0` ballast, 6.0 V-class by naming convention only (OI-5) | Generation off-die (bench pad); switching on-die | analog | `spec/program-voltage-decision.md` "Answer" and Evidence 1; `spec/cell-candidates.md` Candidate 1; `spec/architecture.md` §1.2, §2 |
| 4 | `VPP`, Region II program rail | Unresolved. Thick-oxide regime, "materially higher than Candidate 1", "not a fixed multiple asserted here" | II | `nfet_10v0_asym`, 10 V (access); pass-gate stage `nfet_10v0_asym`-class; ballast `ppolyf_u_2k_6p0` unverified at this level (OI-5) | Generation off-die (bench pad); switching on-die | analog | `spec/program-voltage-decision.md` "Answer" and Evidence 1; `spec/cell-candidates.md` Candidate 2; `spec/architecture.md` §1.1, §2 |
| 5 | `VPP`, Region III program rail | Unresolved. Thin-oxide regime, "same expected regime as Candidate 1", not asserted | III | `pfet_06v0`, 6.0 V (access and pass-gate) | Generation off-die (bench pad); switching on-die | analog | `spec/program-voltage-decision.md` Evidence 1; `spec/cell-candidates.md` Candidate 3; `spec/architecture.md` §1.1 |
| 6 | Level-shifter high-side rail, 6 V tier | Follows the served region's program rail during a program operation; a fixed logic-compatible "fully on" bias during read (value unresolved, OI-7) | I, III | `nfet_06v0` / `pfet_06v0`, 6.0 V | Switching on-die; source rails are rows 3, 5 and the read bias | analog | `spec/architecture.md` §1.1 "Level shifters" |
| 7 | Level-shifter high-side rail, Region II tier | Unresolved. `spec/architecture.md` §1.1 spells out only the 6 V tier; Region II's tier is OI-4 | II | Not stated for the shifter itself. The 10 V pair `nfet_10v0_asym` / `pfet_10v0_asym` is the family named in `spec/program-voltage-decision.md` "Answer" | Switching on-die | analog | `spec/architecture.md` §1.1; `spec/program-voltage-decision.md` "Answer" |
| 8 | Pass-gate gate-drive levels (selected ON level, defined OFF level), per region | Unresolved. Selected ON is a controlled overdrive during program (§2 item 2); OFF must be an actively driven defined level (§3 item 1); neither value is stated | I, II, III separately (pass-gate family is per region) | Region I and III: 6.0 V (`nfet_06v0` / `pfet_06v0`). Region II: 10 V (`nfet_10v0_asym`) | On-die (level shifter output) | analog | `spec/architecture.md` §1.1, §2 item 2, §3 item 1 |
| 9 | Access-device gate bias for active compliance limit (`GATE_BIAS`, placeholder name) | Unresolved; "controlled overdrive" toward saturation, tunable | I, II, III separately | Region I and III: 6.0 V. Region II: 10 V | Not decided (OI-8) | analog | `spec/architecture.md` §2 item 2 |
| 10 | Read bias (`VREAD`, placeholder name) | Unresolved; "fixed, sub-disturb read voltage", "a separate, smaller value than `VPP`" | I, II, III | Below each region's access and capacitor rating by definition; value left to `sim/` and `measurements/` | Not decided (OI-8) | analog | `spec/architecture.md` §4 "Electrical basis" |
| 11 | Sense-amplifier supply and `I_ref` bias | Unresolved; not stated in any record | I, II, III | Not stated | Not decided (OI-8) | analog | `spec/architecture.md` §1.2 (READ leg), §4 |
| 12 | `PL` plate-line program return | Return net; its level during program and read is not stated. Which array rail it ties to is "deferred with the rest of the array" | I, II, III separately: `PL` is a cell port in every candidate | Capacitor and access ratings of the served region (see rows 3 to 5 and 17) | Not decided: the return may be a tie or an on-die switched leg (OI-6) | analog | `design/README.md` "Cell interface" and the sentence following it; `spec/architecture.md` §2 item 1 (return-side leg) |
| 13 | Analog ground reference (`VSS_ANALOG`, placeholder name) | 0 V reference for rows 3 to 12 | I, II, III | As rows 3 to 5 | Not decided (OI-6) | analog | `spec/architecture.md` §2 item 1 ("ground return"); whether it is separate from row 2 is OI-6 |
| 14 | `VB` access-device bulk tie, Regions I and II | p-substrate tie | I, II | `nfet_06v0` 6.0 V (I); `nfet_10v0_asym` 10 V (II) | On-die | analog | `design/README.md` "Cell interface" (`VB`) |
| 15 | `VB` access-device bulk tie, Region III | n-well tie | III | `pfet_06v0`, 6.0 V | On-die | analog | `design/README.md` "Cell interface" (`VB`) |
| 16 | Pass-gate and level-shifter bulk / well ties | Unresolved | I, II, III separately | Same families as rows 6 to 8 | On-die | analog | `spec/architecture.md` §1.1; no record assigns these (OI-3) |
| 17 | Capacitor body / well tie | The capacitor's second terminal is the plate `PL` (row 12) per the cell port list; no separate tie net is defined | I, II, III | `cap_nmos_03v3` (I), `cap_nmos_06v0` (II), `cap_pmos_03v3` (III): rated oxide flavors per `spec/cell-candidates.md`; the `_b` body-tap variants are not in the ratified set | On-die | analog | `design/README.md` "Cell interface" (`PL`); `spec/cell-candidates.md` open question on `_b` variants |

Rows 3 to 5 are logical program rails, one per region, because the ratings
and expected regimes differ per region (`spec/cell-candidates.md`,
`spec/split-axis-plan.md` "Oxide flavor"). They are not asserted to be three
physical nets; see the next section.

## `VPP`: what is already required, and what is unresolved

**Already required by ratified text**

1. `VPP` is bench-supplied through a dedicated program-voltage pad, and
   nothing on-die generates or regulates it (`spec/program-voltage-decision.md`
   "Answer").
2. The program pulse voltage is a split axis, with a nominal center point that
   differs per region and a voltage sweep inside each region
   (`spec/split-axis-plan.md` "Program pulse voltage/width", fourth bullet of
   the list). Programming voltage is set by whatever supplies `VPP`, not by a
   register (`spec/architecture.md` §5, `PULSE_WIDTH`).
3. The level shifters reference "that region's programming-voltage rail"
   during a program operation (`spec/architecture.md` §1.1), and the rail
   must stay within the rating of the devices that see it (rows 3 to 5).

**Not required by ratified text**

A programming-condition split alone does not require distinct physical `VPP`
rails. The pulse recipe is applied through the SPI program path at test time
with identical hardware (`spec/split-axis-plan.md`, same section), one cell is
programmed per operation (`spec/architecture.md` §5 program sequence), and a
bench supply can be re-set between operations. Whether the three logical
rails of rows 3 to 5 are one pad, one pad per region, or something else is
unresolved (OI-3). One consequence is recorded so it is not lost: if the rails
share a physical net, that net is bounded by the lowest-rated device
connected to it, and unselected-region devices on the net see whatever
voltage a Region II operation sets (derived from the ratings in
`spec/cell-candidates.md`; it is a constraint on OI-3, not a decision).

## Domain-crossing rule

The SPI and logic domain (rows 1 and 2) is electrically isolated from the
programming rail by the level shifters of `spec/architecture.md` §1.1 and
never sees the programming voltage directly (`spec/architecture.md` §5,
"Physical/protocol layer"). Concretely:

1. The only permitted path from the logic domain to the program-voltage
   domain (rows 3 to 8) is through a level shifter. No pad, register or
   decode output in the logic domain connects to `VPP` or to a net carried at
   a program-rail level.
2. `VPP` is not routed to any `gf180mcu_fd_io` SPI pad. The program-voltage
   pad is a separate, dedicated pad (`spec/program-voltage-decision.md`
   "Answer").
3. The read leg is disabled for the whole armed state, so the sense path
   (rows 10 and 11) is never exposed to a program-voltage transient
   (`spec/architecture.md` §1.2, `READ_EN = NOT(PROG_EN OR PROG_ARMED)`).
4. Every row and column decoder output is actively driven at all times,
   never high-impedance (`spec/architecture.md` §3 item 1).

## OPEN ITEMS

None of these has a value asserted in this record. Each needs a measurement,
a PDK document, or a `design/` / layout decision, and each is a place a later
`klt erc` spec must not guess.

- **OI-1 Logic-domain device rating.** The rating of
  `gf180mcu_fd_sc_mcu7t5v0` and `gf180mcu_fd_io` cells against the assumed
  3.3 V-class rail is not stated in `spec/cell-candidates.md` and has not been
  checked. The logic rail's class is itself an assumption in
  `spec/architecture.md` §1.1 and §5.
- **OI-2 Logic rail sourcing.** `spec/program-voltage-decision.md` covers
  `VPP` only; whether the logic rail and ground are bench-supplied pads is
  not recorded.
- **OI-3 `VPP` rail topology and well ties.** Whether rows 3 to 5 are one
  physical net, one per region, or otherwise; the pad count; and the well and
  bulk tie assignments of row 16.
- **OI-4 Region II level-shifter tier.** `spec/architecture.md` §1.1 names
  the 6 V-tier shifter only. The device family and rail of the Region II
  shifter are not specified.
- **OI-5 Ballast resistor rating.** The `_6p0` reading of
  `ppolyf_u_2k_6p0` as a 6.0 V-class rating is inferred from naming
  convention and unconfirmed (`spec/architecture.md` "Open questions carried
  forward"); it must be verified before the resistor sits on a Region II
  program path.
- **OI-6 Return and ground topology.** Which array rail `PL` ties to
  (deferred in `design/README.md`), whether the return leg is a tie or an
  on-die pass-gate path (`spec/architecture.md` §2 item 1 leaves placement to
  `design/`), whether Candidate 3's `PL` polarity differs, and whether
  `VSS_LOGIC` and `VSS_ANALOG` are one net.
- **OI-7 Read-time level-shifter bias.** The "fixed logic-compatible fully-on
  bias" of `spec/architecture.md` §1.1 has no stated value or source.
- **OI-8 Analog bias nets.** Value and source (bench or on-die) of
  `GATE_BIAS`, `VREAD`, the sense-amplifier supply and `I_ref`. The latter two
  are bounded by `I_sneak_max` and `I_prog_min`, which are `sim/` and
  `measurements/` deliverables (`spec/architecture.md` §4).
- **OI-9 Partition assignment.** The digital/analog classification in this
  record's Conventions section is not defined by an earlier record and should
  be confirmed against the signoff partition definitions before the net list
  is relied on.
- **OI-10 Actual program voltages.** Gate-oxide breakdown voltages for the
  3.3 V and 6.0 V flavors are unknown until measured
  (`spec/cell-candidates.md` open questions; `spec/program-voltage-decision.md`
  "Reconsideration triggers"). Rows 3 to 5 carry no number until then, and
  this record is to be revisited when they exist.

## References

- `spec/architecture.md` §1.1, §1.2, §2, §3, §4, §5 and its open-questions
  list.
- `spec/program-voltage-decision.md` "Answer", "Evidence and Rationale" 1 and
  2, "Reconsideration triggers".
- `spec/split-axis-plan.md` "Region map", "Split-axis mapping" 1 and 4.
- `spec/cell-candidates.md` "Verified access/isolation (series-device)
  candidates" and "Candidates".
- `design/README.md` "Cell interface".

## Decision

Ratify rows 1 to 17 and the domain-crossing rule as the single supply and
return net inventory for this block, and ratify OI-1 to OI-10 as the named
unresolved items. No voltage is chosen, no existing ratified text is relaxed,
and the `klt erc` supply spec is not drafted here; it follows once this
inventory is ratified and layout exists.
