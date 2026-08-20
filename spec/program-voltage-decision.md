# Decision Record: On-Die vs. Off-Die Program Voltage

**Status**: Ratified — **Provisional** for this characterization die (see
"Finality" below; not a permanent architectural conclusion)
**Date**: 2026-08-20
**Scope**: Sub-issue D of the decomposition of #1 — the program-voltage
generation and switching decision only. Builds on the ratified
`spec/cell-candidates.md` (cell candidates and their programming-voltage
regimes) and `spec/architecture.md` (row/column MUX, program current
limiting, sneak-path and sense scheme), both of which explicitly deferred
this question to this record.

## Question

For the program voltage (`VPP`) used to break down a cell's antifuse
capacitor: what is generated and/or switched **on-die**, and what is
supplied **off-die** (from bench equipment), for both (a) generating `VPP`
and (b) switching/routing `VPP` to the addressed cell?

## Answer

- **Generation: off-die.** `VPP` is supplied to the die from bench
  equipment through a dedicated program-voltage pad/pin. Nothing on this
  die generates or regulates the programming voltage itself (no on-die
  charge pump, voltage multiplier, or HV regulator).
- **Switching: on-die.** Routing `VPP` to the addressed cell — the
  row/column MUX's local high-voltage pass-gate stage, its level shifters,
  and the program current-limiting path — is on-die, using the thick-oxide
  device families (`nfet_06v0`/`pfet_06v0`, `nfet_10v0_asym`/`pfet_10v0_asym`)
  already ratified in `spec/architecture.md` §1–§2. This was not an open
  question this record had to resolve; it restates the existing ratified
  architecture so the on-die/off-die split is stated for switching as well
  as generation, per this issue's acceptance criteria.
