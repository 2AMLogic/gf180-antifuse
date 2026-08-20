# gf180-antifuse — agent instructions

Private canary block: an N×N antifuse array on GlobalFoundries gf180mcu with
MUX'd row/column addressing and an SPI slave for program and read — a
write-once (one-time-programmable) memory test vehicle. The array is a
**device-physics characterization grid first and a memory second**: cell
design, programming conditions, and geometry are deliberately varied across
grid regions so one die maps the antifuse design space instead of proving a
single point.

- **PDK**: gf180mcu (open PDK). Open-source flow: xschem + ngspice for
  design/sim, klayout-tools (`klt`) for layout work. The PDK's dual gate
  oxide (3.3 V and 5/6 V devices) is load-bearing here: thin-oxide MOS
  capacitors are the antifuse candidates, thick-oxide devices build the
  program path that must survive the programming voltage.
- **PRIVATE, and that is a standing operator decision.** Do not propose,
  prepare, or perform a visibility flip; do not mirror content anywhere
  public (issues and PRs in this repo are private surfaces; anything outside
  this repo is not). Visibility changes are operator-only, as everywhere in
  the fleet — treat that rule as load-bearing here, not boilerplate.
- **Scope firewall (hard rule).** This repo discusses antifuse device
  physics, array/addressing design, programming and sensing circuits, and
  measured yield/margin/retention — nothing else. Do not write about
  applications or use cases for a write-once memory, do not speculate about
  why 2AM wants one, and do not reference any other 2AM repo except the
  public gf180 canaries (for circuit/flow conventions) and
  `2AMLogic/klayout-tools` (for tool issues). If a task appears to need
  application context to proceed, stop and leave it for the operator — that
  need is itself the signal the task doesn't belong here.
- **The grid is the experiment.** Every cell-level design choice (capacitor
  W/L, oxide flavor, series-device sizing, program pulse voltage/width) is a
  split axis candidate. The spec must say which axes vary across which grid
  regions and why, and `measurements/` records results per region — an
  aggregate number that averages across splits is a bug, not a result.
- **Programming is an analog event, not a digital write.** Oxide breakdown
  is stochastic: claims about programming need yield-vs-condition curves
  (success fraction across Monte Carlo / corners), not a single transient
  that happened to pop. Read-margin claims need the sense path's worst-case
  corner, programmed and unprogrammed resistance distributions both.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue
  at `2AMLogic/klayout-tools` describing the tool gap generically — that
  tracker is public, so keep ALL design detail and this repo's name out of
  the issue body; describe the gap, not the design.
- **Verification is the product**: no claim without a testbench. PVT corners
  on every recorded result; `sim/` results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
