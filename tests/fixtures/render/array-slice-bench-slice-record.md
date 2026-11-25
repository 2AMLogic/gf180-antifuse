# Record 20261009-021330-3010ff8

- **Record ID**: 20261009-021330-3010ff8
- **Claim**: `spec/architecture.md` §1.1/§1.3 (two-tier addressing: a cell is selected only when both its row and column pass-gates are enabled; every other row/column pass-gate is held OFF) and §3 (unselected access devices do not conduct), as captured by `design/gen_array.py` -> `design/netlists/slice_*.spice`; `spec/cell-candidates.md` (Candidate 2 `nfet_10v0_asym` drain faces BL).
- **Netlist provenance**: schematic (`design/netlists/`, derived by xschem from `design/array/`, `design/mux/`, `design/cells/`); git HEAD `000000000000`; working tree clean.
- **Corner matrix run**: process {typical, ff, ss, fs, sf} (MOS and moscap sections from the request, the matching 10 V LDMOS section from the netlist; one `klt sim` request per process corner, see `testbench/*.request.json`) x temperature {-40, 27, 125} C x supply {-10%, nominal, +10%} (scaling VDDL, every VDDH, every BLG stand-in level together) x all 16 selectable cells of the slice. This is the full CLAUDE.md PVT matrix; no subset.
- **Result**: see per-slice sections below. Per region, per sub-combination; nothing is averaged across regions or sub-combinations.
- **Links**: testbench `sim/array-slice-bench/testbench/`; raw klt reports in the artifact store, manifest `manifests/artifacts/array-slice-bench-20261009-021330-3010ff8.manifest.json`.
- **Timestamp / author**: 2026-11-24T12:00:00Z / Claude Sonnet 5.5 (Loom builder, issue #64)
- **Supersedes**: (none)

## Acceptance thresholds used (this record's own; not spec numbers)

eta >= 0.8; |I(PLG)|/|I(BLG)| in [0.95, 1.053]; V(BL)/V(BLG) >= 0.98; V(PL)/V(BLG) <= 0.02; unselected-cell and idle-bus current <= 0.001 of the ideal V_BLG/R_FIL, with R_FIL = 1e+06 ohm a **bench-only filament stand-in** (see make_bench.py: it makes conduction observable at DC; it is not a post-breakdown model). The BLG levels, VDDH rails and VDDL are bench placeholders, not programming conditions.

## Access-device orientation (structural)

| Candidate | Access device | Derived netlist line | Required | Status |
|---|---|---|---|---|
| Candidate 1 | `nfet_06v0` | `XM1 BL WL CN VB` (d g s b) | BL on drain | confirmed |
| Candidate 2 | `nfet_10v0_asym` | `XM1 BL WL CN VB` (d g s b) | BL on drain | confirmed |
| Candidate 3 | `pfet_06v0` | `XM1 CN WL BL VB` (d g s b) | BL on source | confirmed |

## Results

### slice_i_ii (rows 0-3, cols 9-12)

- corners run: 720 (pass 720, fail 0, error 0, inconclusive 0); 0 not gradable
- engine: ngspice 46
- batch jobs (one per process corner): `klt-sim-f668f55ef5a1` (aws-batch-fleet, m7i.4xlarge, spot), `klt-sim-592b02474f98` (aws-batch-fleet, m6i.4xlarge, spot), `klt-sim-764f24b2d983` (aws-batch-fleet, m7i.4xlarge, spot), `klt-sim-43cce0a2ca75` (aws-batch-fleet, m7i.4xlarge, spot), `klt-sim-b22ced4fc06f` (aws-batch-fleet, c7i.4xlarge, spot)
- pdk: {'name': 'gf180mcuD', 'source': 'PDK_ROOT environment variable', 'version': 'open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b'}
- sha256 of the full, un-elided text: none attestable (ff, fs, sf, ss, typical: the input report is already coverage-elided); no sidecar written

**Selected cell reaches the BL/PL program path** (per region, per capacitor-geometry x access-sizing sub-combination; worst case over every corner and every selected cell of that sub-combination). eta = selected-cell access-path current / (V_BLG / R_FIL).

| Region | Cap level | Access level | selections x corners | eta min (worst corner) | I(PLG)/I(BLG) min | V(BL)/V(BLG) min | V(PL)/V(BLG) max | not meeting criteria |
|---|---|---|---|---|---|---|---|---|
| Region I (Candidate 1) | 2x | 2x | 90 | 0.958 (ss/125C/x0.9 sel=(1,10)) | 1 | 0.998 | 0.00018 | 0 |
| Region I (Candidate 1) | 2x | min | 90 | 0.939 (ss/125C/x0.9 sel=(0,9)) | 1 | 0.998 | 0.000177 | 0 |
| Region I (Candidate 1) | min | 2x | 90 | 0.958 (ss/125C/x0.9 sel=(0,10)) | 1 | 0.998 | 0.00018 | 0 |
| Region I (Candidate 1) | min | min | 90 | 0.939 (ss/125C/x0.9 sel=(1,9)) | 1 | 0.998 | 0.000177 | 0 |
| Region II (Candidate 2) | 2x | 2x | 90 | 0.987 (ss/-40C/x0.9 sel=(2,12)) | 1 | 0.99 | 0.000269 | 0 |
| Region II (Candidate 2) | 2x | min | 90 | 0.984 (ss/-40C/x0.9 sel=(0,12)) | 1 | 0.99 | 0.000268 | 0 |
| Region II (Candidate 2) | min | 2x | 90 | 0.987 (ss/-40C/x0.9 sel=(2,11)) | 1 | 0.99 | 0.000269 | 0 |
| Region II (Candidate 2) | min | min | 90 | 0.984 (ss/-40C/x0.9 sel=(0,11)) | 1 | 0.99 | 0.000268 | 0 |

**Unselected cells isolated** (per region; worst unselected-cell access-path current relative to the region's own ideal V_BLG/R_FIL; classes are relative to the selected cell: `same_col` = BL powered, word line off; `same_row` = word line on, column pass-gate off; `other`; `bus` = a powered global bit-line bus of a band that holds no selected cell).

| Region | Class | corner x selection instances | worst ratio (corner) | over threshold |
|---|---|---|---|---|
| Region I (Candidate 1) | bus | 360 | 0.00131 (ff/125C/x0.9 sel=(0,11)) | 24 |
| Region I (Candidate 1) | other | 720 | 2.25e-06 (ff/125C/x0.9 sel=(1,9)) | 0 |
| Region I (Candidate 1) | same_col | 360 | 6e-05 (ff/125C/x0.9 sel=(0,9)) | 0 |
| Region I (Candidate 1) | same_row | 720 | 0.00065 (ff/125C/x0.9 sel=(0,10)) | 0 |
| Region II (Candidate 2) | bus | 360 | 0.000385 (ff/125C/x0.9 sel=(0,9)) | 0 |
| Region II (Candidate 2) | other | 720 | 0.000105 (ff/125C/x0.9 sel=(2,11)) | 0 |
| Region II (Candidate 2) | same_col | 360 | 0.000167 (ff/125C/x0.9 sel=(2,11)) | 0 |
| Region II (Candidate 2) | same_row | 720 | 0.000363 (ff/125C/x0.9 sel=(0,11)) | 0 |

### slice_ii_iii (rows 0-3, cols 20-23)

- corners run: 720 (pass 720, fail 0, error 0, inconclusive 0); 0 not gradable
- engine: ngspice 46
- batch jobs (one per process corner): `klt-sim-a880fc8a95ec` (aws-batch-fleet, m6i.4xlarge, spot), `klt-sim-6004047be6e5` (aws-batch-fleet, c7i.8xlarge, spot), `klt-sim-01c768895dc5` (aws-batch-fleet, m7i.4xlarge, spot), `klt-sim-8573da2b2531` (aws-batch-fleet, m7i.4xlarge, spot), `klt-sim-365e43a65965` (aws-batch-fleet, m7i.4xlarge, spot)
- pdk: {'name': 'gf180mcuD', 'source': 'PDK_ROOT environment variable', 'version': 'open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b'}
- sha256 of the full, un-elided text: none attestable (ff, fs, sf, ss, typical: the input report is already coverage-elided); no sidecar written

**Selected cell reaches the BL/PL program path** (per region, per capacitor-geometry x access-sizing sub-combination; worst case over every corner and every selected cell of that sub-combination). eta = selected-cell access-path current / (V_BLG / R_FIL).

| Region | Cap level | Access level | selections x corners | eta min (worst corner) | I(PLG)/I(BLG) min | V(BL)/V(BLG) min | V(PL)/V(BLG) max | not meeting criteria |
|---|---|---|---|---|---|---|---|---|
| Region II (Candidate 2) | 2x | 2x | 90 | 0.987 (ss/-40C/x0.9 sel=(1,21)) | 1 | 0.99 | 0.000269 | 0 |
| Region II (Candidate 2) | 2x | min | 90 | 0.984 (ss/-40C/x0.9 sel=(0,20)) | 1 | 0.99 | 0.000268 | 0 |
| Region II (Candidate 2) | min | 2x | 90 | 0.987 (ss/-40C/x0.9 sel=(0,21)) | 1 | 0.99 | 0.000269 | 0 |
| Region II (Candidate 2) | min | min | 90 | 0.984 (ss/-40C/x0.9 sel=(1,20)) | 1 | 0.99 | 0.000268 | 0 |
| Region III (Candidate 3) | 2x | 2x | 90 | 0.939 (ss/125C/x0.9 sel=(2,23)) | 1 | 0.998 | 0.000177 | 0 |
| Region III (Candidate 3) | 2x | min | 90 | 0.884 (ss/125C/x0.9 sel=(0,23)) | 1 | 0.998 | 0.000169 | 0 |
| Region III (Candidate 3) | min | 2x | 90 | 0.939 (ss/125C/x0.9 sel=(2,22)) | 1 | 0.998 | 0.000177 | 0 |
| Region III (Candidate 3) | min | min | 90 | 0.884 (ss/125C/x0.9 sel=(0,22)) | 1 | 0.998 | 0.000169 | 0 |

**Unselected cells isolated** (per region; worst unselected-cell access-path current relative to the region's own ideal V_BLG/R_FIL; classes are relative to the selected cell: `same_col` = BL powered, word line off; `same_row` = word line on, column pass-gate off; `other`; `bus` = a powered global bit-line bus of a band that holds no selected cell).

| Region | Class | corner x selection instances | worst ratio (corner) | over threshold |
|---|---|---|---|---|
| Region II (Candidate 2) | bus | 360 | 0.000385 (ff/125C/x0.9 sel=(0,22)) | 0 |
| Region II (Candidate 2) | other | 720 | 5.85e-05 (ff/125C/x0.9 sel=(0,20)) | 0 |
| Region II (Candidate 2) | same_col | 360 | 0.000131 (ff/125C/x0.9 sel=(0,20)) | 0 |
| Region II (Candidate 2) | same_row | 720 | 0.000297 (ff/125C/x0.9 sel=(0,21)) | 0 |
| Region III (Candidate 3) | bus | 360 | 3.48e-06 (ss/125C/x0.9 sel=(0,20)) | 0 |
| Region III (Candidate 3) | other | 720 | 1.77e-06 (ff/125C/x0.9 sel=(0,20)) | 0 |
| Region III (Candidate 3) | same_col | 360 | 1.77e-06 (ff/125C/x0.9 sel=(0,22)) | 0 |
| Region III (Candidate 3) | same_row | 720 | 6.47e-06 (ff/27C/x1.1 sel=(1,20)) | 0 |

