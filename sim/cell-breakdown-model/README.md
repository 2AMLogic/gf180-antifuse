# sim/cell-breakdown-model/

Single-cell bench for the behavioral breakdown-augmented cell model in
[`design/breakdown/`](../../design/breakdown/README.md) (issue #62). Per
ratified candidate, and therefore per `spec/split-axis-plan.md` region, it
establishes three things:

- **(a) Regression.** With the breakdown element disabled (`bden=0`), or
  enabled but unprogrammed (`bden=1 prog=0`), the cell reproduces the
  committed `sim/cell-device-characterization` records.
- **(b) Programmed read and `I_prog_min`.** The programmed-cell read current
  at the assumed filament resistance, per PVT corner, and from it
  `I_prog_min`, the upper side of `spec/architecture.md` §4's
  `I_sneak_max < I_ref < I_prog_min`.
- **(c) Trigger and latch.** The breakdown event fires above the assumed
  threshold, not below it, and stays latched after the stress ends.

Everything in (b) and (c) is **conditional on the assumed parameters** in
`design/breakdown/breakdown_params.spice`. No number is labelled
`measured`, and nothing here is a property of gf180 silicon. The
programming-yield Monte Carlo and ballast sizing are out of scope; they
are follow-ups.

## Results so far

All numbers in (b) are conditional on the **assumed** parameters. All runs
were on the batch fleet; the job IDs are in each record.

| | Candidate 1 / Region I | Candidate 2 / Region II | Candidate 3 / Region III |
|---|---|---|---|
| Static-bench record | [`20261009-020137-66efd11`](records/20261009-020137-66efd11.md) | [`20261009-020409-66efd11`](records/20261009-020409-66efd11.md) | [`20261009-020416-66efd11`](records/20261009-020416-66efd11.md) |
| Trigger record (`uic`) | [`20261009-023645-6eff628`](records/20261009-023645-6eff628.md) | [`20261009-023648-6eff628`](records/20261009-023648-6eff628.md) | [`20261009-023651-6eff628`](records/20261009-023651-6eff628.md) |
| (a1) disabled/unprogrammed vs stock, same deck: R_on, C(V), leakage | all exactly equal | C(V), leakage exactly equal; R_on within reltol (worst 1.1e-5) | all exactly equal |
| (a1) same, I_off | all within criterion | all within criterion | all within criterion |
| (a2) committed headline I_sneak_max | 9.8192e-12 vs 9.8191e-12 A | 7.2888e-9 vs 7.2887e-9 A | 1.3949e-11 vs 1.3956e-11 A |
| (a2) committed headline R_on | 1.4466e4 vs 1.4466e4 Ω | 65.490 vs 65.490 Ω | 1080.1 vs 1098.0 Ω (floating CN; see below) |
| (b) I_prog_min at §4's `ss_-40c_bl0p90v` | 9.19 µA | 11.0 µA | 0.24 pA |
| (b) I_prog_min, worst corner | **8.35 µA at `ss_125c_bl0p90v`** | 10.98 µA at `ss_125c_bl0p90v` | 4.9 fA at `typical_27c_bl1p00v` |
| (b) I_prog_min / I_sneak_max | 8.5e5 | 1.5e3 | < 1: **no `I_ref` window** (#75) |
| (c) trigger, converged corners as predicted | 74/74 (16/90 not converged) | 78/78 (12/90 not converged) | 84/84 (6/90 not converged) |
| #74 record, raised-cosine edges (control + `trig1`/`prog`) | [`20261013-235220-dd70803`](records/20261013-235220-dd70803.md) | [`20261013-235232-dd70803`](records/20261013-235232-dd70803.md) | [`20261013-235241-dd70803`](records/20261013-235241-dd70803.md) |
| #74 record, C∞ edges (`trigc`/`progc`) | [`20261014-001717-86afd07`](records/20261014-001717-86afd07.md) | [`20261014-001720-86afd07`](records/20261014-001720-86afd07.md) | [`20261014-001723-86afd07`](records/20261014-001723-86afd07.md) |
| #74: one cell per deck, C∞ edges, all four decks x both stimuli | **360/360 converged** | **360/360 converged** | **360/360 converged** |
| #74: trigger outcome as predicted (`trigc` + `progc`, enabled decks) | 180/180 | 180/180 (`progc`: no corner breaks down, see below) | 180/180 |

- **Hot, not cold, is the worst read corner.** For Candidates 1 and 2 the
  worst programmed read is at ss / **125 °C** / low rail, not at the
  ss / −40 °C / low rail corner `spec/architecture.md` §4 names for the
  selected cell. The difference is about 9 % for Candidate 1.
- **Candidate 3 cannot read a programmed cell at the inherited placeholder
  bias.** At WL = 0 V with the n-well at 3.3 V, the PMOS access device is
  effectively off once the filament pulls CN low. I_prog_min is therefore
  not derivable until a Candidate 3 read bias is chosen (#75).
  **Resolved by #75** (below): the `bias_op` bench compares nine read-bias
  arrangements; the chosen one ties the n-well to the read rail.

- **Candidate 2's window is narrow.** It has the narrowest window of the
  three, because its 25 µm LDNMOS access device leaks about 700× more than
  Candidate 1's at the fast/hot corner.
- **Non-converged trigger corners (#74) came from the bench, not the
  breakdown element.** Two cells in one deck and a raised-cosine edge
  together account for every failure. With one cell per deck and C∞
  edges, all 1080 attempted corners converge on the fleet engine. See
  "Transient convergence (#74)".
- **The BL-driven program leg overstresses the access device at the
  assumed V_bd in every candidate. Candidate 2 cannot reach its assumed
  V_bd through that leg at all**: the 10 V LDNMOS's junction clamps BL/CN
  near 11.9 V. These results are conditional on the assumed V_bd; see
  "Transient convergence (#74)".

## Candidate 3 read bias (#75)

`bias_op` is a sixth bench, Candidate 3 only, run on its own:

```bash
python3 sim/cell-breakdown-model/run_experiment.py --candidates 3 --benches bias_op
```

It is **not** part of the default bench list, so the #62 records and a
default run are unchanged (`tests/test_c3_read_bias.py` regenerates the
committed Candidate 1/2/3 requests and decks and requires byte equality).
One `klt sim` request covers 45 PVT corners. Each of the nine
`BIAS_SCENARIOS` is a set of instances in the same deck, with its own read
rail (the swept `VBL` times a scale), selected-WL level and well drive
(`fixed` volts, or `track` = the scaled rail plus an offset). For each
scenario and each of the 4 sub-configurations it measures the BL current of:

| Instance | Cell state | WL | Used for |
|---|---|---|---|
| `off_*` | unprogrammed | 3 OFF levels | `I_off` |
| `offp_*` | programmed (median filament) | 3 OFF levels | `I_off` of an unselected programmed cell, the worst sneak case |
| `un_*` | unprogrammed | scenario ON level | selected-unprogrammed current |
| `pm_*`, `pw_*` | programmed (median, worst filament) | scenario ON level | `I_prog` |

The programmed and unprogrammed cells share the scenario's rail and well in
one solve. The leakage bound is recomputed per scenario:
`I_sneak_max` = (N-1) x `I_off`, and the verdict uses the solver-floor-limited
`I_zero,f` = (N-1) x max(`I_off`, abstol) + max(`I_sel,unprog`, abstol), since
ngspice does not resolve currents below abstol (1e-12 A) and several
scenarios return exactly 0.0 A. A scenario is feasible only with **no** failed
corner (klt status other than `pass`, or a missing or `None` measurement:
reported, never dropped) and min over corners of `I_prog` > max over corners
of `I_zero,f`. It also records n-well/BL/CN voltages for junction polarity and
gate-oxide checks.

| Record | Outcome |
|---|---|
| [`20261014-104105-9220086`](records/20261014-104105-9220086.md) | All scenarios but the placeholder are feasible. Chosen: **`s3_vb_track`** (WL on 0 V, n-well = the read rail), `I_prog_min` 1.25 nA at `ss_-40c_bl0p90v`, `I_zero,f` 3.2e-11 A, window 39 at placeholder geometry. Decision: [`spec/candidate3-read-bias-decision.md`](../../spec/candidate3-read-bias-decision.md). |

The placeholder scenario `s0_placeholder` reproduces the #62 failure exactly
(4.8572e-15 A at `typical_27c_bl1p00v`, 2.4003e-13 A at `ss_-40c_bl0p90v`).
Mismatch/Monte Carlo is not included. The conditional-on-assumed-filament
caveat above applies throughout.

## Running it

```bash
python3 sim/cell-breakdown-model/run_experiment.py --check-env
python3 sim/cell-breakdown-model/run_experiment.py               # all candidates
python3 sim/cell-breakdown-model/run_experiment.py --candidates 2

# issue #74 transient-convergence campaigns, one record per candidate each
python3 sim/cell-breakdown-model/run_experiment.py --campaign conv74  --candidates 1   # control + trig1/prog
python3 sim/cell-breakdown-model/run_experiment.py --campaign conv74c --candidates 1   # trigc/progc (C∞ edges)
python3 sim/cell-breakdown-model/run_experiment.py --campaign opstart --candidates 1   # no-uic reproducer
```

Each run mints one record ID per candidate and writes the following, all
write-once and append-only (`sim/README.md`):

| Path | Contents |
|---|---|
| `corners/<id>/<bench>/` | `request.json`, the generated `body.spice`, klt's `report.json` (coverage id lists elided) and its `report.json.sha256`, and the per-corner deck (`<corner-id>.cir`) and ngspice log (`<corner-id>.log`) |
| `netlist-snapshots/<id>.spice` | Frozen cell netlist plus wrapper, element and parameters |
| `records/<id>.md` | The record |

The committed `report.json` has its `coverage.checked` / `coverage.inapplicable`
id lists replaced by their counts (`harness.report.elide_coverage`): these are
characterization benches, so every entry restates
`characterization_without_limits` and the counters beside the lists already say
how many. Every measurement value, corner status, diagnostic, `environment`,
`provenance` and coverage counter is kept, and the sha256 of the full klt
report is committed alongside it as `report.json.sha256`.

**The corner grids run on the `batch` backend (the Spot fleet), never as a
local ngspice grid.** Every request names `"backend": "batch"`. If a batch
submit fails, the run records the error (`submit-error.txt` and the bench
status in the record) and does not fall back to running locally.

For debugging, `--smoke N:BENCH` runs **one corner of one bench** locally
and writes only under the git-ignored `.work/`. It is a probe, not
evidence. `--klt "<cmd>"` swaps the klt command. That is how every bench
was pre-flighted against the fleet runner's klt version before submission:

```bash
python3 sim/cell-breakdown-model/run_experiment.py --smoke 2:access_op \
    --klt "uvx --from git+https://github.com/2AMLogic/klayout-tools@v0.5.0 klt"
```

Requirements: `klt` on `PATH` and a gf180mcuD install that
`sim/harness/pdk.py` resolves. The script uses the stdlib only.

## Layout

```
sim/cell-breakdown-model/
  model.py              library: bench constants, collection and grading
  benches.py            library: SPICE deck and `klt sim` request builders
  render.py             library: record renderers (standard, bias); re-exports render_conv.py
  render_conv.py        library: #74 convergence-record renderer
  run_experiment.py     CLI driver / record writer; library facade re-exporting model.py + benches.py + render.py (stdlib only)
  .work/                git-ignored: local --smoke probe debris with host paths
  records/, corners/, netlist-snapshots/   written by each successful run (append-only)
```

## Benches

All benches use the existing experiment's own stimulus. `model.py` imports
the characterization experiment's `run_experiment.py` as a library, so
candidate definitions, the OFF-bias levels, the C–V bias points, the
1.0 V ±10 % read rail, `gmin = 1e-13` and the geometry levels are identical
by construction. This experiment's own `run_experiment.py` is the CLI
facade over `model.py` / `render.py` (see "Layout").

| Bench | Analysis | Corners | Instances per deck |
|---|---|---|---|
| `access_op` | operating point (see below) | 5 MOS × 3 T × 3 read-rail = 45 | 4 sub-configs × 3 OFF biases × {stock, `b0`, `b1`} for I_off; 4 × {median, worst} programmed read at WL on |
| `access_ac` | `.ac`, read at 10 MHz | same 45 | 4 × {stock, `b0`, `b1`} for R_on |
| `cap_op` | operating point | 3 moscap × 3 T = 9 | 4 × 5 C–V biases × {stock, `b0`, `b1`}, leakage |
| `cap_ac` | `.ac`, read at 1 kHz | same 9 | same, C(V) |
| `trigger` | `.tran` 20 µs | 3 moscap × 3 T × 10 stress points = 90 | 2 dynamic instances (median and 1 % Weibull quantile); one stressed per corner |
| `trig1_<v>`, `trigc_<v>` (#74) | `.tran` 20 µs, `uic` | 3 moscap × 3 T × 5 stress points = 45 | **1**: the `trigger` stimulus (PL driven, BL = 0); raised-cosine / C∞ edges |
| `prog_<v>`, `progc_<v>` (#74) | `.tran` 20 µs, `uic` | same 45 | **1**: BL-driven program leg (VPP pulse → ballast → BL, PL = 0); raised-cosine / C∞ edges |
| `opstart` (#74) | `.tran` 20 µs, **no** `uic` | 3 moscap × 3 T at the rated level = 9 | 1 stock cell (`trigc_st` deck) |

`<v>` is `st` (stock cell), `b0` (element disabled), `b1m` or `b1l`
(element enabled and dynamic, at the median or 1 % quantile). Within a
stimulus the four decks differ only in the cell line.

The 4 sub-configs are {min, 2×} access sizing × {min, 2×} capacitor
geometry.

- **One request per bench, all variants as instances.** `klt sim` owns the
  deck's single `.control` block and runs one analysis per corner. The
  existing benches' `op → alter → op → ac` sequences therefore cannot be
  submitted as they are. Each quantity becomes its own instance with its
  own bias source and a 0 V ammeter.
- **Measurements are `.meas` cards only** (see "Fleet klt version" below).
  - **Operating point.** A 3-point DC sweep of an unconnected dummy source
    (`VDMY -1 1 1`), read at its interior point: `.meas` cannot read an
    `.op`, and FIND needs an interval.
  - **AC.** A 3-point sweep centred on the characterization experiment's
    frequency, read exactly at the centre.
  - **Complex currents.** An ideal current-controlled voltage source
    (`H`, 1 Ω transresistance, draws nothing) turns each ammeter's complex
    current into a node voltage, so `vr()`/`vi()` can read it.
  - **Derived quantities.** `model.py`'s `derive()` computes the
    characterization experiment's quantities from those raw values: |I|,
    Re(V/I) and |I|/(2π·1 kHz).
- **Programmed read.** BL is at the read rail, WL is "fully on" (the
  existing benches' placeholder bias), PL = 0, and the state is forced
  programmed (`prog=1`). Two filament values are used: median (z = 0) and
  worst case (z = `bd_zrf_wc` = +3σ, which is 81.7 kΩ).
- **`I_prog_min`.** The worst-case-filament read current, minimised over
  the 4 sub-configurations. It is reported at the corner §4 names for the
  selected cell (ss / −40 °C / low rail) **and** at the worst corner over
  all 45, because those are not always the same corner. The existing
  characterization already found Candidate 3's `sf` corner far weaker than
  `ss`.
- **Trigger stress.** PL is driven with a raised-cosine pulse: 10 µs flat,
  100 ns edges. The access device is on and BL = 0, so pre-breakdown the
  capacitor sees the full PL voltage. The five levels are the rated
  voltage and 0.9, 0.95, 1.0 and 1.1 × V_bd(1 µs).
  - Polarity: positive for the NMOS-access Candidates 1 and 2, negative for
    Candidate 3. In each case the forming filament pulls CN *away* from
    forward-biasing the access device's CN-side junction.
  - State and damage are read at 19.9 µs, after the pulse has ended.
  - This is a **model-mechanism check**, not a program-path claim: the
    program bias scheme is not ratified, and the real program leg drives BL
    through the access device.
- **Program-leg stress (#74, `prog`/`progc`).** This follows the ratified
  topology (`spec/architecture.md` §1.2, §2). A VPP pulse drives BL through
  a ballast resistor, PL = 0 V is the return, and the five levels are the
  same magnitudes as above, positive for every candidate. The bias values
  are bench choices, because the spec leaves them open:
  - **Ballast.** `I_target_max` is not fixed by the spec, so R = V_bd / 500 µA
    is a **placeholder** (16.0 / 30.4 / 15.8 kΩ). It is an ideal resistor.
  - **Gate drive.** WL rides on VPP with the #62 static "on" bias added
    (`spec/supply-domains-decision.md` rows 8 and 9 leave it unresolved).
    For NMOS this is WL = 3.3 V or 5 V + VPP(t).
  - **Candidate 3 well.** The n-well also rides on VPP: VB = 3.3 V + VPP(t)
    (row 15 leaves the well level unresolved).
  - **Candidates 1 and 2 bulk.** VB is the p-substrate tie at 0 V (row 14).

  Before breakdown, the access device passes the full level to CN, so
  the oxide sees the same stress as in the PL-driven bench. The two
  exceptions are noted under "Transient convergence (#74)".

## Methodology findings

### Fleet klt version

The first submission (job `klt-sim-4c0059c15650`) was refused before
simulating:

```
batch job klt-sim-4c0059c15650 finished 'failed' (job command exited 87):
the job's klt reported: the fleet runner runs klt 0.5.0 but the submitting
client is 0.7.0+g4cbdfa769875 -- the request was not run (update the runner
image or use a compatible client)
```

The fleet image's klt (0.5.0) predates this host's client. It lacks:

- `expr` measurements;
- per-section corner libraries (`{"lib", "section"}`);
- the batch backend itself, so a version-matched 0.5.0 *client* cannot
  submit at all.

Rather than run anything locally, the requests were restricted to features
0.5.0 has:

- `.meas`-only measurements, as above;
- single-library process bundles (see "Two model libraries" below);
- `batch.runner_version_check: "warn"`, so the job runs.

Every bench was pre-flighted at one corner against a throwaway klt 0.5.0
(`uvx`, above). Each report's `environment.remote` records
`runner_klt_version` and `runner_compatibility: mismatch`. Because
the requests use nothing the runner lacks, the skew cannot have dropped an
option. A dropped measurement would show up as a missing value, and the
record counts those. The durable fix is updating the runner image, which
is a worker-spec change outside this repo.

### Two model libraries (Candidate 2)

Candidate 2 needs `smbb000149.ngspice` for its access device and
`sm141064.ngspice` for its capacitor. The runner's process bundles read
every section from the request's single `models.lib`. Each bench therefore
sweeps one library through `models.lib`. The section that stays fixed in
that bench is loaded from the body with the executing host's PDK path
(`/opt/pdk/gf180mcuD`, as observed in fleet-generated decks):

| Bench | Swept through `models.lib` | Fixed in the body |
|---|---|---|
| Access | `smbb000149` MOS corner | `sm141064 moscap_typical` |
| Capacitor and trigger | `sm141064` moscap corner | `smbb000149 typical` |

Candidate 2's devices use no `sm141064` MOS section. The original decks
loaded one anyway, and dropping it changes nothing: Candidate 2's
`typical_27c_bl1p00v` `ioff_lo` and R_on reproduce the committed log
exactly at the pre-flight corner.

### Wrapping by hierarchical node

The element attaches at `XC.CN` inside the wrapper (see
`design/breakdown/README.md`). That is how the committed netlists stay
unedited and uncopied.

### design.ngspice cannot be `.include`d in a batch deck

klt emits the corner `.lib` cards ahead of the circuit body. The fleet's
PDK lives at a different absolute path than this host's, and ngspice does
not expand `$PDK_ROOT` inside `.include`. A deck that `.include`s
`design.ngspice` therefore cannot travel. Its global switches (`sw_stat_*`,
`mc_skew`, `fnoicor`, and so on) are copied at run time, verbatim, out of
the resolved PDK file into the generated body, with that file's sha256 in
the header.

### Absolute `--outdir`

klt runs ngspice with its cwd set to the corner directory but hands it
paths relative to the invocation directory. A relative `-o` therefore makes
every corner fail before ngspice starts, reported only as N "measurement
produced no value" errors. This is already filed as
2AMLogic/klayout-tools#2892. The runner always passes an absolute path.

### Transient: one event per deck, smooth edges

- **Several cells breaking down in one deck abort the transient.** The
  global timestep collapses at each stiff breakdown event, and the failure
  shows up in a *different* instance's stock moscap macro. The trigger
  bench therefore keeps two instances but stresses only one per corner,
  through its own scalar amplitude source, which klt's supply axis sweeps.
- **PULSE corners at these voltages stall the stock Candidate 2 cell.** The
  slope discontinuity at the end of a PULSE edge makes the stock
  `cap_nmos_06v0` macro stall ("timestep too small") with **no** breakdown
  element present. Raised-cosine edges, which have a continuous first
  derivative, avoid it.

### Transient start (`uic`)

The first full trigger runs had many corners abort with "timestep too
small" on a stock moscap macro node:

| Candidate | Record | Corners errored |
|---|---|---|
| 1 | `20261009-020137-66efd11` | 32/90, mostly −40 °C |
| 2 | `20261009-020409-66efd11` | 53/90, all temperatures |
| 3 | `20261009-020416-66efd11` | 18/90 |

Most of these failed in the *idle* instance, or before any stress was
applied. A local single-deck bisection at −40 °C pinned it down:

- The **bare stock** `cell_candidate1`, with no wrapper and no breakdown
  element, fails the same way.
- Its capacitor alone and its access device alone each run cleanly.
- The series cell starting from ngspice's computed operating point fails.
- The same deck started from `uic` (zero initial conditions) runs.

`uic` also clears the failing Candidate 2 125 °C deck and the Candidate 1
`moscap_ff` −40 °C deck, which had hit the 300 s timeout.

The trigger bench therefore runs `tran ... uic`. Every stress source is 0
at t = 0 and the pulse starts at 1 µs, so the cell settles long before it
is stressed, and the damage integrator's D(0) = 0 becomes explicit rather
than inherited from an operating point.

The original runs are kept as evidence of the stock cells' operating-point
transient start problem. The `uic` trigger re-runs are separate records,
each linked from the original run's record. Any future transient work on
these cells (program-pulse benches, yield Monte Carlo) should expect the
same behaviour.

### Transient convergence (#74)

Issue #74: the #62 trigger transient did not converge at 16 / 12 / 6 of
90 corners (Candidates 1 / 2 / 3). The yield Monte Carlo needs the event
to converge at every corner.

All simulation evidence below is from the batch fleet, with ngspice 46,
runner klt 0.7.0 and models_lib sha256 `6edba54d…`. Local ngspice 46
runs, one deck at a time with the same model files, were used only as
probes. They reproduce the fleet's failures exactly: same node, same
time. So the "local 42 vs fleet 46" disagreement in the issue was an
engine-version difference, and it no longer applies.

#### 1. The control reproduces exactly

The #62 two-instance `trigger` deck was resubmitted unchanged, on a newer
runner image and a different instance type. It failed at **the same
corners** as the #62 records for all three candidates. Every failure
matched in node and time except one: Candidate 3's
`moscap_ff_125c_pla-8p69v` was a 300 s timeout before and is now a
"timestep too small" at 1.1 µs. The per-corner timeout depends on host
speed. The failures are therefore a deterministic property of the decks,
not fleet noise.

#### 2. Cause 1: two cells in one deck

ngspice reports most control failures in the stock moscap of the **idle**
instance, the one whose terminals are all held by ideal sources. Per
candidate, counting failures reported at a moscap node:

| Candidate | Idle instance | Stressed instance |
|---|---|---|
| 1 | 9 | 0 |
| 2 | 4 | 3 |
| 3 | 3 | 0 |

The rest are 300 s timeouts or a WL/VB source branch.

Local probes at single failing corners showed:

- Deleting the idle instance clears the failure. This held for Candidate
  2 at `moscap_ss_27c_pla6p00v` (rated voltage, no breakdown anywhere)
  and at the `moscap_typical_125c_pla15p20v` timeout, and for Candidate 1
  at `moscap_typical_-40c_pla8p00v`.
- Replacing the idle instance with a bare stock cell, with no breakdown
  element anywhere in it, does **not** clear the failure.
- The pass/fail outcome flips on deck details that do not change the
  circuit. A hand-written deck equivalent to a failing one converged.

**Why the idle cell is the victim.** ngspice expands a capacitor whose
value depends on its own voltage (the PDK's `cap_*` macros) into three
elements (seen with `listing expand`):

- an E-source that copies V(cap) onto an internal 1 F capacitor;
- the 1 F capacitor itself;
- a B-source whose current is `i(E) * C(V)`.

So the solver carries a branch "current" `ec_moscap#branch` whose value is
dV/dt in V/s, and it holds that value to the absolute current tolerance
(1 pA). An idle cell at rest jitters at femtovolt level. Once a stiff
event elsewhere has collapsed the shared timestep, that jitter divided by
the step is a large "current" that must converge to 1 pA. One cell per
deck removes the bystander.

**Results with one cell per deck** (`trig1`/`prog`, still raised-cosine
edges, 45 corners per deck):

| Candidate | `trig1` st / b0 / b1m / b1l | `prog` st / b0 / b1m / b1l |
|---|---|---|
| 1 | 45 / 45 / 45 / 45 | 45 / 45 / 45 / 45 |
| 2 | **41** / **41** / 45 / 45 | 45 / 45 / 45 / 45 |
| 3 | 45 / 45 / 45 / 45 | 45 / 45 / 45 / 45 |

Each entry is the number of corners converged out of 45.

#### 3. Cause 2: the raised-cosine edge

Candidate 2's 8 remaining failures are the **stock** cell and the
**disabled** wrapper. Both fail at the same four corners:
`moscap_ff_27c` at 13.68, 14.44, 15.20 and 16.72 V on PL. The failures
are a timestep collapse at t = 11.2011 µs in the stock moscap, or a
300 s timeout.

That time is exactly the end of the falling edge. There the raised
cosine's slope is continuous, but its second derivative jumps. The
`min`/`max` clamps that make the edge are invisible to ngspice's
breakpoint logic.

**Attribution: stock cell.** No breakdown element is active in either
failing deck. The enabled decks pass at the same corners. At 15.2 and
16.7 V their cell has broken down before the falling edge, so CN never
makes the full swing. At 13.68 V, though, the median enabled cell stays
intact, so its passing is more of the deck sensitivity seen in §2.

The fix is a C∞ edge, f(u) / (f(u) + f(1 − u)) with f(u) = exp(−1/u).
Every derivative of this edge is continuous and zero at both ends; it
has the same 100 ns rise and fall.

- **Locally**, it clears the committed reproducers
  `corners/20261013-235232-dd70803/trig1_st/moscap_ff_27c_pl16p72v.cir`
  and `…pl13p68v.cir`.
- **On the fleet**, `trigc`/`progc` are the full campaign with this edge:

| Candidate | Record | `trigc` st / b0 / b1m / b1l | `progc` st / b0 / b1m / b1l |
|---|---|---|---|
| 1 | `20261014-001717-86afd07` | 45 / 45 / 45 / 45 | 45 / 45 / 45 / 45 |
| 2 | `20261014-001720-86afd07` | 45 / 45 / 45 / 45 | 45 / 45 / 45 / 45 |
| 3 | `20261014-001723-86afd07` | 45 / 45 / 45 / 45 | 45 / 45 / 45 / 45 |

All 1080 corners converge, every measurement has a value, and no corner
times out. Every attempted corner is counted, and nothing is filtered.

#### 4. Cause 3: operating-point start (unchanged; `uic` stays)

The `opstart` bench is the `trigc_st` deck at the rated level, without
`uic`, so it holds a stock cell and no breakdown element. It is a fleet
reproducer of the start-up failure described under "Transient start".
Results:

| Candidate | Record | Converged | Failures |
|---|---|---|---|
| 1 | `20261014-010714-84c7e1d` | 6/9 | all three −40 °C corners: timestep collapse at t ≈ 0.1 ns in the stock moscap |
| 2 | `20261014-010717-84c7e1d` | 7/9 | two −40 °C corners |
| 3 | `20261014-010720-84c7e1d` | 9/9 | none |

**Attribution: stock cell.** Every transient bench therefore keeps
`uic`.

#### 5. Hypotheses tested and not supported

- **The breakdown element.** No non-converged corner in any
  single-instance deck has the element enabled. The element's numerical
  parameters (`bd_tcomp`, `bd_num_dw`) and the solver options were
  therefore **not changed**: no measured failure points at them.
  `design/breakdown/` is untouched (`check_params.py` still passes).
- **Access-junction overstress as the stiffness source.** In the
  PL-driven bench, a broken-down Candidate 1 cell pulls CN up to 6.8–7.8 V
  against the substrate-tied 6 V `nfet_06v0`. That is the reverse bias
  the issue suspected. Yet all of those corners converge once the deck
  holds one cell. Candidate 2's CN never rises above 0.38 V, and its #62
  failures were still there. The overstress is real (next item), but it
  is not what broke convergence.

#### 6. Threshold, latch and inertness

These results are all conditional on the assumed parameters.

- **Prediction.** For every enabled deck, the state predicted from the
  E-model is compared with what the simulation produced. The prediction
  applies the E-model to the disabled deck's mid-pulse oxide voltage at
  the same corner. Below threshold, the damage predicted from that
  voltage matches the simulated D within 1 %.
- **Result.** The outcome matches the prediction and latches (st exactly
  0 or 1 at 19.9 µs, after the pulse) at:
  - 90/90 corners per stimulus per candidate in `trigc`/`progc`;
  - the same in `trig1`/`prog`, except Candidate 2's `trig1`. There the
    8 corners whose disabled deck failed have no prediction; that
    record's text calls them "threshold boundary".
- **Inertness.** The disabled deck and the enabled-but-intact decks
  reproduce the stock deck in transient. Values agree exactly or within
  solver noise: the worst case is a sub-nV difference on CN at rest
  (relative 2.5e-2 on a 3 nV quantity).

#### 7. Device terminal voltages (assumption-conditional design finding)

Each record logs the extremes over the whole transient of every
access-device terminal pair. They are compared with the ratified ratings
(`nfet_06v0` / `pfet_06v0` 6 V, `nfet_10v0_asym` 10 V). Convergence does
not make these circuits valid:

- **Candidate 1, PL-driven.** After breakdown, the CN-side junction sees
  6.8–7.8 V (> 6 V).
- **Candidate 1, BL-driven.**
  - Before breakdown, BL and CN sit at VPP against the substrate: 7.2–8.8 V.
  - After breakdown, CN drops while WL stays at VPP + 3.3 V, so
    V(WL, CN) reaches 9.1–10.3 V.
- **Candidate 3.**
  - The CN-to-n-well junction reaches 10.7–14.0 V after breakdown, in
    both stimuli.
  - The #62 static bias (WL = −3.3 V, VB = 3.3 V) already puts 6.6 V
    gate-to-well on the 6 V device at every level, including the rated
    voltage.
- **Candidate 2, BL-driven.** BL and CN **clamp near 11.9 V** whatever
  VPP is. This is consistent with junction breakdown in the
  `nfet_10v0_asym` model, whose card sets `bvs = 11` on the CN-side
  source junction (and `bvd = 14.5`). With VPP at 13.7–16.7 V, 60–160 µA
  flows through the ballast into that clamp, the oxide never sees more
  than about 11.9 V, and **no corner breaks down**. Under the
  assumed V_bd of 15.2 V, Candidate 2 cannot be programmed through this
  leg with its bulk at 0 V. That extends the "Finding: Candidate 2 under
  the assumed field" in `design/breakdown/README.md`.

Each of these follows from the **assumed** V_bd (8.0 / 15.2 / 7.9 V)
exceeding the access ratings. `spec/cell-candidates.md` expects the 6 V
devices to "comfortably exceed" the programming voltage. This conflict is
recorded here for the program-path work. It does not change the spec or
the parameters.

#### Guidance for the yield Monte Carlo (#63)

- Put one cell in each transient deck.
- Use C∞ pulse edges (`edge_lines("cinf")`) and `tran ... uic`.
- Keep klt's per-corner failure accounting, so any corner that still
  fails stays in the denominator.

The convergence shown here covers the 2 Weibull quantiles × 5 levels × 9
PVT corners × 2 stimuli. The #62 decks showed how sensitive the solver is
to deck details, so a Monte Carlo over continuous `ubd`/`zrf` draws may
still hit isolated failures.

### Regression criterion: why not "every digit equal"

The regression quantities fall into two classes.

**Well-conditioned: R_on (AC) and C(V) (AC).** These are resolved far
above the solver's tolerances and are held to ngspice's `reltol` (1e-3).
In practice they reproduce to the printed digit.

**gmin-floor currents: I_off and capacitor leakage.** As the existing
experiment's README explains, these are upper bounds set by `gmin` on a
node that has no other DC path. They are 1e-13 A class, an order of
magnitude below ngspice's default `abstol` (1e-12 A). For such a current
the solver's own convergence test, |Δi| ≤ reltol·|i| + abstol, does not
pin the printed digits. Two local single-corner controls show this:

- **Candidate 1:** one stock cell alone in a deck reproduces the committed
  log exactly (9.670043e-14 A). The same stock cell with nothing more than
  a 0 V ammeter added in series prints 9.672818e-14 A, a 2.9e-4 shift with
  no breakdown element anywhere. At the same corner, with tightened
  `reltol`/`abstol`, stock and wrapper agree exactly.
- **Candidate 2:** the same stock `cell_candidate2` instance prints
  1.1313e-13, 1.1352e-13 or 1.2487e-13 A at `typical_27c_bl1p00v` (WL = 0 V)
  depending only on **which other instances share the deck**, again with no
  breakdown element involved. The internal CN voltage is identical
  (3.994672e-2 V) in every case. Tightening `reltol` to 1e-4 does not move
  these values; going below about 1e-5 stops the multi-instance `.op`
  converging at all.

So the regression is judged per class:

| Class | Criterion |
|---|---|
| Well-conditioned | \|Δ\| ≤ 1e-3·\|ref\| |
| gmin-floor | \|Δ\| ≤ 1e-3·\|ref\| + 1e-12 A, the solver's own bound |

Exact-match counts and the worst relative deviation are reported alongside,
so a deviation is visible rather than hidden by the loose bound.

**Caveat: R_on is not always well-conditioned either.** R_on is a
small-signal quantity taken at an operating point where no DC current
flows (the capacitor blocks it). The cell node CN therefore floats to
wherever the sub-`abstol` leakages put it, and for Candidates 2 and 3 the
access device's conductance depends on that voltage.

Candidate 3 at `ss_-40c_bl0p90v` shows this:

| Deck | CN at the operating point | R_on |
|---|---|---|
| Single stock instance (committed log's structure) | 1.23 V, 0.33 V above BL | 1098.048 Ω, reproduced exactly with or without the 0 V ammeter |
| The bench's multi-instance deck | slightly different | 1080.1 Ω |

The 1080.1 Ω value is identical under local ngspice 42 and fleet ngspice
46, so the engine version is ruled out.

The records therefore show a few R_on values outside `reltol` against the
committed logs: Candidate 2 up to 3 % at `fs_125c`, and Candidate 3's
headline 1.6 %. In each case the stock instance and the wrapper instances
agree exactly within the same deck. The deviation comes from deck
structure acting on a floating node, not from the breakdown element.

The element's inertness does not rest on these statistics. With `bden=0`
every B-source in `af_breakdown` evaluates to exactly 0 A with an exactly
zero Jacobian, so the cell's own equations are unchanged, and the
well-conditioned quantities confirm that numerically.

**Finding for the existing evidence.** The committed characterization
records' `I_off` and `I_sneak_max` figures inherit the same sub-`abstol`
indeterminacy, observed here at up to about 10 % for Candidate 2. This
does not change their conservative-upper-bound reading. It does mean a
re-run in a differently structured deck should not be expected to
reproduce them digit for digit. Those records are not edited
(append-only); this is noted for whoever next sizes `I_ref` against them.

## Corner-id convention

The corner IDs follow `sim/README.md`:

| Bench | Example | Supply field |
|---|---|---|
| Access | `ff_125c_bl1p10v` | Read rail on BL |
| Capacitor | `moscap_ss_-40c_nosupply` | None (`nosupply`) |
| Trigger | `moscap_typical_27c_pla8p00v` | Which instance (`pla`/`plb`) was stressed, and V(PL) |
