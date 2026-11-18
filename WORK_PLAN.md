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

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)

## In Progress

Issues currently being built (`loom:building`).

- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak
- **#404**: Chip-level native DRC findings in repo-drawn geometry (antenna, die-level density, CUP.2) have no tracking work
- **#414**: Geometry-claims checker does not tie readme_quote's numbers to bbox_um — a coordinated prose+sidecar edit still passes

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#347**: docs: sourced wafer.space Run 3 precheck reading (would-reject verdict)
- **#416**: layout: fix the run3 chip-level findings the precheck's own stages enforce
- **#417**: checker: pin readme_quote numerals to bbox_um via per-claim quote_values

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan — closes #255

## Proposed

Issues carrying `loom:curated`.

- **#12**: Champion: Merge-Risk Hold Digest *(curated)* *(held)*
- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)* *(held)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)* *(held)*
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak *(curated)*
- **#313**: sim/program-read-legs: capacity_wait_s spends the same per-submit subprocess budget as the run, and a subprocess timeout is not retried *(curated)*
- **#316**: Follow-on: establish the foreign-host re-run byte-identity evidence for the shared report scrubber (PR #309 / #285 step 5) *(curated)*
- **#338**: wafer.space: precheck treatment and foundry conversation on the unmodified nfet_10v0_asym PCell's CO.4/DF.6_MV/PL.4_MV findings (#299) *(curated)*
- **#404**: Chip-level native DRC findings in repo-drawn geometry (antenna, die-level density, CUP.2) have no tracking work *(curated)*
- **#414**: Geometry-claims checker does not tie readme_quote's numbers to bbox_um — a coordinated prose+sidecar edit still passes *(curated)*

## Proposed (Architect / Hermit)

- **#267**: Remove sim/run_corners.py: dispatcher registers 4 of 8 experiments and only forwards to drivers that run directly *(hermit)*
- **#301**: Route run_klt_campaign through harness.klt; drop manual --resume resubmit *(hermit)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers) *(held)*
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 1 |
| Curated | 11 |
| Architect / Hermit proposals | 2 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
