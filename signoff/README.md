# signoff/

This block's **T1 state, graded mechanically**. `signoff/report.json` is the
verdict of record — not a prose checklist, not a comment thread.

| File | What it is |
|---|---|
| `manifest.json` | The block manifest `klt signoff --manifest` grades: this block's `block` name, its `kind`, and the evidence envelope backing each T1 item. |
| `report.json` | The committed output of grading that manifest. Regenerate it, never hand-edit it. |
| `verify.sh` | Re-grades and asserts the committed report is still true. |

Regenerate and check:

```sh
klt signoff --manifest signoff/manifest.json --format json > signoff/report.json
./signoff/verify.sh
```

**Which `klt` build this verdict was graded with.** The committed
`signoff/report.json` was regenerated (issue #63) by klayout-tools
`0.6.0+g1eb3e4bfd0f5` (commit
`1eb3e4bfd0f5957bb643fdecfde26c7badea2c67`) -- the report's own
`build.version` / `build.git_commit` fields. It replaces a report graded by
`0.5.0+g32f69f811682`: the installed `klt` had moved to `0.6.0`, whose bundled
checklist hashes differently, so the committed report had stopped matching a
fresh grading run (`verify.sh` failed on `source_doc_content_hash`,
`build.*` and `grading_ruleset_id`, not on any evidence). Nothing about the
item set changed: still 22 rendered T1 rows, all `unmet` / `no_evidence`.
A build older than the one named here will not reproduce this report
byte-for-byte.

`klt signoff --manifest` exits **3** whenever any T1 item is `unmet`
(`tier: null`) and **0** only when every item is met. Exit 3 is a *verdict*,
not a tool failure — it is the current, correct exit status for this block.
`verify.sh` accepts 0 and 3 and fails on 1/2 (unreadable manifest or tiers
doc) or on any drift from the committed report.

## Current verdict

`tier: null` — **0 of 22 T1 items met**, graded against
`design-evidence-tiers.md` at
`sha256:a561c23904a849080951c0750291f0edd99eca3f014996a2378153616a83cdaa`
(the copy bundled in klayout-tools `0.6.0+g1eb3e4bfd0f5`, which is the
eleven-item checklist — item 11, "Power delivery (structural)", included).
Both values are copied from the committed `signoff/report.json`
(`source_doc_content_hash` and `build.version`); if a regenerated report
changes either, this paragraph moves with it.
Every item renders `unmet` with `reason: "no_evidence"`.

That is the honest state of this block, not a placeholder: apart from the
partial `klt sim` reports described in the next section, **no `klt` JSON
evidence envelope exists in this tree.** There is no `klt drc`, `lvs`,
`extract`, `yield`, `pex`, `sta`, `functional-verification`, `erc`, or
generic envelope to cite, and the only `klt sim` reports cover two access-device
quantities of two of the three cell candidates, so nothing could raise any row
above `no_evidence` without overstating it. The manifest therefore declares
`"evidence": {}` and cites nothing *to the grader*; the `klt sim` reports added
by issue #63 sit under the ungraded `supporting_evidence` key (next section).

## klt-native simulation evidence (issue #63): which rows moved, which did not

The PVT corner campaign's access-device bench (I_off, R_on) is now also
expressed as a checked-in `klt sim` request set
(`sim/cell-device-characterization/klt/`), run on the Spot batch fleet. Its
reports are real `klt sim` envelopes, listed under the manifest's
**`supporting_evidence`** key with pinned `content_hash`es.

**Rows that moved: none.** All 22 T1 rows remain `unmet` / `no_evidence`.
`supporting_evidence` is deliberately *not* an `evidence` key: `klt signoff`
ignores it, so it cannot move a row, and `verify.sh` checks that every entry
names a file in the tree whose sha256 still matches. The reasons no graded row
was claimed:

- **Item 5 (analog, `sim`)** asks for corner-matrix results "covering every
  spec row at its bound corners" with per-row pass/fail. This campaign
  characterises two inputs of `spec/architecture.md` sections 3-4 (`I_off` and
  `R_on` of the access device, for Candidates 1 and 3 only) against no ratified
  limit; the read-margin, `I_ref`, program-leg and sense-path rows have no
  testbench yet. Citing it would make the row green on a coverage claim the
  grader cannot check (the same trap rule 2 below describes).
- **Items 1, 2, 9, 10** accept any passing envelope; citing a sim report there
  would be exactly the false claim rule 2 forbids.
- **Item 6** needs `klt yield` Monte Carlo evidence; none was produced. Issue
  #66 later added a programming-yield Monte Carlo campaign
  (`sim/programming-yield/`), still **not cited** for this row, for three
  reasons. (1) Its evidence form is `klt sim` `monte_carlo` reports plus a
  per-sample success criterion applied by the experiment's own script
  (latched state, current bound, and a read-margin lookup against a table
  from a second request), not a `klt yield` envelope with per-measurement
  limits; a composite criterion is not a limit on any one measurement. (2)
  Every yield is conditional on **assumed** breakdown statistics
  (`design/breakdown/breakdown_params.spice`: nothing is `measured`), so a
  green item 6 would assert a statistical result about silicon that the
  model cannot support. (3) Candidate 3 has no read-decision criterion at
  the inherited placeholder bias (#75), so the campaign cannot span all
  three regions on the read side. Closing the row needs measured breakdown
  data in `measurements/` and a `klt yield` request whose limits express the
  criterion.
- **Item 8** (characterization report) needs a per-region `generic` envelope;
  none was produced. The per-region Markdown records stay the human-readable
  per-region result.
- **Candidate 2 (Region II) is not covered**: its fleet requests failed (see
  `sim/cell-device-characterization/README.md`, "klt sim campaign"), so
  `supporting_evidence` cites only the 16 passing Candidate 1 / Candidate 3
  reports. A cited sim report that does not span all three regions could not
  support a whole-block row regardless.


## Synthesis evidence (issue #60): which rows moved, which did not

`rtl/synth/antifuse_spi_regs.synth.report.json` is a `klt synthesize` response
for the digital partition's SPI register file (reproduction in `rtl/README.md`).
It is listed under `supporting_evidence` with a pinned `content_hash`, not
under `evidence`.

**Rows that moved: none.** All rows remain `unmet`; `report.json` is unchanged
because nothing graded changed.

- **Item 1 (digital)** is the row this evidence is for, but `klt signoff`
  (0.6.0 and the host's 0.7.1.dev) does not recognise a `klt synthesize`
  response: citing it under `1.digital` renders `unmet` /
  `unrecognized_envelope` instead of `no_evidence`, a worse-looking row with
  no more truth. It also covers only the SPI register file, not the global
  row/column decoders of the digital partition. Tool gap filed upstream as
  2AMLogic/klayout-tools#4015.
- **Item 9** stays `unmet`: it is graded on "some passing envelope was cited"
  with no relevance check (rule 2 below), the register-file bench emits
  `RESULT:` lines, not a `klt` envelope, and item 9 covers the whole block,
  whose analog benches are incomplete.

### Why this reads differently from the hand-maintained checklist

Issue #10's checkbox list marks items 1, 5, and 9 met. Those annotations are
about *artifacts that exist* — committed schematics and derived netlists, the
PVT corner campaign under `sim/cell-device-characterization/`, the committed
testbenches. They are not wrong about the tree. They are graded `unmet` here
because `klt signoff` grades only one thing: whether the item cites a
readable, passing, fresh `klt` JSON envelope. This repo's corner campaign is
run by its own harness (`sim/harness/`, ngspice) and records results as
Markdown evidence records, which no `klt` verb produces and `klt signoff`
cannot read.

**Neither reading supersedes the other on the underlying facts, and the
divergence is itself the finding**: the evidence this block has is real but
is not in the form the tier grader can check, so it cannot be mechanically
re-verified and cannot roll up into the fleet view. Closing that gap means
producing `klt`-native evidence (or, for item 8 only, a generic envelope),
not re-arguing the checkboxes.

## Block kind: `mixed-signal`

Declared `mixed-signal`, **not** `analog`. The ratified
`spec/architecture.md` puts genuine digital content inside this block's
boundary, so an `analog`-only declaration would grade the wrong column:

- §1.1 specifies the global row/column decode as a conventional binary
  decoder built from the `gf180mcu_fd_sc_mcu7t5v0` standard-cell library,
  running in the logic-voltage domain.
- §5 specifies an SPI slave (mode 0, 4-wire) with a byte-addressed register
  file (`ADDR_ROW`, `ADDR_COL`, `CTRL`, `PULSE_WIDTH`, `STATUS`, `RDATA`)
  and the arm-then-strobe program interlock sequencer.

This matches the kind issue #10 already anticipated ("mixed-signal (program
path + sense)"). A `mixed-signal` manifest renders both columns of the
per-kind items (1, 2, 5, 7, 11) once per partition — hence 22 rendered T1
rows rather than 11.

### Partition boundary

A mixed-signal claim must state which silicon each column's evidence covers.
The boundary is the **level shifters** of `spec/architecture.md` §1.1 and the
`PROG_EN`/`READ_EN` control interface of §1.2:

| Partition | Contains |
|---|---|
| **Digital** | SPI slave (`SCLK`/`MOSI`/`MISO`/`CS_N` pads, shift/capture logic), the register file, the program arm/strobe sequencer and its arm-timeout, and the global row/column binary decoders — everything on the logic-voltage side of the level shifters. Drives the one-hot row/column select lines and `PROG_EN`/`READ_EN`. |
| **Analog** | Everything on the far side of the level shifters: the level shifters themselves, the local high-voltage row/column pass-gate stages, the antifuse cell array, the program leg (ballast resistor + active current limit, §2) and the `VPP` rail, and the read leg's current-threshold sense amplifier and `I_ref` reference branch (§4). |

`RDATA` crosses back from the sense amplifier's comparator output into the
digital `STATUS`/`RDATA` registers; that comparator output is the analog
partition's boundary pin on the read side.

The analog partition's array, local pass-gate stage and level shifters are now
captured as design sources (`design/README.md`); the sense path, program leg,
digital partition and SPI slave are not, so the boundary above is still a
statement about the ratified architecture rather than a fully committed
netlist.

## Disclosures the grader reports but does not enforce

Two T1 items require the claimant to disclose coverage alongside the verdict,
because `klt signoff` reports those fields without grading on them:

- **Item 3 (DRC) — deck coverage.** A `met` verdict is `status: "clean"`
  alone; `coverage.layers_in_stream_without_rules`, `coverage.rules_skipped`
  and `coverage.deck_scope` are reported on the citation but never compared
  against the claim. **Nothing to disclose here yet**: item 3 is `unmet` with
  no citation, so no DRC coverage has been measured on this block at all.
- **Item 7 (post-layout) — device body bias.** A `pex` citation whose
  `body_bias.status` is `"unbiased"` still grades `met`, even though a
  resimulation of a netlist whose device bodies have no DC path is
  physically wrong rather than merely imprecise. **Nothing to disclose here
  yet**: item 7 is `unmet` with no citation.

Both disclosures become mandatory the moment those rows are cited. A future
`met` on either row is not evidence that its coverage was disclosed — it has
to be read out of the citation and stated in this file.

## Rules this directory holds itself to

1. **Every citation pins a `content_hash`.** An unpinned citation cannot have
   its freshness checked, and a passing report against a superseded netlist
   or layout is evidence of nothing. `verify.sh` rejects an unpinned entry
   before it ever reaches the grader — and rejects an evidence key that names
   no real T1 item, since `klt signoff` ignores an unrecognised key silently
   and a typo would otherwise read as an honest gap.
2. **Never cite an envelope that does not actually support the item.** Items
   1, 2, 9 and 10 have no `klt` verb behind them and are graded on "some
   passing envelope was cited" with no relevance check at all — any clean
   report turns those rows green. Making a row green that way is a false
   claim this repo's tooling cannot catch; the accurate `unmet` row stays.
3. **Item 7 takes `klt pex` only** (for this block's analog partition; its
   digital partition would also accept an SDF-annotated `klt
   functional-verification` run). A clean DRC or a pre-layout corner sim
   renders `wrong_kind`.
4. **Item 8 is the only item a `generic` envelope may satisfy.** Items 3-7
   reject `"kind": "generic"` outright. Item 8 stays `unmet` until an
   aggregated characterization artifact actually exists — and per this
   repo's `CLAUDE.md`, that artifact must report per grid region, since an
   aggregate that averages across splits is a bug, not a result.
   `sim/characterization-report/` now generates a per-region device
   characterization bundle, but it covers device characterization only and
   reports programming yield, full sense margin and retention as
   unmeasured (status `incomplete`), so it does not meet item 8's contract;
   no envelope is cited and item 8 stays `unmet`.
5. **`report.json` is regenerated, never edited.** If `verify.sh` fails, the
   verdict changed; re-run the grader, read the diff, and update this file's
   claim to match.

## CI

`verify.sh` is the command CI should run. This repo has no
`.github/workflows/` on `main` yet — bootstrapping it is issue #14, with PR
#15 open against it — so this check is not yet wired to a PR-blocking job. It
is written to be dropped straight into that workflow (or into
`package.json`'s `check:ci` hook, which #15 also touches) with no
adaptation: it needs only `klt` and `python3`, reads nothing outside the
repo, and prints the exact remediation command on failure.
