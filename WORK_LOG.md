# Work Log

Merged PRs and closed issues from the last 30 days at the first Guide snapshot.


### 2026-10-29

- **PR #220**: docs: add Run 3 direct-pad bench plan and record template
- **Issue #212** (closed): Run 3 test chip: bench measurement plan (V_bd, R_prog, read margin)
- **PR #214**: feat: draw candidate 3 bitcell layout with DRC/LVS/ERC evidence
- **PR #217**: docs: first-principles gate-oxide V_bd(t_pulse) model with generator and tests
- **Issue #205** (closed): Model gate-oxide V_bd and TDDB versus pulse width for thin and thick gf180 oxides
- **PR #216**: docs: add compliance-limited filament resistance model and read-margin comparison
- **Issue #209** (closed): Model post-breakdown filament resistance and programmed-cell read margin
- **PR #215**: docs: add Run 3 test chip floorplan, instance counts and pad budget
- **Issue #206** (closed): Run 3 test chip: top-level floorplan, instance counts and pad budget
- **Issue #197** (closed): T1 item 2 (layout, analog): artifact-anchored envelope binding cell_candidate1.gds and its generator
- **Issue #127** (closed): Measure V_bd and carry Candidates 2 and 3 until then (operator ruling 2026-10-20)

### 2026-10-28

- **PR #200**: feat: cite compound ERC+LVS evidence as 11.analog at klt 0.8.0
- **Issue #196** (closed): T1 item 11 (Power delivery, analog partition): cite compound ERC+LVS evidence
- **PR #193**: feat(sim): V_bd sensitivity re-run records and per-candidate comparison
- **Issue #130** (closed): Re-run program- and read-bias benches with sourced V_bd and compare candidates

### 2026-10-27

- **PR #189**: refactor: route cell-default parsing through numfmt.parse_defaults
- **Issue #184** (closed): Consolidate five duplicated .subckt cell-default parsers onto sim/harness/numfmt.py
- **PR #188**: feat: cite klt drc report as 3.digital and add run_drc.sh
- **Issue #175** (closed): T1 item 3 (DRC clean, digital partition): klt drc on the routed digital GDS
- **PR #187**: fix: clear routed-GDS DRC via tapcell pitch and PDN split-cut removal
- **Issue #186** (closed): Routed digital GDS fails klt drc: 5937 violations across 9 rules
- **PR #181**: feat: attest digital testbenches for item 9 and regrade signoff with klt 0.8.0
- **Issue #173** (closed): T1 item 9 (Testbenches shipped, digital partition): attest the iverilog and cocotb benches with klt signoff --attest 9
- **PR #180**: feat(rtl): route antifuse_digital_top with a PDN and cite it as 2.digital
- **Issue #174** (closed): T1 item 2 (Layout, digital partition): klt place-and-route of antifuse_digital_top with a PDN, committed routed GDS
- **PR #179**: signoff: attest T1 item 1 (digital) via klt signoff --attest; regrade with klayout-tools 0.8.0
- **Issue #172** (closed): T1 item 1 (Design sources, digital partition): attest the RTL and synthesized netlists with klt signoff --attest 1

### 2026-10-24

- **PR #170**: chore(sim): remove unused ngspice deck runner
- **Issue #169** (closed): Remove sim/harness/runner.py: unused ngspice deck runner
- **PR #168**: docs: update README sim rows for klt campaign path
- **Issue #167** (closed): README sim status table still lists removed --check-env / local grid command
- **PR #166**: refactor(sim): retire legacy local-ngspice grid driver
- **Issue #158** (closed): Retire legacy local-ngspice grid driver in cell-device-characterization (superseded by klt campaign)

### 2026-10-23

- **PR #163**: feat(sim): publish evidence manifests from five more sim runners
- **Issue #160** (closed): Wire publish_for_runner into the remaining five sim runners
- **PR #161**: feat(sim): wire evidence publishing into two runners and add live klt manifest
- **PR #157**: feat(sim): add publish_run helper for storing whole run directories
- **PR #154**: verification: port-only cocotb suite for SPI register block with mutation evidence
- **Issue #153** (closed): Live verification of artifact-store evidence writer (real klt put/verify) and runner wiring
- **Issue #151** (closed): verification: port-only cocotb suite for antifuse_spi_regs run through klt functional-verification (T1 items 5/7/9 groundwork, digital partition)
- **Issue #149** (closed): Adopt the common artifact store for sim evidence (manifests in git, bytes via klt artifact)
- **PR #152**: feat: store new sim evidence via klt artifact, commit only manifests
- **PR #155**: rtl: add one-hot row/column decoder, digital top and synth report
- **Issue #150** (closed): rtl: global row/column one-hot decoders per architecture §1.1, with exhaustive bench and klt synthesize report (T1 item 1, digital partition)

### 2026-10-22

