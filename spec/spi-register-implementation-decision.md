# Decision Record: SPI Register File and Sequencer Implementation Choices

**Status**: Ratified for this characterization die. Design-stage choices within
the interface ratified in `spec/architecture.md` §5, plus **Amendment A1**
(2026-10-17, below), the one place this record edits §5, under the operator
ruling of 2026-10-17 (attended fleet-decide discussion 17, Q3 option 1).
**Date**: 2026-10-08 (A1: 2026-10-17)
**Scope**: The behaviour `spec/architecture.md` §5 explicitly leaves to the
design stage — out-of-range `ADDR_ROW`/`ADDR_COL` writes, the meaning and
reset value of the `PULSE_WIDTH` code, and the arm-timeout constant — plus the
smaller choices a synthesizable implementation cannot avoid (clocking,
transaction commit, flag clearing, writes during `BUSY`). The implementation
is `rtl/antifuse_spi_regs.v`; its port and timing contract is
`rtl/README.md`. Nothing here changes a register, bit position, reset value
or sequence that §5 already fixes **except as amended by A1**, and nothing
here touches `spec/split-axis-plan.md` (N = 32 stays the working target; N is
a parameter).

## Question

How does the SPI slave and program/read sequencer behave where §5 is silent,
such that (a) a single glitched bit or malformed frame can never produce a
program pulse, (b) no write can address a cell other than the one the host
named, and (c) program-pulse width remains a host-settable split axis?

## Answer

### The three choices §5 asked for

1. **Out-of-range `ADDR_ROW` / `ADDR_COL` write: reject and flag.** The
   complete data byte is compared against N (`byte < N`) *before* any
   low-order bits are selected. An out-of-range write leaves the register
   unchanged (so `row_sel`/`col_sel` always hold a valid cell), sets
   `PROTOCOL_ERROR`, and — like every protocol error — clears `PROG_ARM`.
   With N = 32, values 32 and 255 do not alias to 0 or 31. For N that is not
   a power of two (e.g. 20) values from N up to `2^ceil(log2 N) - 1` are also
   rejected, even though they fit in the address width.
2. **`PULSE_WIDTH` code is a direct count of sequencer-clock cycles.**
   `prog_en` is high for exactly `code` cycles of `clk`; the physical width
   is `code x T_clk`. Range 1..255. **Code `0x00` is illegal**: a write of
   `0x00` is rejected (register unchanged, `PROTOCOL_ERROR` set), because a
   zero-length "pulse" would raise `BUSY`/`PROG_DONE` without stressing the
   cell and would corrupt a yield-vs-pulse-width record. **Reset value
   `0x01`** (the shortest pulse): a die that comes out of reset and is armed
   without a deliberate `PULSE_WIDTH` write applies the least stress rather
   than the most. A direct count rather than a table index keeps the register
   a free split-axis knob; the width grid is then set by the `clk` period,
   which is a bench decision.
3. **Arm timeout: `ARM_TIMEOUT = 4096` `clk` cycles** (module parameter).
   `PROG_ARM` is high for exactly that many cycles from the arm commit and
   then auto-clears *without* setting `PROTOCOL_ERROR` (expiry is the
   specified safe outcome, not a fault); a strobe committing in the last
   armed cycle fires, one cycle later does not. Rationale: the strobe is a
   16-bit frame whose commit point is its *end*, so the window must cover one
   full frame at the slowest SCLK the host uses. 4096 cycles is 16 frame
   times at the fastest permitted SCLK (`clk`/8 -> ~128 cycles per frame) and
   one frame at SCLK = `clk`/200; it is short enough that a forgotten arm
   expires within microseconds-to-milliseconds at realistic `clk`, and long
   enough that no host needs to hurry. Hosts running SCLK slower than about
   `clk`/200 must raise the parameter.

### Choices the implementation had to add

