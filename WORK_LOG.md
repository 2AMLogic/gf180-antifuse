# Work Log

Merged PRs and closed issues from the last 30 days at the first Guide snapshot.


### 2026-11-18

- **PR #440**: docs: state geometry-claims checker scope and mark rtl/pnr note as unpinned
- **Issue #439** (closed): Geometry-claims checker does not cover design-record docs outside layout/README.md
- **PR #437**: docs(rtl): localize col_sel[2] LVS split to an abstract-cell multi-pad pin artifact
- **Issue #436** (closed): Routed digital GDS: col_sel[2] extracts as two nets, gate-level LVS mismatch
- **PR #433**: checker: fail claims whose quote spells an interval but omit quote_values
- **Issue #419** (closed): geometry-claims checker: deleting quote_values re-opens the #414 coordinated-edit bypass
- **PR #431**: test: guard WORK_PLAN.md plan-body block against generator-foreign annotations
- **Issue #430** (closed): Guide plan-body block carries hand-applied annotations the generator never emits (recurrence of #420)
- **PR #428**: test: pin erc/lvs/economy sign-off reports to the committed layout by name
- **Issue #427** (closed): Pin the ERC/LVS/economy sign-off reports to the committed layout, and name the expected report set
- **PR #426**: test: pin run3_top stage report hashes to the committed GDS
- **Issue #424** (closed): run3_top stage evidence: no test pins a report's recorded input hash to the committed GDS
- **PR #423**: layout: record the run3 antenna stage's measured ratios and after-round report
- **Issue #422** (closed): run3_top README: the antenna groups' measured ratios and the deferred remedy's "after: 0" round have no committed source
- **PR #421**: docs: drop hand-applied *(held)* markers from WORK_PLAN.md rows
- **Issue #420** (closed): WORK_PLAN.md *(held)* annotation is hand-applied post-generation and drifts between Guide runs
- **PR #417**: checker: pin readme_quote numerals to bbox_um via per-claim quote_values
- **Issue #414** (closed): Geometry-claims checker does not tie readme_quote's numbers to bbox_um — a coordinated prose+sidecar edit still passes
- **PR #416**: layout: fix the run3 chip-level findings the precheck's own stages enforce
- **Issue #404** (closed): Chip-level native DRC findings in repo-drawn geometry (antenna, die-level density, CUP.2) have no tracking work
- **PR #413**: check: pin README-quoted VB-strap and gate-pad intervals to the committed GDS
- **Issue #407** (closed): No check ties layout/README.md's quoted geometry intervals to the committed GDS (three hand-found drifts: #378, #391, #401)
- **PR #411**: docs(sim): correct stale klt concurrency-cap retry comment in cell-breakdown-model
- **Issue #300** (closed): Decide whether sim/program-read-legs requests should carry a klt-side batch.capacity_wait_s
- **PR #410**: docs(spec): repoint CN ring-gap citations at the shared point modules
- **Issue #409** (closed): spec/capacitor-geometry-decision.md cites the candidate-1/3 generate.py shims for CN gap-span measurements that now live in the points modules
- **PR #403**: refactor(layout): share candidate-3 geometry via a candidate3_points table
- **Issue #397** (closed): Consolidate the two candidate-3 generators onto a shared point table (as #315 did for candidate 1)
- **PR #405**: docs: correct candidate-1 VB-strap metal band bottoms in layout README
- **Issue #401** (closed): layout: candidate-1 family VB-strap bullet quotes access north-band bottoms 0.04 um low (README:426-437)
- **PR #402**: layout: assemble the Run 3 test chip (run3_top.gds) with DRC/LVS/ERC evidence
- **Issue #211** (closed): Run 3 test chip: full-chip assembly with DRC/LVS through klt
- **PR #400**: docs(layout): correct Amin_G2x VB-strap rationale to the measured spacing constraint
- **Issue #391** (closed): layout: cell_candidate3_Amin_G2x's VB-strap rationale says the cap gate pad sits BETWEEN the two ring north bands; measured, it now sits below both
- **PR #398**: docs: sync signoff README 3.analog row with the committed 5-finding DRC report
- **Issue #396** (closed): signoff/README.md's 3.analog rationale is stale: it cites candidate 1's DF.1c and "6 findings", but the committed drc_native_report.json has 5 and no DF.1c (#287 is closed)
- **PR #386**: docs: refresh candidate-1/3 native DRC finding counts in ROADMAP and PCell-exception record
- **Issue #383** (closed): docs/spec: the native-finding count tables in docs/ROADMAP.md and spec/pdk-pcell-drc-exception-decision.md are stale for candidates 1 and 3 (DF.1c cleared by #296, DF.4d_MV/DV.6 by #297)
- **Issue #287** (closed): Native PDK runset finds real DRC violations in all three bitcells that the curated deck misses: MOSCAP COMP width (all 3), 6 V gate length (cand 2), Nwell overlap and Dualgate enclose (cand 3)
- **PR #394**: refactor(layout): one drift-check driver — candidate-2 generators reuse bitcell_gen drive/helpers
- **PR #392**: docs(spec): anchor the generate.py PCell citation to the acc bg.run call, not line numbers
- **Issue #390** (closed): spec: pdk-pcell-drc-exception-decision.md cites generate.py "lines 96-99", now lines 110-112
- **Issue #280** (closed): Remove the second copy of the GDS drift-check driver in layout/cell_candidate2/generate.py (reuse bitcell_gen)
- **PR #389**: layout: clear candidate3_Amin_G2x's generator-owned DF.4d_MV/DV.6 via acc-block ring padding (1.29 um), re-fit DX, Y_TAP_ACC and the strap x-extents
- **PR #388**: docs(spec): re-record candidate 2's DRC census (27 -> 25) after #296 cleared the cap__core findings
- **PR #387**: docs: qualify Run 3 slot-booking and GDS-date claims in spec/ and ROADMAP
- **PR #384**: docs: replace stale inline ERC coverage figures with per-cell table pointer
- **PR #381**: layout: clear candidate 3's generator-owned DF.4d_MV/DV.6 via acc-block ring padding (1.29 um), re-fit DX and VB strap
- **Issue #385** (closed): docs/spec: candidate 2's native DRC finding count is stale in pdk-pcell-drc-exception-decision.md (27 quoted, committed report says 25)
- **Issue #382** (closed): layout: cell_candidate3_Amin_G2x still carries the generator-owned DF.4d_MV x5 + DV.6 x1 that #297 cleared on cell_candidate3; apply ring_padding_acc_um to the 2x-area pfet variant
- **Issue #379** (closed): Correct the remaining unqualified "Run 3 quarter slot" / "GDS due 2026-12-16" wording in spec/ and docs/ROADMAP.md
- **Issue #378** (closed): layout/erc/README.md: candidate-1 coverage figures (11.79 um2, extent_uncovered_fraction 0.055) are stale against the committed report (13.0148, 0.114166)
- **Issue #297** (closed): layout: clear candidate 3's generator-owned DF.4d_MV x5 and DV.6 via ring_padding_um, and file the klayout-tools well-overlap defect upstream

