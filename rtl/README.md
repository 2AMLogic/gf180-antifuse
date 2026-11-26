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
uvx --from "klayout-tools==0.8.0" klt synthesize rtl/synth/antifuse_spi_regs.synth.json \
    --pdk gf180mcuD --format json > rtl/synth/antifuse_spi_regs.synth.report.json
# the mapped netlist lands in rtl/synth/.klt/synthesize/<run_id>/antifuse_spi_regs_synth.v
# (scratch, gitignored); rtl/synth/antifuse_spi_regs_synth.v is a copy of it.
# Check a checkout without re-synthesizing (exit 0 = unchanged, 3 = drifted):
uvx --from "klayout-tools==0.8.0" klt synthesize rtl/synth/antifuse_spi_regs.synth.json \
    --pdk gf180mcuD --check rtl/synth/antifuse_spi_regs.synth.report.json --rerun
```

Request: Yosys, `gf180mcu_fd_sc_mcu7t5v0`, default parameters (N = 32,
`ARM_TIMEOUT` 4096, `READ_SETTLE` 8). The request names no corner, so the tool
picks the library's nominal one (`tt_025C_1v80`); that affects the ABC delay
estimate, not the cell mapping evidence below. The `--check --rerun` pass above
re-ran the flow and matched the committed report. Result (reports regenerated with klayout-tools 0.8.0; netlists and figures unchanged from 0.6.0,
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
uvx --from "klayout-tools==0.8.0" klt synthesize rtl/synth/antifuse_digital_top.synth.json \
    --pdk gf180mcuD --format json > rtl/synth/antifuse_digital_top.synth.report.json
# rtl/synth/antifuse_digital_top_synth.v is a copy of the mapped netlist, as above.
uvx --from "klayout-tools==0.8.0" klt synthesize rtl/synth/antifuse_digital_top.synth.json \
    --pdk gf180mcuD --check rtl/synth/antifuse_digital_top.synth.report.json --rerun
```

Same flow and library as above, default parameters (N = 32), top
`antifuse_digital_top`. The `--check --rerun` pass matched the committed
report (exit 0). Result (reports regenerated with klayout-tools 0.8.0; netlists and figures unchanged from 0.6.0, Yosys 0.67, PDK gf180mcuD):

| Quantity | Value |
|---|---|
| Instances | 532 (96 flip-flops, unchanged from `antifuse_spi_regs`: the decoders are combinational) |
| Area | 15893.25 um^2 (sequential 7182.69 um^2) |
| Latches | 0 (`structural.latches`) |
| Combinational loops / multi-driven nets | 0 / 0 (`structural`, from the tool) |
| ABC critical-path estimate | 13621 ps, wire-free, pre-layout; not signoff timing |

The one Yosys warning is the `translate_off` elaboration guard in the RTL.
Decoder function is checked at RTL by `verification/run_decode.sh`; the
routed netlist has the gate-level run below, but these pre-route synthesized
netlists do not. Both `--check --rerun` commands are the freshness checks in
`signoff/inventories/item-1-digital.json`, which backs `1.digital`.

Not done (for either netlist):