- **Clocking.** One free-running sequencer clock `clk`. SCLK, MOSI and CS_N
  are asynchronous inputs, double-flop synchronized and oversampled; there is
  no SCLK-clocked logic. Pulse width, read settle and arm timeout are
  therefore counted in `clk` cycles and continue when SCLK stops.
  Requirement: `f_clk >= 8 x f_SCLK`. `rst_n` is active-low, asserts
  asynchronously (outputs go idle immediately) and releases synchronously
  inside the module. `sense_in` is double-flop synchronized.
- **Transaction and commit point.** A transaction is exactly one CS_N-low
  frame of 16 SCLK rising edges (command byte + data byte). Nothing takes
  effect until CS_N rises: the commit point. A frame with 1..15 or more than
  16 rising edges sets `PROTOCOL_ERROR`, changes no register, and cannot arm
  or fire. A frame with zero edges is ignored without error. SCLK edges while
  CS_N is high are ignored. A fire needs its own `FIRE` frame after an
  arm has committed, so no single frame can both arm and fire (see the `CTRL`
  and `FIRE` rules below).
- **MISO.** Launched on the SCLK falling edge, sampled by the host on the
  rising edge (mode 0); first data bit is launched at the falling edge after
  the 8th rising edge; MISO is 0 during the command byte; `miso_oe` follows
  CS_N and `miso` is 0 with CS_N high. Read data is captured at the 8th
  rising edge; reads have no side effect except the `STATUS` rule below.
- **`CTRL` write decode** (after A1; reserved bits `[7:3]` nonzero is
  rejected whole): `0x00` disarms (no error); `0x01` arms and clears
  `PROG_DONE` **only when not already armed** (a re-arm while armed is
  rejected and drops the arm, so the timeout cannot be refreshed — the host
  disarms or lets it expire, then arms again); `0x04` starts a read only when
  not armed; every other value, `0x02` and `0x03` (any value with the
  `PROG_STROBE` bit) included, is rejected. **No `CTRL` write can fire.**
  `CTRL` reads back `{5'b0, read-in-flight, PROG_STROBE, PROG_ARM}`;
  `PROG_STROBE` is a read-only status bit that is set for the pulse, and
  `PROG_STROBE` and `PROG_ARM` clear on its completion, as §5 requires.
- **`FIRE` command** (A1, write-only command address `0x78`, command byte
  `0xF8`): commits a program pulse **only if `PROG_ARM` was already set by an
  earlier committed transaction**; otherwise it is rejected (`PROTOCOL_ERROR`,
  no pulse), so arm-and-fire in one transaction never fires and never arms.
  The data byte is ignored (hosts send `0x00`). A read of `0x78` is an
  unknown-address read. While `BUSY` a `FIRE` is rejected like every write.

- **Protocol errors** (all set `PROTOCOL_ERROR` and drop an idle `PROG_ARM`):
  malformed frame; out-of-range address; zero pulse code; reserved `CTRL`
  bits or a rejected `CTRL` code; write to a read-only register (`STATUS`,
  `RDATA`); read or write of an unknown address (reads return `0x00`); and
  any `ADDR_ROW`/`ADDR_COL`/`PULSE_WIDTH` write while armed (§5 item 6 —
  a *valid* such write takes effect, the arm is cleared).
- **Writes while `BUSY`** (program pulse or read settle): every write is
  rejected, sets `PROTOCOL_ERROR`, and does not disturb the operation in
  flight. Target and pulse settings are therefore frozen for the whole
  operation. Reads, including `STATUS`, are always allowed.
- **Flag lifetime.** `PROG_DONE` sets at pulse completion and clears when the
  next arm is accepted (or reset). `READ_VALID` sets when the read completes
  and clears when the next read starts (or reset). `PROTOCOL_ERROR` is sticky
  and clears on a completed `STATUS` read or reset. `RDATA` holds the last
  completed read.
- **Read.** `READ_STROBE` raises `read_en` for `READ_SETTLE = 8` `clk` cycles
  (parameter, 3..255; the lower bound covers the `sense_in` synchronizer),
  samples the synchronized `sense_in` on the last settle cycle into
  `RDATA[0]`, sets `READ_VALID`, clears `BUSY`. No completion handshake from
  the analog side is assumed; the settle time is a fixed cycle count that the
  sense-path design must meet. `read_en` and `prog_en` are never both high,
  and `read_en` is never high while `PROG_ARM` is set.
