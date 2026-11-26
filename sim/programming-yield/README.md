# sim/programming-yield/

Programming-yield Monte Carlo campaign (issue #66, T1 item 6). For each
ratified cell candidate, and therefore for each `spec/split-axis-plan.md`
grid region, it measures **success fraction vs program-pulse condition**
with confidence intervals, one curve per region and access-sizing
sub-configuration, under the behavioral breakdown-augmented model of
`design/breakdown/` (issue #62).

> **Every curve is conditional on ASSUMED breakdown statistics.** All the
> kinetics and the filament distribution in
> `design/breakdown/breakdown_params.spice` are labelled `assumed`; only
> the oxide thicknesses are `literature`; nothing is `measured`. These
> yields are **not a prediction of silicon.** Each record opens with a
> banner saying so. They show how the *design axes* move a yield curve
> under a stated model and exercise the harness; they cannot replace
> measured breakdown data.

## Results so far

All yields are **conditional on the assumed breakdown statistics** (banner
above), pooled over the 9 PVT corners (n = 900 per cell unless stated),
95 % Wilson interval. Per-corner rows, the worst corner per condition, the
current distributions and the sampler check are in the records. One row per
(region, access sizing); columns are the five pulse conditions of
"Pulse conditions" (V = fraction of that candidate's own V_bd(1 us)).

| Region / sizing | 0.96 V, 1 us | 1.00 V, 1 us (nominal) | 1.04 V, 1 us | 1.00 V, 0.25 us | 1.00 V, 4 us |
|---|---|---|---|---|---|
| I (C1) `min` | 0.010 [0.005, 0.019] | 0.513 [0.481, 0.546] | 1.000 [0.996, 1.000] | 0.094 [0.077, 0.115] | 0.997 [0.990, 0.999] |
| I (C1) `2x` | 0.011 [0.006, 0.020] | 0.477 [0.444, 0.509] | 1.000 [0.996, 1.000] | 0.094 [0.077, 0.115] | 0.998 [0.992, 0.999] |
| II (C2) `min`, latch + read | 0.011 | 0.477 | 1.000 | 0.064 | 0.998 |
| II (C2) `min`, **with the assumed 1 mA bound** | 0.007 [0.003, 0.014] | 0.149 [0.127, 0.174] | 0.276 [0.247, 0.306] | 0.021 [0.014, 0.033] | 0.297 [0.268, 0.327] |
| II (C2) `2x`, with the 1 mA bound | 0.007 [0.003, 0.014] | 0.148 [0.126, 0.172] | 0.272 [0.244, 0.302] | 0.021 [0.014, 0.033] | 0.290 [0.261, 0.320] |
| III (C3) `min`, **upper bound** (no read criterion) | 0.011 [0.006, 0.020] | 0.477 [0.444, 0.509] | 1.000 [0.996, 1.000] | 0.094 [0.077, 0.115] | 0.997 [0.990, 0.999] |
| III (C3) `2x`, **upper bound** | 0.011 [0.006, 0.020] | 0.477 [0.444, 0.509] | 1.000 [0.996, 1.000] | 0.094 [0.077, 0.115] | 0.997 [0.990, 0.999] |

Sources (all append-only, in `records/`):

| Region | Records |
|---|---|
| I | `20261013-200244-7932822` (access `min` all five conditions, `2x` at 0.25 us); `20261013-222809-e32ed34` (supplement: `2x` at the 1 us and 4 us conditions) |
| II | `20261014-003936-81de201` (all conditions, flat-top current; supersedes `20261013-222806-e32ed34`, whose current criterion was wrong, see "Current criterion") |
| III | `20261013-200250-7932822` (0.25 us and 4 us, both sizings); `20261013-222812-e32ed34` (supplement: the 1 us conditions); `20261014-003939-81de201` (supplement: the one cell of the previous record that timed out, 300 samples) |

What the numbers do and do not say:

- **The yield curves are steep and centred where designed.** Under the
  assumed Weibull spread (beta = 1.5) the yield goes from about 1 % at 0.96
  V_bd to about 50 % at 1.00 V_bd to 100 % at 1.04 V_bd at a 1 us width, and
  from 9 % to 50 % to 99.7 % across a 0.25 / 1 / 4 us width sweep. The
  closed-form cross-check agrees at every condition except the nominal one,
  where it over-predicts by about 7 points (0.551 against 0.477-0.513) because it credits the
  whole rising and falling edges as flat-top time; that offset is
  structural, not a sampler fault (the sampler check is in every record).
- **No PVT corner moves the latch rate resolvably.** The corner-to-corner
  spread of a condition is within its per-corner interval; the model has no
  temperature or process dependence of breakdown, so this is expected and is
  a statement about the model.
- **Access sizing does not move the latch rate either** (Candidate 1 `min`
  0.513 against `2x` 0.477 at the nominal point; the two come from different
  seed layouts, so they are *not* paired, and their intervals overlap).
  Sizing moves the post-event *current* (Candidate 1: 88 uA against 154 uA
  median), which matters only through the current bound.
- **Candidate 1 and Candidate 3 coincide** because the model gives them the
  same kinetics, nearly the same tox (8.0 against 7.9 nm), the same relative
  pulse and the same seeded draws. That is the model's polarity blind spot
  (`design/breakdown/README.md`), not a finding that PMOS and NMOS oxides
  yield alike.
- **Candidate 2's yield is dominated by the assumed current bound.** Its
  post-event current is the 10 kohm median filament at 15 V across it, a
  median 1.5 mA, so a 1 mA bound removes most latched cells (0.149 against
  0.477 at the nominal point). With the real `I_target_max` and ballast
  unknown, the no-bound column is the latch-and-read yield and the bounded
  one is an illustration of how much that missing number matters.
- **The read criterion never binds.** `I_ref` (geometric mean of the #62
  window) is so far below the programmed read current at z up to 4 that
  `z_crit` is 8 to 15 (a probability of 1.0000 under the assumed filament
  distribution). The read side would only matter with a much wider filament
  spread or a narrower window.
- **Capacitor-geometry** is not resolvable (no area dependence in the
  model), as above.

## What is sampled, and what counts as success

One transient per sample, one breakdown event per deck. Per sample the
cell instance draws, from the `.options seed=` that `klt sim` writes from
`monte_carlo.seed`:

| Draw | Distribution | Meaning |
|---|---|---|
| `ubd` | `aunif(0.5, 0.5)` clamped to [1e-6, 1-1e-6] | per-instance Weibull quantile of the time to breakdown (breakdown *threshold* variability) |
| `zrf` | `agauss(0, 1, 1)` | per-instance filament-resistance draw, in sigmas |

Device mismatch of the stock MOS devices is **not** sampled: the stock
gf180mcu `cap_*` and access-device models carry no breakdown, and the
threshold spread that matters for programming is the breakdown element's.
The record says so; the mismatch axis is a separate follow-up.

A sample is exactly one of **ok / fail / inconclusive**:

1. **Latched.** `st >= 0.99` at the end of the transient. `st <= 0.01` is
   *not programmed* (fail). In between is a half-formed filament:
   *inconclusive* (counted in `err`, never silently as a pass or a fail).
2. **Current within bound.** The programming current through the access
   path, `<= I_bound`. `I_bound` is an **assumed, unratified** campaign
   parameter (default 1 mA, `--ibound`): `spec/architecture.md` section 2
   leaves `I_target_max` open and the cell model has no ballast resistor.
   Because that number is a placeholder, every yield table also carries a
   `yield, no I bound` column (latch and read only), and the current
   distribution is tabulated so any other bound can be applied to the saved
   data. See "Current criterion" below for which current is measured.
3. **Read decision correct at the worst-case read corner** (Candidates 1
   and 2). The programmed cell's read current at that sample's `zrf`,
   `I_read(z)`, must be `>= I_ref`, where `I_read(z)` is the pointwise
   minimum over the read corners (ss; -40/27/125 degC; BL = 0.9 V) of a
   programmed-read table run in the same record (`readtab` request), and
   `I_ref = sqrt(I_sneak_max * I_prog_min,wc)` from the #62 record. `I_ref`
   is **a campaign choice**, not a ratified spec value.
   **Candidate 3 has no `I_ref` window** at the inherited placeholder read
   bias (#75), so criterion 3 is **not evaluated** for it and its yields
   are explicit **upper bounds**.

### Current criterion

The first runs (Candidates 1 and 3, and a Candidate 2 run superseded by
the one below) measured the **maximum |i(VBL)| over the whole pulse**. For
Candidates 1 and 3 that is the filament current (latched samples 20-150 uA
against about 16 uA of charging current in unprogrammed ones), so the value
means what it says. For Candidate 2 it does not: the thick-oxide capacitor's
charging current at 15 V is 3.3 mA in *both* latched and unprogrammed
samples, which swamps the filament and made every sample fail a 1 mA bound
for a reason unrelated to programming. Candidate 2's yield column in its
first record is therefore wrong, and that record is superseded. Later runs
measure the **steady post-event current**: |i(VBL)| 20 ns before the falling
edge, on the flat top, where the charging current is gone (an unprogrammed
sample reads about 0.2 nA there). Because that value is never larger than the
whole-pulse maximum, the Candidate 1 and 3 verdicts against the 1 mA bound
are unchanged by the better measurement; their latched currents are all far
below it.

## Pulse conditions

`spec/split-axis-plan.md` section 4 asks for roughly five conditions per
sub-combination: a voltage sweep at a fixed nominal width plus a width sweep
at a fixed nominal voltage. The nominal centre is each candidate's own
`(1.00 x V_bd(t_ref), t_ref = 1 us)`, so the *relative* structure is
identical across regions while the absolute voltages differ (8.0 / 15.2 /
7.9 V, assumed):

| Condition | Voltage | Width |
|---|---|---|
| `v0p96_w1u` | 0.96 x V_bd | 1 us |
| `v1p00_w1u` (nominal) | 1.00 x V_bd | 1 us |
| `v1p04_w1u` | 1.04 x V_bd | 1 us |
| `v1p00_w0p25u` | 1.00 x V_bd | 0.25 us |
| `v1p00_w4u` | 1.00 x V_bd | 4 us |

The pulse has raised-cosine 100 ns edges (the stock moscap macro stalls on
PULSE slope discontinuities, see `sim/cell-breakdown-model/README.md`).
Because `klt sim` supplies the voltage axis through `corners.supply_v`
and a pulse width is a deck constant, each (sizing, width) pair is one
request; the three voltages of the nominal width share a request.

## Sub-configurations run, and one not run

- **Access sizing `min` and `2x`: run.** Sizing changes the post-breakdown
  current the access device passes, so it moves criterion 2 and the read
  margin.
- **Capacitor geometry `2x`: not run.** `af_breakdown` has no area
  dependence (its kinetics see tox only), so a larger capacitor changes
  the model's breakdown statistics by construction: the split axis is not
  resolvable from a yield curve until the model gains area scaling
  (Poisson-area Weibull). Running it now would manufacture a null result.
  This is a model gap, recorded in each record, not a statement about
  silicon.

## Sample sizing

`n` Monte Carlo samples per (sub-configuration, condition, PVT corner)
cell; the default is `--n 100`. The 95 % Wilson half-width is at most
`1.96 * sqrt(0.25 / n)`: 0.098 at n = 100. Pooling a condition's 9 PVT
corners multiplies the sample size by up to 9 (half-width <= 0.033). `n`
is chosen from the interval width wanted, not from a target yield; each
record states the `n` actually run. A cell that needs a tighter interval is
re-run at a larger `n` as a **new** record.

PVT: moscap `typical`/`ff`/`ss` x -40/27/125 degC. The supply axis is the
pulse amplitude.

### Draw reuse

`klt sim` derives each sample's seed from (`monte_carlo.seed`, corner
index, sample index). Each request here is one (sizing, condition,
process corner), so its only corner axis is temperature, and each process
corner gets its own `monte_carlo.seed` (base + 1000 x process index). The
nine PVT corners of a condition are therefore independent sample sets and
pooling them is valid. The two access sizings, and the five pulse
conditions, reuse the same draws at the same (process, temperature,
sample): a paired design. It makes sizing and width comparisons far less
noisy than independent draws, but their intervals are **not independent**,
and the sampler check counts distinct draws only.

### Job size

The fleet kills a job at 3600 s. A first run put every voltage of a width
into one request (2700 samples); on the slower decks that exceeded the limit
and returned nothing (Candidate 3 at 1 us, Candidate 1 access `2x` at 1 us
and 4 us). Per-sample wall time is 1-4 s and varies by candidate, sizing and
width (a 4 us pulse integrates four times as long). The campaign therefore
submits one request per (sizing, condition, process corner), 300 samples,
and the records state which job each number came from. The first-run records
remain in `records/` as evidence, with their failed jobs shown as `no data`
or `error`; the supplement records say which conditions they re-run.

## Sampler check and analytic cross-check

- **Sampler.** Every record tabulates the mean/sd/min/max of the realized
  `ubd` and `zrf` draws against their targets, and the number of distinct
  `ubd` values.
- **Analytic.** For a constant-field pulse of effective width `tw + tr`,
  `D = T/(tq t50) >= 1` gives `P = 1 - exp(-ln2 (T/t50)^beta)`. Each row
  carries this value. It ignores the edge shape, the stock capacitor's
  divider and the completion term, so a deviation of a few points is
  expected; a large one means a bookkeeping or sampler bug.

## Running it

```bash
python3 sim/programming-yield/run_experiment.py --check-env
python3 sim/programming-yield/run_experiment.py --candidates 1,2,3 --n 100
python3 sim/programming-yield/run_experiment.py --smoke 1      # ONE sample, locally
python3 sim/programming-yield/run_experiment.py --render RID --candidates N
```

Every request names `"backend": "batch"` and is submitted to the Spot
fleet. **If a submit fails, the run records the error
(`submit-error.txt`, and the job status in the record) and does not fall
back to a local grid.** `--smoke` runs one sample in one corner locally; it
writes only under the git-ignored `.work/` and is a probe, not evidence.

Code layout (as in `sim/cell-breakdown-model/`): the experiment's library
lives in the siblings `model.py` (campaign constants, deck and `klt sim`
request builders, statistical analysis, saved-report loaders) and `render.py`
(the Markdown record renderer); `run_experiment.py` is the CLI driver and
re-exports their surface, so loading it as a library keeps every attribute
unchanged. `render.py` imports one-way from `model.py`; neither imports the
CLI.

Evidence layout, all write-once and append-only (`sim/README.md`):

| Path | Contents |
|---|---|
| `corners/<id>/y_access-<sizing>_tw<width>/` | `request.json`, `body.spice`, klt's `report.json` |
| `corners/<id>/readtab/` | the programmed-read table request and report (Candidates 1, 2) |
| `netlist-snapshots/<id>.spice` | frozen cell netlist, wrapper, element and parameters |
| `records/<id>.md` | the record: banner, success criterion, sample sizing, per-region yield tables |

## Methodology findings

### A random `.param` is re-evaluated at every reference

`.param ubd_s={aunif(0.5,0.5)}` does **not** fix one draw per run:
ngspice draws a fresh value at each place the parameter is referenced. A
deck that passes `ubd={ubd_s}` to the instance and also reads `{ubd_s}`
into a probe source gets two different numbers (0.996 and 0.725 in the
same run), so the "recorded" draw would not be the one the cell used, and
every yield tied to it would be silently wrong. The element therefore
reports its own draws on two output-only probe nodes (`V(ubdn)`,
`V(zrfn)` in `design/breakdown/af_breakdown.spice`; no effect on the cell
equations), and the campaign reads them back with `.meas`. This was
checked: with the draw fixed to the value read back, the damage matches
the draw (ubd 0.716 gives D = 0.68, ubd 0.996 gives D = 0.25).

### Fleet klt version

`sim/cell-breakdown-model/README.md` describes a fleet runner (klt 0.5.0)
older than the client. The `monte_carlo` block was pre-flighted at one
sample against klt 0.5.0 and reproduces the same derived draws as the 0.7
client, and the jobs here ran on a matching runner (each record's job list
states the runner version and compatibility). The requests still use only
`.meas` measurements and single-library process bundles, so they run on
either.
