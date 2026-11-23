# Record 20261013-200244-7932822

- **Record ID**: 20261013-200244-7932822
- **Claim**: issue #66 -- programming yield of Candidate 1 / Region I, success fraction vs pulse condition (`spec/split-axis-plan.md` section 4), per access-sizing sub-configuration and PVT corner. Substantiates T1 item 6 (Monte Carlo evidence) only in the conditional form stated in the banner below.
- **Netlist provenance**: schematic (design/netlists/cell_candidate1.spice wrapped by design/breakdown/cell_candidates_bd.spice), clean tree at run time

> **PROVENANCE BANNER -- READ FIRST.** Every number below is **conditional on the ASSUMED breakdown statistics** of `design/breakdown/breakdown_params.spice` (critical field, field-acceleration, Weibull shape, completion time, filament median and spread are all labelled `assumed`; only the oxide thicknesses are `literature`; nothing is `measured`). These yields are **not a prediction of gf180 silicon**. They show how the *design axes* move a yield curve under that stated model, and they exercise the harness; they cannot replace measured breakdown data from `measurements/`.

- **Model parameters** (sha256 of `design/breakdown/breakdown_params.spice`: `33dfcdf713cd1fcb6413f8ee79d3ea2b0667ae9ebebc0cb57123d676e873e87a`):

  | Parameter | Value | Unit | Provenance |
  |---|---|---|---|
  | `c1_bd_tox` | 8.0000e-09 | m | literature |
  | `bd_ebd` | 1.0000e+09 | V/m | assumed |
  | `bd_tref` | 1.0000e-06 | s | assumed |
  | `bd_gam` | 6.9000e-08 | m/V | assumed |
  | `bd_beta` | 1.5000e+00 | 1 | assumed |
  | `bd_tcomp` | 1.0000e-08 | s | assumed |
  | `bd_rf_med` | 1.0000e+04 | ohm | assumed |
  | `bd_rf_sig` | 7.0000e-01 | 1 | assumed |

  Derived: V_bd(t_ref) = **8.000 V** (assumed, not a gf180 number). Pulse polarity positive (as the #62 trigger bench).

- **Success criterion** (per sample; a sample is exactly one of ok / fail / inconclusive):
  1. the breakdown state is **latched** at the end of the transient: `st >= 0.99` (`st <= 0.01` is *not programmed* = fail; anything in between is a half-formed filament and is **inconclusive**, not counted either way);
  2. the **peak access-path current** over the pulse, max |i(VBL)| (this record predates the flat-top measurement; for this candidate the filament current dominates the charging current, so the value is the programming current), is `<= 1.0000e-03 A`. This bound is an **ASSUMED campaign parameter, not a ratified one**: `spec/architecture.md` section 2 leaves `I_target_max` open and the cell model has no ballast resistor, so the current limit here is the access device alone. The current distribution is tabulated so any other bound can be applied to the saved data;
  3. the **post-pulse read decision is correct at the worst-case read corner**: the programmed cell's read current `I_read(z)` at that sample's filament draw `z` is `>= I_ref`, where `I_read(z)` is the pointwise minimum over the read corners (ss, -40, 27, 125 degC, BL = 0.9 V) of the programmed-read table below, interpolated log-linearly in z, and `I_ref = sqrt(I_sneak_max * I_prog_min,wc)` from the #62 record. **`I_ref` is a campaign choice** (geometric mean of the window, which `spec/architecture.md` section 4 does not ratify), not a spec value. The decision uses the programmed side only; the unprogrammed side is the #62 `I_sneak_max`, which the model makes independent of the pulse.

- **Sample sizing**: n = 100 Monte Carlo samples per (sub-configuration, pulse condition, PVT corner) cell. The 95 % Wilson interval half-width is at most 0.098 (p = 0.5, n = 100) and narrower toward the ends; pooling the 3 x 3 PVT corners of a condition multiplies the sample by up to 9. Chosen from that half-width, not from a yield target. A cell that needs a tighter interval is re-run with a larger n as a new record.
- **Sampler**: `klt sim` `monte_carlo` {n=100, vary="mismatch"}; the draws are `ubd = aunif(0.5, 0.5)` clamped to [1e-06, 1 - 1e-06] (uniform Weibull quantile) and `zrf = agauss(0, 1, 1)` (standard-normal filament draw), evaluated once per run from the `.options seed=` klt writes, with a distinct `monte_carlo.seed` per process corner (base 20261013 + 1000 x process index). The draws are a function of (seed, temperature index, sample index), so the PVT corners of a condition are independent samples while the two access sizings and the five pulse conditions reuse the same draws at the same (process, temperature, sample) -- a paired design, README "Draw reuse".

- **Corner matrix run**: ['moscap_ff', 'moscap_ss', 'moscap_typical'] x temperatures [-40, 27, 125] degC x pulse conditions below x access sizing min, 2x (capacitor geometry fixed at `min`). Programming transient only; the read-side PVT is the table below.
- **Not run, and why**: the capacitor-geometry axis (`2x`). `af_breakdown` has **no area dependence** (its kinetics see tox only), so a larger capacitor changes the breakdown statistics of this model by construction -- it is *not resolvable* here and a run would only add the stock capacitor's different divider. The model must gain area scaling (Poisson-area Weibull) before that split axis can be read from a yield curve; running it now would manufacture a null result.

- **Execution**: engine ngspice on the batch fleet; every request names `"backend": "batch"`; no local grid was run. Jobs:
  - access `2x`, `v0p96_w1u`: klt status `submit-error`, job `n/a`, runner klt n/a (n/a), n/a s -- ERROR: exit -15 (attempt 1)
stdout:

stderr:
klt sim: warning: batch job bound 810120s (options.timeout_s 300s x 2700 units + 120s; a conservative fully-serial upper bound, not a runtime estimate) exceeds the fleet's whole-job ceiling of 3600s (max_job_seconds from fleet_config); a job still running at the
  - access `2x`, `v1p00_w0p25u`: klt status `pass`, job `klt-sim-445ce261712d`, runner klt 0.7.0 (match), 652 s
  - access `2x`, `v1p00_w1u`: klt status `submit-error`, job `n/a`, runner klt n/a (n/a), n/a s -- ERROR: exit -15 (attempt 1)
stdout:

stderr:
klt sim: warning: batch job bound 810120s (options.timeout_s 300s x 2700 units + 120s; a conservative fully-serial upper bound, not a runtime estimate) exceeds the fleet's whole-job ceiling of 3600s (max_job_seconds from fleet_config); a job still running at the
  - access `2x`, `v1p00_w4u`: klt status `error`, job `klt-sim-ea6027b35c7d`, runner klt 0.7.0 (match), 3631 s
  - access `2x`, `v1p04_w1u`: klt status `submit-error`, job `n/a`, runner klt n/a (n/a), n/a s -- ERROR: exit -15 (attempt 1)
stdout:

stderr:
klt sim: warning: batch job bound 810120s (options.timeout_s 300s x 2700 units + 120s; a conservative fully-serial upper bound, not a runtime estimate) exceeds the fleet's whole-job ceiling of 3600s (max_job_seconds from fleet_config); a job still running at the
  - access `min`, `v0p96_w1u`: klt status `pass`, job `klt-sim-8c3b446a1440`, runner klt 0.7.0 (match), 2999 s
  - access `min`, `v1p00_w0p25u`: klt status `pass`, job `klt-sim-08a8037f2aa1`, runner klt 0.7.0 (match), 1292 s
  - access `min`, `v1p00_w4u`: klt status `pass`, job `klt-sim-75317562d66b`, runner klt 0.7.0 (match), 1933 s

- **Programmed-read table** (read side; request `readtab`, source of `I_read(z)`); #62 record `20261009-020137-66efd11`: I_sneak_max = 9.8192e-12 A, worst-corner I_prog_min = 8.3513e-06 A:
  - **I_ref (campaign choice) = 9.0556e-09 A**

  | Sizing | z=-3 | z=-2 | z=-1 | z=+0 | z=+1 | z=+2 | z=+3 | z=+4 | z_crit |
  |---|---|---|---|---|---|---|---|---|---|
  | `min` (min over read corners) | 3.5354e-05 | 3.3599e-05 | 3.0561e-05 | 2.5893e-05 | 1.9869e-05 | 1.3597e-05 | 8.3513e-06 | 4.7141e-06 | 14.94 |
  | `2x` (min over read corners) | 6.3612e-05 | 5.8118e-05 | 4.9596e-05 | 3.8436e-05 | 2.6598e-05 | 1.6504e-05 | 9.3882e-06 | 5.0336e-06 | 14.14 |

  `z_crit` is the filament draw above which the read falls under `I_ref`; the assumed filament median/spread put it at `min`: P(z <= z_crit) = 1.0000; `2x`: P(z <= z_crit) = 1.0000.

- **Result** -- success fraction vs pulse condition. One block per access sizing; rows are (condition, PVT corner). `succ/n` counts ok samples over **all** n drawn; `err` are inconclusive samples (klt error / non-converged / half-formed), so `yield` is a **lower bound** (errors counted as not-ok) and `yield_hi` counts them as ok. `yield, no I bound` drops criterion 2 (the unratified current bound) and keeps latch and read. CI is the 95 % Wilson interval on `succ/n`. `analytic` is the closed-form constant-field Weibull prediction, a sampler cross-check only.

### Candidate 1 / Region I, access sizing `min`

| Condition | V_pulse [V] | tw [us] | Corner | n | succ | err | yield | CI95 | yield_hi | yield, no I bound | analytic |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `v0p96_w1u` | 7.680 | 1 | `moscap_ff_-40c` | 100 | 0 | 0 | 0.000 | [0.000, 0.037] | 0.000 | 0.000 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_ff_27c` | 100 | 1 | 0 | 0.010 | [0.002, 0.054] | 0.010 | 0.010 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_ff_125c` | 100 | 4 | 0 | 0.040 | [0.016, 0.098] | 0.040 | 0.040 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_ss_-40c` | 100 | 1 | 0 | 0.010 | [0.002, 0.054] | 0.010 | 0.010 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_ss_27c` | 100 | 1 | 0 | 0.010 | [0.002, 0.054] | 0.010 | 0.010 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_ss_125c` | 100 | 0 | 0 | 0.000 | [0.000, 0.037] | 0.000 | 0.000 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_typical_-40c` | 100 | 0 | 0 | 0.000 | [0.000, 0.037] | 0.000 | 0.000 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_typical_27c` | 100 | 1 | 0 | 0.010 | [0.002, 0.054] | 0.010 | 0.010 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | `moscap_typical_125c` | 100 | 1 | 0 | 0.010 | [0.002, 0.054] | 0.010 | 0.010 | 0.013 |
| `v0p96_w1u` | 7.680 | 1 | **all PVT pooled** | 900 | 9 | 0 | **0.010** | [0.005, 0.019] | 0.010 | 0.010 | 0.013 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ff_-40c` | 100 | 51 | 0 | 0.510 | [0.413, 0.606] | 0.510 | 0.510 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ff_27c` | 100 | 50 | 0 | 0.500 | [0.404, 0.596] | 0.500 | 0.500 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ff_125c` | 100 | 60 | 0 | 0.600 | [0.502, 0.691] | 0.600 | 0.600 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ss_-40c` | 100 | 47 | 0 | 0.470 | [0.375, 0.567] | 0.470 | 0.470 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ss_27c` | 100 | 49 | 0 | 0.490 | [0.394, 0.587] | 0.490 | 0.490 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_ss_125c` | 100 | 56 | 0 | 0.560 | [0.462, 0.653] | 0.560 | 0.560 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_typical_-40c` | 100 | 52 | 0 | 0.520 | [0.423, 0.615] | 0.520 | 0.520 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_typical_27c` | 100 | 58 | 0 | 0.580 | [0.482, 0.672] | 0.580 | 0.580 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | `moscap_typical_125c` | 100 | 39 | 0 | 0.390 | [0.300, 0.488] | 0.390 | 0.390 | 0.551 |
| `v1p00_w1u` | 8.000 | 1 | **all PVT pooled** | 900 | 462 | 0 | **0.513** | [0.481, 0.546] | 0.513 | 0.513 | 0.551 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ff_-40c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ff_27c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ff_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ss_-40c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ss_27c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_ss_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_typical_-40c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_typical_27c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | `moscap_typical_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p04_w1u` | 8.320 | 1 | **all PVT pooled** | 900 | 900 | 0 | **1.000** | [0.996, 1.000] | 1.000 | 1.000 | 1.000 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_-40c` | 100 | 8 | 0 | 0.080 | [0.041, 0.150] | 0.080 | 0.080 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_125c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_-40c` | 100 | 7 | 0 | 0.070 | [0.034, 0.137] | 0.070 | 0.070 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_125c` | 100 | 17 | 0 | 0.170 | [0.109, 0.255] | 0.170 | 0.170 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_-40c` | 100 | 6 | 0 | 0.060 | [0.028, 0.125] | 0.060 | 0.060 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_125c` | 100 | 7 | 0 | 0.070 | [0.034, 0.137] | 0.070 | 0.070 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | **all PVT pooled** | 900 | 85 | 0 | **0.094** | [0.077, 0.115] | 0.094 | 0.094 | 0.134 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_-40c` | 100 | 99 | 0 | 0.990 | [0.946, 0.998] | 0.990 | 0.990 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_27c` | 100 | 99 | 0 | 0.990 | [0.946, 0.998] | 0.990 | 0.990 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_-40c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_27c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_-40c` | 100 | 99 | 0 | 0.990 | [0.946, 0.998] | 0.990 | 0.990 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_27c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_125c` | 100 | 100 | 0 | 1.000 | [0.963, 1.000] | 1.000 | 1.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | **all PVT pooled** | 900 | 897 | 0 | **0.997** | [0.990, 0.999] | 0.997 | 0.997 | 0.997 |

### Candidate 1 / Region I, access sizing `2x`

| Condition | V_pulse [V] | tw [us] | Corner | n | succ | err | yield | CI95 | yield_hi | yield, no I bound | analytic |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `v0p96_w1u` | 7.680 | 1 | (no data) | | | | | | | | |
| `v1p00_w1u` | 8.000 | 1 | (no data) | | | | | | | | |
| `v1p04_w1u` | 8.320 | 1 | (no data) | | | | | | | | |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_-40c` | 100 | 8 | 0 | 0.080 | [0.041, 0.150] | 0.080 | 0.080 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ff_125c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_-40c` | 100 | 7 | 0 | 0.070 | [0.034, 0.137] | 0.070 | 0.070 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_ss_125c` | 100 | 17 | 0 | 0.170 | [0.109, 0.255] | 0.170 | 0.170 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_-40c` | 100 | 6 | 0 | 0.060 | [0.028, 0.125] | 0.060 | 0.060 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_27c` | 100 | 10 | 0 | 0.100 | [0.055, 0.174] | 0.100 | 0.100 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | `moscap_typical_125c` | 100 | 7 | 0 | 0.070 | [0.034, 0.137] | 0.070 | 0.070 | 0.134 |
| `v1p00_w0p25u` | 8.000 | 0.25 | **all PVT pooled** | 900 | 85 | 0 | **0.094** | [0.077, 0.115] | 0.094 | 0.094 | 0.134 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_-40c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_27c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ff_125c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_-40c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_27c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_ss_125c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_-40c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_27c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | `moscap_typical_125c` | 100 | 0 | 100 | 0.000 | [0.000, 0.037] | 1.000 | 0.000 | 0.997 |
| `v1p00_w4u` | 8.000 | 4 | **all PVT pooled** | 900 | 0 | 900 | **0.000** | [0.000, 0.004] | 1.000 | 0.000 | 0.997 |

- **Worst PVT corner per condition** (lowest yield among the corners of a cell; the yield-vs-condition claim for design purposes is this, not the pooled row):

  | Sizing | Condition | Worst corner | yield | CI95 |
  |---|---|---|---|---|
  | `min` | `v0p96_w1u` | `moscap_typical_-40c` | 0.000 | [0.000, 0.037] |
  | `min` | `v1p00_w1u` | `moscap_typical_125c` | 0.390 | [0.300, 0.488] |
  | `min` | `v1p04_w1u` | `moscap_typical_-40c` | 1.000 | [0.963, 1.000] |
  | `min` | `v1p00_w0p25u` | `moscap_typical_-40c` | 0.060 | [0.028, 0.125] |
  | `min` | `v1p00_w4u` | `moscap_typical_-40c` | 0.990 | [0.946, 0.998] |
  | `2x` | `v1p00_w0p25u` | `moscap_typical_-40c` | 0.060 | [0.028, 0.125] |
  | `2x` | `v1p00_w4u` | `moscap_typical_-40c` | 0.000 | [0.000, 0.037] |

- **Sampler check** (10800 usable samples, 2700 distinct (ubd, zrf) draws; the rest are deliberate repeats, see README "Draw reuse"), statistics over the distinct draws: `ubd` mean 0.4961 (uniform: 0.5000, s.e. 0.0056), sd 0.2840 (uniform: 0.2887), min 0.0008, max 0.9994; `zrf` mean +0.0105 (s.e. 0.0192), sd 1.0238 (target 1).

- **Access-path current of latched samples** (max over the pulse; the data behind criterion 2):

  | Sizing | latched samples | median [A] | p95 [A] | max [A] | frac <= 1.0000e-05 | frac <= 1.0000e-04 | frac <= 1.0000e-03 | frac <= 1.0000e-02 |
  |---|---|---|---|---|---|---|---|---|
  | `min` | 5095 | 8.8209e-05 | 9.6408e-05 | 9.6703e-05 | 0.000 | 1.000 | 1.000 | 1.000 |
  | `2x` | 85 | 1.5239e-04 | 1.6893e-04 | 1.6959e-04 | 0.000 | 0.000 | 1.000 | 1.000 |

- **What this does not show**: (i) any silicon yield; (ii) the capacitor-area axis (model has none); (iii) temperature or process dependence of breakdown itself (the model has none, so PVT enters only through the stock capacitor/access device); (iv) ballast sizing (no ballast in the cell model; the current bound is an assumed placeholder); (v) the program-path bias scheme (not ratified; the pulse is applied on PL with BL = 0 and the access device on, as in the #62 trigger bench); (vi) any difference between candidates beyond oxide thickness and the access device: the model gives all three the same kinetics and the same seeded draws, so candidates with equal relative pulse and comparable access devices reproduce each other's latch counts (e.g. Candidates 1 and 3 here). A cross-candidate yield comparison is a statement about this assumed model, not about the oxides.

- **Links**:
  - frozen netlist snapshot: `sim/programming-yield/netlist-snapshots/20261013-200244-7932822.spice`
  - requests, decks and klt reports: artifact store manifest `manifests/artifacts/programming-yield-20261013-200244-7932822.manifest.json`
- **Timestamp / author**: 2026-11-22T12:34:56Z / Claude (loom sweep, issue #66)
- **Supersedes**: (none)