- **Reset.** Resets everything: `PROG_ARM`, any pulse in flight (truncated,
  not resumed), registers to their §5 reset values, `PULSE_WIDTH` to `0x01`.
- **Supported N.** 2..256. Address outputs are `ceil(log2 N)` bits wide
  (5 for N = 32). The byte-wide register reserves the upper bits, so the
  register map does not change with N.

## Amendment A1 — FIRE command (2026-10-17)

**Why.** Before A1 the strobe was `CTRL` data `0x03` (command byte `0x82`).
The fire frame `{0x82, 0x03}` was one command-bit flip from a `ROW` write
(`{0x80, 0x03}`) or a `PULSE_WIDTH` write (`{0x83, 0x03}`) of value `0x03`.
Both are legitimate host frames in the register map; a host that intended one
and had its command bit corrupted while armed fired. The earlier revision of
this record documented that as a known residual and escalated it. The
operator ruling of 2026-10-17 (discussion 17, Q3 option 1) permits a narrow
protocol amendment that removes the path while keeping the single-bit
no-programming guarantee. This record makes that amendment.

**What changes in `spec/architecture.md` §5** (edited in place, marked A1):

| | Before | After A1 |
|---|---|---|
| `CTRL` bit1 `PROG_STROBE` | writable strobe | read-only status, set for the pulse; a `CTRL` write with bit1 set is rejected |
| Program strobe | `CTRL` write `0x03` while armed | `FIRE` command at address `0x78` (command byte `0xF8`) while armed |
| Program sequence step 3 | write `CTRL` with `PROG_STROBE=1` | write the `FIRE` command |

Everything else in §5 is unchanged: addresses `0x00`–`0x05`, their bits and
reset values, the separate-transaction enable-then-fire interlock, the
arm timeout, the write-while-armed rule (item 6), `PULSE_WIDTH` semantics,
the read sequence, and `PROTOCOL_ERROR` behaviour. The array, target/pulse
safeguards, analog boundaries and grid/split-axis requirements are untouched.
`signoff/manifest.json` is untouched.

**Encoding choice and why.** `FIRE` needs a command byte at Hamming distance
as large as the 7-bit address space allows from every defined-register command
byte, so that a bit flip cannot turn a defined-register frame into a `FIRE`.
The defined command bytes are `0x00`–`0x05` (reads) and `0x80`–`0x85`
(writes). Exhausting the 122 free addresses gives a best minimum distance of 5
(`0x7E`, `0x7F`) and 4 for the next class. `0x7F` (`0xFF`) is rejected as a
choice because a stuck-high MOSI line then forms the fire command; `0x7E` is
one bit from it. **`0x78` (`0xF8`) is chosen: minimum distance 4 from every
defined-register command byte** (to `ROW` write `0x80`), 5 from all-zeros and
3 from all-ones. No key sequence or data pattern is required: the data byte is
free for every defined register, so a data key adds no separation against an
intended register frame.

### Fault model

The claim below is made for exactly these faults and no others.

- **FM1 — single-bit corruption.** One MOSI bit of one 16-bit frame is
  inverted: any of the 16 positions, command byte or data byte.
- **FM2 — one fault per host sequence.** At most one fault between resets, so
  every other frame in the sequence is as the host sent it. Armed, unarmed
  and `BUSY` states are all covered; the intended frame is any defined
  register read or write with any data.
- **FM3 — one boundary fault.** A missing or extra SCLK rising edge inside a
  frame, a spurious CS_N rise inside a frame, or a missed CS_N rise between two
  frames. All of these yield a frame with other than 16 edges (a split frame
  has `k` and `16-k` edges, a merged pair 32), which commits nothing, sets
  `PROTOCOL_ERROR` and drops an idle arm.

### Claims

