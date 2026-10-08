# Decision Record: SPI Register File and Sequencer Implementation Choices

**Status**: Ratified for this characterization die (design-stage choices
within the interface already ratified in `spec/architecture.md` §5; none of
them edits that section)
**Date**: 2026-10-08
**Scope**: The behaviour `spec/architecture.md` §5 explicitly leaves to the
design stage — out-of-range `ADDR_ROW`/`ADDR_COL` writes, the meaning and
reset value of the `PULSE_WIDTH` code, and the arm-timeout constant — plus the
smaller choices a synthesizable implementation cannot avoid (clocking,
transaction commit, flag clearing, writes during `BUSY`). The implementation
is `rtl/antifuse_spi_regs.v`; its port and timing contract is
`rtl/README.md`. Nothing here changes a register, bit position, reset value
or sequence that §5 already fixes, and nothing here touches
`spec/split-axis-plan.md` (N = 32 stays the working target; N is a parameter).

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
  CS_N is high are ignored. A single frame carrying both `PROG_ARM` and
  `PROG_STROBE` therefore cannot satisfy the separate-transaction interlock
  (see the `CTRL` rules below).
- **MISO.** Launched on the SCLK falling edge, sampled by the host on the
  rising edge (mode 0); first data bit is launched at the falling edge after
  the 8th rising edge; MISO is 0 during the command byte; `miso_oe` follows
  CS_N and `miso` is 0 with CS_N high. Read data is captured at the 8th
  rising edge; reads have no side effect except the `STATUS` rule below.
- **`CTRL` write decode** (reserved bits `[7:3]` nonzero is rejected whole):
  `0x00` disarms (no error); `0x01` arms, restarts the timeout and clears
  `PROG_DONE`; `0x03` fires **only if `PROG_ARM` was already set by an earlier
  committed transaction** — otherwise it is rejected, so arm-and-strobe in one
  transaction never fires and never arms; `0x04` starts a read only when not
  armed; `0x02`, `0x05`, `0x06`, `0x07` are rejected. Requiring `0x03`
  (not `0x02`) to fire means two bits must be correct in addition to the
  stored arm state. `CTRL` reads back `{5'b0, read-in-flight, PROG_STROBE,
  PROG_ARM}`; `PROG_STROBE` and `PROG_ARM` stay set for the pulse and clear on
  its completion, as §5 requires.
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

## Rationale

The rules share one principle: any ambiguity resolves to "no pulse". Arming
is only ever a consequence of a complete, valid, single-purpose frame; the
fire frame must be separate, correct in two bits, and inside a bounded window;
everything else — truncation, stuck lines, out-of-range or zero parameters,
changes mid-arm — either does nothing or tears the arm down. Freezing the
target and width during an operation means the pulse that is emitted is
exactly the one that was armed, which matters because programming
characterization attributes every outcome to a (row, column, width) tuple.
Counting in a free-running clock keeps pulse length independent of how the
host clocks SCLK, so width is a controlled split axis rather than a bus
artifact.

## Consequences and limits

- Verified by `verification/` (named negative case per interlock rule, two
  values of N); that bench is a digital behavioural check, not synthesis,
  timing or analog evidence.
- Absolute pulse width, read settle time and arm timeout in seconds depend on
  the `clk` frequency chosen at integration; the analog-side settling and the
  `VPP` path are not modelled here.
- `READ_SETTLE` is a placeholder constant until the sense path is designed;
  it must be revisited against the sense-path settling time.

## References

- `spec/architecture.md` §5 (register map, program and read sequences) and
  §1.2 (`READ_EN` disabled for the armed plus pulse duration).
- `spec/split-axis-plan.md` (N = 32 working target; program pulse width as a
  split axis).
- `rtl/antifuse_spi_regs.v`, `rtl/README.md`, `verification/README.md`.
