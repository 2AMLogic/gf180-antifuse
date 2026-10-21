# Decision Record (PROPOSED): Program Bias Scheme vs. Access-Device Ratings

**Status**: PROPOSED -- for operator ratification. Nothing in this record is
ratified, and it relaxes, amends and reinterprets no ratified line of
`spec/cell-candidates.md`, `spec/architecture.md`,
`spec/supply-domains-decision.md` or any other ratified record. It answers
issue #90 with evidence; ratification (or rejection) is the operator's.
**Date**: 2026-10-15
**Scope**: Which program bias scheme keeps the access device inside its
ratified rating (`nfet_06v0` / `pfet_06v0` 6 V, `nfet_10v0_asym` 10 V) at the
program voltage the cell needs, per candidate. Antifuse physics, array and
program-circuit content only.

**Conditionality.** Every number is CONDITIONAL ON THE ASSUMED breakdown
parameters (`design/breakdown/breakdown_params.spice`: V_bd = 8.0 / 15.2 /
7.9 V for Candidates 1 / 2 / 3). They are assumed, not measured and not gf180
numbers. They are unchanged here. The ballast is an ideal resistor sized for a
PLACEHOLDER 500 uA at V_bd. If measured V_bd differs, the findings must be
re-run, not rescaled.

## Evidence

All under `sim/program-bias-scheme/` (README there lists benches and limits).
Each record has one row per PVT corner (3 moscap corners x 3 temperatures x 5
stress levels, 45 corners per bench) with the largest |V| of six access-device
terminal pairs over the whole transient. Levels are never merged below.

