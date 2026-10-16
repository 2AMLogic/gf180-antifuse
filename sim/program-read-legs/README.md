# sim/program-read-legs/

PVT benches for the program leg (ballast + switch) and the read leg (sense
amp + `I_ref` branch) in `design/cells/` -- the transistor-level instantiation
of `spec/architecture.md` sections 1.2, 2 and 4 (see
[`spec/leg-design-record.md`](../../spec/leg-design-record.md)).

## STATUS: first PVT record exists (45 corners x 6 benches, fleet batch)

Record: [`records/20261015-061556-90de2cb.md`](records/20261015-061556-90de2cb.md)
(jobs in each report's `environment.remote`). All six benches returned 45/45
corners with no errors. Headlines, all conditional on the assumptions below:

- Mutual exclusion: 45/45 corners, 14 cases each, never both legs driving; (1,1)
  leaves both OFF.
- Ballast: the Section 2 inequality holds at the minimum-resistance corner for
  VPP 4/5/6 V under the ASSUMED `V_comp` = 1 V, `I_target_max` = 1 mA.
- Read decisions at `I_ref` = 1 uA: Candidates 1 and 2 decide correctly in
  every corner, unprogrammed and programmed (assumed R_prog) sides reported
  separately. **Candidate 3 programmed side fails** (wrong `RDATA` at all 45
  corners at min access sizing, 1/45 at 2x) at `I_ref` = 1 uA; at `I_ref` = 300 pA
  34/45 decide correctly, still failing the cold/slow corners -- Region III read path is not working as designed (see "Open finding").

Re-run trigger: the breakdown-augmented cell model (#62) replaces the assumed
R_prog; `I_ref < I_prog_min` stays unchecked until `I_prog_min` exists.

Client/runner note: the fleet runner image runs `klt 0.7.0`; the host client was
newer and the submit preflight refuses a skewed pair. This record was produced
with a version-matched client (`uvx --from klayout-tools==0.7.0 klt`, passed via
`KLT=<wrapper>`), still on the batch backend; no local grid was run.

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

## Open finding for Candidate 3 (debug probe, now confirmed by the PVT record)

A one-corner local probe (typical, 27 C, `VDD` 3.3 V) of `margin3` shows the
programmed side of Candidate 3 passing only about 4 nA through the read leg at
`I_ref = 1 uA`, so `RDATA` stays 0 -- the `pfet_06v0` access device at
`WL = 0 V` is barely turned on with a read bit line near 1.3 V. The earlier
`R_on` figure for Candidate 3 (`sim/cell-device-characterization/`) is a
small-signal value measured with no DC drain-source drop across the access
device and does not predict this saturation-limited DC drive. This is the
reason `margin3_lowiref` exists. The fleet PVT record confirms it: the Region III programmed side reads wrong
at 44-45 of 45 corners at `I_ref` = 1 uA and at 11 of 45 corners (cold/slow) at 300 pA. Treat Region III's read path as **failing as designed**; it likely
needs a different WL/`VB`/read polarity (design follow-up, not resolved here).

## Layout

```
sim/program-read-legs/
  benches.py            netlist-body + measurement generators (all bench numbers live here)
  run_experiment.py     klt request builder / runner / record writer (stdlib only)
  models/preamble.lib   design.ngspice wrapper section (see "Harness notes")
  .work/                git-ignored: generated decks and requests with host paths
  records/, corners/, netlist-snapshots/   written by each successful run (append-only)
```

`python3 sim/run_corners.py program-read-legs --probe` runs ONE typical corner
on the `local` backend as a debug aid; it records nothing.
