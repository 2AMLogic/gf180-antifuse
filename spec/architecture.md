# Decision Record: Program/Read Architecture

**Status**: Ratified (parametric in N)
**Date**: 2026-08-20
**Scope**: Sub-issue C of the decomposition of #1 — program/read architecture
only: row/column MUX (program + sense path), program current limiting,
sneak-path analysis, sense scheme, and SPI register map. Builds on the
ratified `spec/cell-candidates.md`. Does **not** decide grid size N (sub-issue
B, `spec/split-axis-plan.md` — not yet ratified as of this record) or the
on-die-vs-off-die program-supply question (sub-issue D — depends on this
record and is intentionally left open here).

## Context

`spec/cell-candidates.md` ratified three cell candidates, each pairing a
MOS-capacitor antifuse element with a series access/isolation device rated
for that candidate's programming-voltage regime:

| Candidate | Capacitor (oxide) | Access device | Programming voltage regime |
|---|---|---|---|
| 1 (baseline) | `cap_nmos_03v3` (3.3 V thin) | `nfet_06v0` (6.0 V thick) | Thin-oxide, expected single-digit-volt class |
| 2 (HV) | `cap_nmos_06v0` (6.0 V thick) | `nfet_10v0_asym` (10 V LDNMOS) | Thick-oxide, expected materially higher than Candidate 1 |
| 3 (polarity) | `cap_pmos_03v3` (3.3 V thin) | `pfet_06v0` (6.0 V thick) | Same regime as Candidate 1, PMOS polarity |

Because the grid instantiates multiple candidates across different regions
(CLAUDE.md: "the grid is the experiment"), the array-level addressing must
carry programming current and sense current for **whichever candidate is
present in a given region**, without forcing every region through the
highest-voltage candidate's device ratings. That constraint drives the
two-tier MUX split in this record.

**N is not yet ratified.** Sub-issue B's issue body states a working range
of "16 to 64, narrowed once sub-issue C's addressing scheme is ratified" and
was still `loom:building` (unmerged) at the time this record was written.
Per this issue's own guidance, everything below that depends on N —
address field width, decoder fan-in, MUX fan-out — is stated as a function
of N (`ceil(log2(N))`, `N-1`, etc.) rather than a fixed number. The SPI
register map's address fields are sized generously enough (a full byte per
axis) to cover the entire stated candidate range without a register-map
change once N is ratified; see "SPI slave register map" below.