- **C1 (no unintended fire).** A program pulse requires a committed frame
  whose command byte is `0xF8` while `PROG_ARM` is set. Every defined-register
  frame is at distance >= 4 from `0xF8` in the command byte alone, whatever
  the data. So under FM1/FM2, a host sequence that contains no `FIRE` frame
  cannot produce a pulse. Under FM3, no frame with other than 16 edges
  commits, so a boundary fault cannot assemble a `FIRE` from the bits of
  neighbouring frames.
- **C2 (`FIRE` fails safe).** A single command-bit flip of an intended `FIRE`
  frame is an unknown-address write: no pulse, `PROTOCOL_ERROR`, arm dropped.
  A single data-bit flip of an intended `FIRE` is still the host's `FIRE` (the
  data byte is ignored); that is the pulse the host asked for.
- **C3 (unarmed `FIRE` is inert).** A `FIRE` while not armed is rejected.
  Together with the arm rules: a stray arm made by a flipped frame still needs
  a separately sent `FIRE` frame, which by C1 a single fault cannot create.

**Not claimed.** Faults of two or more bits in a sequence; multi-bit bursts;
noise on SCLK/CS_N that is not one of the FM3 forms; a host that itself sends
a `FIRE` frame it did not mean to (a wrong target or width is a host error,
not a link fault, and the existing arm/target-freeze rules apply); any
protection against corruption of the analog side. Command-byte distance 4 also
defeats up to three command-bit flips of a defined-register frame, but no
guarantee is asserted beyond FM1–FM3. Additional noise/burst/sequence models
may be evaluated separately.

### Evidence

`verification/` carries, for the model above: `fire_only_via_fire_command_all_cmd_bytes`
(all 256 command bytes x three data bytes x armed/unarmed: only `0xF8` while
armed pulses), `ctrl_write_cannot_fire_any_value` (all 256 `CTRL` values
while armed), `single_bit_flip_of_any_register_frame_never_fires` (12
command bytes x 6 data bytes x 16 bit positions x armed/unarmed),
`fire_frame_single_bit_flip_fail_safe`, and
`transaction_boundary_faults_never_fire` (CS_N glitch at every position,
merged frames, missing/extra SCLK edge at every position). Mutation evidence
(`verification/run_spi_mutations.sh`) shows the bench fails when each
protection is removed: the arm guard, the `CTRL` strobe code restored, a
partial `FIRE` address decode, a `ROW`/`PULSE_WIDTH` write of `0x03` that
fires (the pre-A1 residual), `FIRE` on a read command, and acceptance of
overlong or truncated frames. These are digital behavioural checks of the RTL,
not synthesis, timing or analog evidence, and not a merge, signoff or
physical-programming approval.

## Rationale

The rules share one principle: any ambiguity resolves to "no pulse". Arming
is only ever a consequence of a complete, valid, single-purpose frame; the
fire frame must be separate, a dedicated command no single bit flip of a
defined-register frame can form (A1), and inside a bounded window;
everything else — truncation, stuck lines, out-of-range or zero parameters,
changes mid-arm — either does nothing or tears the arm down. Freezing the
target and width during an operation means the pulse that is emitted is
exactly the one that was armed, which matters because programming
characterization attributes every outcome to a (row, column, width) tuple.
Counting in a free-running clock keeps pulse length independent of how the
host clocks SCLK, so width is a controlled split axis rather than a bus
artifact.

## Consequences and limits

- Verified by `verification/` (named negative case per interlock rule, the
  A1 fault-model tests, two values of N, and the mutation suite); that bench is a digital behavioural check, not synthesis,
  timing or analog evidence.
- Absolute pulse width, read settle time and arm timeout in seconds depend on
  the `clk` frequency chosen at integration; the analog-side settling and the
  `VPP` path are not modelled here.
- `READ_SETTLE` is a placeholder constant until the sense path is designed;
  it must be revisited against the sense-path settling time.

## References

- `spec/architecture.md` §5 (register map, program and read sequences, as
  amended by A1) and
  §1.2 (`READ_EN` disabled for the armed plus pulse duration).
- `spec/split-axis-plan.md` (N = 32 working target; program pulse width as a
  split axis).
- `rtl/antifuse_spi_regs.v`, `rtl/README.md`, `verification/README.md`.
