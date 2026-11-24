# Work Log Archive — 2026-09

Sections moved byte-for-byte from [WORK_LOG.md](../WORK_LOG.md) by `loom-daemon work-docs archive`.

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