**Post-breakdown resistance has no stock SPICE model** (per
`spec/cell-candidates.md`'s flagged finding). The sense scheme below is
therefore specified in terms of the *electrical distinction it relies on*
(DC-blocking capacitor vs. a low-resistance filament) rather than a
simulated resistance number, and the worst-case corner it targets is stated
as an assumption to verify once a custom breakdown model or measured
silicon data exists — consistent with this issue's acceptance criteria.

## 1. Row/column MUX — program and sense path

### 1.1 Two-tier structure: global decode + local high-voltage pass-gates

A single MUX structure must carry both the program current path (up to the
programming voltage of whichever candidate occupies the addressed cell) and
the sense (read) path (a low-voltage, low-current measurement path). Using
one MUX device family sized for the worst-case candidate across the whole
array would force every region — including Candidate 1/3 regions — through
oversized, higher-leakage pass devices for no benefit to those regions.
Instead:

- **Global row/column decode** (logic-voltage domain): a conventional
  binary decoder, built from the `gf180mcu_fd_sc_mcu7t5v0` standard-cell
  library, converts the `ADDR_ROW`/`ADDR_COL` register fields
  (`ceil(log2(N))` bits each) into one-hot row-select and column-select
  lines. This logic runs at the SPI-side digital I/O voltage (assumed
  3.3 V-class, via `gf180mcu_fd_io` pads — see "SPI slave register map"),
  never at the programming voltage.
- **Local high-voltage pass-gate stage**, one per row and one per column,
  physically local to the grid region it serves: the pass-gate device
  family is matched to that region's cell candidate — `nfet_06v0`-class for
  Candidate 1/3 regions, `nfet_10v0_asym`-class for Candidate 2 regions —
  so pass-gate voltage margin tracks the region's actual programming
  voltage instead of the array-wide maximum. Region boundaries and which
  candidate occupies which region are sub-issue B's responsibility
  (`spec/split-axis-plan.md`); this record only requires that the pass-gate
  device selection be a per-region parameter, not a single global constant.
- **Level shifters** between the logic-voltage decode output and each
  local pass-gate's gate drive: a cross-coupled NMOS/PMOS latch level
  shifter built from the same thick-oxide device family as the local
  pass-gate stage (`nfet_06v0`/`pfet_06v0` for the 6 V tier), referenced to
  that region's programming-voltage rail during a program operation and to
  a fixed logic-compatible "fully on" bias during read. This is the
  standard high-voltage row/column driver pattern (core-voltage decode →
  level shifter → HV pass transistor); this record specifies the block and
  its interface, not a transistor-level netlist — that is `design/`'s job.

### 1.2 Shared bit-line, mutually exclusive program/read legs

Each column's bit-line connects to exactly one of two legs at a time,
selected by non-overlapping control signals:

- **PROGRAM leg**: bit-line → program current-limiting element (§2) →
  program-voltage rail (`VPP`, assumed bench-supplied per the repo README;
  the on-die-vs-off-die switching/generation question is sub-issue D's
  scope, not this record's).
- **READ leg**: bit-line → sense amplifier input (§4).

`PROG_EN` and `READ_EN` are generated from the same control-logic block and
are architecturally interlocked so at most one is asserted at a time:
`READ_EN = NOT(PROG_EN OR PROG_ARMED)` — the read leg is disabled not only
during an active program pulse but for the entire armed state (see §5),
so a sense amplifier is never exposed to a program-voltage transient. This
is a stated architectural requirement for `design/`'s implementation, not
merely a timing convention.

### 1.3 Row and column dimensions are symmetric

Both row and column addressing use the same two-tier decode structure
described above. A cell is selected only when both its row and its column
pass-gates are enabled by the decoder; every other row/column pass-gate in
the array is held in its defined OFF state (§3) for the duration of the
operation.

## 2. Program current limiting

Two independent limiting mechanisms, so a control-logic fault in one does
not remove current limiting entirely:

1. **Passive ballast resistor (primary, always-present limit).** A poly
   resistor — `ppolyf_u_2k_6p0` (2 kΩ/sq unsalicided poly, the `_6p0`
   suffix naming a variant intended for use up to the 6.0 V-class rail,
   consistent with the naming convention used elsewhere in this PDK for
   6.0 V-rated device variants — this reading of the suffix is inferred
   from naming convention, not confirmed against a reliability datasheet,
   and should be verified before layout) is placed in series in the
   PROGRAM leg between the column pass-gate and the `VPP` rail (or the row
   pass-gate and ground return, for the return-side leg — the exact
   placement is a `design/`-stage layout decision; this record fixes the
   device family and topology, not the schematic). Sizing target: once the
   capacitor's gate oxide breaks down, the filament is expected to present
   a low, roughly ohmic impedance (this is a property of the breakdown
   event itself, not something the stock capacitor SPICE model
   represents — see `spec/cell-candidates.md`). The ballast resistor is
   sized so that `R_ballast >= (VPP - V_compliance) / I_target_max`, where
   `I_target_max` is the maximum programming compliance current the cell
   is expected to survive without thermal damage to the filament or
   adjacent structures. **`I_target_max` is not fixed by this record** —
   it is a measurement/simulation question this architecture depends on
   (state it as an assumption to verify, per this issue's own convention
   for unverified claims), and the ballast value should be treated as a
   split-axis-adjacent tunable if `measurements/` data shows the initial
   choice is off target.
2. **Active compliance limit via the access device bias (secondary,
   tunable limit).** During a program pulse, the level shifter (§1.1)
   drives the local access-device gate to a *controlled* overdrive rather
   than a hard logic-supply rail, biasing the access device toward
   saturation (current-source-like behavior) instead of deep triode. This
   gives a second, independently adjustable current limit set by gate bias
   rather than a fixed passive value, useful for the split-axis program
   pulse voltage/width exploration (CLAUDE.md: "program pulse voltage/width"
   is itself a split axis) without requiring a different ballast resistor
   per grid region.

Both limits act on the same current path in series, so the lower of the
two dominates; the ballast resistor is the mechanism that must hold even if
the active bias control has a fault, which is why it is called the primary
limit.

## 3. Sneak-path analysis (partially-programmed array)

This design uses a 1T1C-style cell (one access transistor in series with
one capacitor antifuse element per cell), addressed by row and column
pass-gates that are OFF for every unselected row/column. This differs from
a purely passive (diode- or two-terminal-resistive-element) crossbar, where
sneak current flows through neighboring programmed cells regardless of
selection state. Here, sneak-path current requires an unselected access
device to be conducting, which should not happen by design — but "should
not happen by design" is not sufficient given the array is expected to
spend most of its operating life in a partially-programmed state
(characterization, not end-of-life). Two failure modes are addressed
explicitly:

1. **Floating unselected lines.** If an unselected row or column pass-gate
   gate node is left floating (rather than actively driven to a defined
   OFF bias) it can drift on, especially adjacent to a rail carrying the
   programming voltage — capacitive coupling from a neighboring active
   line is enough to partially turn on a floating gate. **Requirement**:
   every row and column decoder output must be actively driven to a
   defined level (on or off) at all times during program and read
   operations; no decoder output may be left in a high-impedance state.
   This is a requirement on the decoder/level-shifter design in §1.1, not
   an assumption made elsewhere.
2. **Aggregate OFF-state leakage on the selected bit-line.** Even with
   every unselected access device correctly held OFF, `N-1` OFF-state
   leakage paths (one per unselected row, or per unselected column,
   depending on which axis the sense node sits on) sum onto the same
   bit-line the sense amplifier reads. As N grows (parametric per
   sub-issue B, expected 16–64) this aggregate leakage grows linearly with
   N and must remain small relative to the minimum expected programmed-cell
   conduction current, or a fully-unprogrammed row/column could be
   misread as weakly programmed. This is the primary reason the sense
   scheme (§4) is specified as a current-threshold comparison against a
   reference set above the *worst-case aggregate leakage floor*, not a
   fixed absolute threshold — see §4.
   - **Required design input** (not resolved here): the per-device OFF-state
     leakage of the access device family at the worst-case sneak-path
     corner (§4), and the maximum instantiated N, together bound
     `I_sneak_max ≈ (N-1) x I_off`. This must be verified against `sim/`
     once device-level leakage data is available, and the sense reference
     current (§4) must be set with margin above it.
3. **Unselected bit-lines during a program pulse.** The array-wide
   requirement in item 1 also covers unselected *columns* during a program
   operation on a different column that shares the same row: those
   columns' pass-gates must be held OFF, so the row pass-gate being
   enabled does not also expose non-addressed cells on that row to
   programming current through their own (correctly OFF) column pass-gate.
   No additional mechanism beyond item 1's "always actively driven"
   requirement is needed for this case, but it is called out because it is
   the sneak-path shape most directly relevant to programming (as opposed
   to read) and is easy to overlook if only the read path is considered.

## 4. Sense scheme

**Electrical basis.** An unprogrammed cell is an intact MOS capacitor:
under the DC bias used for a read operation (well below any
disturb/breakdown threshold — read voltage is a separate, smaller value
than `VPP`), it presents a blocking (high-impedance, ideally
non-conducting) path; a programmed cell presents a filament with a
measurably lower resistance. This is a favorable sense case compared to,
e.g., discriminating two resistive states that are both conductive — the
unprogrammed state's expected DC current is close to zero (bounded only by
leakage, §3), while the programmed state's expected DC current is
substantially higher. The sense scheme is therefore specified as a
**current-threshold comparator**, not a resistance-ratio or voltage-divider
scheme against a fixed mid-rail reference:

- Apply a fixed, sub-disturb read voltage across the selected bit-line
  (row pass-gate and column pass-gate both enabled, PROGRAM leg disabled
  per §1.2's interlock).
- The resulting bit-line current is compared, by a current-sensing sense
  amplifier (current-mirror-based comparator against a reference branch),
  to a reference current `I_ref` set **above** the worst-case aggregate
  sneak leakage floor `I_sneak_max` (§3) and **below** the worst-case
  minimum expected programmed-cell current.
- Output: `RDATA` = 1 if bit-line current > `I_ref` (programmed), 0
  otherwise (unprogrammed or unselected).

**Worst-case corner this scheme targets** (stated as the design target;
not yet backed by `sim/` data — see the flagged gap in
`spec/cell-candidates.md`): the corner that minimizes the margin between
the programmed-cell current and `I_ref` is the combination of (a) the
slow/cold corner for the access device in series with a programmed cell
(higher channel resistance lowers the programmed-cell current more than a
typical/fast corner would), and (b) the fast/hot corner for every
unselected access device's OFF-state leakage (higher subthreshold leakage
raises the sneak-current floor `I_sneak_max` more than a typical/cold
corner would). These are two different corners applied to two different
sets of devices in the same read operation (the one selected access device
vs. the `N-1` unselected ones) — a single "worst-case PVT corner" number
for the whole array is not sufficient; both must be modeled once transistor
models allow it.

**Programmed/unprogrammed resistance distributions**: not available from
stock PDK models (`spec/cell-candidates.md`). `I_ref` cannot be set to a
final numeric value in this record. This record's contribution is the
*scheme* (current-threshold comparison, not voltage-divider) and the two
bounding constraints `I_ref` must satisfy once the distributions exist:
`I_ref > I_sneak_max` (worst case, per §3) and `I_ref < I_prog_min` (worst
case, per this section). Both `I_sneak_max` and `I_prog_min` are
measurement/simulation deliverables for `sim/` and `measurements/`, not
values this architecture record invents.

## 5. SPI slave register map

> **Amendment A1 (2026-10-17, operator ruling, discussion 17 Q3 option 1).**
> The program strobe is no longer a `CTRL` bit write. It is a separate
> write-only `FIRE` command at address `0x78` (command byte `0xF8`), chosen at
> Hamming distance >= 4 from every defined-register command byte so one flipped
> command bit cannot turn a register access into a fire. `CTRL.bit1`
> (`PROG_STROBE`) is read-only status. Everything else in §5 is unchanged.
> Fault model, claims, encoding rationale and evidence:
> [`spi-register-implementation-decision.md`](spi-register-implementation-decision.md)
> § "Amendment A1".

**Physical/protocol layer.** SPI slave, mode 0 (CPOL=0, CPHA=0), MSB-first,
4-wire (`SCLK`, `MOSI`, `MISO`, `CS_N`, active-low chip select). I/O pads
assumed to be `gf180mcu_fd_io` cells at a logic-compatible I/O voltage
(3.3 V-class), electrically isolated from the `VPP` programming rail by the
level shifters in §1.1 — the SPI domain never sees the programming voltage
directly.

**Addressing model.** A byte-addressed register file. Command byte 0 of
every transaction is `{RW, REG_ADDR[6:0]}` (`RW`=1 for a host write, 0 for
a host read), followed by one data byte (register width is one byte for
every register below; `ADDR_ROW`/`ADDR_COL` reserve a full byte each so the
register map does not need to change when N is ratified by sub-issue B —
only the number of *valid* low-order bits changes).

| Addr | Name | Width | R/W | Reset | Description |
|---|---|---|---|---|---|
| `0x00` | `ADDR_ROW` | 8 (low `ceil(log2(N))` bits valid) | R/W | `0x00` | Row address for the next program/read operation. Values `>= N` are out of range; behavior on out-of-range write is a `design/`-stage decision, but must not silently address a valid row (e.g., clamp-and-set `PROTOCOL_ERROR`, or ignore the write). |
| `0x01` | `ADDR_COL` | 8 (low `ceil(log2(N))` bits valid) | R/W | `0x00` | Column address, same out-of-range handling as `ADDR_ROW`. |
| `0x02` | `CTRL` | 8 | R/W | `0x00` | `bit0` = `PROG_ARM`, `bit1` = `PROG_STROBE` (**read-only status after A1**: set while the pulse runs; a write with bit1 set is rejected), `bit2` = `READ_STROBE`, `bits[7:3]` reserved (write 0). |
| `0x03` | `PULSE_WIDTH` | 8 | R/W | implementation-defined | Program pulse width control code (a direct cycle count or an index into a pulse-width table — `design/`-stage choice). Program pulse *width* is a split axis per CLAUDE.md, so it must be host-settable per operation, not a fixed hardware constant. Program pulse *voltage* is set by whatever supplies `VPP` (bench or on-die per sub-issue D), not by this register. |
| `0x04` | `STATUS` | 8 | RO | `0x00` | `bit0` = `BUSY`, `bit1` = `PROG_DONE`, `bit2` = `READ_VALID`, `bit3` = `PROTOCOL_ERROR`, `bits[7:4]` reserved (read 0). |
| `0x05` | `RDATA` | 8 | RO | `0x00` | `bit0` = sensed cell state from the last completed read (1 = programmed, 0 = unprogrammed/unselected), per §4. `bits[7:1]` reserved for a future multi-bit/analog readback extension — not used by this record. |
| `0x78` | `FIRE` | command | WO (A1) | — | Program strobe command. Accepted only while `PROG_ARM=1` (set by an earlier committed transaction); otherwise rejected with `PROTOCOL_ERROR`. Data byte ignored (send `0x00`). Not readable (a read is an unknown-address read). |

**Program sequence (enable-then-strobe interlock).** A single stray bit
flip must not be able to trigger a program pulse — this is the
"accidental programming from a glitched single bit" case this issue's
guidance calls out explicitly:

1. Host writes `ADDR_ROW`, `ADDR_COL`.
2. Host writes `CTRL` with `PROG_ARM=1`, `PROG_STROBE=0` — a dedicated SPI
   transaction that only arms, does not fire.
3. Host writes the `FIRE` command (A1; formerly `CTRL` with `PROG_STROBE=1`)
   in a **separate, subsequent** SPI transaction, within a bounded arm-timeout window. If the timeout
   elapses without a strobe, `PROG_ARM` auto-clears and the sequence must
   restart from step 2 — a `FIRE` with no preceding `PROG_ARM` write, or a
   stuck-high `MOSI` line (every command byte then reads `0xFF`, an
   unknown-address write), cannot fire a pulse (A1 wording; the pre-A1 text
   spoke of a stuck-high `PROG_STROBE` line). The timeout value is a
   `design/`-stage constant, not fixed by this record.
4. On `FIRE` committed while `PROG_ARM` is set (`PROG_STROBE` then reads 1): `BUSY` asserts,
   `READ_EN` is held disabled for the armed+pulse duration (§1.2), the
   program pulse fires for the duration encoded in `PULSE_WIDTH` at the
   `VPP` rail's voltage, through the selected row/column pass-gates (§1)
   and the current-limiting path (§2).
5. On pulse completion: `PROG_ARM` and `PROG_STROBE` both self-clear
   (single-use arm — a second pulse requires repeating steps 2–3),
   `PROG_DONE` sets, `BUSY` clears.
6. Any register write to `ADDR_ROW`/`ADDR_COL`/`PULSE_WIDTH` while
   `PROG_ARM=1` and before `PROG_STROBE` is observed clears `PROG_ARM`
   (changing the target or pulse shape mid-arm must not silently retarget
   an already-armed pulse) and sets `PROTOCOL_ERROR`.

**Read sequence.**

1. Host writes `ADDR_ROW`, `ADDR_COL`.
2. Host writes `CTRL` with `READ_STROBE=1`.
3. `BUSY` asserts for the sense amplifier's settling time (a
   `design/`-stage constant); `RDATA` and `READ_VALID` update on
   completion; `BUSY` clears.