- **Gate-level simulation.** The *routed* netlist has one: the port-only
  cocotb suite through `klt functional-verification` ("Gate-level functional
  verification" below). The Verilog benches still cannot take a netlist as
  `RTL=`: they read RTL-internal signals (`dut.arm`, `dut.commit_ev`,
  `dut.read_valid`) the netlist does not have, and the netlist is fixed at
  N = 32 so the N = 20 configuration cannot apply — they stay RTL-only. (The
  earlier note that iverilog "rejects the PDK cell models" was the timing
  branch: iverilog 13.0 logs `sorry: ifnone with an edge-sensitive path is
  not supported` 120 times over the `gf180mcu_fd_sc_mcu7t5v0` timing models
  but exits 0 — the arcs are skipped, the build succeeds. The zero-delay
  `FUNCTIONAL` branch compiles silently.)
- **Equivalence.** `klt synthesize --verify-equivalence` is combinational-only
  and this block is sequential.
- **Timing.** Nothing beyond the ABC estimate above and the unsigned P&R figures under "Place-and-route".

## Place-and-route

`antifuse_digital_top` at the default **N = 32** (the array size captured in
the RTL; a different ratified N means a re-run, not a redesign), routed from
`synth/antifuse_digital_top_synth.v` with `klt place-and-route` (klayout-tools
0.8.0, OpenROAD `26Q3-1510-g6cb3f2b704`, PDK gf180mcuD, `gf180mcu_fd_sc_mcu7t5v0`).
One local single-unit run, about 4 minutes. The route was re-run once for the
slow corners (issue #446): optimization liberty `pdk.corner:
"ss_125C_1v62"` (was nominal only) plus a zero output delay (below), which is
the request delta that took both failing 1.62 V corners positive — see
"Post-route STA" for the SPEF-annotated result on this geometry.

```sh
rtl/pnr/run_pnr.sh            # re-run, refresh the committed artifacts
rtl/pnr/run_pnr.sh --check    # cheap provenance check, no OpenROAD
rtl/pnr/run_pnr.sh --rerun    # full re-run diffed against the committed report
```

| File | What it is |
|---|---|
| [`pnr/antifuse_digital_top.pnr.json`](pnr/antifuse_digital_top.pnr.json) | The request: 35 % utilization, 10 um core margin, `power.preset: gf180mcu_7t_6M` (PDN on Metal1/4/5 plus tapcells, endcaps, fill), seed 1, optimization corner `ss_125C_1v62` and `constraints.output_delay_ns: 0` (issue #446; both P&R inputs chosen here, like the clock target — not spec values). |
| `pnr/antifuse_digital_top.pnr.report.json` | The `klt place-and-route` response, with host paths rewritten repo-relative by `scrub_report_paths.py` (shared with `rtl/sta`, issue #285). |
| `pnr/antifuse_digital_top.{gds,def}`, `pnr/antifuse_digital_top_routed.v` | Routed GDS, DEF and the as-built netlist (CTS buffers and fill included): the reference a later LVS run should use. |
| `pnr/antifuse_digital_top.attest.json` | The T1 item 2 attestation, written by `pnr/attest.py` and cited as `2.digital` in `signoff/manifest.json`. |

Result: status `ok`, stage `route`, `power.pdn: true`, tapcell master
`gf180mcu_fd_sc_mcu7t5v0__filltie` (220 tapcells, 106 endcaps, per
`power.placed`), 0 antenna and 0 route DRC violations, die 54333 um^2,
40.6 % utilization at route.

Not claimed, and not part of this change:

- **Pin plan.** klt 0.8.0 exposes only the pin layers (`io.layer_h`/`layer_v`);
  OpenROAD places the ports itself. The pins are not placed to match the
  analog interface, so any analog/digital integration needs its own plan.
- **Timing target, not timing signoff.** The 50 ns `clk` target is a P&R input
  chosen here, not a spec value (the open question is `docs/ROADMAP.md`,
  "Digital timing"). Setup at the two slow 1.62 V corners is closed on this
  route (issue #446): OpenROAD's in-flow estimate (`corners[]` in the P&R
  report, `spef_sta: null`, optimized at `ss_125C_1v62`) is non-negative at
  every corner (worst setup +1.864 ns at `ss_125C_1v62`), and the post-route
  SPEF-annotated STA below confirms the same geometry. Timing signoff as a T1
  citation additionally needs a ratified target (the routed zero-delay
  `klt functional-verification` report is now committed below, #445); until
  then the STA report stays `supporting_evidence`.
- **DRC** of the routed GDS is `rtl/pnr/antifuse_digital_top.drc.json`
  (`klt drc`, regenerated by `rtl/pnr/run_drc.sh`; coverage in
  `signoff/README.md`). **LVS and power-delivery checks** are separate items.

### Foreign-host re-run and the report-path guard (issue #316)

`run_pnr.sh` and `run_sta.sh` lint the scrubbed report with
`klt env-provenance lint-envelope` (klayout-tools 0.8.0) and fail the run on
its exit 3, so an absolute host path the scrubber has no rule for stops the
run instead of landing silently in the append-only committed report.
`PRESERVE_RAW=<path>` copies the pre-scrub report aside for evidence runs that
must show what `klt` emitted before scrubbing; both scripts otherwise destroy
it. The scrubber (`rtl/scrub_report_paths.py`) collapses `$PDK_ROOT` to
`~/<basename>` — the portable form this report already carries for the
`~/.ciel`/`~/.volare` search roots — because a PDK resolved outside `$HOME`
has no `~`-under-`$HOME` shape for the plain home collapse to catch.
`tests/test_scrub_report_paths.py` pins the rule and its negative control:
without `$PDK_ROOT` set, an outside-`$HOME` PDK root survives the scrub as an
absolute path while every `$HOME`-shaped check reads clean — the lint is what
stops it.

Foreign-host evidence (2026-11-15, klayout-tools 0.8.0, this report's flow):

- **Host form**: a second checkout at `/tmp/fh316/checkout` (recorded repo
  path `/home/ubuntu/GitHub/gf180-antifuse`), `HOME=/tmp/fh316/home` (recorded
  `/home/ubuntu`), `PDK_ROOT=/home/ubuntu/.ciel` — resolving outside that
  `$HOME`, so the `~/` collapse cannot fire. Single-unit local runs; no job or
  parallelism flag raised.
- `rtl/pnr/run_pnr.sh`: **exit 0**. The pre-scrub report carried
  `layer_map.path: /home/ubuntu/.ciel/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map`
  — absolute, outside the synthetic `$HOME`; the scrubbed report carries
  `~/.ciel/gf180mcuD/...`, byte-identical to the committed form.
  `provenance.pdk.source` records the resolution method
  (`PDK_ROOT environment variable`), not a path, and `ambiguous_sources` is
  absent, so neither leaks. Lint: `clean: 0 absolute path(s)`, exit 0. Note
  the raw report contains `/home/ubuntu/...` while `grep -c '/home/'` on the
  scrubbed report is 0 — the grep this issue's parent leaned on passes a
  leaking report; the lint is the guard.
- `rtl/pnr/run_pnr.sh --check` on that host: **exit 0** (`match` on both
  content hashes).
- `rtl/pnr/run_pnr.sh --rerun` on that host: **exit 3**, a deviation from the
  expectation that it verifies cross-host reproduction. The drift list is
  exactly the fresh side being unscrubbed (`gds_path`/`def_path`/`verilog_path`/
  `power.placed.def_path` absolute vs committed repo-relative, `layer_map.path`
  absolute vs `~/`) plus resolution provenance (`provenance.pdk.source` and
  `ambiguous_sources`: `PDK_ROOT` env vs search roots). **No verdict field
  drifted** — status, stage, power and routing all reproduced. Diffing the
  fresh report *after* the same scrub leaves only run-scoped bookkeeping
  (invocation ids and their interpolated paths), `provenance.klayout_version`
  (0.30.12 committed vs 0.30.13 fresh — version drift under the repo pin) and
  the two resolution-provenance fields. Filed upstream as
  [2AMLogic/klayout-tools#5863](https://github.com/2AMLogic/klayout-tools/issues/5863);
  until it lands, `--check` (hash-level, exit 0 above) plus this drift
  classification is the cross-host verification available for this report.

### Post-route STA (issue #250)

`rtl/sta/run_sta.sh` runs `klt extract --parasitics` on the routed GDS to write a
SPEF, then one `klt sta` request that times that fixed routed geometry at all 15
corners of the P&R report (`klayout-tools==0.8.0`, PDK `gf180mcuD`, 50 ns `clk`,
`output_delay_ns: 0`). `rtl/sta/run_sta.sh --check` re-hashes the inputs against
`rtl/sta/inputs.sha256` and re-validates the report shape without OpenROAD.

| File | What it is |
|---|---|
| `sta/antifuse_digital_top.extract.json`, `sta/antifuse_digital_top.sta.json` | The two requests. |
| `sta/antifuse_digital_top.spef` | The extracted parasitics (`def_net_names`, DEF connections and pins, so OpenSTA can attach every net). |
| `sta/antifuse_digital_top.sta.report.json` | The `klt sta` response, `geometry_source: routed`, host paths rewritten by `scrub_report_paths.py`. |
| `sta/inputs.sha256` | sha256 of GDS, DEF, routed netlist, SPEF and both requests. |

Annotation: 550 of 550 design nets are named by the SPEF at every corner and
`annotation_complete` is true. The DEF carries the connectivity STA reads; the
routed netlist is hashed as the as-built reference but is not read by `klt sta`.
Seven floating `clkload*` cell outputs have no parasitics. The extractor
computed parasitics for 1663 nets but wrote `*D_NET` blocks only for the 550
the DEF names (unlabelled or duplicate-named nets get none).

The baseline STA reported 83 unconstrained endpoints. Setting
`output_delay_ns: 0` constrains all 79 output ports in the routed DEF. This
zero delay is a P&R assumption chosen for issue #446. The request sets no
input delay on the asynchronous SPI inputs `cs_n`, `sclk` and `mosi`, or on
the asynchronous sense-amplifier input `sense_in`. Each feeds a two-flop
synchronizer whose first-stage D pin remains unconstrained. At all 15 corners,
STA reports `timing_status` as `constrained` and `constraint_completeness`
as `incomplete` for those four endpoints.

Setup and hold slack are the worst slack in ns; violations are path counts;
max-tran and max-cap are the `electrical_checks` counts; the last column is the
in-flow estimate from the P&R report.

| Corner | Setup | Hold | Setup viol. | Hold viol. | Max-tran | Max-cap | P&R setup (in-flow) |
|---|---|---|---|---|---|---|---|
| `ff_125C_1v98` | 37.816 | 1.369 | 0 | 0 | 0 | 0 | 38.130 |
| `ff_125C_3v60` | 43.822 | 0.668 | 0 | 0 | 0 | 0 | 43.990 |
| `ff_125C_5v50` | 45.544 | 0.454 | 0 | 0 | 0 | 0 | 45.620 |
| `ff_n40C_1v98` | 41.076 | 1.041 | 0 | 0 | 0 | 0 | 41.334 |
| `ff_n40C_3v60` | 45.810 | 0.471 | 0 | 0 | 0 | 0 | 45.932 |
| `ff_n40C_5v50` | 46.903 | 0.336 | 0 | 0 | 0 | 0 | 46.974 |
| `ss_125C_1v62` | 0.640 | 5.486 | 0 | 0 | 0 | 0 | 1.864 |
| `ss_125C_3v00` | 34.805 | 1.746 | 0 | 0 | 0 | 0 | 35.200 |
| `ss_125C_4v50` | 40.558 | 1.048 | 0 | 0 | 0 | 0 | 40.805 |
| `ss_n40C_1v62` | 4.195 | 5.082 | 0 | 0 | 0 | 0 | 5.240 |
| `ss_n40C_3v00` | 39.616 | 1.231 | 0 | 0 | 0 | 0 | 39.921 |
| `ss_n40C_4v50` | 43.618 | 0.726 | 0 | 0 | 0 | 0 | 43.797 |
| `tt_025C_1v80` | 30.231 | 2.258 | 0 | 0 | 0 | 0 | 30.756 |
| `tt_025C_3v30` | 42.556 | 0.847 | 0 | 0 | 0 | 0 | 42.765 |
| `tt_025C_5v00` | 44.987 | 0.550 | 0 | 0 | 0 | 0 | 45.125 |

All 15 corners ran and all meet setup and hold with zero max-transition and
max-capacitance violations: worst setup +0.640 ns at `ss_125C_1v62`, worst
hold +0.336 ns at `ff_n40C_5v50` (issue #446; the previous route failed
setup at `ss_125C_1v62` (-5.533 ns, 15 paths) and `ss_n40C_1v62` (-2.231 ns,
which also carried 15 max-transition and 1 max-capacitance violations)). The
two 1.62 V corners still lie outside the 3.3 V-class `VDD_LOGIC` assumption
in `spec/supply-domains-decision.md` row 1 (OI-1 still open), and the 50 ns
target is not a ratified spec value; the corner set and the target are
unchanged here. Without a ratified timing target, T1 item 5 (digital) stays
`unmet` even with the routed zero-delay `klt functional-verification` report
below (#445); both reports stay `supporting_evidence` only (`signoff/README.md`).

Foreign-host evidence (issue #316, 2026-11-15; same host form as the P&R run
recorded above — a second checkout at a different repo path,
`HOME=/tmp/fh316/home`, `PDK_ROOT=/home/ubuntu/.ciel` resolving outside it):
`rtl/sta/run_sta.sh` **exit 0**, lint `clean: 0 absolute path(s)`,
`report ok: 15 corners, all SPEF-annotated`. The raw report carries no
absolute PDK path at all: `provenance.pdk.source` is the resolution-method
string, identical before and after the scrub, `ambiguous_sources` is absent,
and this envelope has no `layer_map` field — the only host-dependence is the
repo-root prefix, which the scrubber has always collapsed.
`rtl/sta/run_sta.sh --check` on that host: **exit 0** — all six input hashes
verify, including `sta/antifuse_digital_top.spef`, which the foreign-host
`klt extract` regenerated **byte-identically** (`inputs.sha256` is unchanged
by the run). There is no `klt sta --check --rerun` equivalent
([2AMLogic/klayout-tools#5841](https://github.com/2AMLogic/klayout-tools/issues/5841));
the hash-plus-shape `--check` above is the available cross-host verification
for this report.

## Gate-level functional verification (issue #445)

`rtl/run_gate_sim.sh` runs one `klt functional-verification` request
(`verification/cocotb/request_digital_top.json`) whose only repo source is
the routed netlist `pnr/antifuse_digital_top_routed.v`, with the
`gf180mcu_fd_sc_mcu7t5v0` behavioural cell models resolved from the
installed PDK by the request's `pdk` block (zero-delay `FUNCTIONAL` branch;
no SDF — see the `--sdf` leg below). Top `antifuse_digital_top`, N = 32,
`ARM_TIMEOUT` 4096 and `READ_SETTLE` 8 baked into the cells, Icarus 13.0,
cocotb. **Result: 21/21 tests pass** (`verification/cocotb/report_digital_top.json`
is committed; the suite is the port-only
`verification/cocotb/test_antifuse_digital_top.py` — SPI registers through
the top-level pins plus row/column decoder coverage through the `*_onehot`
ports, with a per-cycle monitor checking the one-hot lines every test).
`rtl/run_gate_sim.sh --check` re-hashes the inputs
(`verification/cocotb/inputs_digital_top.sha256`) and re-validates the
report shape and the port-only discipline, no simulator needed.

| File | What it is |
|---|---|
| `verification/cocotb/request_digital_top.json` | The zero-delay request: routed netlist + `pdk` block (variant `gf180mcuD`, library `gf180mcu_fd_sc_mcu7t5v0`). |
| `verification/cocotb/test_antifuse_digital_top.py` | Port-only suite (21 tests): the port-applicable `test_spi_regs.py` coverage at the netlist's own constants, plus `decoder_onehot_all_indices` (all 32 rows and columns) and `onehot_idle_while_sel_changes`. |
| `verification/cocotb/report_digital_top.json` | The committed report, host-path-scrubbed by `scrub_report_paths.py` and linted clean (`klt env-provenance lint-envelope`, issue #316's guard). |
| `verification/cocotb/inputs_digital_top.sha256` | Input hashes for the zero-delay run. The separate `inputs_digital_top_sdf.sha256` also binds the SDF run to the DEF, SPEF and STA request. |
| `rtl/run_gate_sim.sh` | The runner: no args runs and refreshes; `--check` verifies; `--sdf` regenerates and checks the annotated report. |
| `rtl/sta/antifuse_digital_top.sdf.json`, `verification/cocotb/request_digital_top_sdf.json` | The `--sdf` leg's two requests (below). |

The flow pins klayout-tools git rev
`6bd18bbc8637f6d767b3c24e77bd5db7a39e4bbe` (0.9.3.dev2575): the request
`pdk` block that keeps host PDK paths out of the committed request is
unreleased ([2AMLogic/klayout-tools#6977](https://github.com/2AMLogic/klayout-tools/issues/6977)),
and that build's report envelope emits checkout-free artifact paths
(`scope: "external", path: null`). `KLT_CMD` overrides the invocation for a
host dev install of the same rev.

### Post-route simulation with SDF timing

`rtl/run_gate_sim.sh --sdf` generates nominal TT/25 °C/1.8 V timing from the
routed DEF and SPEF, then runs the 21 port-level tests on the routed Verilog.
The request sets the testbench clock to the same 50 ns period used by STA.
This is the engineering constraint used for this run. A product clock target
and all-corner functional timing remain open.

All 21 tests pass. Icarus reports partial annotation, with 1,070 conditional
IOPATH entries and 144 IFNONE edge paths dropped, plus 95 TIMINGCHECK
diagnostics. The report records all three classes. The passing scope is the
timing that Icarus actually annotated. The zero-delay control uses a 10 ns
clock. Replaying the same routed inputs with SDF at 10 ns passes 3 of 21.
The earlier counter-capture trace on a previous routed revision is
documented in the [upstream timing diagnosis](https://github.com/2AMLogic/klayout-tools/pull/7160).

The committed result is `verification/cocotb/report_digital_top_sdf.json`.
The runner removes OpenSTA's optional wall-clock DATE header before the run so
the report's SDF SHA-256 can be reproduced. The item 7.digital citation in
`signoff/manifest.json` pins this normalized digest independently. Offline checks
compare it with the simulator's reported digest. A live replay also compares
the generated SDF bytes with the pin. In a checkout with two PDK
installations, set `PDK_ROOT` to the pinned Ciel tree to select it explicitly.
