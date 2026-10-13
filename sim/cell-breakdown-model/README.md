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

- **Hot, not cold, is the worst read corner.** For Candidates 1 and 2 the
  worst programmed read is at ss / **125 °C** / low rail, not at the
  ss / −40 °C / low rail corner `spec/architecture.md` §4 names for the
  selected cell. The difference is about 9 % for Candidate 1.
- **Candidate 3 cannot read a programmed cell at the inherited placeholder
  bias.** At WL = 0 V with the n-well at 3.3 V, the PMOS access device is
  effectively off once the filament pulls CN low. I_prog_min is therefore
  not derivable until a Candidate 3 read bias is chosen (#75).
- **Candidate 2's window is narrow.** It has the narrowest window of the
  three, because its 25 µm LDNMOS access device leaks about 700× more than
  Candidate 1's at the fast/hot corner.
- **Non-converged trigger corners** are a transient-robustness limitation
  of the stock cells around the event, not a model outcome (#74).

## Running it

```bash
python3 sim/run_corners.py --check-env cell-breakdown-model
python3 sim/run_corners.py cell-breakdown-model                 # all candidates
python3 sim/cell-breakdown-model/run_experiment.py --candidates 2
```

Each run mints one record ID per candidate and writes the following, all
write-once and append-only (`sim/README.md`):

| Path | Contents |
|---|---|
| `corners/<id>/<bench>/` | `request.json`, the generated `body.spice`, klt's `report.json`, and the per-corner deck (`<corner-id>.cir`) and ngspice log (`<corner-id>.log`) |
| `netlist-snapshots/<id>.spice` | Frozen cell netlist plus wrapper, element and parameters |
| `records/<id>.md` | The record |

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

## Benches

All benches use the existing experiment's own stimulus. Its
`run_experiment.py` is imported as a library, so candidate definitions, the
OFF-bias levels, the C–V bias points, the 1.0 V ±10 % read rail,
`gmin = 1e-13` and the geometry levels are identical by construction.

| Bench | Analysis | Corners | Instances per deck |
|---|---|---|---|
| `access_op` | operating point (see below) | 5 MOS × 3 T × 3 read-rail = 45 | 4 sub-configs × 3 OFF biases × {stock, `b0`, `b1`} for I_off; 4 × {median, worst} programmed read at WL on |
| `access_ac` | `.ac`, read at 10 MHz | same 45 | 4 × {stock, `b0`, `b1`} for R_on |
| `cap_op` | operating point | 3 moscap × 3 T = 9 | 4 × 5 C–V biases × {stock, `b0`, `b1`}, leakage |
| `cap_ac` | `.ac`, read at 1 kHz | same 9 | same, C(V) |
| `trigger` | `.tran` 20 µs | 3 moscap × 3 T × 10 stress points = 90 | 2 dynamic instances (median and 1 % Weibull quantile); one stressed per corner |

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
  - **Derived quantities.** `run_experiment.py`'s `derive()` computes the
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