### 2026-11-17

- **PR #377**: layout: draw the Run 3 bare-cap C2 fallback (2F), measure its native runset, propose the decision record
- **PR #375**: fix: give cell_candidate2 its own fitted ERC supply spec (supplies_c2.json)
- **Issue #373** (closed): layout/erc: cell_candidate2 shares candidate 1's supplies.json, so its Region-I missing_tie 'clean' covers only ~45% of its drawn tap area
- **Issue #372** (closed): Run 3 fallback: a variant that passes the native runset without candidate 2's nfet_10v0_asym findings (decide by 2026-12-01)
- **Issue #207** (closed): Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts
- **PR #371**: layout: draw the ratified capacitor geometry (1.0/2.0 um) in all seven cells; re-fit marker, CN and VB
- **Issue #296** (closed): layout: draw the ratified legal capacitor geometry in all seven cells (clears DF.1c on all seven and PL.2_MV on candidate 2; re-fit the three base cells hardcoded MOSCAP marker and CN/VB straps)
- **PR #367**: test: pin numfmt.close tolerance and numfmt.logical_lines continuation rules
- **PR #366**: docs: note candidate-1 split-point exception in layout README
- **Issue #344** (closed): layout/README.md still says per-candidate geometry stays in each generate.py
- **Issue #340** (closed): sim/harness/tests/test_numfmt.py: no direct coverage for numfmt.close and numfmt.logical_lines
- **PR #363**: fix(sim): state the stored contract on post-manifest cleanup failure; refuse empty retab records
- **PR #361**: fix: remove stored run-dir copies once the evidence manifest lands
- **Issue #362** (closed): Evidence store: two diagnostics gaps left after the run-dir-consuming store (#356)
- **Issue #356** (closed): Runs since the 10-23 store-only rule commit raw sim bytes as well as storing them: find and fix the cause
- **PR #359**: fix(check): grandfather ruling-era manifests out of tracked-bytes rule
- **Issue #346** (closed): check:ci fails on main: check_artifact_manifests.py reports committed-and-stored bytes for sim/ artifacts