4. Host reads `RDATA`.

`READ_STROBE` self-clears on completion, symmetric with the program
sequence's self-clearing strobes.

## Acceptance criteria cross-check

- Row/column MUX carrying both program and sense paths: §1 (two-tier
  decode + per-region HV pass-gate, shared bit-line with an interlocked
  program/read leg select).
- Program current limiting names a specific element and sizing rationale:
  §2 (`ppolyf_u_2k_6p0` ballast resistor, sizing inequality; access-device
  saturation bias as a second, tunable limit).
- Sneak-path analysis covers the partially-programmed-array case
  explicitly: §3 (floating-line and aggregate-leakage failure modes, both
  addressed as requirements on the decoder and the sense reference).
- Sense scheme states its worst-case corner and resistance-distribution
  assumptions: §4 (two-sided PVT corner statement; `I_ref` bounding
  inequalities left symbolic pending `sim/`/`measurements/` data, per this
  issue's "state it as an assumption to verify" allowance).
- SPI register map is concrete: §5 (byte-addressed register table with
  field/width/R-W, full program and read sequences).
- No application/use-case framing: this record discusses only device
  physics, array addressing, and programming/sensing circuits, consistent
  with CLAUDE.md's scope firewall.

## Open questions carried forward (not resolved here)

- **Grid size N and split-axis region map** (sub-issue B,
  `spec/split-axis-plan.md`): not yet ratified. This record's address
  widths, decoder fan-in, and per-region MUX device selection are all
  parametric in N and in the region map until B lands; re-check this
  record against the ratified split-axis plan once available, in
  particular whether region boundaries are contiguous or interleaved
  (affects whether the local HV pass-gate stage in §1.1 is laid out as
  contiguous blocks or must be duplicated/interleaved across the array).
- **On-die vs. off-die program voltage generation** (sub-issue D): this
  record assumes an externally supplied `VPP` rail (per the repo README)
  and does not decide how `VPP` is generated or gated on-die. Sub-issue D
  depends on this record for the current-limiting and interlock structure
  `VPP` must interface with.
- **Ballast resistor sizing and `I_target_max`**: named a specific device
  family and a sizing inequality (§2) but not a final resistance value —
  that requires either a custom breakdown-augmented SPICE model or
  measured silicon data, neither of which exists yet per
  `spec/cell-candidates.md`.
- **`ppolyf_u_2k_6p0` voltage-rating interpretation**: the `_6p0` suffix is
  read as a 6.0 V-class rating by analogy to this PDK's device-naming
  convention elsewhere (e.g. `cap_nmos_06v0`); this has not been confirmed
  against a reliability datasheet, since none was found in the locally
  checked-out PDK tree during this record's research (same gap noted in
  `spec/cell-candidates.md` for oxide breakdown voltages). Verify before
  this resistor is relied on in a Candidate 2 (higher-voltage) region's
  program path.
