# sim/program-read-legs/

PVT benches for the program leg (ballast + switch) and the read leg (sense
amp + `I_ref` branch) in `design/cells/` -- the transistor-level instantiation
of `spec/architecture.md` sections 1.2, 2 and 4 (see
[`spec/leg-design-record.md`](../../spec/leg-design-record.md)).

## STATUS: benches and runner are complete; no PVT record exists yet

**The PVT tables have not been produced.** Both batch submits (jobs
`klt-sim-b1f21dd1d468` and `klt-sim-c9421542227c`, 45 corners each, `ballast`
bench) were rejected before any simulation ran: the fleet runner image has
`klt 0.5.0`, this host has `klt 0.7.0`, and the submit preflight refuses a
skewed pair (`batch_runner_version_mismatch`, exit 87). Per the host rules the
grid was **not** run locally instead. No file under `records/`, `corners/` or
`netlist-snapshots/` exists, so nothing here is evidence yet.

Why a downgrade of the client is not a way out (checked, not assumed): a
`klt 0.5.0` client cannot express these requests at all -- it has no
`measurements[].expr` (operating-point quantities), no per-section model
library (needed to put `design.ngspice` ahead of the gf180mcu `.lib` cards,
see below) and does not stage the netlist's `.include` closure to the fleet.

To produce the record once the fleet runner matches the host client, run on a
host with `KLT_SIM_BACKEND=batch`:

    python3 sim/run_corners.py program-read-legs

which submits one `klt sim` request per bench and writes
`records/<record-id>.md` (plus `corners/`, `netlist-snapshots/`) only if the
fleet returns resolved corners. A failed submit writes nothing.

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
- Process corners only; no mismatch/Monte Carlo, so the sense mirror's offset
  spread is not evidenced.

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

## Open finding for Candidate 3 (single-corner debug probe, not evidence)

A one-corner local probe (typical, 27 C, `VDD` 3.3 V) of `margin3` shows the
programmed side of Candidate 3 passing only about 4 nA through the read leg at
`I_ref = 1 uA`, so `RDATA` stays 0 -- the `pfet_06v0` access device at
`WL = 0 V` is barely turned on with a read bit line near 1.3 V. The earlier
`R_on` figure for Candidate 3 (`sim/cell-device-characterization/`) is a
small-signal value measured with no DC drain-source drop across the access
device and does not predict this saturation-limited DC drive. This is the
reason `margin3_lowiref` exists. Whether any `I_ref` works for Region III
across PVT, or whether the PMOS candidate needs a different WL/`VB`/read
polarity, is what the fleet run is meant to answer; until it runs, treat
Region III's read path as **unproven**.

## Layout

```
sim/program-read-legs/
  benches.py            netlist-body + measurement generators (all bench numbers live here)
  run_experiment.py     klt request builder / runner / record writer (stdlib only)
  models/preamble.lib   design.ngspice wrapper section (see "Harness notes")
  .work/                git-ignored: generated decks and requests with host paths
  records/, corners/, netlist-snapshots/   created by the first successful run
```

`python3 sim/run_corners.py program-read-legs --probe` runs ONE typical corner
on the `local` backend as a debug aid; it records nothing.
