# Routed antifuse digital characterization

The N=32 SPI register and row/column decoder macro passed all 21 port-level cases at each of 15 PVT corners at the 50 ns implementation clock. Area, Fmax and power are reported measurements or estimates with no ratified product limits. Power uses engine-default switching activity with routed SPEF parasitics.

The core occupies 44,211.3 µm² inside a 54,333.3 µm² die. SPEF annotation covered 550/550 design nets. Seven floating clock loads have no sinks. Four first-stage asynchronous endpoints are unconstrained: u_regs/_730_/D, u_regs/_733_/D, u_regs/_736_/D, u_regs/_738_/D. Setup and hold each had zero violations on constrained paths. The committed STA uses the ideal clock model.

## Performance at the routed corners

| Liberty corner | Fmax (MHz) | Power (mW) | Setup slack (ns) | Hold slack (ns) | Tests at 50 ns |
|---|---:|---:|---:|---:|---:|
| ff_125C_1v98 | 82.0731 | 0.2978 | 37.8157 | 1.36851 | 21/21 |
| ff_125C_3v60 | 161.857 | 1.0246 | 43.8217 | 0.66834 | 21/21 |
| ff_125C_5v50 | 224.404 | 2.449 | 45.5437 | 0.45354 | 21/21 |
| ff_n40C_1v98 | 112.053 | 0.281 | 41.0756 | 1.04071 | 21/21 |
| ff_n40C_3v60 | 238.672 | 0.9833 | 45.8101 | 0.47106 | 21/21 |
| ff_n40C_5v50 | 322.864 | 2.3723 | 46.9027 | 0.33632 | 21/21 |
| ss_125C_1v62 | 20.2593 | 0.1873 | 0.64007 | 5.48594 | 21/21 |
| ss_125C_3v00 | 65.8104 | 0.6979 | 34.8048 | 1.74553 | 21/21 |
| ss_125C_4v50 | 105.913 | 1.6147 | 40.5583 | 1.04755 | 21/21 |
| ss_n40C_1v62 | 21.8317 | 0.1844 | 4.19503 | 5.08157 | 21/21 |
| ss_n40C_3v00 | 96.3055 | 0.6724 | 39.6164 | 1.23149 | 21/21 |
| ss_n40C_4v50 | 156.7 | 1.5692 | 43.6184 | 0.72611 | 21/21 |
| tt_025C_1v80 | 50.5836 | 0.2327 | 30.2307 | 2.25785 | 21/21 |
| tt_025C_3v30 | 134.329 | 0.8249 | 42.5556 | 0.84676 | 21/21 |
| tt_025C_5v00 | 199.495 | 1.9542 | 44.9874 | 0.5498 | 21/21 |

## Functional requirements

