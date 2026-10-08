# rtl/

Synthesizable digital sources (Verilog-2001).

| File | What it is |
|---|---|
| [`antifuse_spi_regs.v`](antifuse_spi_regs.v) | SPI slave, register file and program/read sequencer for the register map in `spec/architecture.md` §5. Design-stage choices: [`spec/spi-register-implementation-decision.md`](../spec/spi-register-implementation-decision.md). |

Not captured here: a synthesized gate-level netlist (tracked as a follow-up),
and anything on the analog side of the abstract outputs below.

## `antifuse_spi_regs`

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `N` | 32 | Grid size, supported 2..256. Address outputs are `clog2(N)` bits. |
| `ARM_TIMEOUT` | 4096 | `PROG_ARM` lifetime in `clk` cycles (>= 1). |
| `READ_SETTLE` | 8 | `read_en` duration in `clk` cycles (3..255). |

Unsupported values stop simulation at elaboration (`translate_off` block).

### Ports

| Port | Dir | Description |
|---|---|---|
| `clk` | in | Free-running sequencer clock. All state is in this single domain. |
| `rst_n` | in | Active low. Asserts asynchronously (outputs idle immediately), releases synchronously after 2 `clk` edges. |
| `sclk`, `mosi`, `cs_n` | in | SPI mode 0, MSB first. Asynchronous to `clk`; double-flop synchronized. |
| `miso` | out | 0 whenever `miso_oe` is 0. |
| `miso_oe` | out | High while `cs_n` is (synchronized) low; tri-state the pad with it. |
| `row_sel[clog2(N)-1:0]`, `col_sel[...]` | out | Target cell. Always a valid index (< N); reset 0. Frozen while `busy`. |
| `prog_en` | out | Program pulse, high for exactly `PULSE_WIDTH` `clk` cycles. Never high with `read_en`. |
| `read_en` | out | Read leg enable, high for exactly `READ_SETTLE` cycles. Never high while `PROG_ARM` is set or `prog_en` is high. |
| `sense_in` | in | Sensed cell state, 1 = programmed. Asynchronous; double-flop synchronized and sampled on the last `read_en` cycle. |
| `busy` | out | `STATUS.BUSY`: pulse or read in progress. |

### Clock and reset contract

- `clk` must be free-running and must not be gated while the block is in use;
  pulse length, read settle and arm timeout are `clk` cycle counts and
  continue when SCLK stops. Physical widths are `cycles x T_clk`.
- `f_clk >= 8 x f_SCLK` (SCLK half period >= 4 `clk` cycles).
- `rst_n` may be asserted at any time without synchronization; hold it low
  for at least one `clk` edge. Reset truncates a pulse in flight (it is not
  resumed) and restores every register to its reset value, including
  `PULSE_WIDTH = 0x01`.
- No SPI traffic for 2 `clk` cycles after `rst_n` rises.

### SPI timing contract

- A transaction is one `cs_n`-low frame of exactly 16 SCLK rising edges:
  command byte `{RW, ADDR[6:0]}` then data byte. It commits when `cs_n`
  rises. Frames of 1..15 or > 16 edges set `PROTOCOL_ERROR` and have no other
  effect; a frame with no edges is ignored.
- `cs_n` must fall >= 4 `clk` cycles before the first SCLK rising edge, rise
  >= 4 `clk` cycles after the last SCLK rising edge, and stay high >= 4 `clk`
  cycles between frames. SCLK is low when `cs_n` is high. MOSI changes on the
  falling edge and is stable around the rising edge (>= 1 `clk` each side).
- MISO is launched on the SCLK falling edge (the first data bit at the
  falling edge after the 8th rising edge) and is stable at the rising edge;
  it is 0 during the command byte and released with `cs_n` high.
- Arming window: the strobe frame must *commit* within `ARM_TIMEOUT` cycles of
  the arm commit, so one frame at the host's SCLK must fit comfortably (about
  `16 x T_SCLK`). Raise `ARM_TIMEOUT` for SCLK slower than ~`clk`/200.
- Register behaviour, `CTRL` decode, error conditions, `BUSY` writes and flag
  lifetimes are specified in the decision record linked above.

### Analog-side handshake

The block drives abstract enables only and expects no completion handshake:
`prog_en` for `PULSE_WIDTH` cycles, `read_en` for `READ_SETTLE` cycles, then a
single `sense_in` sample. The analog sense path must settle within
`READ_SETTLE - 2` `clk` cycles of `read_en` rising (two cycles go to the
`sense_in` synchronizer).

### Lint

```sh
verification/run_spi_regs.sh --lint
# = verilator --lint-only -Wall rtl/antifuse_spi_regs.v
#   iverilog -g2005 -Wall -o /dev/null rtl/antifuse_spi_regs.v
```

Both are clean (no warnings).
