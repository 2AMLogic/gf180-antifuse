# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#183**: build: wire package.json test/check scripts to the repo's real checks

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)
- **#204**: First-principles breakdown models: gate-oxide V_bd/TDDB for all candidates and well-junction avalanche for Candidate 3
- **#205**: Model gate-oxide V_bd and TDDB versus pulse width for thin and thick gf180 oxides
- **#208**: Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists
- **#209**: Model post-breakdown filament resistance and programmed-cell read margin

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#209**: Model post-breakdown filament resistance and programmed-cell read margin

## In Progress

Issues currently being built (`loom:building`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#182**: Wire package.json check scripts to the repo's real checks (currently vacuous exit 0)
- **#205**: Model gate-oxide V_bd and TDDB versus pulse width for thin and thick gf180 oxides
- **#206**: Run 3 test chip: top-level floorplan, instance counts and pad budget
- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts
- **#208**: Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists
- **#210**: Run 3 test chip: program-voltage (8-16 V) pad and protection approach

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#183**: build: wire package.json test/check scripts to the repo's real checks

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#205**: Model gate-oxide V_bd and TDDB versus pulse width for thin and thick gf180 oxides *(curated)*
- **#206**: Run 3 test chip: top-level floorplan, instance counts and pad budget *(curated)*
- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts *(curated)*
- **#208**: Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists *(curated)*
- **#209**: Model post-breakdown filament resistance and programmed-cell read margin *(curated)*
- **#210**: Run 3 test chip: program-voltage (8-16 V) pad and protection approach *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 6 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 7 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 1 |
| Curated | 10 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
