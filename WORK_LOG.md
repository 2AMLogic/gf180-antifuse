# Work Log

Merged PRs and closed issues from the last 30 days at the first Guide snapshot.


### 2026-10-17

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
