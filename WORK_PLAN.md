# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs stuck under a `loom:operator` merge-risk hold — implementation work is done, only a human merge decision is missing.

_None._

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

_None._

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition)
- **#64**: design: capture the N=32 array, local HV pass-gate MUX and level shifters as xschem sources (analog partition)
- **#65**: design: program leg (ballast + current limit) and read leg (sense amp + I_ref) schematics with worst-case margin bench
- **#79**: docs: README spec table and reproduction section for T1 item 10

## In Progress

Issues currently being built (`loom:building`).

- **#66**: sim: programming-yield Monte Carlo campaign, yield-vs-condition per grid region (T1 item 6)

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

- **#68**: design: program leg + read leg schematics, benches, ballast record (#65)

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **#88**: sim: Candidate 2 klt campaign via version-matched client; regenerate signoff (#63)

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition) *(curated)*
- **#59**: layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition) *(curated)*
- **#63**: sim: express the PVT corner campaign as a klt sim request and cite it in the signoff manifest *(curated)*
- **#64**: design: capture the N=32 array, local HV pass-gate MUX and level shifters as xschem sources (analog partition) *(curated)*
- **#65**: design: program leg (ballast + current limit) and read leg (sense amp + I_ref) schematics with worst-case margin bench *(curated)*
- **#79**: docs: README spec table and reproduction section for T1 item 10 *(curated)*

## Proposed (Architect / Hermit)

- **#73**: sim: integrated program-to-read transition and voltage-stress bench *(architect)*

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 0 |
| Very important | 0 |
| Important | 0 |
| Ready (`loom:issue`) | 5 |
| In Progress (`loom:building`) | 1 |
| PRs awaiting review | 1 |
| Approved PRs awaiting merge | 2 |
| Curated | 7 |
| Architect / Hermit proposals | 1 |
| Active epics | 1 |

<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
