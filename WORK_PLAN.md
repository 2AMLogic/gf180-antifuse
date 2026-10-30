# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)
- **#204**: First-principles breakdown models: gate-oxide V_bd/TDDB for all candidates and well-junction avalanche for Candidate 3
- **#208**: Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#227**: Consolidate duplicated importlib module-loader boilerplate into sim/harness

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#218**: docs: model Candidate 3 well-junction avalanche per program-bias arrangement
- **#228**: refactor: share file-path module loader in sim/harness

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

_None._

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts *(curated)*
- **#208**: Model Candidate 3 well-junction avalanche breakdown and decide whether an in-rating program scheme exists *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#203**: wafer.space Run 3 quarter slot: cut-down antifuse breakdown test chip (GDS due 2026-12-16)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 4 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 0 |
| Curated | 6 |
| Architect / Hermit proposals | 0 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
