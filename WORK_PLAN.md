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

Human-approved issues ready for implementation (`loom:issue`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)

## In Progress

Issues currently being built (`loom:building`).

- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak
- **#443**: signoff: manifest still pins the pre-#296 GDS hash, so 4.analog and 11.analog grade stale_evidence and verify.sh fails on main
- **#445**: Digital: klt functional-verification of the routed antifuse_digital_top netlist (item 5 digital's missing report; groundwork for item 7 digital)
- **#446**: Digital timing: close setup at ss_125C_1v62 and ss_n40C_1v62 on the routed antifuse_digital_top (bounded design iteration; 5.digital stays uncited)
- **#447**: T1 item 7 (analog) probe: klt pex on the drawn bitcells and a post-layout re-run of the access-device bench

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#347**: docs: sourced wafer.space Run 3 precheck reading (would-reject verdict)
- **#455**: verification(rtl): zero-delay gate-level functional-verification of the routed digital top (21/21)
- **#456**: fix(rtl): close setup at both 1.62 V corners by re-routing with slow-corner optimization liberty

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#256**: docs(spec): propose constant-voltage TDDB and sub-programming soak plan
- **#451**: fix: re-pin analog signoff evidence to post-#296 GDS hash and guard pins in check:ci

## Proposed

Issues carrying `loom:curated`.

- **#12**: Champion: Merge-Risk Hold Digest *(curated)*
- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*
- **#117**: T1 items 1 and 9 (analog partition): attest the cell sources and testbenches with klt signoff --attest *(curated)*
- **#176**: T1 item 4 (LVS clean, digital partition): klt lvs against the gate-level netlist with power_connectivity *(curated)*
- **#255**: Measurement plan: constant-voltage time-to-breakdown statistics (Weibull slope, voltage acceleration) and a sub-programming soak *(curated)*
- **#313**: sim/program-read-legs: capacity_wait_s spends the same per-submit subprocess budget as the run, and a subprocess timeout is not retried *(curated)*
- **#316**: Follow-on: establish the foreign-host re-run byte-identity evidence for the shared report scrubber (PR #309 / #285 step 5) *(curated)*
- **#338**: wafer.space: precheck treatment and foundry conversation on the unmodified nfet_10v0_asym PCell's CO.4/DF.6_MV/PL.4_MV findings (#299) *(curated)*
- **#443**: signoff: manifest still pins the pre-#296 GDS hash, so 4.analog and 11.analog grade stale_evidence and verify.sh fails on main *(curated)*
- **#444**: design/regen-netlists.sh: export through klt netlist instead of raw xschem so the item-1 freshness check can run on a worker (unblocks #117) *(curated)*
- **#445**: Digital: klt functional-verification of the routed antifuse_digital_top netlist (item 5 digital's missing report; groundwork for item 7 digital) *(curated)*
- **#446**: Digital timing: close setup at ss_125C_1v62 and ss_n40C_1v62 on the routed antifuse_digital_top (bounded design iteration; 5.digital stays uncited) *(curated)*
- **#447**: T1 item 7 (analog) probe: klt pex on the drawn bitcells and a post-layout re-run of the access-device bench *(curated)*

## Proposed (Architect / Hermit)

- **#267**: Remove sim/run_corners.py: dispatcher registers 4 of 8 experiments and only forwards to drivers that run directly *(hermit)*
- **#301**: Route run_klt_campaign through harness.klt; drop manual --resume resubmit *(hermit)*
- **#454**: Remove the unused Run 3 pad helper that puts L37–L48 on the wrong edge *(hermit)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)
- **#203**: wafer.space Run 3 quarter slot (space not yet secured; GDS 2026-12-16 only if obtained): cut-down antifuse breakdown test chip

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 1 |
| In Progress (`loom:building`) | 5 |
| PRs awaiting review | 3 |
| Approved PRs awaiting merge | 2 |
| Curated | 14 |
| Architect / Hermit proposals | 3 |
| Active epics | 2 |
<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
