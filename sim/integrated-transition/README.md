# sim/integrated-transition

Integrated program-to-read transition and voltage-stress bench (issue #73): the committed
array slice, its addressing stage, one program leg and one read leg per band, driven through
idle/reset, arm, pulse, completion, arm timeout and immediate read, across PVT, control skew and
external VPP ramp cases.

This is the electrical check of `spec/architecture.md` section 1.2 (the read leg is disabled for the
whole armed state and during a pulse; at most one leg drives the shared bit line) and section 3
(unselected lines are actively driven; unselected cells stay isolated) **on the assembled
netlists**, which the component benches (`sim/array-slice-bench/`, `sim/program-read-legs/`) cannot
establish on their own.

## Status

See `records/` (newest first). Record `20261016-054944-66fb0003`: 1416 fleet units, 1405 graded, 11 not gradable (unit errors, never counted as passes). Armed isolation, exclusion, pulse isolation and unselected-line bias met on every graded point; Region III read decision met on 250 of 469 graded points and Region II no-false-high on 453 of 466 (Region III programmed reads are known-unproven, #75). Details and unchecked stress pairs are in the record.

## What is assembled (nothing is copied or substituted)

```
                      VPP (external, ramped)
                        |
   program_leg  ---- BLG_<band> ---- column pass-gates ---- BL_c ---- cell access --- CN --| cap |-- PL_r
   read_leg     ----/    (floating when both legs are off)                                          |
        |                                                                                  row pass-gates --- PLG_<band>
   SENSE, RDATA                           level shifters drive every pass-gate and word line from CSEL_c / RSEL_r
```

* `design/netlists/slice_i_ii.spice` (rows 0-3, columns 9-12, Regions I and II) and
  `slice_ii_iii.spice` (columns 20-23, Regions II and III): cells, row and column local pass-gates,
  level shifters, from `design/gen_array.py`.
* `program_leg.spice`, `read_leg.spice` (and their `leg_interlock.spice`), instanced once per band on that
  band's `BLG_<band>` bus. The legs of the band that holds no selected cell stay disabled, so the idle
  band is a standing check of the idle-bus exposure.
* The bench adds only sources: supplies, the external VPP, behavioural control waveforms, an `I_ref`
  current source, a bus bleed, an ammeter on each leg, and (selected cell only, variants below) an assumed
  filament conductance.

## Sequence and scenarios

| Time (us) | Event |
|---|---|
| 0 - 0.5 | power-up ramp (C-infinity), settle. Nothing is measured |
| 0.6 | external VPP ramps from VDD to V_PK over `tvr` |
| 1.2 | ARM: row select, then column select (`tcsl` later); legs stay OFF |
| 1.8 - 2.8 | PROG_EN of the selected band (pulse) |
| `tren` | READ_EN of the selected band (immediately at completion in the base case) |
| 6.3 | end |

Scenarios (`make_bench.py: SCENARIOS`): `base`, `vslow` (500 ns VPP ramp), `rd_ovl` (READ_EN rises
20 ns before PROG_EN starts to fall), `rd_gap` (read 200 ns after completion), `csel_late` (column
select 100 ns after the row select), `timeout` (armed, no pulse, selects released, immediate read).
Filament variants: `unprog`; `prog_lo` / `prog_hi` (assumed 10 kohm / 100 kohm across the selected
capacitor).

### Cost and the two tiers

A fleet unit (one process x temperature x point) costs about 12 s on the ngspice-46 runner at the 5 ns step
(about 6 s at 10 ns, but that step aborted some units, below); the same deck takes about 2 s on a local
ngspice 42. The full product of every axis would be about 5000 units, so the matrix is two tiers
(`make_bench.py: TIER_POINTS`, `TIER_B_CORNERS`):

| Tier | PVT | Cells | Points | Units |
|---|---|---|---|---|
| A | full: 5 process x {-40, 27, 125} C x supply scale {0.9, 1.0, 1.1} | 4 per region (rows 0-3 of one column: all four capacitor x access sub-combinations) | `base` scenario, `unprog` and `prog_lo` | 1080 |
| B | reduced, 7 corners: ss at -40 / 125 C with scale 0.9; ff at -40 / 125 C with scale 1.1; typical, fs, sf at 27 C with scale 1.0 | 2 per region (rows 0 and 3: opposite on both axes) | `vslow`, `rd_ovl`, `rd_gap`, `csel_late`, `timeout` unprogrammed; `rd_ovl`, `rd_gap` with `prog_lo`; `base` with `prog_hi` | 336 |

The scenarios in tier B are therefore **not** run at all 45 corners; a record says so and the tables show
which corners each row covers. (Scale 0.9 / 1.1 move VDD, VDDH, VCLAMP and V_PK together.)

## What is measured and how it is judged

`analyze.py` holds every threshold; `run_bench.py` prints them in each record. They are this bench's own
acceptance numbers, not spec values.

* **Armed isolation**: sense-node and RDATA excursion during the armed state, the leg enables PON/RON, the mean
  current into the read leg over the last 100 ns of arm, for both bands.
* **Exclusion**: `min(PON, RON)` over the whole run.
* **Pulse**: RON, sense-node and RDATA excursion while PROG_EN is high; program-leg DC current on the flat top.
* **Transition**: RDATA correct and stable by the end, no glitch on the unprogrammed side, and the delay after
  READ_EN at which it is correct and stays correct (and the analog sense node has settled), read off ten fixed
  sample times.
* **Unselected select lines**: deviation of every unselected word line / column-gate from its OFF level.
* **Stress**: |V| of gate-source, gate-drain and drain-source of every HV-exposed MOS and the two terminals of
  every capacitor and resistor, taken from the committed netlists (`nlflat.py`), against `limits.py`.

## Limits and what is unchecked

`limits.py` lists the only limits a committed record states and where they come from. `spec/cell-candidates.md`
gives one rating per device family and names no terminal pair; it is applied to gate-source and gate-drain only.
Drain-source and junction pairs, `ppolyf_u_2k_6p0` (rating OPEN, `spec/leg-design-record.md` section 3), and the
selected cell's own capacitor are **unchecked**: peaks are printed, never judged. Staying under a rating says
nothing about long-term disturb or retention.

## Things to know before reading the numbers

* **Transient start and edges.** `uic` start and C-infinity edges (100 ns control edges, ramped supplies): the stock
  moscap macro stalls on slope discontinuities and on some operating-point starts
  (`sim/cell-breakdown-model/README.md`, "Transient convergence (#74)").
* **Step size matters on the fleet.** With a 10 ns maximum step three of nine probe units (typical corner, 125 C,
  lowest supply) aborted on the ngspice-46 fleet and passed with 5 ns or 2 ns; local ngspice 42 passed all. The bench uses
  5 ns. A unit that still aborts is recorded as an error and never counted as a pass. (Filed against the tool: the
  abort is reported only as `measurement produced no value`, and `keep_artifacts`, the only route to a log, fails when many
  `supply_v` keys are swept.)
* **Branch currents ring.** The trapezoidal integrator rings at the step rate on a floating bus after a select
  edge (+-1.6 uA seen locally), so leg currents are window averages, never instantaneous values or peaks.
* **The floating bus.** With both legs off the bus level comes from charge injection by the select edges and
  from leakage; the bench reports it and asserts nothing about it.

## Layout (follows `sim/README.md`; append-only)

```
make_bench.py        generates testbench/ (`--check` fails on drift)
nlflat.py            flattens the committed netlists to leaf devices (probe roster)
limits.py            supported limits with provenance
analyze.py           grading, stress aggregation (pure functions)
render.py            Markdown/CSV record renderers (pure text; write_records does the disk writes)
run_bench.py         CLI: submits via klt sim, grades, writes records; re-exports render.py
test_integrated.py   offline tests
testbench/tb_<slice>_<process>.spice, <slice>_<process>.request.json (tier A), <slice>_<process>_x.request.json (tier B), probes_<slice>.json
reports/<record-id>/<slice>_<process>.report.json.gz   raw measurements of every unit
records/<record-id>.md                                  evidence record
../../measurements/integrated-transition/<record-id>.{md,csv}   per-region view and per-point rows
```

```bash
python3 sim/integrated-transition/make_bench.py --check
python3 -m unittest discover -s sim/integrated-transition -p 'test_integrated.py'
python3 sim/integrated-transition/run_bench.py --preflight    # two units on the fleet, nothing recorded
python3 sim/integrated-transition/run_bench.py                # both tiers via klt sim (KLT_SIM_BACKEND=batch), ~1400 units
```

Reports and records are never edited; a re-run mints a new `<record-id>`. If a batch submit fails the script
prints the error and stops; it never runs the grid locally.