- **Level shifter and decoder timing** (arm-timeout constant, pulse
  settling time, read settling time): named as required blocks with
  stated functional requirements, not sized — `design/`-stage work once
  schematics are drafted.

## References

- `spec/cell-candidates.md` — ratified cell candidates this record's
  per-region MUX/access-device pairing is built on, and the source of the
  post-breakdown-model gap this record works around in §4.
- GlobalFoundries gf180mcu open PDK (`open_pdks`, locally checked out at
  `~/.ciel/gf180mcuD`) — `gf180mcu_fd_sc_mcu7t5v0` standard-cell library
  (global decode logic), `gf180mcu_fd_io` (SPI pads), `ppolyf_u_2k_6p0`
  (ballast resistor), all verified present via `klt pdk list` and a
  filesystem scan of `libs.tech/xschem/symbols` and `libs.ref/` on
  2026-08-20; re-verify against the PDK version actually checked out
  before relying on these names, per the same caveat in
  `spec/cell-candidates.md`.
- CLAUDE.md — split-axis framing (program pulse voltage/width as a split
  axis, driving the `PULSE_WIDTH` register requirement in §5) and the
  scope firewall (no application/use-case framing).

## Decision

Ratify the architecture in §1–§5 above: a two-tier (global logic-voltage
decode + per-region high-voltage pass-gate) row/column MUX with an
interlocked program/read leg select, a dual passive-plus-active program
current limit, sneak-path requirements on decoder drive state and sense
reference margin, a current-threshold sense scheme, and the byte-addressed
SPI register map with an enable-then-strobe program interlock. Everything
dependent on N (address widths, MUX fan-out, per-region device selection)
is ratified parametrically and must be re-checked once sub-issue B
(`spec/split-axis-plan.md`) is ratified. Sub-issue D (on-die/off-die `VPP`)
builds on this record's assumption of an externally supplied `VPP` rail and
the interlock structure in §1.2/§5.