### 2026-11-16

- **PR #352**: fix: reject --analyze-report with --mode full-band; run its tests in a tmp checkout
- **Issue #351** (closed): array-slice-bench: test_analyze_report writes into the live evidence tree on regression; --analyze-report note is false under --mode full-band
- **PR #350**: sim: --analyze-report grades only, implying --no-write
- **Issue #349** (closed): sim: --analyze-report writes a record claiming the full 5-process PVT matrix while grading one process
- **PR #348**: fix(bench): write the report sha256 sidecar only when the full text was held
- **Issue #330** (closed): array-slice-bench --analyze-report writes a sidecar that attests only the elided text
- **PR #345**: spec: record scoped DRC exception for unmodified PDK PCell geometry
- **Issue #299** (closed): Operator ruling: candidate 2's unmodified PDK nfet_10v0_asym PCell trips 20 native sign-off rules that cannot be waived, hand-edited or substituted away
- **PR #343**: Consolidate the three candidate-1 split-grid generators into one point table
- **Issue #315** (closed): Consolidate three near-identical candidate-1 split-grid generators into a point table
- **PR #339**: fix(tests): expect the post-#326 remote sharding key in request shape assertions
- **Issue #333** (closed): check:ci red: RequestBatchOpts shape assertions reject the remote sharding key (PR #326)
- **Issue #337** (closed): main red: program-read-legs request tests not updated for the remote sharding key
- **PR #336**: docs: narrow the stale process-minimum caveats to the access axis and fix the check-header numbering
- **Issue #307** (closed): design/check-netlists.sh comment asserts no ratified record fixes the process-minimum geometry — stale once the capacitor-geometry record lands
- **PR #335**: refactor: consolidate the design checkers' duplicated SPICE helpers into numfmt
- **Issue #331** (closed): Consolidate duplicated SPICE helpers in design checkers into numfmt
- **PR #332**: fix(rtl): lint scrubbed flow reports for absolute host paths; collapse a $PDK_ROOT outside $HOME
- **PR #325**: fix(design): derive geometry-basis owner/status per entry from ratified capacitor levels
- **Issue #314** (closed): geometry-basis record cites closed #294 as a live owner for the capacitor divergences
- **PR #322**: Remove three test-only symbols: object_table, summarise, BIAS_BY_NAME
- **Issue #290** (closed): Remove three shipped symbols whose only consumer is a test: object_table, summarise, BIAS_BY_NAME

### 2026-11-15

