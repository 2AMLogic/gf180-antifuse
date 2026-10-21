# Sourced gate-oxide V_bd per candidate, and a test-structure plan

Issue #128 (parent #127). Evidence note: every number below traces to a named
source or is marked unsourceable. Nothing here is measured; nothing here was
programmed. Prior results are **not** rescaled by anything in this note
(re-running benches is the sibling re-run issue).

## 1. Source

**S1.** GlobalFoundries GF180MCU PDK documentation, "Custom Design / Electrical
Specifications", section 5.4 *Oxide Breakdown Voltage* (parameter 4, `BVox`),
<https://gf180mcu-pdk.readthedocs.io/en/latest/analog/spice/elec_specs/elec_specs_5_4.html>,
read 2026-10-21 (the page is "latest"; the revision was not pinned, see
Caveats).

| Device (doc label) | Oxide | Min | Typ | Max | Unit |
|---|---|---|---|---|---|
| NCH (NE2) | 3.3 V gate | - | -9 | -7 | V |
| PCH (PE2) | 3.3 V gate | 7 | 8.8 | - | V |
| NCH (NE2) | 6 V gate | - | -16 | -12 | V |
| PCH (PE2) | 6 V gate | 12 | 16 | - | V |

Read as: |BVox| is at least 7 V (3.3 V gate) / 12 V (6 V gate), typically
about 9 / 16 V. The NCH rows put the bound in the "Max" column because the
values are negative; the sign convention (gate vs. substrate polarity) is not
stated by the table.

**S2.** Same documentation, section 5.3 *Gate oxide capacitance*
(`.../elec_specs_5_3.html`): Cox 3.4 / 4.4 / 5.4 fF/um^2 (min/typ/max) for
3.3 V gates, 1.8 / 2.3 / 2.8 fF/um^2 for 6 V gates. Used only to check the tox
values already in `breakdown_params.spice`: eps_SiO2 / Cox(typ) gives about
7.9 nm and 15.0 nm, consistent with 8.0 / 7.9 nm and 15.2 nm there.

**S3.** Same documentation, design manual section 14.1 (*Voltage Limits Due
to Gate Oxide Breakdown*): DC gate-to-node limit 3.63 V (thin oxide),
6.5 V / 6 V (5 V / 6 V thick gate); overvoltage allowed as a duty cycle
bounded by TDDB lifetime. No lifetime numbers, no temperature given. These
are operating limits, not breakdown voltages.

## 2. V_bd per candidate

Field = V / tox, with tox from `breakdown_params.spice` (S2-consistent).

| Candidate | Oxide / structure | Source row | V_bd typ | V_bd lower bound | Field typ | Field at lower bound | Model V_bd(1 us) today |
|---|---|---|---|---|---|---|---|
| 1 | thin 3.3 V, NMOS cap (`cap_nmos_03v3`) | S1 NCH 3.3 V | 9 V | 7 V | 11.3 MV/cm | 8.8 MV/cm | 8.0 V |
| 2 | thick 6 V, NMOS cap (`cap_nmos_06v0`) | S1 NCH 6 V | 16 V | 12 V | 10.5 MV/cm | 7.9 MV/cm | 15.2 V |
| 3 | thin 3.3 V, PMOS cap (`cap_pmos_03v3`) | S1 PCH 3.3 V | 8.8 V | 7 V | 11.1 MV/cm | 8.9 MV/cm | 7.9 V |

Uncertainty: S1 gives only a spec floor and a typical value; it states no
sigma, no sample size, and no lot-to-lot spread. The typ-to-floor range
(2 V thin, 4 V thick) is a specification band, not a standard deviation, and
must not be used as one.

Candidate 3's *structure* (PMOS cap with a thick-oxide PMOS access device):
S1 covers the thin PCH oxide only. The access device's oxide is not an
antifuse and is not given a breakdown number here (it is covered by the
S3 operating limit).

## 3. Effect on `breakdown_params.spice`: no value changed

