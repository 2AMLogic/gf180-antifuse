# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Ready

Human-approved issues ready for implementation (`loom:issue`).

_None._

## In Progress

Issues currently being built (`loom:building`).

- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#553**: Assemble and verify the addressed 1,024-cell GF180 analog array
- **#554**: Cite reproducible full-array GDS for analog layout item 2

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan

## Proposed

Issues carrying `loom:curated`.

- **#12**: Champion: Merge-Risk Hold Digest *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#118**: T1 item 10: attest repo hygiene once the PR-blocking CI workflow lands *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak *(curated)*
- **#313**: sim/program-read-legs: capacity_wait_s spends the same per-submit subprocess budget as the run, and a subprocess timeout is not retried *(curated)*
- **#316**: Follow-on: establish the foreign-host re-run byte-identity evidence for the shared report scrubber (PR #309 / #285 step 5) *(curated)*
- **#338**: wafer.space: precheck treatment and foundry conversation on the unmodified nfet_10v0_asym PCell's CO.4/DF.6_MV/PL.4_MV findings (#299) *(curated)*
- **#558**: run3_top README geometry basis still says the netlist disagrees with the drawn cells until #296 lands *(curated)*

## Proposed (Architect / Hermit)

- **#454**: Remove the unused Run 3 pad helper that puts L37–L48 on the wrong edge *(hermit)*
- **#560**: Draw each Run 3 top-edge power pad in a single strip *(hermit)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 1 |
| Ready (`loom:issue`) | 0 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 2 |
| Approved PRs awaiting merge | 1 |
| Curated | 9 |
| Architect / Hermit proposals | 2 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
