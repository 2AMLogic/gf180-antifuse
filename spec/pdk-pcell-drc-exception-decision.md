# Decision Record: Scoped DRC Exception for Unmodified PDK PCell Geometry

**Status**: Ratified. Operator ruling of 2026-11-15 (@rjwalters, attended
`/fleet:decide` session, round `20261111-r14`, question q105, recorded on
#299): option (b) — "Ratify a scoped exception in spec/ for findings inside
unmodified PDK PCell geometry only; negotiate with the foundry later." This
record writes that ruling down as enforceable text. It departs from no
ratified text because none existed: at this record's base (`2ca60fce`,
re-verified 2026-11-16, matching the curation's grep at `6dbddcc3`)
`git grep -niE "drc" -- spec/` matches only incidental lines inside
`spec/capacitor-geometry-decision.md` (71, 173-174, 220, 256, 284, 289) —
**no ratified spec document states a DRC-clean target at all.** This record
therefore **creates** the standard for one bounded class of finding on the
operator's authority; it relaxes nothing. It is not a `-proposed` record: the
operator has ruled. Per the ruling it still goes through repo review and any
ratification hold.
**Date**: 2026-11-16 (ruling dated 2026-11-15)
**Scope**: Native-deck DRC findings whose geometry was emitted inside an
unmodified PDK PCell instance (defined operationally below), on this repo's
gf180mcu cells. It changes how such findings are **dispositioned**; it
changes no geometry, no generator, no committed report, no waiver, and no
rule deck. The repo's no-waiver rule stays in force for every shape this
repo can change — every repo-drawn finding remains a violation to fix.
**Evidence**: the committed cross-check report
`layout/cell_candidate2/drc_crosscheck_report.json` (`klt drc --engine both
--deck gf180mcu --top cell_candidate2 --pdk gf180mcuA --deck-var
decks=all,-mslot`, released `klayout-tools==0.9.2`, KLayout 0.30.13, PDK
`gf180mcuA` `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, native
deck tree hash `sha256:8af3b4875893f3ffbff639bd7e2966c5e3b9b27f70d03e86d6da46ca9510fbc4`),
first measured 2026-11-14 (#299), re-verified 2026-11-16 at `6dbddcc3`
(Curator) and again at this record's base `2ca60fce` (Builder) — census
unchanged. Coverage of candidates 1 and 3 measured the same day from their
committed reports.

## Problem

Candidate 2's access device is the PDK's own drain-extended
`nfet_10v0_asym`, instantiated by `klt gen --pdk-pcell` from parameters only.
The PDK's **own native sign-off runset** flags 20 findings inside that PCell:
`CO.4` x16, `DF.6_MV` x2, `PL.4_MV` x2 (census pinned below). PR #288
cross-checked the 16 `CO.4` markers against the foundry runset: they are
real, not the false positives klayout-tools' docs describe, and the ready
made waiver documented upstream was deliberately **not** applied.

Three routes out of these findings exist, and each is forbidden by this
repo's standing rules:

1. **Waive them** (or `--deck-var` a rule off) — deletes the evidence; the
   committed rollup's `waived_count: 0` is part of candidate 2's recorded
   state, and #295 (merged as PR #323) exists precisely so a report's
   `status` cannot overstate a cell's DRC state.
2. **Hand-edit the PCell geometry** — the geometry belongs to the PDK's
   generator; editing it by hand is a change this repo's flow does not make.
3. **Substitute the device** — swaps the access device the schematic
   ratified.

None of these is a Builder's call, which is why this was an operator ruling
rather than a task. Meanwhile nothing in `spec/` states what these findings
*are*: the standard they fail lives only in issue prose (#207's acceptance
criteria), `layout/README.md` verdict tables and `docs/ROADMAP.md` — none of
which is ratified text an agent is forbidden to relax. Until this record,
there was nowhere the disposition could be *read from*, and conversely no
boundary that stopped a repo-drawn violation later being blamed on "the
PDK's cell". Both halves are fixed below: the exception is written down, and
its boundary is a runnable test, not an adjective.

## Decision

A native-deck DRC finding is **covered** by this exception — dispositioned
as "inside unmodified PDK PCell geometry: recorded, reported as measured,
and not a blocker at cell level" — if and only if both of these hold:

1. **Provenance of the geometry**: the violating geometry was emitted
   *inside* a PDK PCell instance created by `klt gen --pdk-pcell` from
   parameters only, with **no post-generation edit of any shape inside that
   instance**. The repo's generators may place, strap and connect the
   instance; they may not move, resize or redraw anything the PCell drew.
2. **Operational test**: the finding's `cell` attribute in the committed
   native report is the PCell's own cell name (the cell the
   `--pdk-pcell` invocation emits, e.g. `nfet_10v0_asym` — a cell name this
   repo never draws under), and the composed cell's generator passes only
   parameters to that invocation.

Everything else — every finding on a shape this repo drew, placed or
composed — is **not covered** and remains a violation to fix.

### Enumerating coverage from a committed report

```bash
# covered findings = those whose `cell` is the PDK PCell's own cell name
python3 -I -c "import json,collections,sys; d=json.load(open(sys.argv[1])); \
  print(collections.Counter((v['cell'], v['rule']) for v in d['reports']['native']['violations']))" \
  layout/cell_candidate2/drc_crosscheck_report.json
```

Rows whose cell is a PDK PCell's own cell name are covered; all other rows
are not. The key is `cell`, deliberately, and **not** `source_cell`: the
native report leaves `source_cell` `null` on all 27 findings and carries no
`source_cell_rollup` — only the *curated* report populates those fields, so
a classifier keyed on `source_cell` would silently match nothing. In the
native report, `cell` *is* the attribution of where the geometry lives.

### Why `klt gen mos_array` is repo-drawn and `--pdk-pcell` is the PDK's

The line is **who can change the geometry without hand-editing shapes**.

- A `klt gen mos_array` block is **this repo's geometry**: its W/L are
  parameters this repo picks. #294 ratified the capacitor levels and #296
  redraws them — that is the repo changing its own geometry through its own
  flow, which is exactly what the no-waiver rule governs.
- A `--pdk-pcell` instance's internal construction is **the PDK's**: the
  PDK's own generator script draws the stripes, contacts and gates inside
  the instance, and this repo can pass only the parameters the PCell
  exposes. Measured contrast, both on candidate 2: the capacitor's 0.42 um
  COMP width (`cap__core`, the `DF.1c` finding) is a generator parameter
  this repo controls; the 0.22 um drain-stripe contact geometry that `CO.4`
  fires on is internal PCell construction — `layout/cell_candidate2/generate.py`
  (lines 96-99) passes only `{"w": W_ACC, "l": L_ACC}` to
  `klt gen --pdk-pcell gf180mcu_klayoutapi/nfet_10v0_asym`, and no exposed
  parameter moves the contacts.

### The covered census, pinned as a dated snapshot

From `layout/cell_candidate2/drc_crosscheck_report.json`, provenance as in
the Evidence preamble:

| Rule | Report `description` (verbatim) | Cell | Count |
|---|---|---|---|
| `CO.4` | `CO.4 : COMP overlap of contact. : 0.07µm` | `nfet_10v0_asym` | 16 |
| `DF.6_MV` | `DF.6_MV : Min. COMP extend beyond gate (it also means source/drain overhang). : 0.4µm` | `nfet_10v0_asym` | 2 |
| `PL.4_MV` | `PL.4_MV : Extension beyond COMP to form Poly2 end cap. : 0.22µm` | `nfet_10v0_asym` | 2 |

Total: 20 covered findings, all inside `nfet_10v0_asym`, measured
2026-11-14, re-verified 2026-11-16 at `6dbddcc3` and again at `2ca60fce`.
The same report carries, **not covered**, `cap__core` {`DF.1c`, `PL.2_MV`}
(2), and `cell_candidate2` {`DBU`, `M1.4`, `M2.4`, `M3.4`, `MT30.7`} (5) —
27 findings reported in total, all still reported.

**A changed census must be re-recorded against the new report, never
assumed covered.** The exception attaches to the *class* (findings inside
unmodified PDK PCell geometry), not to the count: if a klt or PDK update
changes which rules fire inside the PCell — new rules, vanished rules,
different counts — the new census is measured, recorded here or in the
report's own evidence trail, and dispositioned afresh. Coverage is decided
by the operational test, row by row; the table above is a snapshot, not the
boundary.

### Limits — what the exception does not cover

Each limit has an owner; none is waved through by this record:

- **Every repo-drawn shape.** The `cap__core` `DF.1c` and `PL.2_MV`
  findings are the standing example: repo-drawn capacitor geometry under
  rules this repo can satisfy, owned by #296 (levels ratified in #294),
  and still blocking candidate 2's DRC-clean criterion.
- **Die-level density** `M1.4` / `M2.4` / `M3.4` / `MT30.7`: a standalone
  cell trips them by construction; they become meaningful at chip assembly
  with dummy fill — **#211**.
- **`DBU`** (composed GDS written at `dbu = 0.0005` against the runset's
  0.001): a klt writer default, not geometry, not the PCell — filed
  upstream as `2AMLogic/klayout-tools#5721`.
- **Candidate 3's generator-owned findings** `DF.4d_MV` x5 + `DV.6` x1 on
  `mos_array$1` — repo-drawn drift-extended geometry, **cleared by #297**
  (acc-block ring padding) in the base cell; absent from
  `layout/cell_candidate3/`'s committed report, while the `Amin_G2x`
  measurement cell's report still carries the set (#287/#297 family).
- **Any finding whose `cell` is not a PDK PCell's own cell name**, whatever
  its cause.

And the invariants this record fixes, in all cases: **no waiver is applied,
no rule is disabled, no PCell shape is hand-edited and no device is
substituted.** The committed reports keep reporting all 27 findings; the
exception changes how they are *dispositioned*, never what is measured.

### Bounded by construction, shown to be

Applying the enumeration command to all three committed cross-check
reports (candidates 1 and 3 re-verified 2026-11-18 at `82465b36`; the
candidate 2 row dates from 2026-11-16 at `2ca60fce`):

| Report | Native findings | Covered findings |
|---|---|---|
| `layout/cell_candidate1/drc_crosscheck_report.json` | 5 (`cell_candidate1` `DBU`/`M2.4`/`M3.4`/`MT30.7`/`PL.8`) | **0** |
| `layout/cell_candidate2/drc_crosscheck_report.json` | 27 | 20 (all `nfet_10v0_asym`) |
| `layout/cell_candidate3/drc_crosscheck_report.json` | 6 (`cell_candidate3` `DBU`/`M1.4`/`M2.4`/`M3.4`/`MT30.7`/`PL.8`) | **0** |

Candidates 1 and 3 instantiate no PDK PCell at all — their findings sit in
the top cells (the `mos_array` / `mos_array$1` generator-cell findings were
cleared by #296 and #297) — so **zero** findings on either fall inside this
exception. Candidate 2 is the only cell the exception reaches today, and
within it, only the 20 `nfet_10v0_asym` rows.

## Rejected alternatives

- *Apply `klt`'s offered waiver (or `--deck-var` a rule off) so the reports
  read clean* — rejected: it deletes the evidence; #295 (PR #323) exists so
  a report's `status` cannot overstate a cell's DRC state, and the
  committed `waived_count: 0` is part of candidate 2's evidence.
- *Hand-edit the PCell geometry, or substitute the device* — rejected: both
  are declined options (c)/(d) of the ruling, and remain `docs/ROADMAP.md`
  "Not planned".
- *Ship a checker script that classifies covered findings mechanically* —
  rejected for this record: the enumeration command above does it in one
  line; a standing check can be filed separately if one is wanted later.

## Open items

- **Precheck condition (open, conditions this record).** The ruling adds:
  read wafer.space's public precheck to see whether Run 3 tapeout would
  reject these violations; if it would, the disposition goes back to the
  operator well before the **2026-12-16** GDS date (#203). That reading is
  **#338 step 1** (agent-doable, no contact); this record carries it as a
  condition and does **not** claim precheck acceptance. The foundry
  conversation itself is **#338 step 2** and has **not happened** — the
  operator sends; agents do not contact wafer.space. Nothing here should be
  read as foundry agreement.

## What this record does not establish

- **It is not a manufacturability, yield or reliability claim.** It records
  the operator's direction that the three rules — `CO.4` (COMP overlap of
  contact, 0.07 um), `DF.6_MV` (COMP extension beyond gate, 0.4 um) and
  `PL.4_MV` (poly end cap, 0.22 um) — are **mask-geometry margin rules
  rather than process limits**, and states plainly that **no measurement in
  this repo bounds the margin given up** by shipping them. That margin is
  exactly what the foundry conversation (#338) is for.
- **Not measured**: whether any other *legal* parameter set of the same
  `nfet_10v0_asym` PCell would clear `CO.4`, `DF.6_MV` and `PL.4_MV`. No
  parameter sweep over the PCell exists in this repo; this record does not
  assume one exists.
- **It does not close candidate 2's DRC-clean criterion** (#207 owns the
  disposition rewrite in `layout/README.md`), does not fix the repo-drawn
  findings (#296, #297), and does not touch `signoff/` (its `3.analog` row
  cites candidate 1's native report and is unaffected by this ruling).

## Downstream

- **#207** consumes this record for candidate 2's `layout/README.md` DRC
  disposition and its remaining acceptance criterion.
- **#338** owns the precheck reading (step 1) and the foundry conversation
  (step 2, operator sends).
- **#296** owns the repo-drawn `cap__core` findings; **#297** candidate 3's;
  **#211** the die-level density; `2AMLogic/klayout-tools#5721` the `DBU`
  writer default.
- **#203** holds the external dates the precheck condition protects
  (slot purchase 2026-12-09, GDS 2026-12-16).

## Provenance

- Operator ruling: 2026-11-15, attended `/fleet:decide` round
  `20261111-r14`, q105, option (b), recorded on #299. Options (a), (c) and
  (d) declined.
- Census and rule descriptions: read from the committed
  `layout/cell_candidate2/drc_crosscheck_report.json` (added by PR #323,
  #295); first measured 2026-11-14 on `klayout-tools==0.9.2`, KLayout
  0.30.13, PDK `gf180mcuA` (`open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`),
  `--deck-var decks=all,-mslot`, native deck tree hash
  `sha256:8af3b4875893f3ffbff639bd7e2966c5e3b9b27f70d03e86d6da46ca9510fbc4`.
- Re-verified 2026-11-16: census, rule descriptions and zero coverage of
  candidates 1 and 3 re-run by the Curator at `6dbddcc3` and by the Builder
  at `2ca60fce`; command output recorded in the PR that lands this record.
- `generate.py` parameter citation: `layout/cell_candidate2/generate.py`
  lines 96-99 at this record's base.