| Scheme | Records |
|---|---|
| BL-driven (VPP on BL through ballast, PL = 0, WL = on bias + VPP) -- #62/#74 evidence re-tabulated, no new simulation | `20261015-081141/43/44-ece0130` |
| PL-driven (VPP through ballast on PL, BL = 0, WL static at the #62 "on" bias, VB static) | C2 `20261015-091611-ff07fee`, C3 `20261015-093632-ff07fee`, C1 `20261015-100043-ff07fee` |

Terminal pairs: `bc` BL-CN, `cj` CN-VB, `bj` BL-VB (fixed by where the program
voltage is applied) and `wc`, `wb`, `gb` (set by the gate/well drive).

## Findings, per candidate (worst corner within one level; median-quantile element, `b1m`)

### Candidate 2 / Region II (rating 10 V)

| Scheme | Level (V_bd 15.2) | Max pair | Pairs over 10 V (any corner) | Programmed |
|---|---|---|---|---|
| BL-driven | 1x (15.2 V) | `cj` 11.89, `bj` 11.90, `gb` 20.20 | 3 | 0/9 (clamped near 11.9 V, `bvs = 11`) |
| BL-driven | 1.1x (16.72 V) | `cj` 11.89, `gb` 21.72, `wc` 10.10 | 5 | 0/9 |
| **PL-driven** | 1x (15.2 V) | `wc` 5.00, `wb` 5.00, `gb` 5.00, `bc`/`cj` 0.34 | **0** | **9/9** |
| **PL-driven** | 1.1x (16.72 V) | same | **0** | **9/9** |

`plb_b1l` (low quantile) programs 9/9 from 0.95x and reports 0 pairs over
rating at every level. 45/45 corners converged on each selected-cell bench.
**A program path at the assumed V_bd exists: apply VPP to PL and hold BL at
0 V.** The oxide sees the full V_bd while the access device sees only the gate
drive and the program current times its on-resistance.

### Candidate 1 / Region I (rating 6 V)

| Scheme | Level (V_bd 8.0) | Max pair | Pairs over 6 V | Programmed |
|---|---|---|---|---|
| BL-driven | 1x | `cj` 8.00, `bj` 8.00, `wc` 9.41, `gb` 11.30 | 5 | 9/9 |
| PL-driven | 1x | `bc` 6.44, `cj` 6.44, others <= 3.31 | 2 | 9/9 |
| PL-driven | 1.1x (8.8 V) | `bc` 7.31, `cj` 7.31 | 2 | 9/9 |

PL-driven removes the pre-breakdown stress (0 pairs over rating before
breakdown) and the gate-pair overstress. After breakdown the CN node rises by
the program current times the on-resistance of the minimum-geometry access
device (0.3 um / 0.7 um), 6.3-7.5 V, still over the 6 V rating. This
is a compliance/sizing result: the PL-driven scheme leaves it open, and the
bench did not test a wider access device or a lower compliance current. NOT
resolved by this record.

### Candidate 3 / Region III (rating 6 V)

| Scheme | Level (V_bd 7.9) | Max pair | Pairs over 6 V | Programmed |
|---|---|---|---|---|
| BL-driven | 1x | `bc` 7.56, `cj` 11.07, `gb` 6.60 | 3 | 9/9 |
| PL-driven | 1x | `bc` 7.52, `cj` 10.82, `gb` 6.60 | 3 | 9/9 |
| PL-driven | 1.1x (8.69 V) | `bc` 9.62, `cj` 12.92, `wc` 6.32 | 4 | 9/9 |

PL-driven does **not** help Candidate 3. The CN-to-n-well junction (`cj`) is
fixed by the cell, not by which terminal carries VPP, and the static `gb` of
6.60 V comes from the #62 gate/well levels (WL = -3.3 V, VB = +3.3 V), present
even at the 3.3 V rated level. A gate/well drive change (for example a lower
n-well tie) is untested here and would need its own bench. NOT resolved by
this record.

## Unselected cells under a PL-driven scheme (`plu_st`)

PL is shared by every cell on it, so the unselected cells see the PL pulse
too. With WL off, BL = 0 V and CN floating, the access pairs stay small
(C1 <= 0.72 V; C2 <= 0.02 V at converged corners; C3 `wb` 3.30 V, `cj` <=
1.73 V). That is the access device only. The unselected cell's **oxide**
stress depends on where the floating CN settles, which the stock macro (a
two-terminal C(V), no junction leakage) cannot say: with real junction
leakage CN is pulled toward the substrate and the oxide of every unselected
cell on the PL would see up to the full pulse. This is the open risk of the
PL-driven scheme and needs either a PL organised so only the selected cell's
PL is raised, or a model with junction leakage. Convergence: C1 45/45; C2
30/45 (all -40 C corners fail with `Timestep too small`, 15 corners stay in
the denominator); C3 24/45 (21 corners time out at 300 s).

## Proposal

1. **Region II**: adopt the PL-driven (return-side) program leg as the
   program path for Candidate 2 under the assumed V_bd. `spec/architecture.md`
   1.2 already names the return-side leg ("row pass-gate and ground return")
   as an allowed form, so this selects among forms the ratified record keeps
   open; it does not change a ratified line. The BL-driven leg is shown
   incapable at the assumed V_bd (0/9 programmed at every level).
2. **Regions I and III**: leave the scheme choice open. PL-driven removes the
   Candidate 1 pre-breakdown and gate-pair overstress but not the post-breakdown
   compliance overstress; it does nothing for Candidate 3. Resolution
   candidates, each needing its own bench: access-device width / compliance
   current (C1), gate and n-well tie levels (C3), or revisiting V_bd once
   measured data exists.
3. **Consequences to carry into #65 and #66 if ratified**: the program-voltage
   switch moves to the PL side. At 15.2-16.7 V it exceeds a 10 V pass-gate, so
   the Region II switch, level-shifter tier (OI-4) and ballast rating (OI-5)
   must be resolved for a 17 V-class path; the body-plate (`PL`) isolation
   rating is not modelled; and the unselected-cell question above is
   unanswered.

## Not done

- No Monte Carlo (that is #66); process corners only.
- No spec file other than this new record was touched.
- No bench for the Region I width/compliance lever, the Region III
  gate/well-drive lever, a split-rail scheme, array-level shared-PL effects,
  or an unselected-cell model with junction leakage.
- `plu_st` incomplete at C2 (-40 C) and C3 (21 corners), counted in the
  denominators above.
