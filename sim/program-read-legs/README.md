# sim/program-read-legs/

PVT benches for the program leg (ballast + switch) and the read leg (sense
amp + `I_ref` branch) in `design/cells/` -- the transistor-level instantiation
of `spec/architecture.md` sections 1.2, 2 and 4 (see
[`spec/leg-design-record.md`](../../spec/leg-design-record.md)).

## STATUS: PVT records exist (fleet batch runs, 2026-10-15)

Records (both kept; `sim/` results are append-only evidence):
[`records/20261015-061556-90de2cb.md`](records/20261015-061556-90de2cb.md)
(earlier run, version-matched `klt 0.7.0` client, same 45 corners x 6 benches) and
[`records/20261015-151616-d3df921.md`](records/20261015-151616-d3df921.md) (latest).
The latest record is six `klt sim` requests, 45 corners each, all resolved (270/270), run on the
Spot batch fleet (job id of each in the record's `remote=` field; runner and
client `klt` versions matched). The earlier submits were rejected by a runner
version mismatch; that no longer applies. Programmed-side numbers are
**conditional on the assumed `R_prog`**. The corner-only records ran no mismatch; mismatch
Monte Carlo is a separate record (next section).

Headline (see the record for the per-corner tables; sides and regions are never
averaged): mutual exclusion holds at 45/45 corners; the ballast inequality is met
at every VPP; Regions I and II decide correctly at 45/45 corners on both sides at
`I_ref = 1 uA`; **Region III's programmed side fails at slow/cold corners**
(0/45 correct at `I_ref = 1 uA`, 34/45 at 300 pA) -- see the finding below.

To regenerate, on a host with `KLT_SIM_BACKEND=batch`:

    python3 sim/run_corners.py program-read-legs

A failed submit writes nothing. Every request carries
`batch.capacity_wait_s = 1800` (the fleet rule's floor is 600 s; the value
matches `sim/cell-breakdown-model`), so klt waits for fleet capacity *before*
refusing a launch, and a refusal that still happens is retried by the harness
policy (`K.BACKOFF`) as the same request — two layers: wait, then resubmit.

## Mismatch Monte Carlo (record `records/20261016-010943-88897b2.md`)

