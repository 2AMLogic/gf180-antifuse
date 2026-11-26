# verification/

Digital (RTL) verification. Analog evidence lives in `sim/`; nothing here is
SPICE, and a pass here is a behavioural check of `rtl/`, not timing or
synthesis evidence.

The single attested cold start for the digital partition is
`verification/run_digital_cold_start.sh` (both Verilog benches plus the cocotb
request, through a pinned `uvx` klt); see `signoff/README.md`.

## One-hot decoder bench

Files: [`tb_antifuse_decode.v`](tb_antifuse_decode.v) (exhaustive
self-checking bench), [`run_decode.sh`](run_decode.sh) (runner).

```sh
verification/run_decode.sh          # N = 32, 20, 2, 256
verification/run_decode.sh --lint   # decoder and digital top, verilator + iverilog
```

Every `(en, idx)` pair is checked, including `idx >= N` at N = 20 (not a
power of two). `en = 0` and `idx >= N` must give all zeros; `en = 1`,
`idx < N` must give exactly one hot line, `sel[idx]`. Exit status is nonzero on
any `FAIL`, a missing `RESULT: ALL ... PASSED`, a compile failure or a lint
warning. `RTL=path/to/variant.v` substitutes the decoder (a mutant that drops
`en`, shifts the index by one, or turns `==` into `>=` all exit nonzero).

## SPI register file bench

Files: [`tb_antifuse_spi_regs.v`](tb_antifuse_spi_regs.v) (self-checking
Verilog-2001 bench), [`run_spi_regs.sh`](run_spi_regs.sh) (runner).

**Prerequisites:** Icarus Verilog (`iverilog`, `vvp`); Verilator for lint.
Nothing else.

**Cold start, from the repo root:**

```sh
verification/run_spi_regs.sh          # simulate all configurations
verification/run_spi_regs.sh --lint   # verilator --lint-only -Wall + iverilog -Wall
verification/run_spi_regs.sh --quick  # N=32 configuration only
verification/run_spi_mutations.sh     # mutation evidence (about 2 minutes)
```

Exit status is nonzero if any check fails, a simulation does not report
`RESULT: ALL ... PASSED`, a compile fails, or lint reports anything. Runtime
is about 30 seconds. `RTL=path/to/variant.v` substitutes the DUT source (used for
mutation checks).

### Configurations

| N | READ_SETTLE | ARM_TIMEOUT | Why |
|---|---|---|---|
| 32 | 8 | 4096 | Ratified grid size, default settle. |
| 20 | 200 | 2048 | Second supported N, not a power of two (addresses 20..31 fit in 5 bits but are invalid); long settle so a rejected-write frame fits inside a read. |

### Named tests

Each prints `[PASS]`/`[FAIL]` (or `[SKIP]`, for the read-settle BUSY test when
the settle is too short for a frame to fit, i.e. N = 32 config).

- `reset_values_and_idle_outputs`, `read_write_every_register`,
  `reserved_bits_read_zero`, `ctrl_reserved_bits_rejected`,
  `unknown_address_and_read_only_writes`
- `program_full_sequence`, `pulse_width_min_default_mid_max` (codes 1, default,
  16, 255, 2 measured with SCLK idle), `pulse_width_zero_code_rejected`
- Interlock negative cases, each asserting no `prog_en` cycle throughout:
  `neg_strobe_without_arm`, `neg_arm_and_strobe_in_one_transaction`,
  `neg_strobe_after_arm_timeout`, `neg_stuck_high_strobe`,
  `neg_repeated_strobe_after_completion`,
  `neg_target_or_width_write_while_armed` (row, column, width, out-of-range),
  `neg_arm_timeout_boundary` (commit one cycle inside the window fires, one
  cycle outside does not), `arm_flag_high_exactly_ARM_TIMEOUT_cycles`,
  `disarm_write_and_rearm`, `reset_while_armed_and_while_active`
- Single-bit-fault model (amendment A1; fault model FM1-FM3 and claims in
  `spec/spi-register-implementation-decision.md`):
  `fire_only_via_fire_command_all_cmd_bytes` (all 256 command bytes x 3 data
  bytes x armed/unarmed; only `0xF8` while armed pulses),
  `ctrl_write_cannot_fire_any_value` (all 256 `CTRL` values while armed),
  `single_bit_flip_of_any_register_frame_never_fires` (12 command bytes x 6
  data bytes x 16 bit positions x armed/unarmed),
  `fire_frame_single_bit_flip_fail_safe` (command-bit flip: no pulse, error,
  arm dropped; data-bit flip: still the intended `FIRE`),
  `transaction_boundary_faults_never_fire` (CS_N glitch at every bit position,
  merged frames from a missed CS_N rise, missing or extra SCLK edge at every
  position)
- `busy_writes_rejected_during_program_pulse`,
  `busy_writes_rejected_during_read_settle`
- Read path: `read_strobe_rdata_and_settle` (sense 0 and 1, `READ_VALID`,
  settle length, self-clearing strobe), `neg_read_strobe_while_armed`