- **Finality: PROVISIONAL for this characterization die, not a final
  architectural conclusion.** This is a first-pass default justified by the
  test vehicle's characterization goal and by facts not yet known (below),
  not a claim that on-die generation is permanently ruled out. It must be
  re-opened once the split-axis measurement campaign this die exists to run
  produces the data this record currently lacks (see "Reconsideration
  triggers" below).

## Evidence and Rationale

### 1. The programming voltage is not one number — it spans an unresolved, multi-regime range

Per `spec/cell-candidates.md` (ratified 2026-08-20, merged as commit
`28c5aaa`), the three ratified cell candidates target two materially
different programming-voltage regimes, and **neither regime has a
resolved numeric value**:

- Candidates 1 and 3 (`cap_nmos_03v3` / `cap_pmos_03v3`, 3.3 V thin oxide,
  `toxe = 8 nm`): "expected to be several times the 3.3 V rated voltage,
  consistent with published gate-oxide-breakdown antifuse literature...
  the actual number for this process is an empirical question for the
  split-axis / measurement plan, not something this survey invents."
- Candidate 2 (`cap_nmos_06v0`, 6.0 V thick oxide, `toxe ≈ 15.2 nm`, ~2x
  Candidate 1's oxide thickness): "expected to require a higher absolute
  programming voltage than Candidate 1's thin-oxide cell... not a fixed
  multiple asserted here."
- The same record states directly that "actual gate-oxide breakdown
  voltages for the 3.3 V and 6.0 V oxide flavors are not present in the
  SPICE model files... and were not found in a reliability/characterization
  document in the locally checked-out PDK tree" — it is explicitly left as
  a measurement/split-axis deliverable, not a design input available today.

**Consequence for this decision**: an on-die generator (charge pump or HV
regulator) has to be designed to a target output voltage. With the target
itself unresolved — and spanning at least two materially different regimes
across the grid's own candidates, by the ratified spec's own account — there
is no single voltage to design a generator around yet. Off-die (bench)
supply lets the actual program voltage be swept as a controlled experimental
variable per grid region and per split-axis point, which is what the
measurement campaign these candidates were selected for needs (CLAUDE.md:
"the grid is the experiment," "programming is an analog event... claims
about programming need yield-vs-condition curves"). A fixed-output on-die
generator would instead impose one voltage (or a small number of trimmed
steps) on every region regardless of which candidate or split-axis point
occupies it — cutting against the split-axis plan's premise before the
plan has established which voltage each region actually needs.

*(Date-stamped: this citation reflects `spec/cell-candidates.md` as ratified
2026-08-20, commit `28c5aaa`. If sub-issue A's spec is later revised — e.g.
an actual breakdown-voltage number is established — re-check this record's
"Reconsideration triggers" section below.)*

### 2. The ratified MUX/path architecture already puts on-die switching in place, and is voltage-source-agnostic

Per `spec/architecture.md` (ratified 2026-08-20, merged as commit
`ed0dacb`):

- The PROGRAM leg is: "bit-line → program current-limiting element (§2) →
  program-voltage rail (`VPP`, assumed bench-supplied per the repo README;
  the on-die-vs-off-die switching/generation question is sub-issue D's
  scope, not this record's)."
- The per-region local high-voltage pass-gate stage (§1.1) and its level
  shifters are already specified in terms of the ratified cell candidates'
  device families (`nfet_06v0`-class for Candidate 1/3 regions,
  `nfet_10v0_asym`-class for Candidate 2 regions) — this switching path is
  on-die regardless of where `VPP` itself originates, because it has to
  exist either way to route programming current to the addressed cell and
  keep every unselected row/column OFF (§1.1–§1.3, sneak-path requirements
  in §3).
- The SPI logic domain is explicitly isolated from `VPP` by the level
  shifters ("the SPI domain never sees the programming voltage directly"),
  and `PULSE_WIDTH` (§5) is stated to control program pulse *width* only —
  "Program pulse *voltage* is set by whatever supplies `VPP` (bench or
  on-die per sub-issue D), not by this register." This confirms the ratified
  architecture was deliberately written to be agnostic to this record's
  answer: switching, current limiting, and the SPI register map do not
  change depending on where `VPP` is generated. That agnosticism is exactly
  why this decision could be deferred to sub-issue D without destabilizing
  sub-issue C's ratified architecture, and why it can be revisited later
  (see "Finality," below) without a re-architecture of §1–§5.

The on-die pass-gate/level-shifter/ballast-resistor path in
`spec/architecture.md` §1–§2 already uses thick-oxide devices — the same
`nfet_06v0`/`pfet_06v0`/`nfet_10v0_asym`/`pfet_10v0_asym` families
`spec/cell-candidates.md` selected specifically because gf180mcu's
dual-gate-oxide device set gives a device rated well above each candidate's
expected programming-voltage regime without itself becoming a second,
unintended fuse (CLAUDE.md: "thick-oxide devices build the program path
that must survive the programming voltage"). That switching-path
architecture is unaffected by this record's generation answer; a future
on-die generator, if one is added, would feed into the same `VPP` rail this
switching path already expects.

### 3. Off-die generation avoids committing die area and a design effort to an unresolved target on a characterization vehicle

An on-die charge pump or HV regulator sized for oxide breakdown is a
non-trivial design effort in its own right (multi-stage charge pump,
output regulation/ripple control, its own reliability margin against the
same breakdown physics being characterized) that gf180mcu's dual-gate-oxide
device set supports but does not eliminate the design cost of. Committing
that effort now, before the breakdown-voltage measurement this die exists
to produce is available, risks building a generator sized for the wrong
regime (per point 1: at least two regimes, magnitude unresolved for both).
Bench supply avoids that risk on this iteration and keeps the deliverable
narrowly scoped to what `spec/architecture.md` already needs: a switching
and current-limiting path that accepts an external `VPP`.

## Reconsideration triggers

This decision is provisional and should be re-opened, not silently
preserved, once any of the following occurs:

- **A measured (or reliably simulated, once a custom breakdown model
  exists per `spec/cell-candidates.md`'s flagged gap) breakdown voltage is
  established** for a specific candidate/region, narrowing "several times
  3.3 V" and "materially higher than Candidate 1" to actual numbers.
- **The split-axis measurement campaign converges on a small number of
  production-relevant program-voltage set points** (rather than a
  continuously swept research variable) for a given candidate — at which
  point a fixed or few-step on-die generator becomes a design question
  worth costing out against continued bench dependency.
- **A future test-vehicle iteration is scoped as something other than a
  first-pass characterization die** (e.g. a follow-on intended to validate
  a self-contained program path) — CLAUDE.md's scope firewall means this
  record does not speculate about what such an iteration would be for, only
  notes that the on-die-generation question would need to be revisited
  under different constraints than "the target voltage is not yet known."

## References

- `spec/cell-candidates.md` — programming-voltage regime citations (§
  "Candidates," ratified 2026-08-20, commit `28c5aaa`).
- `spec/architecture.md` — row/column MUX, program current limiting, and
  SPI register map that this record's switching answer restates and that
  its generation answer must interface with (ratified 2026-08-20, commit
  `ed0dacb`).
- `README.md` — prior placeholder assumption ("Program voltage supplied
  externally for the test vehicle") that this record now formally ratifies
  as provisional, rather than an unratified placeholder.
- CLAUDE.md — dual-gate-oxide device set (thin-oxide capacitor, thick-oxide
  program path) and the "grid is the experiment" / "programming is an
  analog event" framing this record's rationale depends on.

## Decision

Ratify: `VPP` generation is **off-die** (bench-supplied through a dedicated
program-voltage pad), and `VPP` switching/routing to the addressed cell is
**on-die** (the row/column MUX, level shifters, and program current-limiting
path already ratified in `spec/architecture.md` §1–§2). This is a
**provisional** decision for this characterization die, justified by the
unresolved, multi-regime programming-voltage target in
`spec/cell-candidates.md` and the characterization goal of sweeping `VPP`
as an experimental variable rather than fixing it to one on-die-generated
value — not a permanent ruling-out of on-die generation. Re-open per the
"Reconsideration triggers" above once the measurement campaign this die
exists to run produces the data this record currently lacks.
