# Work Plan

<!-- guide:plan-body:start -->
## Operator Attention: Merge-Risk-Hold Pileup

Judge-approved PRs under a hold (`loom:blocked` or `loom:operator`) — only a human merge decision is missing.

- **#85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **#88**: sim: Candidate 2 klt campaign via version-matched client; regenerate signoff (#63)
- **#92**: design+sim: Candidate 3 read bias (n-well tied to read rail) with PVT evidence
- **#94**: design: program bias scheme vs access-device ratings; PROPOSED decision record (#90)

## Very Important

`loom:very-important` (one counts per workspace); every stage takes these first.

_None._

## Important

`loom:important`; taken before unlabelled work.

- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition)
- **#59**: layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition)

## Ready

Human-approved issues ready for implementation (`loom:issue`).

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4)
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition)

## In Progress

Issues currently being built (`loom:building`).

- **#73**: sim: integrated program-to-read transition and voltage-stress bench
- **#90**: design: program-leg access-device overstress at assumed V_bd; Candidate 2 not programmable via BL-driven leg

## PRs Awaiting Review

PRs waiting on Judge (`loom:review-requested`).

_None._

## Approved (Awaiting Merge)

PRs that passed review and are queued for Champion auto-merge (`loom:pr`).

- **#85**: layout: first drawn candidate-1 bitcell with klt drc (T1 2.analog, 3.analog); LVS blocked upstream
- **#88**: sim: Candidate 2 klt campaign via version-matched client; regenerate signoff (#63)
- **#92**: design+sim: Candidate 3 read bias (n-well tied to read rail) with PVT evidence
- **#94**: design: program bias scheme vs access-device ratings; PROPOSED decision record (#90)

## Proposed

Issues carrying `loom:curated`.

- **#14**: CI: bootstrap a PR-blocking workflow, routed to the self-hosted runner (2am#525 AC4) *(curated)*
- **#58**: design: SPI slave register file RTL and bench per architecture §5 (T1 items 1 and 9, digital partition) *(curated)*
- **#59**: layout: first drawn bitcell (candidate 1) with klt drc and klt lvs (T1 items 2, 3, 4, analog partition) *(curated)*
- **#63**: sim: express the PVT corner campaign as a klt sim request and cite it in the signoff manifest *(curated)*
- **#75**: design: Candidate 3 read bias -- placeholder WL=0 V cannot read a programmed cell (I_prog_min undefined) *(curated)*
- **#90**: design: program-leg access-device overstress at assumed V_bd; Candidate 2 not programmable via BL-driven leg *(curated)*
- **#99**: Re-qualify reference sim records under open_pdks f6eeac7 as new records *(curated)*

## Proposed (Architect / Hermit)

_None._

## Epics

- **#10**: Track the gap to T1 sim-validated / bronze (klayout-tools design-evidence tiers)

## Backlog Balance

| Bucket | Count |
|------|-------|
| Operator merge-risk holds | 4 |
| Very important | 0 |
| Important | 2 |
| Ready (`loom:issue`) | 2 |
| In Progress (`loom:building`) | 2 |
| PRs awaiting review | 0 |
| Approved PRs awaiting merge | 4 |
| Curated | 7 |
| Architect / Hermit proposals | 0 |
| Active epics | 1 |

<!-- guide:plan-body:end -->

The sections above reflect labels. Issue #14 already has implementation PR #15,
which is awaiting operator-mechanical work with a failing design netlist check;
continue that PR rather than starting another implementation. Epic #10 uses
signoff/report.json as its verdict of record; its historical checklist is superseded.
