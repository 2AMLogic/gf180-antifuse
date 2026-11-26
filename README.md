# gf180-antifuse

An N×N antifuse array on GlobalFoundries gf180mcu — MUX'd row/column
addressing, SPI program/read — designed and verified by AI agents. A
write-once memory as a **device-physics characterization vehicle**: the grid
deliberately varies antifuse cell design and programming conditions across
regions, so a single die measures the design space (programming yield, read
margin, retention) rather than proving one operating point.

![fleet burndown](https://raw.githubusercontent.com/2AMLogic/2am/main/fleet-metrics/charts/gf180-antifuse.svg)

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

The analog design includes the three antifuse cell candidates, the 32 × 32
array and its row/column selectors, and the program and read legs.
The [addressed array layout](layout/array_32x32/README.md) connects all 1,024
cells across three regions of 352, 352 and 320 cells. Native GF180D LVS
matches all 2,944 devices, 1,611 nets and 75 external pins. The released
KLT 0.9.2 LVS deck reports 86 extra body nets, and DRC findings remain.
The [design inventory](design/README.md) describes how the circuits connect.
Each region records its own layout checks. [Region I](layout/array_region_i/README.md),
[Region II](layout/array_region_ii/README.md), [Region III](layout/array_region_iii/README.md).

The SPI slave, register file and program/read sequencer have self-checking
Icarus tests in `verification/`. A dedicated `FIRE` command strobes programming
(amendment A1 of `spec/architecture.md` §5). The digital top has both a
[synthesized netlist](rtl/synth/antifuse_digital_top_synth.v) and a
[routed netlist](rtl/pnr/antifuse_digital_top_routed.v).

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

Run these commands from the repo root. The design checks below ran on a
shared worker on 2026-10-09, the simulation driver checks on 2026-11-23,
and the signoff regrade on 2026-11-26.

**Tools and PDK.** `xschem` 3.4.7, `ngspice` 46, `python3` (stdlib only for
`sim/`), and the gf180mcu PDK (`gf180mcuD`, `open_pdks` commit
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, the revision recorded in
[`spec/cell-candidates.md`](spec/cell-candidates.md)). Point `PDK_ROOT` at a
root containing `gf180mcuD/` (scripts fall back to `~/.ciel`; install with `pip install ciel==2.6.1`, then `ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; a tree whose `SOURCES` differs from the pin is refused). The
`signoff/` grade needs a specific `klt` build, below.

| Dir | Command | Outcome |
|---|---|---|
| `design/` | `design/regen-netlists.sh --check` | ran OK: all three netlists reproduce exactly. (Without `--check` it rewrites `design/netlists/`.) |
| `design/` | `design/check-netlists.sh` | ran OK: reproducibility, ngspice elaboration, capacitor-geometry sweep all pass. |
| `design/` | `design/run_analog_cold_start.sh` | ran OK on a worker with no working `xschem` (failing stub first on `PATH`): prints `ANALOG COLD START PASSED`, ~1 s wall-clock. Runs `check-netlists.sh --skip-regen`: ngspice elaboration, capacitor-geometry sweep, region-map drift, slice smoke and leg interlock truth table at the typical corner. It skips the reproducibility step, including the generator checks. Elaboration and mechanism only: no corners, no device evidence. |
| `sim/` | `--help` on each of the eight Cold start commands in [`sim/README.md`](sim/README.md) | ran OK (2026-11-23): every driver printed its usage directly, including the worked-example flags (`--check-env`, `--probe`, `--mc`, `--resume`). |
| `sim/` | the eight Cold start campaigns themselves | **not run here**: every experiment submits its PVT grid as `klt sim` requests instead of looping ngspice locally — to the klt batch fleet when `KLT_SIM_BACKEND=batch` is exported as on the dispatch workers (four drivers also pin `"backend": "batch"` in their requests; the other four default to `local` if `KLT_SIM_BACKEND` is unset — see [`sim/README.md`](sim/README.md); fleet job id in `environment.remote` of each report), and the shared worker does not run the grid itself. Existing results are in each experiment's `records/` (append-only; a re-run mints a new record). |
| `signoff/` | `./signoff/verify.sh` | Passed on 2026-11-26 with the pinned `klayout-tools==0.8.0`. The fresh grade matched the committed report byte for byte, with 11 of 22 T1 items met. |

Methodology, record format and how to read results:
[`design/README.md`](design/README.md), [`sim/README.md`](sim/README.md),
[`sim/cell-device-characterization/README.md`](sim/cell-device-characterization/README.md),
[`signoff/README.md`](signoff/README.md). The [CI workflow](.github/workflows/ci.yml) runs
netlist, layout and signoff checks on pull requests and pushes to `main`.

## Repo layout

| Dir | Holds |
|---|---|
| `spec/` | Ratified targets, split-axis plan, decision records |
| `design/` | Schematics (xschem), cell and array design |
| `rtl/` | Digital sources (SPI register file and sequencer) |
| `verification/` | RTL benches (Icarus), one-command runner |
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

Apache License 2.0 — see [LICENSE](LICENSE).
