# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts *(held)*

## Important

`loom:important`; taken before unlabelled work.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip
- **#211**: Run 3 test chip: full-chip assembly with DRC/LVS through klt *(held)*
- **#296**: layout: draw the ratified legal capacitor geometry in all seven cells (clears DF.1c on all seven and PL.2_MV on candidate 2; re-fit the three base cells hardcoded MOSCAP marker and CN/VB straps)
- **#372**: Run 3 fallback: a variant that passes the native runset without candidate 2's nfet_10v0_asym findings (decide by 2026-12-01)

## Ready

Human-approved issues (`loom:issue`) ready for implementation — excluding held (`loom:blocked`/`loom:operator`/`loom:frozen`), `loom:building`, and issues closed by an open `loom:pr` PR (listed under Approved).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)

## In Progress

Issues currently being built (`loom:building`).

- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak
- **#296**: layout: draw the ratified legal capacitor geometry in all seven cells (clears DF.1c on all seven and PL.2_MV on candidate 2; re-fit the three base cells hardcoded MOSCAP marker and CN/VB straps)
- **#372**: Run 3 fallback: a variant that passes the native runset without candidate 2's nfet_10v0_asym findings (decide by 2026-12-01)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#347**: docs: sourced wafer.space Run 3 precheck reading (would-reject verdict)

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan — closes #255
- **#371**: layout: draw the ratified capacitor geometry (1.0/2.0 um) in all seven cells; re-fit marker, CN and VB — closes #296

## Proposed

Issues carrying `loom:curated`.

- **#12**: Champion: Merge-Risk Hold Digest *(curated)* *(held)*
- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)* *(held)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)* *(held)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)* *(held)*
- **#207**: Run 3 test chip: Candidate 2 and Candidate 3 bitcell layouts *(curated)* *(held)*
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak *(curated)*
- **#296**: layout: draw the ratified legal capacitor geometry in all seven cells (clears DF.1c on all seven and PL.2_MV on candidate 2; re-fit the three base cells hardcoded MOSCAP marker and CN/VB straps) *(curated)*
- **#300**: Decide whether sim/program-read-legs requests should carry a klt-side batch.capacity_wait_s *(curated)* *(held)*
- **#313**: sim/program-read-legs: capacity_wait_s spends the same per-submit subprocess budget as the run, and a subprocess timeout is not retried *(curated)* *(held)*
- **#316**: Follow-on: establish the foreign-host re-run byte-identity evidence for the shared report scrubber (PR #309 / #285 step 5) *(curated)* *(held)*
- **#338**: wafer.space: precheck treatment and foundry conversation on the unmodified nfet_10v0_asym PCell's CO.4/DF.6_MV/PL.4_MV findings (#299) *(curated)* *(held)*
- **#372**: Run 3 fallback: a variant that passes the native runset without candidate 2's nfet_10v0_asym findings (decide by 2026-12-01) *(curated)*

## Proposed (Architect / Hermit)

- **#267**: Remove sim/run_corners.py: dispatcher registers 4 of 8 experiments and only forwards to drivers that run directly *(hermit)* *(held)*
- **#280**: Remove the second copy of the GDS drift-check driver in layout/cell_candidate2/generate.py (reuse bitcell_gen) *(hermit)* *(held)*
- **#301**: Route run_klt_campaign through harness.klt; drop manual --resume resubmit *(hermit)* *(held)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers) *(held)*
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 1 |
| Important | 5 |
| Ready (`loom:issue`, net of holds/building/merge-pending) | 1 |
| In Progress (`loom:building`) | 3 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 2 |
| Curated | 13 |
| Architect / Hermit proposals | 3 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
