# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts

## Important

`loom:important`; taken before unlabelled work.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)
- **#211**: Run 3 test chip: full-chip assembly with DRC/LVS through klt

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#282**: Remove dead module-level declarations left behind by the numfmt and gen_blocks consolidations
- **#285**: Remove the duplicated host-path scrubber embedded in rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh

## In Progress

Issues currently being built (`loom:building`).

- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak
- **#276**: tests/test_hv_pad_protection.py needs pytest, so check:ci cannot run it

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan
- **#291**: test: port test_hv_pad_protection.py from pytest to unittest

## Proposed

Issues carrying `loom:curated`.

- **#12**: Champion: Merge-Risk Hold Digest *(curated)*
- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts *(curated)*
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak *(curated)*
- **#275**: Run 3 test chip: chip-level reference netlist and machine-readable pad table, checked against the floorplan record *(curated)*
- **#276**: tests/test_hv_pad_protection.py needs pytest, so check:ci cannot run it *(curated)*
- **#283**: Finish the klt coverage-elision policy: two write sites #271 left re-deriving the raw write *(curated)*
- **#292**: Drawn bitcell geometry and the geometry the committed SPICE evidence was run at differ (cand 2 access 8 µm vs simulated 25 µm; capacitor ≈4× less area on all three) and nothing compares them *(curated)*
- **#294**: spec: decision record pinning the capacitor-geometry split levels to the process-minimum LEGAL W/L (both drawn levels, 0.42/0.84 um, violate the 1 um MOSCAP minimum) *(curated)*
- **#300**: Decide whether sim/program-read-legs requests should carry a klt-side batch.capacity_wait_s *(curated)*

## Proposed (Architect / Hermit)

- **#267**: Remove sim/run_corners.py: dispatcher registers 4 of 8 experiments and only forwards to drivers that run directly *(hermit)*
- **#280**: Remove the second copy of the GDS drift-check driver in layout/cell_candidate2/generate.py (reuse bitcell_gen) *(hermit)*
- **#290**: Remove three shipped symbols whose only consumer is a test: object_table, summarise, BIAS_BY_NAME *(hermit)*
- **#301**: Route run_klt_campaign through harness.klt; drop manual --resume resubmit *(hermit)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 1 |
| Important | 3 |
| Ready (`loom:issue`) | 3 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 2 |
| Curated | 13 |
| Architect / Hermit proposals | 4 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