- **PR #334**: docs: re-derive the ROADMAP snapshot from committed evidence
- **Issue #324** (closed): docs/ROADMAP.md T1-ladder paragraph will be stale after #323: 7 rows met incl. 3.analog, now 6 with 3.analog unmet
- **PR #329**: feat: generate run3_top chip-level reference netlist and pad table, checked against the spec sources
- **Issue #275** (closed): Run 3 test chip: chip-level reference netlist and machine-readable pad table, checked against the floorplan record
- **PR #327**: sim: commit klt reports with per-report sha256 sidecars at the last two raw write sites
- **Issue #283** (closed): Finish the klt coverage-elision policy: two write sites #271 left re-deriving the raw write
- **PR #326**: feat(sim): shard program-read-legs requests under the fleet's 3600s job ceiling
- **PR #323**: layout/signoff: commit native-deck DRC reports for all seven cells; grade 3.analog on the native verdict
- **Issue #295** (closed): layout/signoff: commit a native-deck DRC report for all seven cells and stop recording curated-only 'clean' as DRC clean
- **PR #319**: test: assert exactly one B-element card names each measured HV pad node
- **Issue #302** (closed): HV pad deck test: the `"B" in text` half of the measured-node assertion is vacuous
- **PR #311**: feat(sim): emit batch.capacity_wait_s from program-read-legs requests
- **Issue #317** (closed): check_artifact_manifests.py fails on main: 2026-11-06 re-qualification manifests store bytes that are also committed
- **PR #320**: docs: move WORK_LOG '## Archives' index to EOF so live entries stop nesting under it
- **Issue #304** (closed): WORK_LOG rotation: the '## Archives' index nests the whole live log under it
- **PR #318**: refactor: remove dead declarations left by numfmt and gen_blocks consolidations
- **PR #309**: refactor(rtl): dedupe the committed-report host-path scrubber
- **PR #308**: design: add drawn-vs-simulated geometry-basis gate with a recorded divergence set
- **PR #305**: spec: decision record pinning capacitor-geometry split levels to the process-minimum legal W/L
- **Issue #294** (closed): spec: decision record pinning the capacitor-geometry split levels to the process-minimum LEGAL W/L
- **Issue #292** (closed): Drawn bitcell geometry and the geometry the committed SPICE evidence was run at differ, and nothing compares them
- **Issue #285** (closed): Remove the duplicated host-path scrubber embedded in rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh
- **Issue #282** (closed): Remove dead module-level declarations left behind by the numfmt and gen_blocks consolidations
- **PR #291**: test: port test_hv_pad_protection.py from pytest to unittest
- **PR #298**: layout: draw the Candidate 3 G2x-capacitor bitcell (cell_candidate3_Amin_G2x)
- **Issue #310** (closed): check_artifact_manifests.py fails on main: 15,713 entries flagged 'bytes are committed AND stored'
- **Issue #306** (closed): check_artifact_manifests.py is red on main: 15.7k 'bytes are committed AND stored' findings across the 202610/202611 sim manifest families
- **Issue #276** (closed): tests/test_hv_pad_protection.py needs pytest, so check:ci cannot run it
- **PR #289**: docs: state the breakdown params' 12/3 provenance split in the roadmap
- **PR #286**: refactor(sim): delegate program-read-legs klt retry to the harness policy
- **PR #284**: fix: skip disposable .work/ scratch when publishing run evidence
- **Issue #278** (closed): docs/ROADMAP.md: breakdown-model row says "every parameter assumed"; 3 of 15 are provenance=literature
- **Issue #277** (closed): Remove the hand-rolled klt retry loop in sim/program-read-legs: harness/klt.py owns fleet-refusal retry and this driver opts out of it
- **Issue #274** (closed): Run 3 test chip: draw the Candidate 3 G2x-capacitor bitcell
- **Issue #270** (closed): Stop publishing the git-ignored .work/ scratch tree as evidence: 42% of tracked manifest bytes index disposable files

### 2026-11-14