- `address_range_boundaries_no_aliasing` (N-1 accepted; N, 2^k-1, N+1,
  0x80|5, 0xFF rejected; the following pulse lands on the last valid cell)
- `spi_truncated_and_overlong_frames`, `spi_cs_isolation_and_miso_timing`,
  `spi_minimum_sclk_period_8_clk`
- `global_monitors`: always-on checks that `prog_en`, `read_en` and `PROG_ARM`
  are mutually exclusive as specified, `row_sel`/`col_sel` are stable during
  every pulse, and MISO never changes while SCLK is high.

### Mutation check

`verification/run_spi_mutations.sh` applies each of nine single-line
mutations to a temporary copy of `rtl/antifuse_spi_regs.v`, runs the N = 32
bench on it, and requires the bench to fail; the unmutated RTL must pass.
Mutants: arm guard removed (the line tagged `// ARM-GUARD`); the pre-A1
`CTRL` strobe code restored; `FIRE` decoded with a don't-care address bit
(`0x79`, `0x7A`); a `ROW` or `PULSE_WIDTH` write of `0x03` while armed fires
(the pre-A1 residual); `FIRE` accepted as a read command; overlong or
truncated frames accepted. The runner exits nonzero if any mutant survives or
fails to apply. The recorded run is in the pull request. The mutations show
the named tests detect these removals; they do not prove no other fault
exists outside the stated fault model.

## Port-only cocotb suite (`klt functional-verification`)

Files in [`cocotb/`](cocotb): `test_spi_regs.py` (the suite),
`request_spi_regs.json` (Icarus, `rtl/antifuse_spi_regs.v`, N = 32,
READ_SETTLE = 8, `ARM_TIMEOUT` elaborated to 300 so the timeout tests are
short; the constants at the top of the test module must match the request's
`parameters`), `mutation_proposals.json` (eight byte-exact mutants, grouped
by rejection case), `report_spi_regs.json` (committed `--mutations` report:
baseline plus per-mutant verdicts; its `log_path`/`results_xml` fields point
at the scratch output directory of the recorded run).

The suite touches only top-level ports, so the same module can later be
pointed at a netlist view (not done here; see `rtl/README.md`). It is
additive: the Verilog bench above stays as the RTL-internal evidence.

It covers every register in `spec/architecture.md` section 5 including reset
values and out-of-range `ROW`/`COL`, the arm-then-`FIRE` sequence, the
rejection cases (`FIRE` unarmed, `FIRE` while busy, wrong frame length), the
arm timeout and its boundary (a FIRE accepted at the window edge, rejected one
cycle later), the `PULSE_WIDTH` and `READ_SETTLE` cycle counts, and a
per-cycle check that `prog_en` and `read_en` are never high together.

**Cold start, from the repo root.** The host `klt` may lack cocotb; use a
throwaway environment pinned to the same `klt` revision:

```sh
KLT='uvx --from klayout-tools[functional-verification]@git+https://github.com/2AMLogic/klayout-tools.git@6bb7cf2336776b9f768fab21c678ee8a2c54e709 klt'
$KLT functional-verification verification/cocotb/request_spi_regs.json --format json
$KLT functional-verification verification/cocotb/request_spi_regs.json \
     --mutations verification/cocotb/mutation_proposals.json --format json
grep -n 'dut\.' verification/cocotb/test_spi_regs.py   # port names only
```

Mutants killed (recorded run, 21/21 tests pass, score 1.0): `FIRE` unarmed
(`arm_guard_removed`, `fire_on_read_command`, `fire_address_partial_decode_0x79`,
`fire_address_partial_decode_0x7A`), `FIRE` while busy
(`busy_write_guard_removed`), bad frame length (`overlong_frame_accepted`,
`truncated_frame_accepted`, `frame_bad_never_errors`). The `READ_SETTLE = 8`
configuration cannot fit a rejected-write frame inside a read, so the
write-rejected-while-reading case stays with the Verilog bench's N = 20
configuration.

### Gate-level run of the routed netlist (issue #445)

`test_antifuse_digital_top.py` is the same port-only discipline pointed at
the **routed netlist** `rtl/pnr/antifuse_digital_top_routed.v` (N = 32,
`ARM_TIMEOUT` 4096, `READ_SETTLE` 8 baked in), with the
`gf180mcu_fd_sc_mcu7t5v0` behavioural cell models resolved from the PDK by
the request's `pdk` block — zero-delay `FUNCTIONAL` branch, no SDF. It
reuses the port-applicable `test_spi_regs.py` coverage at the netlist's own
constants and adds decoder coverage through the `row_onehot`/`col_onehot`
ports: a per-cycle one-hot monitor active in every test, a sweep of all 32
row and 32 column indices, and an idle-one-hot test. Recorded result:
21/21 pass. The runner, report, input hashes, the SDF-annotated leg (which
fails functionally today — klayout-tools#6991) and the pinned klt build are
documented in `rtl/README.md`, "Gate-level functional verification"
(`rtl/run_gate_sim.sh`).
