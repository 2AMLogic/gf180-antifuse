# design/breakdown/ — behavioral breakdown-augmented cell model

`spec/cell-candidates.md` records that the stock gf180mcu `cap_*` models are
a pure pre-breakdown C–V fit, with no breakdown event, no post-breakdown
resistive branch and no leakage element. Any programmed-cell or
programming-yield simulation therefore needs a custom model.
`spec/architecture.md` §2 and §4 leave `I_target_max`, the ballast value and
`I_ref < I_prog_min` open on exactly that gap. This directory adds the
smallest model that closes it **as a labelled assumption**, not as a
property of this process (issue #62).

| File | What it is |
|---|---|
| [`af_breakdown.spice`](af_breakdown.spice) | The behavioral breakdown element `af_breakdown a b`: B-sources plus one capacitor, ngspice-native, no Verilog-A/OSDI. |
| [`cell_candidates_bd.spice`](cell_candidates_bd.spice) | Wrappers `cell_candidate{1,2,3}_bd BL WL PL VB`, which add the element to the **unmodified** committed cells. |
| [`breakdown_params.spice`](breakdown_params.spice) | Every number the model uses, one `.param` per line, each with a `provenance=` label. |
| [`check_params.py`](check_params.py) | Fails on an unlabelled number, an unknown label, `measured` without data in `measurements/`, or wrapper/netlist default drift. |

Run the check with `python3 design/breakdown/check_params.py`. It uses
the stdlib only and needs no PDK. The bench that exercises the model is
[`sim/cell-breakdown-model/`](../../sim/cell-breakdown-model/README.md).

## How the wrapper attaches without editing the cell

`design/netlists/cell_candidateN.spice` is derived from xschem and must not
be edited. Its capacitor node `CN` is internal, not a port. The wrapper
instantiates the cell as `XC` and connects the element to `XC.CN`. ngspice
flattens hierarchical names, so `XC.CN` inside the wrapper is the same
node as the cell's own `CN`. Before building on this, a resistor attached
that way was checked to carry exactly V(CN)/R. No device line is repeated,
so a schematic change reaches the wrapper on the next `regen-netlists.sh`.
`check_params.py` asserts that the wrapper's `wcap/lcap/wacc/lacc` defaults
still equal the netlist's.

The element sits in **parallel** with the stock capacitor, so the stock
model keeps supplying the C–V. Candidate 2's `nfet_10v0_asym` keeps its
ratified drain→`BL`, source→`CN` orientation (`design/README.md`), because
`BL/WL/PL/VB` pass straight through.

## Model

Terminals `a` = the gate plate (`CN`) and `b` = the body plate (`PL`).

| Quantity | Expression |
|---|---|
| Oxide field | E = \|V(a,b)\| / tox (flat-band and surface potential ignored) |
| Median time-to-breakdown (E-model) | t50(E) = tref · exp(−γ·(E − E_bd)) |
| Per-instance Weibull quantile | tq = (ln(1/(1−u_bd)) / ln 2)^(1/β), equal to 1 at u_bd = 0.5 |
| Damage (Miner's rule + completion) | dD/dt = dyn·en·( 1/(tq·t50(E)) + s_d/t_comp ), with D(0) = 0 |
| Dynamic state | s_d = smoothstep((D − 1)/dw) |
| Breakdown state | s = max(prog, s_d) |
| Filament | I(a→b) = en · s · V(a,b) / r_f, with r_f = r_f,med · exp(σ_rf · z_rf) |

- **Latching.** D never decreases, so once a transient drives D past 1 the
  state stays at 1 after the stress is removed. No hysteretic switch is
  needed.
- **Completion term.** Without `s_d/t_comp`, a partly formed filament pulls
  V(a,b) down, the E-model rate collapses with it, and D stalls just past
  1 with the state half on. That was observed while building this, and it
  is a numerical artefact, not hard breakdown.
- **Stochastic hooks.** `ubd` is the per-instance breakdown-threshold
  draw: it shifts that instance's breakdown field by ln(tq)/γ. `zrf` is the
  per-instance filament draw. A Monte Carlo deck draws them per instance,
  e.g. `ubd={aunif(0.5,0.4999)} zrf={agauss(0,1,1)}`. The yield Monte Carlo
  itself is a follow-up, not part of this directory.
- **Modes.**

  | Setting | Use |
  |---|---|
  | `bden=0` | Disabled: the element is instantiated but every B-source is identically 0 A with zero Jacobian, so the cell's own equations are unchanged. |
  | `bden=1 prog=0 dyn=0` | Unprogrammed, static. |
  | `bden=1 prog=1` | Programmed. |
  | `bden=1 dyn=1` | Transient programming. **Transient only**: in an `.op` the integrator capacitor is open and D settles to rate·`rdleak`, which is not a damage integral. |

## Parameters and provenance

All values are in [`breakdown_params.spice`](breakdown_params.spice) with
their reasoning. In summary:

| Label | Parameters |
|---|---|
| `literature` | Oxide thickness per candidate: 8.0 / 15.2 / 7.9 nm. Read from the pinned gf180mcu PDK model files (`nfet_03v3`, `nfet_06v0`, `pfet_03v3` toxe), following `spec/cell-candidates.md`'s association of each capacitor with its MOS flavour. |
| `assumed` | Everything else: E_bd = 10 MV/cm at tref = 1 µs, γ = 3 decades per MV/cm, Weibull β = 1.5, t_comp = 10 ns, r_f,med = 10 kΩ with σ_ln = 0.7, the worst-case filament quantile z = +3, and four numerical-only constants. |
| `measured` | Nothing. `measurements/` holds no data yet. |

`spec/cell-candidates.md` leaves the breakdown voltages of both oxide
flavours as an open question. The assumed field therefore produces
**assumed** breakdown voltages:

| Candidate | V_bd at 1 µs |
|---|---|
| 1 | 8.0 V |
| 2 | 15.2 V |
| 3 | 7.9 V |

Every downstream number (I_prog_min, the trigger levels) is conditional on
them. γ was not picked freely. It is the smallest round value for which a
cell at its **rated** voltage survives more than 10 years under this
model: Candidate 1 at 3.3 V gives t50 ≈ 4·10¹¹ s. A smaller γ would
predict read-disturb breakdown that the PDK's own voltage ratings rule
out.

## What is deliberately the same across candidates, and why that is a gap

The kinetics (E_bd, γ, β, t_comp) and the filament distribution are shared
by all three candidates. Only tox differs. That is a simplification with
known blind spots:

- **Polarity.** `spec/cell-candidates.md` chose Candidate 3 because NMOS
  and PMOS breakdown statistics are *not* symmetric. This model has no
  number for that asymmetry and treats |V| symmetrically. Candidate 3 vs
  Candidate 1 therefore differs here only by 0.1 nm of tox. The polarity
  split is a measurement question, and this model cannot answer it.
- **Thick oxide.** Using one critical field for 15.2 nm and 8 nm oxide
  ignores thickness-dependent breakdown physics.
- **Not modelled at all:**
  - temperature or process dependence of breakdown;
  - tox process skew (the PDK's `mc_toxe` and `*_tox` offsets are not
    propagated into E);
  - pre-breakdown tunnelling leakage (the stock model has none either);
  - the dependence of filament resistance on program compliance current;
  - non-ohmic post-breakdown conduction.

Each of these is a candidate refinement once `measurements/` has data.
None is papered over by the numbers above.

## Finding: Candidate 2 under the assumed field

At the assumed 10 MV/cm, Candidate 2's 15.2 nm capacitor needs about
15.2 V to break down within 1 µs. That is above the 10 V rating of its
`nfet_10v0_asym` access device. Whether that matters depends on the
program bias scheme (which terminals carry VPP, and how the access gate is
driven), and that scheme is not ratified. It is recorded here as an
assumption-conditional observation for the program-path work, not a spec
change.
