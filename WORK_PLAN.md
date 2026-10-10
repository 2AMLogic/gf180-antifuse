# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

- **#67**: sim: express the PVT corner campaign as klt sim requests (#63)
- **#68**: design: program leg + read leg schematics, benches, ballast record (#65)
- **#69**: design: N=32 array, local HV pass-gate stage and level shifters as xschem sources + slice bench (#64)
- **#76**: design: behavioral breakdown-augmented cell model and single-cell bench (#62)
- **#80**: spec: supply-domain inventory decision record
- **#81**: sim: reproducible per-split device characterization report (#72)
- **#82**: spec: measurement matrix and extraction protocol for yield, read margin and retention
- **#85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **#87**: docs: Auditor worker deployment discovery and handoff (#84)

## Operator Priority

Issues the operator starred (`loom:operator-priority`); land these first.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition)
- **#59**: layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition)
- **#62**: design: behavioral breakdown-augmented model for the three antifuse cell candidates
- **#63**: sim: express the PVT corner campaign as a klt sim request and cite it in the signoff manifest
- **#64**: design: capture the N=32 array, local HV pass-gate MUX and level shifters as xschem sources (analog partition)
- **#65**: design: program leg (ballast + current limit) and read leg (sense amp + I_ref) schematics with worst-case margin bench
- **#72**: sim: reproducible per-split characterization report for T1 item 8
- **#77**: spec: supply-domain inventory (net, voltage class, region, owner) for T1 item 11
- **#78**: spec: measurement matrix and extraction protocol for yield, read margin and retention per grid region
- **#79**: docs: README spec table and reproduction section for T1 item 10
- **#84**: Auditor Capability Request: klt unavailable for signoff verification

## In Progress

Issues currently being built (`loom:building`).

_None._

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#67**: sim: express the PVT corner campaign as klt sim requests (#63)
- **#68**: design: program leg + read leg schematics, benches, ballast record (#65)
- **#69**: design: N=32 array, local HV pass-gate stage and level shifters as xschem sources + slice bench (#64)
- **#76**: design: behavioral breakdown-augmented cell model and single-cell bench (#62)
- **#80**: spec: supply-domain inventory decision record
- **#81**: sim: reproducible per-split device characterization report (#72)
- **#82**: spec: measurement matrix and extraction protocol for yield, read margin and retention
- **#83**: docs: README spec table and reproduction section
- **#85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **#87**: docs: Auditor worker deployment discovery and handoff (#84)

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition) *(curated)*
- **#59**: layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition) *(curated)*
- **#62**: design: behavioral breakdown-augmented model for the three antifuse cell candidates *(curated)*
- **#63**: sim: express the PVT corner campaign as a klt sim request and cite it in the signoff manifest *(curated)*
- **#64**: design: capture the N=32 array, local HV pass-gate MUX and level shifters as xschem sources (analog partition) *(curated)*
- **#65**: design: program leg (ballast + current limit) and read leg (sense amp + I_ref) schematics with worst-case margin bench *(curated)*
- **#72**: sim: reproducible per-split characterization report for T1 item 8 *(curated)*
- **#77**: spec: supply-domain inventory (net, voltage class, region, owner) for T1 item 11 *(curated)*
- **#78**: spec: measurement matrix and extraction protocol for yield, read margin and retention per grid region *(curated)*
- **#79**: docs: README spec table and reproduction section for T1 item 10 *(curated)*
- **#84**: Auditor Capability Request: klt unavailable for signoff verification *(curated)*

## Proposed (Architect / Hermit)

- **#66**: sim: programming-yield Monte Carlo campaign, yield-vs-condition per grid region (T1 item 6) *(architect)*
- **#73**: sim: integrated program-to-read transition and voltage-stress bench *(architect)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Tier | Count |
|------|-------|
| Operator merge-risk holds | 1 |
| Operator priority | 0 |
| Ready (`loom:issue`) | 3 |
| In Progress (`loom:building`) | 0 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 10 |
| Curated | 7 |
| Architect / Hermit proposals | 5 |
| Active epics | 1 |

<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