`bd_ebd` is a **single field shared by all three candidates**, defined as the
median field at `bd_tref = 1 us`. S1 does not support replacing it:

1. S1 states no ramp rate, area, or current criterion, so it cannot be placed
   on the 1 us time axis. Converting would need `bd_gam`, which is assumed.
2. The sourced fields differ between candidates (about 10.5 to 11.3 MV/cm at
   typ), while the model carries one value; per-candidate tuning would add a
   split the model does not have.
3. A guessed time conversion would be an unsourced number presented as
   literature, which the issue forbids.

So `bd_ebd` stays `assumed` (10 MV/cm), and its annotation now cites this
note. The sourced typical fields bracket the assumption (10.5 to 11.3 MV/cm
against 10) and the floors sit below it (7.9 to 8.9 MV/cm); that is a
plausibility cross-check, not a replacement. `c1/c2/c3_bd_tox` were already
`literature`.

## 4. Unsourceable items (for the operator)

No usable public source found for these; none was filled in:

- Time/ramp condition and current criterion behind S1 `BVox`, and its
  statistical spread (sigma, sample size, temperature).
- TDDB acceleration (`bd_gam`) and Weibull shape (`bd_beta`) for gf180 oxides.
- Post-breakdown filament resistance and its dependence on compliance
  (`bd_rf_med`, `bd_rf_sig`).
- NMOS-vs-PMOS thin-oxide breakdown asymmetry beyond the 0.2 V typ difference
  in S1.
- Any antifuse-mode (program-pulse) V_bd on gf180: S1 is a conventional oxide
  breakdown spec, not a fuse-programming figure.

Request to the operator: a foundry reliability report or shuttle-run
characterization data covering the above, if one is obtainable under the
shuttle agreement; otherwise these wait on section 5.

## 5. Plan: shuttle-seat test structure (plan only)

No physical programming is requested or authorized by this issue; building or
running any of this needs its own operator go-ahead.

**Probed** (stand-alone, pad-accessible, no array/MUX in the path):

| Structure | Per candidate | Why |
|---|---|---|
| Single moscap at each candidate's drawn W/L, gate and bulk to pads | C1 thin NMOS, C2 thick NMOS, C3 thin PMOS | direct V_bd of the antifuse oxide |
| Area ladder (about 4 areas spanning two decades, same oxide) | per oxide | Weibull area scaling; separates intrinsic from edge/defect |
| Same cap with the candidate's series access device | per candidate | V_bd as seen through the program path, including the voltage lost across the access device |
| Perimeter-heavy vs area-heavy pair | per oxide | edge vs bulk breakdown |

**Measurements:**

- Ramp breakdown (voltage ramp, fixed compliance) at several ramp rates over
  at least three decades, to extract the time/ramp dependence that S1 lacks
  (feeds `bd_gam`, `bd_tref` placement).
- Constant-voltage stress at 3 or more voltages for time-to-breakdown
  (feeds `bd_ebd`, `bd_gam`, `bd_beta`).
- Post-breakdown I-V at 2 or more compliance currents (feeds `bd_rf_med`,
  `bd_rf_sig`).
- Temperature and corner: at least two temperatures; dies from the shuttle's
  available process corners, since the array-level claims need PVT.

**Expected spread to size sample counts:** S1 gives only the 2 V (thin) /
4 V (thick) typ-to-floor band. With a Weibull shape near the model's 1.5,
about 30 structures per cell of the matrix above are needed for a shape
estimate with roughly 25% relative uncertainty; this is a sizing estimate,
not a claim about gf180.

**Outputs:** results land in `measurements/` per candidate and structure,
never averaged across them; only then may any `.param` be relabelled
`measured`.

## Caveats

- S1 is the PDK's published spec table, labelled "latest"; the open_pdks
  revision pinned in `spec/pdk-pin-decision.md` was not matched to a doc
  revision. The `_b` body-tap cap variants are not covered by S1.
- Sign convention of the NCH rows is not stated by the source.
