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
- **#127**: Measure V_bd and carry Candidates 2 and 3 until then (operator ruling 2026-10-20)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#196**: T1 item 11 (power delivery, analog): replace the antenna-only ERC citation with a supply-net ERC + LVS compound citation

## In Progress

Issues currently being built (`loom:building`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#182**: Wire package.json check scripts to the repo's real checks (currently vacuous exit 0)
- **#197**: T1 item 2 (layout, analog): artifact-anchored envelope binding cell_candidate1.gds and its generator

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#198**: feat(signoff): cite item-2 analog layout envelope for cell_candidate1

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#183**: build: wire package.json test/check scripts to the repo's real checks

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#196**: T1 item 11 (power delivery, analog): replace the antenna-only ERC citation with a supply-net ERC + LVS compound citation *(curated)*
- **#197**: T1 item 2 (layout, analog): artifact-anchored envelope binding cell_candidate1.gds and its generator *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 1 |
| Curated | 6 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
