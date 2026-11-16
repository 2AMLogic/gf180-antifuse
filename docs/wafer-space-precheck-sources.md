# wafer.space Run 3 precheck: what the public sources establish

Issue #338, step 1 (the buildable half). Step 2 — the conversation with
wafer.space and the PDK maintainers — is operator-only and **has not
happened**: nothing below reflects any answer from wafer.space or the PDK
maintainers, and no outbound message was sent or drafted (#338 AC8). This
note is evidence with a verdict, not a decision; the scoped `spec/` exception
and its decision record belong to #299.

**Verdict (AC6):**

> **Would reject.** Run 3's precheck, as publicly documented at the pinned
> revisions below, would fail on the 20 `nfet_10v0_asym`-internal findings
> (`CO.4` x16, `DF.6_MV` x2, `PL.4_MV` x2, measured 2026-11-14 at `feb788e1`,
> `layout/README.md`): its only gating DRC is the PDK's own native KLayout
> runset — the same runset that reports those rules — run with violations
> fatal by default and no waiver or exclusion mechanism anywhere in the
> chain. Per #338 AC6 this routes to the operator (`loom:operator`), well
> before the 2026-12-16 submission deadline (S10). Whether wafer.space
> accepts the unmodified PCell as drawn is exactly what step 2 must settle;
> this note claims nothing beyond the public material.

## Sources

All reads below are **2026-11-16**. Each entry pins the revision read; the
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

So the precheck's KLayout DRC is the PDK's **own native runset** — the same
one this block's cross-check ran (`layout/README.md`), with the precheck's
`decks` override (S2) replacing the default.

**S9.** The runset itself: `fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv`,
`klayout/drc/` — the deck source open-pdks stages (S4/S8; open-pdks
`gf180mcu/Makefile.in` clones it as `PDK_LIB_PV` and copies
`klayout/drc/*` into the installed `tech/drc`). Read at PV HEAD
`6290c6342fdb` (2026-11-02, "Merge pull request #42 ... ldnmos-fixes"):

- `options.rb`: `decks` is a comma list with `-` exclusions; `all` selects
  every registered deck. `VARIANTS` maps gf180mcuA..F to `metal_top` /
  `mim_option` / `metal_level` only — **BEOL stack and MIM option**; no FEOL
  rule depends on the variant.
- `rule_decks/contact.rb`: rule `CO.4` (`CO.4_comp_overlap`, deck tags `all
  feol contact`) outputs "CO.4 : COMP overlap of contact. : 0.07µm".
- `rule_decks/comp.rb`: `DF.6_MV` (`df_6_mv`, tags `all feol comp`), 0.4 µm.
- `rule_decks/poly2.rb` (whole module tags `all feol poly2`): `PL.4_MV`,
  0.22 µm.

Local cross-check (repo-internal, read 2026-11-16): the installed decks at
`~/.ciel/gf180mcuA` and `~/.ciel/gf180mcuD` (this repo's pinned open-pdks
build) are **byte-identical A vs D** (`diff -r` over
`libs.tech/klayout/tech/drc` reports no differences). The installed tree
does differ from PV HEAD (S9) in more than the three rules' files —
`comp.rb`, `contact.rb`, `density.rb`, `dummy_comp.rb`, `geom.rb`,
`poly2.rb` and the `testing/` fixtures all differ — but **none of those
differences touch the three rules**. Within the files that hold them the
changes are `CO.5a`/`CO.5b` derivations, a `DF.11` derivation rewrite, a
`PL.5a_LV` report-string correction, and marker-exclusion refinements
(`mvsd`/`mvpsd`/`otp_mk`/`ymtp_mk`/`sramcore`) around
`DF.6_MV`/`PL.4_LV`/`PL.4_MV`/`PL.5a_MV`/`PL.5b_MV`; `CO.4`, `DF.6_MV` and
`PL.4_MV` keep their presence, deck tags and thresholds in both trees. The
`nfet_10v0_asym` PCell carries none of those markers (its 20 findings were
reported without them; `layout/README.md`).

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

## Answers

### Does the precheck enforce CO.4, DF.6_MV, PL.4_MV? (AC2, per rule)

**Yes for all three**, by the same mechanism. The gating stage is KLayout DRC
(S2), which runs the PDK's native runset at `gf180mcuD` (S8/S7) with decks
`all,-antenna,-density,-cup` (S2/S5). `all` selects every registered deck;
all three rules are registered under decks tagged `all` and `feol` (S9:
`CO.4` in `contact`, `DF.6_MV` in `comp`, `PL.4_MV` in `poly2`), and
`antenna`/`density`/`cup` are none of these. Each rule therefore **runs and
reports**, its count lands unfiltered in `klayout__drc_error__count` (S5),
and any non-zero count fails the flow (S6). This deck is the same native
runset that produced the 20 findings this block measured at `gf180mcuA`
(`layout/README.md`) — same rules, same values (S9 vs repo-internal
cross-check).

For magic DRC: the stage runs, but it **cannot reject** — the precheck sets
`ERROR_ON_MAGIC_DRC: False` (S2/S6). What magic's own gf180mcu rule set
would say about these three geometry conditions is **not answered by the
public material read**: magic's findings are a generic count of magic's own
rule strings (S6), and no public document read maps them to
`CO.4`/`DF.6_MV`/`PL.4_MV`. Marked unsourced; moot for the verdict, since
the stage cannot fail the submission.

### The two discrepancies (AC3)

- **PDK variant (gf180mcuD vs gf180mcuA): immaterial for these three rules.**
  The precheck runs `gf180mcuD` only (hard exit otherwise, S2). Variants
  differ only in metal stack and MIM option (S9 `options.rb`); all three
  findings are FEOL rules, invariant across variants; the installed A and D
  deck trees are byte-identical (S9). Caveat: this compares deck *content*;
  the precheck's pinned build could carry a different deck revision — see
  Caveats.
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
- **The deck at the precheck's pinned build.** The open-pdks commit is
  pinned (S4) but the deck inside comes from the PV sources fetched at
  build time; the PV HEAD read (S9) still reports all three rules
  identically, and the local-install diff shows no change to them — but a
  future PV or precheck revision can change the answer. **Re-read S1, S2,
  S4 and S9 against the then-current revisions before 2026-12-16.**
- **Magic's gf180mcu rule set.** Whether magic would report these three
  conditions, in its own naming, is not established by any source read
  (S6/S9 are KLayout-side). Unsourced.
- **Any acceptance path.** No public source documents a waiver, per-design
  exception, or foundry tolerance for PCell-internal findings (S1, S2, S10,
  S12). If one exists, it is not public — that is step 2's question, and
  this note must not be read as an answer to it.