- **PR #146**: docs: remove stale #84 auditor-worker handoff record
- **Issue #135** (closed): Remove docs/auditor-worker-handoff.md: stale, unreferenced record for closed #84
- **PR #142**: fix(layout): add MOS-cap marker so candidate-1 LVS matches; cite 4.analog
- **Issue #140** (closed): T1 item 4 (analog): klt lvs on candidate 1 now runs but reports mismatch; resolve and cite 4.analog
- **PR #141**: feat: cite klt erc envelope as 11.analog and record the missing LVS half
- **Issue #120** (closed): T1 item 11 (analog): run klt erc on first bitcell and cite as 11.analog
- **PR #138**: docs: add klt erc supply spec and gap table for item 11
- **Issue #119** (closed): T1 item 11 (analog): klt erc supply spec from the supply-domain decision record, then cite ERC with item 4's LVS

### 2026-10-21

- **PR #133**: sim: add Candidate 3 gate/well-drive program-bias benches and record
- **Issue #129** (closed): Candidate 3 gate/well-drive program-bias bench
- **PR #131**: docs: sourced gate-oxide V_bd per candidate and test-structure plan
- **Issue #128** (closed): Source V_bd per candidate from primary data and plan a test structure
- **PR #94**: design: program bias scheme vs access-device ratings; PROPOSED decision record (#90)
- **Issue #90** (closed): design: program-leg access-device overstress at assumed V_bd; Candidate 2 not programmable via BL-driven leg
- **PR #88**: sim: Candidate 2 klt campaign via version-matched client; regenerate signoff (#63)
- **Issue #63** (closed): sim: express the PVT corner campaign as a klt sim request and cite it in the signoff manifest

### 2026-10-20

- **PR #85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **Issue #59** (closed): layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition)
- **PR #122**: rtl: synthesize antifuse_spi_regs with klt and record the netlist and report
- **Issue #60** (closed): rtl: synthesize antifuse_spi_regs against gf180mcu std cells and cite the netlist in the signoff manifest
- **PR #61**: feat: SPI register file RTL, bench and decision record
- **Issue #58** (closed): design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition)
- **PR #92**: design+sim: Candidate 3 read bias (n-well tied to read rail) with PVT evidence
- **Issue #75** (closed): design: Candidate 3 read bias -- placeholder WL=0 V cannot read a programmed cell (I_prog_min undefined)

### 2026-10-17

- **PR #116**: refactor(sim): share number-parsing, formatting and git helpers in sim/harness
- **Issue #114** (closed): Consolidate duplicated SPICE-number and record-format helpers into sim/harness
- **PR #113**: refactor(design): share xschem emitter between array and leg generators
- **PR #112**: refactor(sim): share one klt sim submit helper across run scripts
- **Issue #111** (closed): Consolidate four divergent run_klt wrappers in sim/ scripts into sim/harness
- **Issue #110** (closed): Consolidate duplicated xschem emitter code in gen_array.py and gen_leg_schematics.py

### 2026-10-16

- **PR #108**: sim: integrated program-to-read transition and stress bench with first fleet record
- **Issue #73** (closed): sim: integrated program-to-read transition and voltage-stress bench
- **PR #105**: sim: full-band addressing-stage leakage per region at read bias
- **Issue #70** (closed): design: quantify full-band addressing leakage in the sense-margin budget
- **PR #103**: sim: mismatch Monte Carlo for read-leg sense mirror against I_ref
- **PR #96**: sim: PVT record for program/read legs from fleet batch run
- **PR #69**: design: N=32 array, local HV pass-gate stage and level shifters as xschem sources + slice bench (#64)
- **Issue #102** (closed): sim: mismatch Monte Carlo for read-leg sense mirror vs I_ref
- **Issue #65** (closed): design: program leg (ballast + current limit) and read leg (sense amp + I_ref) schematics with worst-case margin bench
- **Issue #64** (closed): design: capture the N=32 array, local HV pass-gate MUX and level shifters as xschem sources (analog partition)

### 2026-10-15

- **PR #100**: feat: pin open_pdks f6eeac7d and fail visibly on PDK revision mismatch
- **PR #93**: sim: program/read-leg PVT evidence from the batch fleet (#65)
- **Issue #98** (closed): Re-pin open_pdks to f6eeac7 and make PDK search verify the pinned revision (ciel 2.6.1)
- **PR #91**: sim: programming-yield Monte Carlo campaign, yield-vs-condition per grid region (#66)
- **PR #89**: sim: converge the breakdown-event transient at every PVT corner (#74)
- **PR #83**: docs: README spec table and reproduction section
- **PR #68**: design: program leg + read leg schematics, benches, ballast record (#65)
- **Issue #79** (closed): docs: README spec table and reproduction section for T1 item 10
- **Issue #74** (closed): sim: breakdown-event transient fails to converge at some PVT corners (cell-breakdown-model trigger bench)
- **Issue #66** (closed): sim: programming-yield Monte Carlo campaign, yield-vs-condition per grid region (T1 item 6)

### 2026-10-13

