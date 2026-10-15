# gf180-antifuse

An N×N antifuse array on GlobalFoundries gf180mcu — MUX'd row/column
addressing, SPI program/read — designed and verified by AI agents. A
write-once memory as a **device-physics characterization vehicle**: the grid
deliberately varies antifuse cell design and programming conditions across
regions, so a single die measures the design space (programming yield, read
margin, retention) rather than proving one operating point.

![fleet burndown](https://raw.githubusercontent.com/2AMLogic/2am/main/fleet-metrics/charts/gf180-antifuse.svg)

**Private repo.** Visibility is an operator decision; nothing here is
published.

## What the block is

- **Cell**: thin-oxide MOS capacitor antifuse (programmed by gate-oxide
  breakdown at elevated voltage) behind a thick-oxide access/isolation
  device. Candidate cell variants and their split axes are the subject of
  the spec, not a given.
- **Array**: N×N grid (N chosen in `spec/`), row/column MUX carrying both
  the program current path and the read sense path. Region-by-region splits
  across the grid (geometry, oxide flavor, program conditions).
- **Interface**: SPI slave — address, program-enable, read. Program voltage
  supplied externally for the test vehicle (a `spec/` decision record covers
  what is on-die vs. off-die).

## Status

The spec — cell candidates, N, split-axis plan, program/read architecture,
and the measurement matrix — came first. The first design sources are now in
`design/`: xschem schematics and derived netlists for the three ratified
antifuse cell candidates. The array, row/column MUX, sense path and SPI slave
are specified at the interface level only and are not captured yet — see
`design/README.md` for what is and is not designed.

## Spec table

One row per ratified parameter. Values live only in the linked decision
record; this table does not restate them.

| Parameter | Ratified in |
|---|---|
| Candidate 1 (baseline): capacitor and access device | [`spec/cell-candidates.md`](spec/cell-candidates.md) |
| Candidate 2 (high-voltage): capacitor and access device | [`spec/cell-candidates.md`](spec/cell-candidates.md) |
| Candidate 3 (polarity): capacitor and access device | [`spec/cell-candidates.md`](spec/cell-candidates.md) |
| Grid size N | [`spec/split-axis-plan.md`](spec/split-axis-plan.md#grid-size-n) (working target, subject to revision) |
| Region map and split-axis mapping | [`spec/split-axis-plan.md`](spec/split-axis-plan.md#region-map) |
| Row/column MUX and program/read path | [`spec/architecture.md`](spec/architecture.md#1-rowcolumn-mux--program-and-sense-path) |
| Program current limiting | [`spec/architecture.md`](spec/architecture.md#2-program-current-limiting) |
| Sense scheme | [`spec/architecture.md`](spec/architecture.md#4-sense-scheme) |
| Program-voltage source (on-die vs. off-die) | [`spec/program-voltage-decision.md`](spec/program-voltage-decision.md) (provisional for this die) |
| SPI register map | [`spec/architecture.md`](spec/architecture.md#5-spi-slave-register-map) |

The per-candidate device names are also tabulated in
[`design/README.md`](design/README.md).

## Reproducing results

Commands are run from the repo root. Outcomes below were observed on a
shared worker host on 2026-10-09; "not run here" means deliberately not
executed there, not that it fails.

**Tools and PDK.** `xschem` 3.4.7, `ngspice` 46, `python3` (stdlib only for
`sim/`), and the gf180mcu PDK (`gf180mcuD`, `open_pdks` commit
`c6d73a35f524070e85faff4a6a9eef49553ebc2b`, the revision recorded in
[`spec/cell-candidates.md`](spec/cell-candidates.md)). Point `PDK_ROOT` at a
root containing `gf180mcuD/` (scripts fall back to `~/.volare`). The
`signoff/` grade needs a specific `klt` build, below.

| Dir | Command | Outcome |
|---|---|---|
| `design/` | `design/regen-netlists.sh --check` | ran OK: all three netlists reproduce exactly. (Without `--check` it rewrites `design/netlists/`.) |
| `design/` | `design/check-netlists.sh` | ran OK: reproducibility, ngspice elaboration, capacitor-geometry sweep all pass. |
| `sim/` | `python3 sim/run_corners.py --list` | ran OK |
| `sim/` | `python3 sim/run_corners.py --check-env cell-device-characterization` | ran OK: ngspice and PDK found. |
| `sim/` | `python3 sim/run_corners.py cell-device-characterization` | **not run here**: it executes the full PVT grid of ngspice runs, which the shared worker must not run locally. Existing results are in `sim/cell-device-characterization/records/` (append-only; a re-run mints a new record). |
| `signoff/` | `./signoff/verify.sh` | **fails with the host `klt` (0.6.0+g1eb3e4bfd0f5)**: the committed report was graded by `klt` 0.5.0+g32f69f811682, so a different build reports drift. This is a build mismatch, not evidence drift; the `klt` build pin and the regrade command are in [`signoff/README.md`](signoff/README.md). The report was not regenerated. |

Methodology, record format and how to read results:
[`design/README.md`](design/README.md), [`sim/README.md`](sim/README.md),
[`sim/cell-device-characterization/README.md`](sim/cell-device-characterization/README.md),
[`signoff/README.md`](signoff/README.md). CI for these checks is tracked in
issue #14 and is not present yet.

## Repo layout

| Dir | Holds |
|---|---|
| `spec/` | Ratified targets, split-axis plan, decision records |
| `design/` | Schematics (xschem), cell and array design |
| `sim/` | ngspice testbenches + results — append-only evidence |
| `layout/` | Layout, DRC/LVS via klayout-tools |
| `measurements/` | Silicon results, recorded per grid region |
| `signoff/` | `klt signoff` block manifest + graded T1 verdict — the verdict of record |

## Conventions

Follows the fleet's gf180 canary conventions (see the public
`gf180-bandgap` / `gf180-temp-por` repos for the style): verification is the
product, PVT corners on every recorded result, spec changes via decision
record, and tool friction filed upstream at `2AMLogic/klayout-tools`
(generically — no design detail in that public tracker).

Apache-2.0.
