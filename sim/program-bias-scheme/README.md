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
| `gwa_*`, `gwb_*` (`st`, `b1m`, `b1l`) | **Candidate 3 only** (#129): the `plb` leg with the access device's gate (WL) and n-well tie (VB) set per scheme instead of the #62 "on" bias. `gwa`: WL -3.3 V, VB 0 V (well tie lowered to the BL return level). `gwb`: WL -6.0 V, VB 0 V (stronger gate drive). Same six pairs, same 45 corners, same signed PL levels. Opt-in: `--candidates 3 --benches gwa_st,gwa_b1m,gwa_b1l,gwb_st,gwb_b1m,gwb_b1l`. The record ends with a per-level verdict: in-rating corners / attempted corners per bench, and whether any bench holds at every corner of a level. |

The deck helpers, the C-infinity pulse edge, `tran ... uic`, one cell per
deck, per-corner failure accounting, and the 45-corner grid are reused from
`sim/cell-breakdown-model/run_experiment.py` (imported as a library), so the
levels and the breakdown parameters are identical to the BL-driven evidence.
A corner that does not converge stays in the denominator.

## Running

```
python3 sim/program-bias-scheme/run_experiment.py --retabulate        # no simulation
python3 sim/program-bias-scheme/run_experiment.py --candidates 1,2,3  # batch fleet, 4 benches x 45 corners per candidate
python3 sim/program-bias-scheme/run_experiment.py --candidates 3 --benches gwa_st,gwa_b1m,gwa_b1l,gwb_st,gwb_b1m,gwb_b1l  # batch fleet, 6 benches x 45 corners
python3 sim/program-bias-scheme/run_experiment.py --candidates 3 --benches gwa_st,gwa_b1m,gwa_b1l,gwb_st,gwb_b1m,gwb_b1l --resume RECORD_ID  # finish an interrupted batch run (only benches without a report are resubmitted)
python3 sim/program-bias-scheme/run_experiment.py --smoke 1:plb_b1m:3 # ONE local corner, debug only, records nothing
```

The default mode submits to the batch fleet (`KLT_SIM_BACKEND=batch` /
`backend: batch` in each request). A failed submit writes a
`submit-error.txt` and no fallback local grid is run.

Each run writes `corners/<id>/<bench>/`. The committed `report.json` there has
its `coverage.checked` / `coverage.inapplicable` id lists replaced by their
counts (`harness.report.elide_coverage`): these are characterization benches, so
every entry restates `characterization_without_limits` and the counters beside
the lists already say how many. Every measurement value, corner status,
diagnostic, `environment`, `provenance` and coverage counter is kept -- including
everything `--resume` reads back out of a saved report -- and the sha256 of the
full klt report is committed alongside it as `report.json.sha256`.

## Layout

```
sim/program-bias-scheme/
  model.py                  library: bench/drive constants, deck-body and klt request builders, saved-report loaders
  render.py                 library: record renderers
  run_experiment.py         CLI driver / record writer; library facade re-exporting model.py + render.py
  compare_vbd.py            V_bd sensitivity comparison (#130); reads saved reports only, runs no simulation
  vbd-sensitivity-runs.json run manifest: record ids of the typ / floor sensitivity runs compare_vbd.py reads
  .work/                    git-ignored: local --smoke probe debris with host paths
  records/, corners/, netlist-snapshots/   written by each successful run (append-only)
```

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
- The gate/well-drive benches (`gwa`, `gwb`) try two static (WL, VB) pairs; "no scheme keeps all six pairs in rating" is a statement about those pairs, not about every possible drive. `corners/20261021-024938-9f8fa78` is an interrupted first attempt (submitter killed after 2 of 6 benches by a tool time limit), kept as evidence, no record.
- Process corners only; no Monte Carlo (the yield curve is #66).

## V_bd sensitivity runs (#130)

`--vbd-case typ|floor` (here and in `sim/cell-breakdown-model/run_experiment.py`) re-runs a bench with each
candidate's V_bd(t_ref) set to the primary-sourced BVox of `docs/breakdown-vbd-sources.md` (typ 9 / 16 / 8.8 V,
floor 7 / 12 / 7 V). It overrides `bd_ebd` per candidate as `.param bd_ebd = V_bd / tox` in the generated deck; the
shared `design/breakdown/breakdown_params.spice` is unchanged, and every record carries a "V_bd SENSITIVITY POINT"
bullet. The identification of BVox with V_bd at t_ref = 1 us is an assumption; these are sensitivity points, not
parameter updates. The re-tabulation of a sensitivity run's BL-driven leg is
`--retabulate --candidates N --vbd-case CASE --retab-src RECORD_ID` (RECORD_ID = the fresh
`sim/cell-breakdown-model` `progc_*` run). `compare_vbd.py` writes the per-candidate, per-level comparison against the
assumed-V_bd records from the run ids in `vbd-sensitivity-runs.json`; its output is
`spec/vbd-sensitivity-comparison-proposed.md`. Batch runs name this host's PDK variant dir in the body and export
`PDK_ROOT` to its parent (klt >= 0.8 refuses an absolute `.lib` outside `$PDK_ROOT`).