- **PR #288**: layout: reach LVS match on candidate 2 at klt 0.9.2 and cross-check DRC against the PDK runset
- **PR #281**: feat(sim): elide klt coverage id lists from committed reports in four runners
- **PR #279**: feat: draw the three remaining Candidate 1 split-grid bitcells
- **PR #272**: docs: roadmap as of 2026-11-13
- **Issue #273** (closed): Run 3 test chip: draw the Candidate 1 split-variant bitcells (G2x capacitor, A2x access)
- **Issue #271** (closed): Elide klt coverage id lists before committing report.json: 101 MiB (33% of tracked bytes) of uniform 'characterization_without_limits' bookkeeping, already solved in array-slice-bench

### 2026-11-13

- **PR #261**: docs: add Run 3 bench fixture requirements note
- **Issue #260** (closed): Run 3 test chip: bench test board and fixture for breakdown and programming measurements

### 2026-11-10

- **PR #258**: feat(layout): draw candidate-2 bitcell on klt 0.9.1, record DRC/LVS gaps

### 2026-11-06

- **PR #253**: sim: re-qualify breakdown-model #130 V_bd sensitivity points under open_pdks f6eeac7d
- **PR #251**: rtl: add post-route SPEF-annotated 15-corner klt sta for the routed digital block
- **Issue #250** (closed): Post-route SPEF-annotated multi-corner klt sta for routed antifuse_digital_top
- **PR #249**: sim: re-qualify the cell-breakdown-model #74 opstart campaign under open_pdks f6eeac7d
- **PR #248**: sim: re-qualify breakdown-model C-infinity edge convergence campaign under open_pdks f6eeac7d
- **PR #247**: sim: re-qualify breakdown-model #74 convergence campaign under open_pdks f6eeac7d
- **PR #246**: sim: re-qualify breakdown-model static, trigger and read-bias benches under open_pdks f6eeac7d
- **PR #243**: sim: re-qualify device characterization under open_pdks f6eeac7d

### 2026-11-05

- **PR #241**: refactor(sim): share one .measure scalar parser via harness.numfmt
- **PR #240**: refactor(layout): share bitcell generator flow across candidates
- **Issue #239** (closed): Consolidate three duplicated .measure scalar parsers onto sim/harness/numfmt.py
- **Issue #238** (closed): Consolidate duplicated bitcell generate.py plumbing across candidate layouts
- **PR #236**: feat(design): add xschem-free analog cold start and --skip-regen
- **Issue #235** (closed): Add a worker-safe, single-corner analog cold-start entry point for the item-9 inventory

### 2026-10-30

- **PR #228**: refactor: share file-path module loader in sim/harness
- **Issue #227** (closed): Consolidate duplicated importlib module-loader boilerplate into sim/harness
- **Issue #204** (closed): First-principles breakdown models: gate-oxide V_bd/TDDB for all candidates and well-junction avalanche for Candidate 3
- **PR #231**: refactor: use shared gen_blocks plumbing in C3 junction model script
- **Issue #230** (closed): Remove duplicate generated-block plumbing in breakdown_c3_junction_model.py (use gen_blocks)
- **PR #218**: docs: model Candidate 3 well-junction avalanche per program-bias arrangement
- **Issue #208** (closed): Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists

### 2026-10-29

- **PR #183**: build: wire package.json test/check scripts to the repo's real checks
- **Issue #182** (closed): Wire package.json check scripts to the repo's real checks (currently vacuous exit 0)
- **PR #224**: refactor: share generated-table helpers between breakdown model scripts
- **Issue #222** (closed): Consolidate duplicated generated-block helpers in breakdown model scripts
- **PR #221**: docs: propose bare-pad PL approach for the program voltage with PVT pad-path evidence
- **Issue #210** (closed): Run 3 test chip: program-voltage (8-16 V) pad and protection approach
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

## Archives

- [2026-09](work_log/WORK_LOG_2026-09.md)
