# gf180-antifuse

An N×N antifuse array on GlobalFoundries gf180mcu — MUX'd row/column
addressing, SPI program/read — designed and verified by AI agents. A
write-once memory as a **device-physics characterization vehicle**: the grid
deliberately varies antifuse cell design and programming conditions across
regions, so a single die measures the design space (programming yield, read
margin, retention) rather than proving one operating point.

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

## Repo layout

| Dir | Holds |
|---|---|
| `spec/` | Ratified targets, split-axis plan, decision records |
| `design/` | Schematics (xschem), cell and array design |
| `sim/` | ngspice testbenches + results — append-only evidence |
| `layout/` | Layout, DRC/LVS via klayout-tools |
| `measurements/` | Silicon results, recorded per grid region |

## Conventions

Follows the fleet's gf180 canary conventions (see the public
`gf180-bandgap` / `gf180-temp-por` repos for the style): verification is the
product, PVT corners on every recorded result, spec changes via decision
record, and tool friction filed upstream at `2AMLogic/klayout-tools`
(generically — no design detail in that public tracker).

Apache-2.0.
