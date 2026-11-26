# wafer.space Run 3 precheck: what the public sources establish

Issue #338 tracks the wafer.space precheck evidence and the operator's
conversation with wafer.space and the PDK maintainers. This note records
the public tool and local measurements for step 1. The operator owns step 2,
including slot availability. The internal exception is recorded under #299.

**Verdict (AC6).** The public Run 3 KLayout DRC stage would reject
Candidate 2 as drawn. On the deck selected by the published precheck, the
unmodified `nfet_10v0_asym` produces all 20 previously tracked findings
plus one `MDN.10c`. The stage counts each finding as an error (S5/S6).
The bare-capacitor fallback removes those 21 device findings. Both cell
streams still fail the separate database-unit rule. See the replay below
for cell and deck identities. December 16 is the Run 3 deadline if space
is obtained (#203).

## Sources

The original source review was **2026-11-16**. The deck pins and KLayout
DRC settings in S2/S4/S9 were rechecked **2026-11-25**. Each entry pins the revision read; the
precheck and its inputs are updated between runs (the repository's own
history shows PDK/LibreLane bumps, S4/S3), so **every answer here is
revision-bound and must be re-read against the then-current precheck before
the 2026-12-16 GDS date (#203)**.

**S1.** `wafer-space/gf180mcu-precheck` README, at commit
`9b4e7dab6af073d02b81ecc368069540d2f67db9` (2026-10-20, "chore: update pdk
and librelane (#50)"; repo pushed 2026-10-20, Apache-2.0).
<https://github.com/wafer-space/gf180mcu-precheck>. Documents the stages:
single top cell matching `--top`; origin/dbu/max-metal (Metal5)/slot-size
checks; CoB id-marker and pad-opening checks; density; zero-area polygons;
KLayout antenna; **magic DRC**; **KLayout DRC**. Run instructions:
`PDK_ROOT=gf180mcu`, `PDK=gf180mcuD`, `python3 precheck.py --input
chip_top.gds`. The README names **no runset, deck file or version**, and
says **nothing** about PCell-internal findings, waivers or exceptions.

**S2.** Same repository, `precheck.py` at the same commit (695 lines, read in
full). Facts used below:

- PDK is hard-pinned: the script exits unless `PDK == "gf180mcuD"`.
- The flow (`PrecheckFlow`) is: ReadLayout, CheckTopLevel, CheckSize,
  GenerateID, KLayout.Render, KLayout.Density + checker, zero-area polygons +
  checker, KLayout.Antenna + checker, **Magic.DRC +
  `Checker.MagicDRC`**, **KLayout.DRC + `Checker.KLayoutDRC`**, WriteLayout.
- `"ERROR_ON_MAGIC_DRC": False` — commented in the source as "Do not error
  on magic DRC violations". No `ERROR_ON_KLAYOUT_DRC` override is set.
- `MAGIC_GDS_FLATGLOB` lists glob patterns for foundry-provided IO, SRAM and
  fill cells, commented "Prevent false positive DRC errors in I/O cells".
  `nfet_10v0_asym` does **not** appear in the list.
- `"KLAYOUT_DRC_OPTIONS": {"decks": "all,-antenna,-density,-cup", "variant":
  PDK, "workers": ...}` — the `cup` deck is disabled "for now"; the KLayout
  DRC otherwise runs **all** decks of the PDK's runset.

**S3.** Same repository, `flake.lock` at the same commit: the LibreLane
dependency is `github:librelane/librelane` branch `dev`, locked at
`99148a9c1e648cdfdb9d7b772481af32e0dfbe8b`; ciel is pinned at `3.1.0`.

**S4.** Same repository, `Makefile` at the same commit: the PDK is installed
with `ciel enable 792ef67037d74c8c51811eab3ce23cf793491296 --pdk-root
$(PDK_ROOT) --pdk-family $(PDK)` — an open-pdks build commit pin. The
DRC deck files themselves are not tracked in open-pdks; the build fetches
them from the gf180mcu process-verification sources (S8/S9). The Makefile
also clones `wafer-space/gf180mcu-example-layouts` (S12).

**S5.** LibreLane at the locked revision `99148a9`:
`librelane/steps/klayout.py`. For `gf180mcuA..D`, `KLayout.DRC` runs
`klayout -b -zz -r <KLAYOUT_DRC_RUNSET> -rd input=... -rd topcell=... -rd
report=...` plus one `-rd k=v` per `KLAYOUT_DRC_DEFINES` entry; it then
converts the XML report to the metric `klayout__drc_error__count`. The
converter counts **every** category in the report — no filtering by rule or
region. The precheck's `KLAYOUT_DRC_OPTIONS` dict reaches the runset as
`KLAYOUT_DRC_DEFINES` through the variable's own deprecation mapping in this
file.

**S6.** LibreLane at the same revision, `librelane/steps/checker.py`:
`Checker.KLayoutDRC` is a `MetricChecker` whose threshold is `Decimal(0)`,
and `MetricChecker.run` raises a deferred error when the metric exceeds it
(`metric_value > threshold`), unless `ERROR_ON_KLAYOUT_DRC` is set false;
**the default is true** (`default=True` on the variable). So any KLayout
DRC violation fails the precheck flow, which exits non-zero (S2's
`main()`). `Checker.MagicDRC` behaves the same on `magic__drc_error__count`
with default true — overridden to false by the precheck (S2), so magic
findings are counted and reported but **cannot fail the flow**.
`librelane/steps/magic.py` (same revision) shows magic's findings are parsed
from magic's own report into a generic count; the step's `MAGIC_GDS_FLATGLOB`
variable is documented as "Flatten cells by name pattern on input. May be
used to avoid false positive DRC errors."

**S7.** LibreLane at the same revision, `librelane/config/config.py`: PDK
variables (`KLAYOUT_DRC_RUNSET`, `KLAYOUT_DRC_DEFINES`) are loaded from
`$PDK_ROOT/$PDK/libs.tech/librelane/config.tcl` (fallback
`libs.tech/openlane/config.tcl`), i.e. from the installed PDK, not from
LibreLane itself.

**S8.** open-pdks at the precheck's pinned build commit `792ef67`
(`fossi-foundation/open-pdks`): `gf180mcu/librelane/config.tcl` stages the
PDK config that S7 loads. Verified identical (lines 159-162) in the local
ciel installs of `gf180mcuA` and `gf180mcuD` (this repo's pinned build;
repo-internal read 2026-11-16):

```
KLAYOUT_DRC_RUNSET = $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc
KLAYOUT_DRC_OPTIONS = {variant: $PDK, decks: "all,-antenna,-density"}
```

The precheck runs the PDK's native KLayout runset, with the deck selection
in S2 overriding the default. S9 identifies the source revision of that
runset.

**S9.** The precheck's open-pdks build `792ef670` selects process-verification
(PV) commit `a561909c667ce1e8485313f5d280a7014f524e49` for
`gf180mcu_fd_pv`. Its Makefile reads the concrete commit from the manifest,
fetches the repository at that revision, and copies `klayout/drc/*` into
the installed PDK. [PDK manifest](https://github.com/fossi-foundation/open-pdks/blob/792ef67037d74c8c51811eab3ce23cf793491296/gf180mcu/gf180mcu.json#L105)
· [Fetch and install recipe](https://github.com/fossi-foundation/open-pdks/blob/792ef67037d74c8c51811eab3ce23cf793491296/gf180mcu/Makefile.in)

At this PV revision, `klayout/drc/options.rb` selects decks by tag.
`contact.rb`, `comp.rb` and `poly2.rb` register `CO.4`, `DF.6_MV` and
`PL.4_MV` respectively in the front-end decks. The newer upstream fix at
`6290c6342fdbf2849179bda6d345c72ed15b285b` changes which edges are
included for the latter two rules. Their thresholds stay the same, but their
findings on this PCell change. [Public shuttle PV deck](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv/tree/a561909c667ce1e8485313f5d280a7014f524e49/klayout/drc)
· [Upstream change](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv/pull/42)

**S10.** wafer.space public site, read 2026-11-16: homepage states the Run 3
submission deadline **16 December 2026 AoE**; the technology page's flow is
"Design ... Sign-off: Complete DRC/LVS/ERC checks and follow our design
guidelines ... Submit"; the design-help page lists unaffiliated paid
services only. **No waiver, exception or PCell-tolerance policy is stated
anywhere on the pages read.**

**S11.** Run 1 guidance (wafer.space's Crowd Supply updates), as verified by
the #338 curation on 2026-11-16: participants were told to run the precheck
locally before submitting, described as the same check the submission
platform runs. The platform's own deployment revision is **not publicly
pinned** — treated in Caveats as unsourceable, not as a verified fact of my
own read.

**S12.** `wafer-space/gf180mcu-example-layouts` (pushed 2026-06-16): ten
files — eight `chip_top.oas` example layouts, a LICENSE and a README. No run
logs, no DRC results, no claims about passing or PCell findings. It contains
P&R/template-style chip tops; nothing in it documents an analog-PCell
precedent either way.

## Cell replay on the public shuttle deck (2026-11-25)

KLayout 0.30.12 ran the precheck's native DRC stage selection against the
individual cell layouts in design commit `55d8a6ce`. Each table row counts
items in the XML report by rule and owning cell.

| Cell | PV revision | Findings inside `nfet_10v0_asym` | Cell-top findings |
|---|---|---|---|
| Candidate 2 | public pin `a561909c` | CO.4 ×16, DF.6_MV ×2, PL.4_MV ×2, MDN.10c ×1 | DBU ×1 |
| Candidate 2, same GDS | upstream fix `6290c634` | CO.4 ×16, MDN.10c ×1 | DBU ×1 |
| Bare-capacitor fallback | public pin `a561909c` | 0 (access device omitted) | DBU ×1 |

`MDN.10c` checks POLY2 extension beyond COMP in the field. The report
locates its edge at (0.27, −1.813) to (0.27, 1.813) µm in
`nfet_10v0_asym`. The fallback still hits the database-unit rule tracked
in #448. These cell results cover one stage. Chip routing, density,
antenna, and the hosted submission service require separate evidence.

To reproduce, use a checkout of the PV revision in the table as `$pv` and
run from this design repository. Set `top` to `cell_candidate2` or
`cell_candidate2_fallback`, and `out` to an existing scratch directory.

```sh
git show "55d8a6ce:layout/$top/$top.gds" > "$out/$top.gds"
klayout -b -r "$pv/klayout/drc/gf180mcu.drc" \
  -rd input="$out/$top.gds" -rd topcell="$top" -rd report="$out/$top.lyrdb" \
  -rd variant=gf180mcuD -rd decks=all,-antenna,-density,-cup -rd workers=1
```

The Candidate 2 GDS SHA-256 is
`5cb4a64fa103f2b698aeaffedddfc28405931e6afbfec8f21cf8b90678462e7a`.
The fallback GDS SHA-256 is
`92b431518b22a3c8067b31442b2c91792df72b9358bb5362b111121a994f7a16`.

## Answers

### Does the precheck enforce CO.4, DF.6_MV, PL.4_MV? (AC2, per rule)

**Yes for all three**, by the same mechanism. The gating stage is KLayout DRC
(S2), which runs the PDK's native runset at `gf180mcuD` (S8/S7) with decks
`all,-antenna,-density,-cup` (S2/S5). `all` selects every registered deck;
all three rules are registered under decks tagged `all` and `feol` (S9:
`CO.4` in `contact`, `DF.6_MV` in `comp`, `PL.4_MV` in `poly2`), and
`antenna`/`density`/`cup` are none of these. Each rule therefore **runs and
reports**, its count lands unfiltered in `klayout__drc_error__count` (S5),
and any non-zero count fails the flow (S6). The cell replay above reproduces all 20 of the findings originally
measured at `gf180mcuA` (#338) and identifies the additional LDNMOS rule.

For magic DRC: the stage runs, but it **cannot reject** — the precheck sets
`ERROR_ON_MAGIC_DRC: False` (S2/S6). What magic's own gf180mcu rule set
would say about these three geometry conditions is **not answered by the
public material read**: magic's findings are a generic count of magic's own
rule strings (S6), and no public document read maps them to
`CO.4`/`DF.6_MV`/`PL.4_MV`. Marked unsourced; moot for the verdict, since
the stage cannot fail the submission.

### The two discrepancies (AC3)

- **PDK variant.** The precheck requires `gf180mcuD` (S2). The design's
  earlier diagnostic used `gf180mcuA`. The public-deck replay uses D and
  reports all three rules on this PCell. The comparison in #523 uses A and
  independently confirms that the upstream fix clears DF.6_MV and PL.4_MV.

- **DRC engine (magic):** magic DRC is a second engine this block has never
  run (verified 2026-11-16 by the curation: no magic DRC anywhere in the
  repo). It runs in the precheck but is non-gating (S2/S6), so its behavior
  cannot change the reject/not-reject outcome. Whether magic's deck reports
  these conditions at all remains unmeasured and is out of scope here
  (#338 Out of Scope); it is a step-2 question if the operator wants it
  answered.

### Does the precheck accept violations inside unmodified PDK PCells? (AC4)

**Not documented, and no exclusion mechanism found** in: the precheck code
(S2 — no waiver, allowlist, filter or PCell-aware logic anywhere in the
flow), the LibreLane KLayout DRC step and checker it calls (S5/S6 — count
everything, fail on anything), or the PDK config (S8 — deck selection is the
only knob, and the precheck's selection still includes these decks). The
only tolerance mechanism in the chain is `MAGIC_GDS_FLATGLOB` (S2/S6), which
is magic-only, flattens *specific foundry IO/SRAM/fill cells* to avoid false
positives, does not remove any geometry violation, and does not include
`nfet_10v0_asym`. No stated policy on the site pages read (S10); no
precedent in the example layouts (S12 — no results there at all).

### Facts surfaced by the other stages (recorded neutrally; owners exist)

- The density stage runs the PDK density deck and gates on it (S2/S6,
  `Checker.KLayoutDensity` default-on): the die-level density findings
  (`M1.4`/`M2.4`/`M3.4`/`MT30.7`) would likewise be fatal. Owner: #211.
- The zero-area-polygon check is fatal by default (S2): relevant to the DBU
  writer default question, owner `2AMLogic/klayout-tools#5721` — one line,
  no action here.
- The precheck enforces max metal layer Metal5 and slot dimensions (S1);
  no bearing on the three PCell rules; no action here.

## Caveats

What the sources do **not** say:

- **The platform's actual deployment.** S11's "the platform runs the same
  check" is the submission platform's own Run 1 description, curated-read
  2026-11-16; the deployed precheck revision is not publicly pinned. This
  note's verdict is about the public tool; only step 2 can confirm what the
  platform will enforce in December 2026.
- **Future revisions.** The public sources identify the current deck (S4/S9).
  Recheck those pins and the S2 settings if the precheck changes before
  submission. The local cell measurements apply to the revisions above.

- **Magic's gf180mcu rule set.** Whether magic would report these three
  conditions, in its own naming, is not established by any source read
  (S6/S9 are KLayout-side). Unsourced.
- **Any acceptance path.** No public source documents a waiver, per-design
  exception, or foundry tolerance for PCell-internal findings (S1, S2, S10,
  S12). If one exists, it is not public — that is step 2's question, and
  this note must not be read as an answer to it.
