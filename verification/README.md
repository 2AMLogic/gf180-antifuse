# verification/

Digital (RTL) verification. Analog evidence lives in `sim/`; nothing here is
SPICE, and a pass here is a behavioural check of `rtl/`, not timing or
synthesis evidence.

## SPI register file bench

Files: [`tb_antifuse_spi_regs.v`](tb_antifuse_spi_regs.v) (self-checking
Verilog-2001 bench), [`run_spi_regs.sh`](run_spi_regs.sh) (runner).

**Prerequisites:** Icarus Verilog (`iverilog`, `vvp`); Verilator for lint.
Nothing else.

**Cold start, from the repo root:**

```sh
verification/run_spi_regs.sh          # simulate all configurations
verification/run_spi_regs.sh --lint   # verilator --lint-only -Wall + iverilog -Wall
```

Exit status is nonzero if any check fails, a simulation does not report
`RESULT: ALL ... PASSED`, a compile fails, or lint reports anything. Runtime
is a few seconds. `RTL=path/to/variant.v` substitutes the DUT source (used for
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

The interlock guard is the line tagged `// ARM-GUARD` in
`rtl/antifuse_spi_regs.v` (`3'b011: if (arm) do_fire = 1'b1; else err = ...`).
Replacing it with an unconditional `do_fire = 1'b1` makes
`neg_strobe_without_arm` (and the other interlock cases) fail and the runner
exit nonzero; restoring it passes. The recorded run is in the pull request.
