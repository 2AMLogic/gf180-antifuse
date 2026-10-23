# rtl/

Synthesizable digital sources (Verilog-2001).

| File | What it is |
|---|---|
| [`antifuse_spi_regs.v`](antifuse_spi_regs.v) | SPI slave, register file and program/read sequencer for the register map in `spec/architecture.md` §5. Design-stage choices: [`spec/spi-register-implementation-decision.md`](../spec/spi-register-implementation-decision.md). |
| [`antifuse_decode.v`](antifuse_decode.v) | Binary index to one-hot select decoder with enable (see [`antifuse_decode`](#antifuse_decode)). |
| [`antifuse_digital_top.v`](antifuse_digital_top.v) | Digital-partition top: `antifuse_spi_regs` plus one `antifuse_decode` per axis (see [`antifuse_digital_top`](#antifuse_digital_top)). |
| [`synth/`](synth/) | Synthesized gate-level netlists and `klt synthesize` reports for `antifuse_spi_regs` and `antifuse_digital_top` (see [Synthesis](#synthesis)). |

Not captured here: anything on the analog side of the abstract outputs below,
and a gate-level simulation of the synthesized netlist (see Synthesis).

## `antifuse_decode`

Global row/column decoder of `spec/architecture.md` §1.1: `sel[i] = en & (idx == i)`.
Purely combinational.

| Name | Dir | Description |
|---|---|---|
| `N` (parameter, default 32) | | Number of select lines, supported 2..256; unsupported values stop simulation at elaboration (`translate_off` block). |
| `idx[clog2(N)-1:0]` | in | Binary index. |
| `en` | in | Low forces every line to 0. |
| `sel[N-1:0]` | out | One-hot select. For `idx >= N` (non-power-of-two `N`) all zeros. |

"Exactly one line hot" holds only for `en = 1` and `idx < N`; every other
input gives all zeros.

## `antifuse_digital_top`

Instantiates `antifuse_spi_regs` and two `antifuse_decode` (row, column).
Parameters `N`, `ARM_TIMEOUT`, `READ_SETTLE` pass through. Ports are those of
`antifuse_spi_regs` (unchanged, including the binary `row_sel`/`col_sel`) plus
`row_onehot[N-1:0]` and `col_onehot[N-1:0]`.

Decoder enable: `prog_en | read_en`. No row or column line is selected while
idle; during a program pulse or a read leg the addressed row and column lines
are hot. `prog_en` and `read_en` are already mutually exclusive and
`read_en` is held off for the whole armed state (§1.2), so the enable adds no
new interlock path. This choice is the design's, not the spec's: §1.2 fixes
the legs' interlock and §1.3 requires every other pass-gate OFF during an
operation, and the enable is the narrowest term that satisfies both. The
level shifters and pass gates driven by these lines are the analog partition
and are not captured here.

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

### Host contract: program sequence (amendment A1)

The program strobe is the `FIRE` command, not a `CTRL` bit. A host programs a
cell with separate CS_N-low frames, in this order:

1. write `ADDR_ROW` (`{0x80, row}`), `ADDR_COL` (`{0x81, col}`), and optionally
   `PULSE_WIDTH` (`{0x83, code}`, code 1..255);
2. arm: write `CTRL = 0x01` (`{0x82, 0x01}`);
3. fire: write the `FIRE` command (`{0xF8, 0x00}`) within `ARM_TIMEOUT` `clk`
   cycles of step 2's commit. The data byte is ignored; send `0x00`;
4. poll `STATUS` (`{0x04, x}`) until `BUSY` clears and `PROG_DONE` is set.

`CTRL` writes of `0x02`/`0x03` (the pre-A1 strobe bit) are rejected. `FIRE`
while not armed, while `BUSY`, or in a frame of other than 16 edges is
rejected and sets `PROTOCOL_ERROR`. Fault model, claims and evidence:
[`spec/spi-register-implementation-decision.md`](../spec/spi-register-implementation-decision.md)
§ "Amendment A1".

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
- Arming window: the `FIRE` frame must *commit* within `ARM_TIMEOUT` cycles of
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

```sh
verification/run_decode.sh --lint
# = verilator --lint-only -Wall / iverilog -g2005 -Wall on antifuse_decode.v,
#   and on antifuse_digital_top.v with antifuse_spi_regs.v and antifuse_decode.v
```

Clean as well.

### Synthesis

```sh
uvx --from "klayout-tools==0.6.0" klt synthesize rtl/synth/antifuse_spi_regs.synth.json \
    --pdk gf180mcuD --format json > rtl/synth/antifuse_spi_regs.synth.report.json
# the mapped netlist lands in rtl/synth/.klt/synthesize/<run_id>/antifuse_spi_regs_synth.v
# (scratch, gitignored); rtl/synth/antifuse_spi_regs_synth.v is a copy of it.
# Check a checkout without re-synthesizing (exit 0 = unchanged, 3 = drifted):
uvx --from "klayout-tools==0.6.0" klt synthesize rtl/synth/antifuse_spi_regs.synth.json \
    --pdk gf180mcuD --check rtl/synth/antifuse_spi_regs.synth.report.json --rerun
```

Request: Yosys, `gf180mcu_fd_sc_mcu7t5v0`, default parameters (N = 32,
`ARM_TIMEOUT` 4096, `READ_SETTLE` 8). The request names no corner, so the tool
picks the library's nominal one (`tt_025C_1v80`); that affects the ABC delay
estimate, not the cell mapping evidence below. The `--check --rerun` pass above
re-ran the flow and matched the committed report. Result (klayout-tools 0.6.0,
Yosys 0.67, PDK gf180mcuD):

| Quantity | Value |
|---|---|
| Instances | 423 (96 flip-flops: 92 `dffrnq_1`, 4 `dffsnq_1`) |
| Area | 13820.98 um^2 (sequential 7182.69 um^2) |
| Latches | 0 (`structural.latches`; the netlist also has no latch cells) |
| Combinational loops / multi-driven nets | 0 / 0 (`structural`, from the tool) |
| ABC critical-path estimate | 11269 ps, wire-free, pre-layout; not signoff timing |

The full cell breakdown is `instance_counts_by_type` in the report. The one
Yosys warning is the `translate_off` elaboration guard in the RTL.

### Synthesis: `antifuse_digital_top`

```sh
uvx --from "klayout-tools==0.6.0" klt synthesize rtl/synth/antifuse_digital_top.synth.json \
    --pdk gf180mcuD --format json > rtl/synth/antifuse_digital_top.synth.report.json
# rtl/synth/antifuse_digital_top_synth.v is a copy of the mapped netlist, as above.
uvx --from "klayout-tools==0.6.0" klt synthesize rtl/synth/antifuse_digital_top.synth.json \
    --pdk gf180mcuD --check rtl/synth/antifuse_digital_top.synth.report.json --rerun
```

Same flow and library as above, default parameters (N = 32), top
`antifuse_digital_top`. The `--check --rerun` pass matched the committed
report (exit 0). Result (klayout-tools 0.6.0, Yosys 0.67, PDK gf180mcuD):

| Quantity | Value |
|---|---|
| Instances | 532 (96 flip-flops, unchanged from `antifuse_spi_regs`: the decoders are combinational) |
| Area | 15893.25 um^2 (sequential 7182.69 um^2) |
| Latches | 0 (`structural.latches`) |
| Combinational loops / multi-driven nets | 0 / 0 (`structural`, from the tool) |
| ABC critical-path estimate | 13621 ps, wire-free, pre-layout; not signoff timing |

The one Yosys warning is the `translate_off` elaboration guard in the RTL.
Decoder function is checked at RTL by `verification/run_decode.sh`; there is no
gate-level simulation of this netlist (same limits as below). This report is
not cited in `signoff/manifest.json`: `klt signoff` does not read synthesize
responses (klayout-tools#4015).

Not done (for either netlist):

- **Gate-level simulation.** `verification/run_spi_regs.sh` cannot take the
  netlist as `RTL=`: the bench reads RTL-internal signals (`dut.arm`,
  `dut.commit_ev`, `dut.read_valid`) the netlist does not have, the netlist is
  fixed at N = 32 so the N = 20 configuration cannot apply, and the
  installed iverilog rejects the PDK cell models (`ifnone with an edge-sensitive
  path is not supported`). The RTL bench is unchanged and covers the RTL only.
- **Equivalence.** `klt synthesize --verify-equivalence` is combinational-only
  and this block is sequential.
- **Timing, place and route.** Nothing beyond the ABC estimate above.