- **PR #87**: docs: Auditor worker deployment discovery and handoff (#84)
- **PR #82**: spec: measurement matrix and extraction protocol for yield, read margin and retention
- **PR #81**: sim: reproducible per-split device characterization report (#72)
- **PR #80**: spec: supply-domain inventory decision record
- **PR #76**: design: behavioral breakdown-augmented cell model and single-cell bench (#62)
- **PR #67**: sim: express the PVT corner campaign as klt sim requests (#63)
- **Issue #84** (closed): Auditor Capability Request: klt unavailable for signoff verification
- **Issue #78** (closed): spec: measurement matrix and extraction protocol for yield, read margin and retention per grid region
- **Issue #77** (closed): spec: supply-domain inventory (net, voltage class, region, owner) for T1 item 11
- **Issue #72** (closed): sim: reproducible per-split characterization report for T1 item 8
- **Issue #62** (closed): design: behavioral breakdown-augmented model for the three antifuse cell candidates

### 2026-10-09

- **Issue #71** (closed): Auditor Capability Request: Python 3 unavailable for simulation runner smoke checks

### 2026-10-03

- **PR #56**: docs: embed fleet burndown chart and fleet-ops firewall carve-out (#46)
- **Issue #46** (closed): README: embed the fleet burndown chart (one line)

### 2026-09-25

- **PR #55**: fix: use POSIX bracket expression instead of GNU \s in ngspice error grep
- **PR #54**: fix: make netlist path normalization portable to BSD/macOS sed
- **PR #51**: refactor: extract shared PDK_ROOT resolution into design/lib-pdk-root.sh
- **Issue #53** (closed): check-netlists.sh error detection uses GNU-only \s in grep -E, likely silently misses indented ngspice errors on macOS
- **Issue #52** (closed): regen-netlists.sh fails on macOS: sed -i needs a backup suffix for BSD sed
- **Issue #50** (closed): Remove duplicated PDK_ROOT resolution: consolidate check-netlists.sh and regen-netlists.sh

### 2026-09-24

- **PR #49**: fix: resolve PDK root from $PDK_ROOT before falling back to ~/.volare
- **PR #47**: docs: name the exact klt build signoff/report.json was graded with
- **Issue #48** (closed): check-netlists.sh: honour $PDK_ROOT before falling back to ~/.volare (the CI runner now sets it)
- **Issue #45** (closed): signoff/README.md should name the exact klt build verify.sh was verified against

### 2026-09-22

- **PR #44**: signoff: commit a klt signoff block manifest and its graded T1 verdict
- **Issue #43** (closed): Commit a klt signoff block manifest so this block's T1 state is graded, not hand-read

### 2026-09-14

- **Issue #42** (closed): Remove tracked __pycache__/*.pyc bytecode files
- **Issue #37** (closed): Remove phantom --check-env usage line from sim/run_corners.py docstring

### 2026-09-13

- **PR #41**: refactor: remove append_log wrapper, call write_once directly
- **Issue #40** (closed): Remove append_log wrapper: identical pass-through of write_once

### 2026-09-12

- **PR #39**: Remove NgspiceRun wrapper: single-field dataclass adds no value
- **PR #36**: refactor: remove dead pdk_root assignment in resolve_pdk() env-path branch
- **PR #35**: Remove dead ok/returncode fields from harness NgspiceRun
- **PR #31**: refactor: remove unused pdk_root field from PDKPaths
- **PR #29**: refactor: consolidate scratch-dir/deck-write/run duplication in run_experiment.py
- **PR #27**: refactor: remove unused claim_extra parameter from render_record()
- **PR #25**: fix: consolidate gen_models/gen_models_moscap duplication in run_experiment.py
- **PR #23**: Remove unused variant_override parameter in resolve_pdk()
- **PR #20**: fix: enforce append-only guard on raw per-corner ngspice logs
- **Issue #38** (closed): Remove NgspiceRun wrapper: single-field dataclass adds no value
- **Issue #34** (closed): Remove dead pdk_root local variable in resolve_pdk()'s GF180_PDK_PATH branch
- **Issue #33** (closed): Remove dead ok/returncode fields from harness NgspiceRun
- **Issue #32** (closed): Remove unused PDKPaths.pdk_root field
- **Issue #30** (closed): Remove unused pdk_root field from PDKPaths
- **Issue #28** (closed): Consolidate scratch-dir/deck-write/run duplication in run_experiment.py
- **Issue #26** (closed): Remove unused claim_extra parameter from render_record()
- **Issue #24** (closed): Consolidate gen_models/gen_models_moscap duplication in run_experiment.py
- **Issue #22** (closed): Remove unused variant_override parameter in sim/harness/pdk.py's resolve_pdk()
- **Issue #21** (closed): Remove dead code in sim/harness: unused append_log function and variant_override parameter
- **Issue #19** (closed): Remove unused append_log helper in sim/harness/report.py (or wire it into raw-log writes)
- **Issue #18** (closed): Remove unused append_log() in sim/harness/report.py

### 2026-09-09

- **PR #17**: sim: stand up sim/ evidence convention + cell-device-characterization experiment
- **Issue #16** (closed): sim: access-device OFF-leakage / ON-resistance and moscap C–V characterization over PVT for all three cells — bound `I_sneak_max` at N=32 (architecture §3/§4 "required design input")