The following named checks passed in the committed zero-delay and nominal SDF reports and in every 50 ns corner run. Their scope is the implemented digital port behavior in [architecture §5](../../spec/architecture.md#5-spi-slave-register-map) and its [implementation decision](../../spec/spi-register-implementation-decision.md).

| Requirement | Port-level tests |
|---|---|
| Reset and idle outputs | `reset_values_and_idle_outputs` |
| SPI mode 0, MISO isolation and complete-frame writes | `miso_enable_follows_cs`, `bad_frame_length_sets_protocol_error`, `truncated_and_overlong_writes_do_not_commit`, `overlong_fire_frame_never_pulses` |
| ADDR_ROW, ADDR_COL and PULSE_WIDTH register access | `row_col_pw_read_write`, `out_of_range_row_col_rejected` |
| CTRL, STATUS, read-only and unknown register behavior | `ctrl_arm_disarm_and_reserved`, `read_only_and_unknown_addresses`, `status_read_clears_protocol_error` |
| Arm and FIRE interlock, timeout and busy exclusion | `program_full_sequence`, `arm_timeout_expires`, `arm_timeout_boundary`, `fire_unarmed_rejected`, `fire_with_other_command_bytes_never_pulses`, `fire_while_busy_rejected`, `read_while_armed_rejected` |
| Program pulse width, read settling and RDATA | `pulse_width_cycle_counts`, `read_settle_cycle_count_and_data` |
| One-hot row/column selects over all 32 indices | `onehot_idle_while_sel_changes`, `decoder_onehot_all_indices` |

## Timing coverage and controls

Each PVT run used seed 1 and its own normalized SDF, including interconnect. Icarus applied partial typical-entry annotation and omitted 1,070 conditional IOPATH expressions, 144 IFNONE edge modifier paths and 95 timing checks. Functional results cover the represented arcs. At 25 ns with identical delay files, SS/+125 °C/1.62 V passed 3/21 and FF/−40 °C/5.50 V passed 21/21. Each passed 21/21 at 50 ns. The 25 ns trial is a timing sensitivity control.

The [campaign](sdf-campaign.json) records every named test outcome, SDF digest, simulation source and route-source digest. [Implementation](../pnr/antifuse_digital_top.pnr.report.json), [STA](../sta/antifuse_digital_top.sta.report.json), [zero-delay](../../verification/cocotb/report_digital_top.json) and [nominal SDF](../../verification/cocotb/report_digital_top_sdf.json) are the original KLT reports.

## Evidence inputs

| Input | SHA-256 |
|---|---|
| `rtl/characterization/sdf-campaign.json` | `651f1aaf774b370ba3ef527312f67279f43753c36d773cb3038a3c3df46976b0` |
| `rtl/pnr/antifuse_digital_top.def` | `19e277921100398ed87f45b37e2d5ba0c583225a55d3e0ff6b4a7c2a17632484` |
| `rtl/pnr/antifuse_digital_top.gds` | `dae02f43855fda9b7c8f880fa62be529f3479af070dc34a82cbab4b140373bf5` |
| `rtl/pnr/antifuse_digital_top.pnr.json` | `57b6ea67b4b28d2d6fe61c57b9bb5a1e49c63d02a56e03354a3f97badb2b2db8` |
| `rtl/pnr/antifuse_digital_top.pnr.report.json` | `3ecb11f062da5d1545c76898b57bf33fa9abee06824b2b375c52cd9e6d0dfa18` |
| `rtl/pnr/antifuse_digital_top_routed.v` | `71195344e88fdeebc7dcee9db0940950360f953056a85a29b958796fdb6aa651` |
| `rtl/sta/antifuse_digital_top.sdf.json` | `12daf396781ca972b66a93bff7becaea98be4e7be1be0387beaedb6be00295df` |
| `rtl/sta/antifuse_digital_top.spef` | `a59e2060cb56275f4079b8cc6a6b9da8822e0ccbe8b8043fc193da79f657bde7` |
| `rtl/sta/antifuse_digital_top.sta.json` | `05a6b3ef412a5efc597df1e502c921491e34a69ace30983ad3dd65b7edc402c4` |
| `rtl/sta/antifuse_digital_top.sta.report.json` | `9b53d36ec5c69bbb022ed3bfa1ebb9a6a57e0840b0a221d9d35e5feee625d6a2` |
| `spec/architecture.md` | `d9f3ca783bf3cefa888b639a218e9ebc2f06fa7f08cbb2a04e65aa90a27bb160` |
| `spec/spi-register-implementation-decision.md` | `da52c7e02bfb9bee56a57a9c6f6c36c45ec37f1650cddb1124dbc7fd61f3623a` |
| `verification/cocotb/report_digital_top.json` | `8d2488d31aaa6ea58aa943009e0abd2b273fffc9c1cd5073c49ec28044df80c6` |
| `verification/cocotb/report_digital_top_sdf.json` | `fcb51d4dce710bd6029c84d6ad6e19cb92250b145f7b2fd860eafd4ae40f2803` |
| `verification/cocotb/request_digital_top_sdf.json` | `61eec4690dd6220728f528e3b145a600a4ec487b5bb7273c2de7cce5ef97f682` |
| `verification/cocotb/test_antifuse_digital_top.py` | `31dc84490bb9a4036aaddab6bca94f37f7f2e8a51b902fea245a5bdebc1b70d5` |

## Reproduction

From the repository root:

```sh
python3 rtl/characterization/report.py
./signoff/verify.sh
```

The second command uses klayout-tools 0.8.0. The full timing replay uses the toolchain described in [the routed RTL instructions](../README.md#post-route-simulation-with-sdf-timing), including KLT commit `6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe`, OpenROAD, Icarus 13.0, cocotb 2.0.1 and GF180D open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. Run it in a checkout where the generated STA directory may be updated.

```sh
python3 rtl/characterization/replay_sdf.py --klt "$SDF_KLT" --pdk-root "$PDK_ROOT" --output /tmp/antifuse-sdf-campaign.json
cmp rtl/characterization/sdf-campaign.json /tmp/antifuse-sdf-campaign.json
```
