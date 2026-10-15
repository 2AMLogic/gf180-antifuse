# sim/program-bias-scheme/

Program bias schemes evaluated against the ratified access-device ratings of
`spec/cell-candidates.md`, per candidate and per PVT corner (issue #90). The
decision record that interprets these results is the **proposed**
[`spec/program-bias-scheme-proposed-decision.md`](../../spec/program-bias-scheme-proposed-decision.md);
nothing in this directory changes a ratified spec.

Everything here is CONDITIONAL ON THE ASSUMED breakdown parameters
(`design/breakdown/breakdown_params.spice`: V_bd = 8.0 / 15.2 / 7.9 V for
Candidates 1 / 2 / 3). They are not gf180 numbers.

## What is in the records

| Record kind | Source | Simulation run for it |
|---|---|---|
| **Re-tabulation of the BL-driven leg** (`records/20261015-0811{41,43,44}-ece0130.md`) | The `mx_*` / `mn_*` measurements already in `sim/cell-breakdown-model/corners/20261014-0017{17,20,23}-86afd07/progc_*/report.json` | none (`--retabulate`) |
| **PL-driven leg, selected cell (`plb`) and unselected cell (`plu`)** (the other records) | New batch-fleet requests, one per bench | 45 corners per bench on the Spot fleet |

Per candidate, every record has one row per PVT corner (3 moscap corners x 3
temperatures x 5 stress levels) holding the largest |V| of every
access-device terminal pair over the whole transient, with the pairs over the
ratified rating in **bold**. "Level" summaries take the worst corner within
one level only; levels are never merged.

## Terminal pairs

| Pair | Meaning | Depends on the gate/well drive choice? |
|---|---|---|
| `bc` BL-CN | access drain-source | no (set by the cell) |
| `cj` CN-VB | CN-side junction to bulk | no |
| `bj` BL-VB | BL-side junction to bulk | no |
| `wc` WL-CN | gate to CN-side terminal | yes |
| `wb` WL-BL | gate to BL-side terminal | yes |
| `gb` WL-VB | gate to bulk | yes |

The first group is fixed by where the program voltage is applied, not by how
the gate is driven. That distinction matters for what a gate-bias change can
and cannot repair (see the proposed decision record).

## Benches

| Bench | Stimulus |
|---|---|
| `plb_st`, `plb_b1m`, `plb_b1l` | VPP pulse (signed level, the #62 / #74 levels) -> ideal ballast (V_bd / 500 uA placeholder, as in the BL-driven bench) -> **PL**; BL = 0 V through an ammeter; WL, VB static at the #62 "on" bias. Variants: stock cell, element enabled at the median / low Weibull quantile. |
| `plu_st` | The same PL pulse on an **unselected** stock cell: WL at its OFF level, BL = 0 V, CN floating. Shows the stress an unselected cell's access device sees when PL carries the program pulse. |

The deck helpers, the C-infinity pulse edge, `tran ... uic`, one cell per
deck, per-corner failure accounting, and the 45-corner grid are reused from
`sim/cell-breakdown-model/run_experiment.py` (imported as a library), so the
levels and the breakdown parameters are identical to the BL-driven evidence.
A corner that does not converge stays in the denominator.

## Running

```
python3 sim/program-bias-scheme/run_experiment.py --retabulate        # no simulation
python3 sim/program-bias-scheme/run_experiment.py --candidates 1,2,3  # batch fleet, 4 benches x 45 corners per candidate
python3 sim/program-bias-scheme/run_experiment.py --smoke 1:plb_b1m:3 # ONE local corner, debug only, records nothing
```

The default mode submits to the batch fleet (`KLT_SIM_BACKEND=batch` /
`backend: batch` in each request). A failed submit writes a
`submit-error.txt` and no fallback local grid is run.

## Limits of these benches

- The ballast is an ideal resistor (PLACEHOLDER 500 uA target at V_bd); the
  ratified `ppolyf_u_2k_6p0` and its voltage rating (open, OI-5) are not
  modelled.
- The PL node carries a PLACEHOLDER 100 fF shunt capacitance (`C_PL_SHUNT`). Without it the ballasted PL node stalls the `uic` start of the moscap macro (timestep collapse). Two earlier attempts without it are kept as failed evidence, no records: `corners/20261015-083207-76419ad` (Candidate 2, DC WL, 45/45 errored) and `corners/20261015-090309-9b440d0` (Candidate 2, WL/VB ramp, 25/45 errored). The partial `corners/20261015-081614-4b821a1` (Candidate 1, killed mid-run, before the shunt) is also kept.
- Plate-line / body-plate voltage stress is **not modelled**: the stock
  `cap_*` macros are a two-terminal C(V) with no junction to substrate or
  well. A PL-driven scheme puts the program voltage on the capacitor's body
  plate, whose isolation from the substrate is a layout and PDK-structure
  question these benches cannot answer.
- Single cell per deck: array-level effects (shared PL, unselected cells in
  the selected row, sneak paths) are not simulated, except for the single
  unselected-cell `plu` case.
- Process corners only; no Monte Carlo (the yield curve is #66).