`python3 sim/run_corners.py program-read-legs --mc` submits, per bench, one `klt sim` request per
corner point (typical/27 C/3.30 V, ss/-40 C/2.97 V, ff/125 C/3.63 V) with
`monte_carlo = {n: 200, vary: "mismatch"}` on the batch backend. `sw_stat_mismatch` is set by the
`design_mm` section of `models/preamble.lib`; it is one PDK-wide switch, so every MOS in the bench is
varied, not only the sense mirror (the record says so). Each margin row has 200 independent draws and
reports the decision yield with its one-sided 95 % Clopper-Pearson lower bound (98.5 % is the best a
200-for-200 row can state). The `offset` bench gives the mirror's current offset against `I_ref`
(sigma about 9-11 % of `I_ref`). Result: Regions I and II decide correctly at 200/200 on both sides at
all three points; Region III's programmed side is 0/200 at typical and slow/cold at `I_ref = 1 uA`
(and 0/200 at slow/cold at 300 pA) -- unproven, not a pass (#75). Programmed rows stay conditional on
the assumed `R_prog`. `--mc --probe` runs one unit locally and records nothing.

## Benches (`benches.py` generates every netlist body)

Each bench is a netlist **body** for `klt sim` (no `.control`), pulling in the
committed `design/netlists/*.spice` with `.include` -- no device line is copied
-- and declaring its quantities as `measurements[].expr` on an `op` analysis.

| Bench | What it shows | Axes (besides the 45-corner PVT grid) |
|---|---|---|
| `exclusion` | Both legs on one bit line. For every `(PROG_EN, READ_EN)` state, `VPP` (3.63 V, 6.0 V) and bit-line level (0 V, `VPP`) the current through each leg is measured through a zero-volt ammeter. Pass: at most one leg drives (> 1 uA) the line, `(1,1)` and `(0,0)` drive nothing, `(1,0)` only the program leg, `(0,1)` only the read leg, and neither leg sinks the other's level. | state x VPP x BL level (14 cases) |
| `ballast` | Program leg alone with the bit line held at an assumed `V_compliance` (1.0 V) and, pessimistically, at 0 V. Reports `R_ballast`, switch resistance and current against `(VPP - V_comp)/I_target_max`. | VPP 4 / 5 / 6 V |
| `margin1`, `margin2`, `margin3` | Read decision per candidate/region: unprogrammed side loaded with that candidate's recorded `I_sneak_max`; programmed side with an **assumed** filament resistor (10 kohm and 100 kohm) across the capacitor. Both legs on the bit line, program leg OFF (idle `VPP` 6 V, the leakage worst case). Reports read current, bit-line voltage, `SENSE` and `RDATA`; margins are `I_ref / I_read` (unprogrammed) and `I_read / I_ref` (programmed), reported **separately**. | access sizing min / 2x; side |
| `margin3_lowiref` | Candidate 3 again at `I_ref = 300 pA` (see "Open finding"). | same |

Corner grid for every bench: process typical / ff / ss / fs / sf (moscap and
poly-resistor sections follow ff / ss; typical for fs / sf), -40 / 27 / 125 C,
`VDD` 2.97 / 3.30 / 3.63 V with `VCLAMP` tracking at 1.62 / 1.80 / 1.98 V --
45 corners. Logic highs are `E` sources that track `VDD`.

## Assumptions (every one is repeated in every record)

- Programmed-state resistance is an **assumed placeholder** (10 kohm, 100
  kohm); there is no breakdown model. `I_ref < I_prog_min` stays unchecked.
- `I_sneak_max` per candidate is read from
  `sim/cell-device-characterization/records/` (a gmin-floor upper bound,
  evaluated there at ff/125 C/high supply) and applied at **every** corner:
  the worst-case sneak floor is combined with each selected-cell corner.
- `I_ref` (1 uA) and `VCLAMP` are bench-supplied; there is no on-die
  reference.
- Access sizing "min" is the committed netlist's default `wacc`, not the
  ratified split-axis level (see `design/README.md`).
- The corner-only records have no mismatch; the sense mirror's offset spread is
  evidenced only by the Monte Carlo record above (N = 200 per point, three points,
  not the full 45-corner grid).

## Harness notes (klt friction, for the operator to file generically)

- **Model-card ordering.** `klt sim` emits its `.lib` cards *before* the
  netlist's `.include`s, but the gf180mcu model files need the globals in
  `design.ngspice` (for example `fnoicor`) defined first. The only seam is a
  `corners.process` bundle whose first section is a wrapper library
  (`models/preamble.lib`) that includes it. With `models.pdk` set, a relative
  per-section library is resolved inside the PDK directory, so the wrapper has
  to be named by absolute path: the runner writes a host-specific copy to
  `.work/` (git-ignored) at run time and the committed request snapshots
  record the repo-relative name instead.
- A top-level element can reference a subcircuit-internal node by its flattened
  name (`xc_u_min.cn`, `xpg_x.rb_top`); the benches rely on it to put the
  assumed filament resistor across the capacitor and to read the ballast's
  internal node without editing the committed cell netlists.

## Open finding for Candidate 3 (confirmed by the fleet run)

An earlier single-corner probe suggested that Candidate 3's programmed side
passes only a few nA through the read leg (the `pfet_06v0` access device at
`WL = 0 V` is barely on with a read bit line near 1 V), so `RDATA` stays 0. The
45-corner run confirms it as evidence: at `I_ref = 1 uA` the programmed side
decides correctly at 0/45 corners (worst `I_read` about 4.9 pA at
`ss/-40C/2.97 V`); at `I_ref = 300 pA` it is 34/45, still failing the slow/cold
corners. The earlier `R_on` figure for Candidate 3
(`sim/cell-device-characterization/`) is small-signal and does not predict this
saturation-limited DC drive. No `I_ref` tried works across PVT, so Region III's
read path needs a different WL / `VB` / read polarity (a design change, not
made here). Region III's read path is **unproven**, not passing.

## Layout

```
sim/program-read-legs/
  benches.py            netlist-body + measurement generators (all bench numbers live here)
  model.py              library: constants, klt request/bench builders, analysis + statistics
  render.py             library: record renderers
  run_experiment.py     CLI runner / record writer; re-exports model.py + render.py (stdlib only)
  models/preamble.lib   design.ngspice wrapper section (see "Harness notes")
  .work/                git-ignored: generated decks and requests with host paths
  records/, corners/, netlist-snapshots/   written by each successful run (append-only)
```

The committed `<bench>[.<point>].report.json` has its `coverage.checked` /
`coverage.inapplicable` id lists replaced by their counts
(`harness.report.elide_coverage`): these are characterization benches, so every
entry restates `characterization_without_limits` and the counters beside the
lists already say how many. Every measurement value, corner status, diagnostic,
`environment`, `provenance` and coverage counter is kept, and the sha256 of the
full klt report is committed alongside it as
`<bench>[.<point>].report.json.sha256`.

`python3 sim/run_corners.py program-read-legs --probe` runs ONE typical corner
on the `local` backend as a debug aid; it records nothing.
