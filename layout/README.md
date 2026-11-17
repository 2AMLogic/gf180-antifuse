# layout/

Layout and DRC/LVS signoff via klayout-tools.

**Capacitor geometry levels (2026-11-17).** Every moscap in this directory is
drawn at the levels ratified in `spec/capacitor-geometry-decision.md` (#294):
Minimum W = 1.0 um -- the PDK runset's `DF.1c` "Min. COMP Width for MOSCAP"
floor -- at each device's minimum drawn length (0.28 um thin-oxide, 0.70 um
6 V), and 2x-area doubling **W** at held L (1.0 -> 2.0 um). The access-device
widths keep their section-3 split values (0.42 / 0.84 um, clamped at the
0.42 um `mos_array` generator floor) and are not touched by that record.
Extracted capacitor areas are 0.28 um2 (Regions I/III Minimum), 0.70 um2
(Region II Minimum) and exactly 2.000x those at the 2x points
(`klt extract`, device parameters; the deck's extracted C at its fixed bias:
1.232 fF per Region I/III Minimum capacitor, 2.464 fF per 2x one -- exactly
2.000x, the model's own area proportionality -- and 1.61 fF for the Region II
Minimum `cap_nmos_06v0`). All seven cells were regenerated and
re-signed in the same pass (#296); the per-cell sections below carry the
details and the measured verdicts.

## cell_candidate1/ -- first drawn bitcell (candidate 1), one cell only

`layout/cell_candidate1/` holds a single bitcell of candidate 1
(`spec/cell-candidates.md`): a thin-oxide NMOS capacitor (the antifuse
element, schematic model `cap_nmos_03v3`) in series with a 6.0 V NMOS access
device (`nfet_06v0`), per `design/cells/cell_candidate1.sch`. Nothing about the
array, the multiplexers, the pass gates or the program supply is drawn. The
evidence below covers **one cell of one candidate, not the array**, and makes
no claim about breakdown behaviour.

| File | What it is |
|---|---|
| `generate.py` | Deterministic generator: this candidate's parameters (flavor, `L_ACC`, `DX`, placement, pin map) plus calls into the shared `layout/bitcell_gen.py` (the flow: `klt gen mos_array` x2, `klt draw` for the straps and marker, `klt gen-compose` explicit placement) and `layout/candidate1_points.py` (`straps(1.0, 0.42)`: CN, VB and the MOS-capacitor marker, derived once for the whole candidate-1 family). `--check` regenerates and compares the committed GDS byte-for-byte. |
| `cell_candidate1.gds` | Generated layout, top cell `cell_candidate1`, pins/labels `BL`, `WL`, `PL`, `VB`. |
| `drc_report.json` | `klt drc --deck gf180mcu --top cell_candidate1` report (status `clean`, 0 violations) -- the **curated deck's** verdict; see "DRC" for the native runset's. |
| `drc_crosscheck_report.json` | Curated-vs-native cross-check, `klt drc --engine both --deck gf180mcu --top cell_candidate1 --pdk gf180mcuA --deck-var decks=all,-mslot` (klayout-tools `0.9.2`, KLayout `0.30.13`): curated `clean`, native runset `violations`, **5 findings** -- `DBU` and the die-level density rules only; the cell-level `DF.1c` is **gone** (see "DRC"). |
| `drc_native_report.json` | Plain native-deck envelope, `klt drc --engine klayout --top cell_candidate1 --pdk gf180mcuA --deck-var decks=all,-mslot` (same pin): `status: violations`, 5 findings, same set. This is the envelope `signoff/manifest.json` cites for the `3.analog` row. |
| `lvs_request.json`, `lvs_reference.spice` | The LVS request and its reference netlist. |
| `lvs_report.json` | `klt lvs lvs_request.json` report (status `match`, 0 errors); see "LVS". |

Toolchain: all committed artifacts were regenerated 2026-11-17 with released
`klt 0.8.0` + KLayout `0.30.12` (`uvx --from klayout-tools==0.8.0 --with
klayout==0.30.12`) for the GDS, curated DRC, LVS and ERC, and released
`klt 0.9.2` (KLayout `0.30.13`) for the native deck and the cross-check; PDK
`gf180mcuA`. No tool was installed or changed. (Earlier history: the first
GDS was drawn at `klt 0.7.0` and the first LVS/ERC ran on `0.8.0`, issue
#196; the 2026-11-17 pass re-pinned everything on `0.8.0` because that is the
release that reproduces every committed GDS byte-for-byte.) Regenerate with
`python3 layout/cell_candidate1/generate.py` and verify with `--check`. The
generators need `klt` on PATH; to pin it without touching the host tool, run
`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12 python3
layout/cell_candidate1/generate.py --check`. Per-candidate geometry stays in
each `generate.py`, except the candidate-1 split points
(`cell_candidate1_{A2x_G2x,A2x_Gmin,Amin_G2x}`) **and this cell**: their
shared constants and strap derivation live in `layout/candidate1_points.py`
(this cell calls `straps(1.0, 0.42)`), and each of those `generate.py` files
names one `POINTS` entry. Only the flow and `--check` live in
`layout/bitcell_gen.py`.

### Geometry point

`spec/split-axis-plan.md` sections 2-3 define levels, not numbered
sub-combinations. This cell is the **Minimum x Minimum** point (capacitor
geometry Minimum, access sizing Minimum) of a thin-oxide region. This is a
choice of sub-combination, not a spec change.

| Device | Drawn | Note |
|---|---|---|
| Capacitor (thin oxide NMOS, S and D strapped) | W = 1.0 um, L = 0.28 um | W is the ratified Minimum level (`DF.1c` floor); L is the 3.3 V minimum drawn length. Extracted area 0.28 um2 (`cap_nmos_03v3`). |
| Access (`nfet_06v0`, Dualgate marker) | W = 0.42 um, L = 0.70 um | L matches the schematic's `lacc`. |

**Deviation to read before relying on it.** The access width is clamped to
`klt gen mos_array`'s generator floor (`w_um >= 0.42`, a contact-fit floor
above the PDK's own minimum widths); the schematic's `wacc` default is
0.30 um. The capacitor no longer sits on that floor: its 1.0 um Minimum is
the ratified legal level (`spec/capacitor-geometry-decision.md`), and
`layout/bitcell_gen.py` no longer defaults the capacitor width to the
generator floor -- every generator passes `w_cap_um` explicitly. The
schematic's `wcap`/`lcap` defaults (1 um x 1 um placeholders) and the
drawn-vs-simulated reconciliation remain #292's. `lvs_reference.spice`
carries the drawn values, not the schematic defaults.

### Structure and bodies

- The capacitor is a thin-oxide NMOS gate over COMP with source and drain
  strapped together on net CN (a MOS capacitor). It is drawn as a plain
  transistor from `mos_array`, and `generate.py` adds the PDK MOS-capacitor
  marker (`MOS_CAP_MK`, 166/5) as a hand-placed rectangle over its COMP island,
  because `klt gen` has no MOS-capacitor primitive (upstream
  2AMLogic/klayout-tools#2953). Without that marker the extraction deck reads
  the gate as an `nfet` (see "LVS"). The marker is not drawn over the access
  device.
- Each device sits inside its own P+ tap ring (Metal1 over contacts), so
  neither body floats. The two rings are strapped on the north side (`VB`).
  Both devices are NMOS in the p-substrate; no well is needed or drawn.
- CN is a Metal1 strap from the access source to the capacitor's S and D.
  `BL` (access drain), `WL` (access gate), `PL` (capacitor gate) are pad
  labels with no routing beyond the cell.

### DRC

`klt drc --deck gf180mcu --top cell_candidate1`: `status: clean`, 0 violations,
deck `released: true`, no waiver and no rule disabled. This is the **curated
deck's** verdict; the PDK's own runset is committed alongside it as a
cross-check -- see the last bullet below. A first placement at 3.9 um
pitch drew a Pplus spacing violation between the two tap rings; the committed
cell uses a 4.2 um pitch. The rule was not waived.

Coverage block quoted from `drc_report.json` (`coverage.deck_scope`,
`coverage.layers_in_stream_without_rules`, `coverage.rules_skipped`). The 34
skipped rules are all reported as `no_applicable_geometry` in
`coverage.inapplicable` (no such layers are drawn), which includes
`pplus.enclosing.comp.1`; layer 34/10 is the Metal1 label purpose and 166/5 is the MOS-capacitor
marker (the deck has no rule on it, so DRC does not check its placement).

```json
{
  "deck_scope": [
    "10.4.2 MIM Option B",
    "10.7 DRC_BJT Mark Layer",
    "7.12 Contact",
    "7.13 Metaln",
    "7.14 Vian",
    "7.15 MetalTop",
    "7.4 Nwell",
    "7.5 Comp",
    "7.7 Poly2",
    "7.8 Nplus",
    "7.9 Pplus",
    "9.1 Bond Pad"
  ],
  "layers_in_stream_without_rules": [
    "34/10",
    "166/5"
  ],
  "rules_skipped": [
    "bjt.separation.comp.1",
    "metal1.enclosing.via1.1",
    "metal2.enclosing.via1.1",
    "metal2.enclosing.via2.1",
    "metal2.space.1",
    "metal2.width.1",
    "metal3.enclosing.via2.1",
    "metal3.enclosing.via3.1",
    "metal3.space.1",
    "metal3.width.1",
    "metal4.enclosing.via3.1",
    "metal4.enclosing.via4.1",
    "metal4.space.1",
    "metal4.width.1",
    "metal5.enclosing.via4.1",
    "metal5.space.1",
    "metal5.width.1",
    "metaltop.space.1",
    "metaltop.width.1",
    "mim.enclosing.fusetop.1",
    "mim.enclosing.via4.1",
    "mim.space.1",
    "nwell.enclosing.comp.1",
    "nwell.space.1",
    "pad.enclosing.metal5.1",
    "pplus.enclosing.comp.1",
    "via1.space.1",
    "via1.width.1",
    "via2.space.1",
    "via2.width.1",
    "via3.space.1",
    "via3.width.1",
    "via4.space.1",
    "via4.width.1"
  ]
}
```

**What the clean verdict does not cover.**

- The deck reports a `voltage_domain_warnings` entry: Dualgate (55/0) is
  modelled only for the DF.1a/DF.3a COMP width/space rules and for MOS
  recognition. Every other rule applies the 3.3 V thresholds to the 6 V access
  device, e.g. DF.6 (COMP extension beyond gate, 0.24 vs 0.40 um) and
  PL.5a/PL.5b (field poly to COMP, 0.10 vs 0.30 um), neither transcribed in the
  deck. The access device has not been checked against its own 6 V rules.
- **No voltage-class rule fired.** The deck has no gate-oxide-voltage rule
  that could fire on the thin-oxide capacitor, so there is nothing to record
  as firing by design and nothing was waived. The cell as drawn is the
  intended structure (thin-oxide capacitor, 6 V access device with the
  Dualgate marker).
- Layout-versus-programming-voltage suitability (thin-oxide device in a
  program path) is a design-intent matter this deck cannot judge.
- **The PDK's own runset no longer disagrees on any cell-level rule; the
  cross-check is committed.** `drc_crosscheck_report.json`
  (`klt drc --engine both --deck gf180mcu --top cell_candidate1 --pdk
  gf180mcuA --deck-var decks=all,-mslot`, klayout-tools `0.9.2`, KLayout
  `0.30.13`) runs the curated deck and the PDK's own sign-off runset
  (`gf180mcu.drc`) on the same committed GDS: curated `status: clean`, native
  `status: violations`, **5 findings** -- `DBU` x1 and the die-level density
  rules `M2.4`/`M3.4`/`MT30.7`/`PL.8`. The cell-level **`DF.1c`** ("Min. COMP
  Width for MOSCAP") that every earlier run reported on this cell is **gone**:
  the capacitor COMP island under the 166/5 marker is drawn 1.0 um wide, the
  ratified Minimum (`spec/capacitor-geometry-decision.md`), and the native
  run reports no MOSCAP-rule finding on it. The density rules fire on any
  standalone cell and remain recorded as disclosed, not fixed; `DBU` is the
  stream-format matter already filed upstream. The same native verdict is
  committed a second way as `drc_native_report.json` (a plain `--engine
  klayout` envelope, same pin and deck-var), which is the envelope
  `signoff/manifest.json` cites for the `3.analog` row -- that row still
  grades `unmet` pending the die-level assembly that settles the density
  rules (`signoff/README.md`); the cell-level half of its reason is
  resolved as of this pass.

### LVS

`lvs_request.json` runs `klt lvs` with the gf180mcu extraction deck against
`lvs_reference.spice` (the schematic's netlist,
`design/netlists/cell_candidate1.spice`, unchanged, with its subcircuit
parameters resolved to the drawn literals). The reference keeps
`cap_nmos_03v3` for the capacitor; no `device_map` and no waiver is used.

`lvs_report.json`: `status: match`, `error_count: 0`, layout sha256 pinned to
the committed GDS; `klt lvs --check lvs_report.json` exits 0. Nets paired:
`BL`, `WL`, `PL`, `VB` and the internal strap `CN`.

**Why it first reported a mismatch (a layout error).** klt `0.7.1.dev2422`
extracted the capacitor as an `nfet` and so reported `device.unmatched` for
`nfet` (layout) and `CAP_NMOS_03V3` (reference), plus the dependent `topology`
errors and unpaired `PL`/`VB`. The deck recognises a MOS capacitor only as a
COMP island under `MOS_CAP_MK` (166/5); the committed cell had no such marker.
The reference netlist and the request were right. The fix is the marker in
`generate.py`, with the GDS regenerated. The cap's drawn size, the connectivity
and the curated-deck DRC verdict (`clean`) did not change.

**What the match does not establish.** The report carries three warnings that
bound it:

- `device.geometry_not_compared`: the capacitor's `A` and `P` are secondary
  parameters, so the capacitor's geometry is not verified by this compare.
- `device.placeholder_value`: the `subckt-call` reference form gives the
  capacitor a placeholder `C` of 0, so its capacitance is not a real
  comparison either. Capacitor identity, terminal connectivity and the
  `nfet_06v0` access device's parameters are what was compared.
- the `pfet`/`bjt` topology warnings are classes with no devices on either
  side.

The capacitor's drawn size (W 1.0 um, L 0.28 um) therefore rests on
`generate.py` and the extraction (`klt extract`), not on this LVS.

## cell_candidate1_{Amin_G2x,A2x_Gmin,A2x_G2x}/ -- the other three Candidate 1 split points

`layout/cell_candidate1/` draws the **Minimum x Minimum** point of candidate 1.
These three directories draw the other three points of the same 2 x 2 split
grid, so the Candidate 1 quadrant of the characterization grid is a grid and not
a single point. Same cell as `cell_candidate1/` in every other respect (thin-oxide
NMOS capacitor `cap_nmos_03v3` in series with a 6.0 V NMOS access device
`nfet_06v0`, per `design/cells/cell_candidate1.sch`), same artifact set
(`generate.py` with `--check`, GDS, `drc_report.json`, `lvs_request.json`,
`lvs_reference.spice`, `lvs_report.json`, `erc_report.json`), same bounds on what
the evidence covers: **one cell per point, not the array**, and no claim about
breakdown behaviour. `design/` is unedited -- the schematic is parameterized and
only `lvs_reference.spice` carries the drawn literals.

Naming follows the floorplan's pad labels, which put access sizing first
(`spec/run3-test-chip-floorplan.md` rows L01-L16): `C1_<access>_<capacitor>`.
`cell_candidate1/` is the `C1_Amin_Gmin` point and is deliberately **not**
renamed -- its reports are cited by `signoff/manifest.json` and its GDS sha256 is
what its own `--check` pins.

### Which axis carries each 2x (and what the 2x is relative to)

**Both 2x levels are taken on device width, at held drawn length.**

- The access axis is already unambiguous: `spec/split-axis-plan.md` section 3
  defines its 2x level as "double the minimum channel width, same drawn length".
- The capacitor axis is a real choice -- section 2 ratifies "double the minimum
  capacitor area (via W and/or L scaling)" and leaves the split open. Width is
  taken here, because that is the axis `sim/` already scales: 
  `sim/cell-device-characterization/run_experiment.py:82-83` labels
  `SIZING_LEVELS` "access-device width multiplier" and `GEOM_LEVELS` "capacitor
  width (-> area) multiplier", and
  `sim/cell-device-characterization/klt/mk_klt_requests.py:161-162` scales
  `wacc`/`wcap` with `lacc`/`lcap` passed through unscaled (line 165). So "A2x"
  and "G2x" mean the same thing in `sim/` and in `layout/`, and the two halves of
  the grid are comparable. Doubling the capacitor's `L` instead would have
  disagreed with `sim/` and grown the block in x, putting the DRC-driven block
  pitch back in play.

**The capacitor levels are the ratified ones** (`spec/capacitor-geometry-decision.md`,
#294): Minimum W = 1.0 um -- the PDK runset's `DF.1c` "Min. COMP Width for
MOSCAP" floor, which the earlier drawn 0.42 um violated -- and 2x-area
W = 2.0 um at held L = 0.28 um. (Before that record landed, this section
documented a 0.42 -> 0.84 um pair pinned to the `mos_array` generator floor;
those levels were illegal under the runset and were replaced grid-wide by
#296.) The access widths keep their section-3 values on the generator floor
(0.42 / 0.84 um); that axis is not under a MOSCAP rule and is untouched here.

**The absolute access widths still differ from `sim/`'s, and that is
pre-existing and deliberate.** `sim/` scales the *schematic* defaults in
`design/netlists/cell_candidate1.spice` (`wacc=0.30u`), so its 2x access point
is 0.60 um where `layout/` is clamped to 0.84 um by the generator floor. The
capacitor widths no longer diverge: both halves now draw Minimum 1.0 um and
2x 2.0 um. The **convention** (which dimension carries the factor, and that
the factor is exactly 2) matches on both axes; reconciling the access clamp
would mean editing `design/`, which is out of scope here.

### Geometry, as drawn and as extracted

Drawn values are from each `generate.py`; the capacitor area and access width
columns are **extracted** (`klt extract`, device parameters), so the 2x on each
axis is measured rather than asserted. Bounding boxes are `klt stats`.

| Cell | Access W x L (drawn) | Access W (extracted) | Capacitor W x L (drawn) | Capacitor area (extracted) | `klt stats` bbox |
|---|---|---|---|---|---|
| `cell_candidate1/` (`C1_Amin_Gmin`) | 0.42 x 0.70 um | 0.42 um | 1.0 x 0.28 um | 0.28 um2 | (-1.23,-1.23)-(7.13,3.65), 8.36 x 4.88 um = 40.80 um2 |
| `cell_candidate1_Amin_G2x/` | 0.42 x 0.70 um | 0.42 um | **2.0** x 0.28 um | **0.56** um2 | (-1.23,-1.23)-(7.13,4.65), 8.36 x 5.88 um = 49.16 um2 |
| `cell_candidate1_A2x_Gmin/` | **0.84** x 0.70 um | **0.84** um | 1.0 x 0.28 um | 0.28 um2 | (-1.23,-1.23)-(7.13,3.65), 8.36 x 4.88 um = 40.80 um2 |
| `cell_candidate1_A2x_G2x/` | **0.84** x 0.70 um | **0.84** um | **2.0** x 0.28 um | **0.56** um2 | (-1.23,-1.23)-(7.13,4.65), 8.36 x 5.88 um = 49.16 um2 |

The two split axes move independently and each by exactly 2, which is the point
of the grid: extracted capacitor area is 0.56 / 0.28 = **2.000** across the
`G` axis at constant `A`, and extracted access width is 0.84 / 0.42 = **2.000**
across the `A` axis at constant `G`. Capacitor drawn length is held at 0.28 um
and access drawn length at 0.70 um in all four cells.

Cells sharing a capacitor level land at the **same** bounding box, which is
expected rather than a mistake: growing a device width moves that block's
`bbox` `y1` by exactly (W - 0.42) um and leaves every x coordinate untouched
(measured on `klt gen mos_array`: y1 3.07 at W = 0.42, 3.49 at 0.84, 3.65 at
1.0, 4.65 at 2.0), and the cell top is set by the taller of the two blocks. So
the x pitch `DX = 4.2` carries over unchanged from `cell_candidate1/` at every
point -- and is **proved** by each cell's own DRC report, not inferred from the
block extents. 40.80 / 49.16 um2 sit under the floorplan's 72 um2 estimate row
for these instances; re-budgeting that row from the measured numbers is the
floorplan record's follow-up, not this pass.

### Results

Toolchain for all three: released `klt 0.8.0` with the engine pinned to the
version that build was tested against --
`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12` -- PDK `gf180mcuA`.
No tool was installed or changed. The pin matters twice: `0.8.0` is the release
that reproduces every committed candidate-1-family GDS byte-for-byte
(`0.9.1` drifts them), and pinning `klayout==0.30.12` keeps
`provenance.klayout_version_mismatch` `false` on every report (an unpinned run
resolves klayout `0.30.13` and sets it `true`, which the tool warns may shift
report counts). Regenerate or verify any cell with:

```
uvx --from klayout-tools==0.8.0 --with klayout==0.30.12 \
  python3 layout/cell_candidate1_A2x_G2x/generate.py --check
```

The committed `drc_crosscheck_report.json` files are the exception to that
pin: they were produced with `uvx --from klayout-tools==0.9.2 klt drc --engine
both` (KLayout `0.30.13`, so
`provenance.klayout_version_mismatch` is `true` on them, matching candidate
2's committed cross-check), and `klt drc --check` verifies each one fresh
against its pinned input GDS.

| Cell | DRC (curated deck) | DRC (native runset) | LVS | ERC |
|---|---|---|---|---|
| `cell_candidate1_Amin_G2x/` | `status: clean`, 0 violations | `violations`, 5: `DBU` x1, density `M2.4`/`M3.4`/`MT30.7`/`PL.8` -- **no `DF.1c`** | `status: match`, 0 errors | `erc_status: clean`, 0 findings |
| `cell_candidate1_A2x_Gmin/` | `status: clean`, 0 violations | `violations`, 5: `DBU` x1, density `M2.4`/`M3.4`/`MT30.7`/`PL.8` -- **no `DF.1c`** | `status: match`, 0 errors | `erc_status: clean`, 0 findings |
| `cell_candidate1_A2x_G2x/` | `status: clean`, 0 violations | `violations`, 5: `DBU` x1, density `M2.4`/`M3.4`/`MT30.7`/`PL.8` -- **no `DF.1c`** | `status: match`, 0 errors | `erc_status: clean`, 0 findings |

- **DRC.** `klt drc --deck gf180mcu`, deck `released: true`, no waiver and no
  rule disabled. Layers in stream without rules are 34/10 (labels) and 166/5
  (capacitor marker), as for `cell_candidate1/`. The native runset's verdict
  (each cell's committed `drc_crosscheck_report.json`, `klt drc --engine both
  --deck gf180mcu --pdk gf180mcuA --deck-var decks=all,-mslot`, klayout-tools
  `0.9.2`, KLayout `0.30.13`) is down to `DBU` and the die-level density rules
  `M2.4`/`M3.4`/`MT30.7`/`PL.8`, which fire on any standalone cell and say
  nothing about it: the cell-level **`DF.1c`** every earlier run reported (the
  sub-1 um MOSCAP COMP width, our own geometry) is **gone** at the ratified
  1.0 / 2.0 um widths, on the dogleg cells as well as the single-band ones.
- **LVS.** `klt lvs lvs_request.json` against each cell's own
  `lvs_reference.spice`, which keeps `cap_nmos_03v3` for the capacitor: **no
  `device_map`, no waiver, no substituted device**. 5/5 nets, 2/2 devices and
  4/4 pins paired in each cell. `klt extract` reads the capacitor as
  `cap_nmos_03v3` (not an `nfet`) at every point, which is the check that the
  resized MOS-capacitor marker still covers the enlarged COMP island.
- **ERC.** `klt erc ... --findings-only` against each cell's **own** new spec
  (next section). `erc_status: clean`, `erc_finding_count: 0`.
  As for `cell_candidate1/`, read **`erc_status`**, not `status`: `status` stays
  `not_checked` because there is no gf180mcu antenna table, and the command exits
  non-zero for that reason even when `erc_status` is `clean` -- pre-existing
  behaviour, identical on the committed cell.

**The candidate-1 caveats all carry over unchanged**, because the cell structure
is identical: Dualgate is not modelled for the 6 V rules, so the access device is
checked against the 3.3 V thresholds; the capacitor's `A`/`P` are secondary
parameters so its geometry is not compared by LVS, and the `subckt-call`
reference form gives it a placeholder `C`. The drawn capacitor sizes above
therefore rest on `generate.py` and `klt extract`, not on LVS. See the
`cell_candidate1/` "DRC" and "LVS" sections for the full statements.

### Hand-placed shapes re-derived for the ratified levels (2026-11-17, #296)

The blocks are composed by port *name*, so `pins=[...]` needs no coordinate work.
The `klt draw` rectangles are absolute in the composed frame and do **not** follow
the blocks, so each had to be re-derived per cell. All three now come from the
one shared derivation in `layout/candidate1_points.py` (`straps()` +
`cn_dogleg()`), which `cell_candidate1/` calls too:

- **`CN` source/drain strap -- a measured per-level window.** CN leaves each
  tap ring through that ring's metal1 exit gap, and the gap is centred on the
  device, so it rises with the width: measured `GAP_E`/`GAP_W` spans
  y -0.28..0.72 um at W = 0.42, -0.07..0.93 at 0.84, 0.01..1.01 at 1.0 and
  0.51..1.51 at 2.0 (centre W/2 + 0.01 um, tabulated in
  `spec/capacitor-geometry-decision.md`). With the 0.23 um `metal1.space.1`
  clearance required from every edge, the capacitor-1.0 points have the common
  window 0.24..0.49 um (access at 0.42) or 0.24..0.70 (access at 0.84), and
  one band (y 0.25..0.48) serves both. That band is exactly the 0.23 um metal1
  **minimum width** (M1.1) tall -- the first cut (0.26..0.47) failed M1.1 on
  its free-standing stretches between pads, observed on the first generated
  cell and fixed by thickening into the window's remaining room. At the
  capacitor-2.0 points the two windows are **disjoint** (0.74..1.28 vs
  -0.05..0.49 or 0.16..0.70) -- the constraint `#294` measured, with no
  single-rect CN. The strap there is a doglegged three-rect metal1 shape:
  a capacitor-side band through the capacitor ring's gap (y 0.78..1.25), an
  access-side band through the access ring's gap (y 0.0..0.45 at access
  0.42, 0.20..0.65 at 0.84), and a riser joining them across the inter-ring
  field -- which is wide enough because the binding edges are the ring
  *metal1* edges (x 2.35 and DX - 1.07 = 3.13, field 0.78 um), not the wider
  comp/pplus tap-ring extents the ERC well boxes quote. The riser clears both
  metal edges by >= 0.25 um; every segment clears its gap edges by
  >= 0.26 um; all DRC-clean on the committed cells.
- **`VB` tap-ring strap -- flat at Minimum, stacked at 2x.** The `TAP_N` pad
  centre rises as W + 2.28 um (measured at all four widths the grid draws).
  At capacitor-1.0 points one band spanning both pads
  (`min(y) - 0.21` .. `max(y) + 0.21`) still clears the capacitor's metal1
  gate pad (y W + 0.75..W + 1.17) by >= 0.32 um. At capacitor-2.0 points that
  gate pad (y 2.75..3.17) sits **between** the two rings' metal north bands
  (access 2.45..2.91 or 2.87..3.33, capacitor 4.03..4.49), so the flat band
  would sweep through it and short PL to VB; there VB is two stacked bands --
  one per ring, each over its TAP_N pad -- joined by a riser at
  x 1.10..1.50, right of the gate pad. (Measured metal1 shapes of the
  generated blocks; the gate pad is a real 0.42 x 0.42 metal1 rect over the
  gate contact, not just a port marker.)
- **`MOS_CAP_MK` capacitor marker.** The cap COMP island is as tall as the
  device width -- measured (0,0)-(1.28, W) at every width, x unchanged -- so
  the marker grows with it (`[-0.1, -0.1, 1.38, W + 0.1]`), keeping
  `cell_candidate1/`'s 0.1 um margin. Under-covering the island would make the
  deck read the gate as an `nfet` and LVS would stop matching, so the clean
  LVS and the `cap_nmos_03v3` census above confirm each marker.

The underlying tool gap -- absolute `klt draw` rectangles silently going illegal
when a swept device parameter moves the blocks under them, with DRC as the only
signal -- is filed generically upstream as
**2AMLogic/klayout-tools#5656** (a port-anchored drawn shape, or a
machine-readable keep-out for the ring's exit gap).

### Per-cell ERC specs (`layout/erc/supplies_c1_*.json`)

Each cell gets its **own** ERC spec. This is forced, not stylistic: the
Region I tie declares `well_layer: null` (native p-substrate, no drawn well
layer) and therefore asserts **hardcoded absolute** `well_boxes` -- the
extents of the two tap rings. A width change moves a ring's comp/pplus `y1`
(W + 2.65 um: 3.07 at 0.42, 3.49 at 0.84, 3.65 at 1.0, 4.65 at 2.0 -- all
measured), so a spec reused across cells would assert a substrate region that
no longer covers the grown ring. `cell_candidate1/`'s own spec is
`layout/erc/supplies.json`, updated in place for its new capacitor-ring `y1`
as part of this pass (its ERC report is regenerated with it, so
`provenance.spec.content_hash` verifies); the split cells keep their per-point
files. Each is a copy of `supplies.json` with only the tie's two `well_boxes`
`y1` values changed:

| Spec | Capacitor-ring box `y1` | Access-ring box `y1` |
|---|---|---|
| `supplies.json` (`cell_candidate1/`, updated 2026-11-17) | **3.65** | 3.07 |
| `supplies_c1_Amin_G2x.json` | **4.65** | 3.07 |
| `supplies_c1_A2x_Gmin.json` | **3.65** | **3.49** |
| `supplies_c1_A2x_G2x.json` | **4.65** | **3.49** |

**Reading the coverage numbers.** In all four cells the assertion covers
**100 % of the drawn tap area** (`uncovered_tap_area_um2: 0.0`,
`uncovered_tap_fraction: 0.0`), which is the figure that says the asserted
substrate region still covers the grown rings. The *extent* figure moves
whenever the two rings end at different heights:

| Cell | `drawn_tap_area_um2` | `uncovered_tap_fraction` | `extent_uncovered_fraction` |
|---|---|---|---|
| `cell_candidate1/` | 13.0148 | 0.0 | 0.114166 |
| `cell_candidate1_Amin_G2x/` | 15.1348 | 0.0 | 0.188735 |
| `cell_candidate1_A2x_Gmin/` | 14.0816 | 0.0 | 0.071339 |
| `cell_candidate1_A2x_G2x/` | 16.2016 | 0.0 | 0.153191 |

`extent_uncovered_fraction` is the fraction of the **cell extent** no asserted
box covers, so in a mixed cell it necessarily rises: the cell top is set by the
taller block's ring while the shorter block's box correctly stops lower,
leaving a strip beside the taller block that is genuinely outside both tap
rings. The rise is geometry, not an under-covering ring --
`uncovered_tap_fraction` staying 0.0 is what rules that out.

## cell_candidate3/ -- bitcell of candidate 3 (PMOS polarity variant), one cell only

`layout/cell_candidate3/` holds one bitcell of candidate 3
(`spec/cell-candidates.md`): a thin-oxide PMOS capacitor (`cap_pmos_03v3`) in
series with a 6.0 V PMOS access device (`pfet_06v0`), per
`design/cells/cell_candidate3.sch`. Same artifact set as `cell_candidate1/`
(`generate.py` with `--check`, GDS, `drc_report.json`, `lvs_request.json`,
`lvs_reference.spice`, `lvs_report.json`, `erc_report.json`). One cell of one
candidate, not the array; no claim about breakdown behaviour.

Toolchain: released `klt 0.8.0` with the engine pinned
(`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12`; regenerated
2026-11-17, #296), PDK `gf180mcuA`; no tool was installed or changed. Geometry
point as for candidate 1 (Minimum x Minimum): cap W 1.0 um x L 0.28 um (the
ratified Minimum level, `spec/capacitor-geometry-decision.md`), access W
0.42 um x L 0.55 um (schematic `lacc`, clamped at the generator floor -- the
same access deviation as candidate 1). `lvs_reference.spice` carries drawn
values.

- **Terminals.** BL is the access **source**, CN the access **drain** (as in
  the schematic, mirror of the NMOS candidates). Access gate is WL; cap gate is
  PL; cap source and drain are strapped on CN. The MOS-capacitor marker
  (166/5) is hand-placed over the cap COMP island, as for candidate 1
  (2AMLogic/klayout-tools#2953).
- **Well connection (stated).** Each device sits in its own N-well with an N+
  tap ring (Metal1 over contacts). The two tap rings are strapped on the north
  side as `VB`, so the access well and the capacitor well are one net, `VB`.
  Nothing connects `VB` to a supply here; it must be held at the most positive
  potential the cell sees (array-level decision, deferred). Well-junction
  breakdown, the known concern of this candidate, is **not** examined by this
  layout or by DRC/LVS.
- **Pitch.** The first placement at 4.2 um (candidate 1's pitch) violated
  `nwell.space.1` and `nplus.space.1`; the committed cell uses 4.8 um. Not waived.
- **DRC.** `klt drc --deck gf180mcu --top cell_candidate3`: `status: clean`,
  0 violations. Layers in stream without rules: 34/10 (labels), 166/5 (cap
  marker). The candidate-1 caveat applies: Dualgate is not modelled for the
  6 V rules, so the access device is checked against the 3.3 V thresholds.
  This `clean` is the **curated deck's**; the native runset's verdict is the
  next bullet, committed in `drc_crosscheck_report.json`.
- **The native runset's remaining findings on this cell are #297's, not the
  capacitor's.** `drc_crosscheck_report.json` (`klt drc --engine both --deck
  gf180mcu --top cell_candidate3 --pdk gf180mcuA --deck-var decks=all,-mslot`,
  klayout-tools `0.9.2`, KLayout `0.30.13`) reports 11 native findings on the
  committed GDS: **`DF.4d_MV` x5** ("Min. Nwell overlap of NCOMP outside
  DNWELL", 0.16 um, in `mos_array$1`) and **`DV.6` x1** ("Min. Dualgate enclose
  COMP", 0.24 um, in `mos_array$1`) -- #297's generator-owned set -- plus
  `DBU` x1 and the die-level density rules `M2.4`/`M3.4`/`MT30.7`/`PL.8`.
  The **`DF.1c`** (MOSCAP COMP width) every earlier run reported is **gone**:
  the capacitor is drawn at the ratified 1.0 um Minimum. The curated deck
  discloses `DF.4d_MV` and `DV.6` as unmodelled. Candidate 3's well
  connection is stated below, but the Nwell overlap it is drawn with does not
  meet the rule; that fix is #297's.
- **LVS.** `status: match`, 0 errors (`klt lvs --check lvs_report.json` run
  from the cell directory exits 0). Same bounds as candidate 1: the capacitor's
  geometry and capacitance are not compared.
- **ERC.** `klt erc ... layout/erc/supplies_region_iii.json` (the existing
  n-well tie spec): `erc_status: clean`, 0 findings, `erc.missing_tie` for the
  n-well tie checked. Antenna checks were skipped (no antenna PDK data).

## cell_candidate3_Amin_G2x/ -- the Candidate 3 capacitor-2x split point

`layout/cell_candidate3/` draws the `C3_Amin_Gmin` point; this directory draws
the `G2x` point the floorplan spends pads L32-L36 on
(`PL_C3_Amin_G2x_1..5`, `spec/run3-test-chip-floorplan.md`). Same cell as
`cell_candidate3/` in every other respect (thin-oxide PMOS capacitor
`cap_pmos_03v3` in series with a 6.0 V PMOS access device `pfet_06v0`, per
`design/cells/cell_candidate3.sch`), same artifact set, same bounds: one cell
of one point, not the array; no claim about breakdown behaviour. `design/` is
unedited -- the schematic is parameterized and only `lvs_reference.spice`
carries the drawn literals. Access sizing is held at **Minimum** (the floorplan
holds all of C3 at `Amin` so C1-Amin vs C3-Amin stays a like-for-like polarity
comparison). `cell_candidate3/` is deliberately **not** renamed, for the same
reason as `cell_candidate1/`: its reports are cited by `layout/README.md` and
its GDS sha256 is what its own `--check` pins.

### Geometry point and which axis carries the 2x

**The 2x is taken on the capacitor's width, at held drawn length, at the
ratified levels: W 1.0 -> 2.0 um, L 0.28 um, exactly doubling the capacitor
area (2.0 x 0.28 = 0.56 um2 against 1.0 x 0.28 = 0.28 um2).**
`spec/capacitor-geometry-decision.md` (#294) fixes both levels -- the 1.0 um
Minimum is the PDK runset's `DF.1c` MOSCAP COMP-width floor (the earlier drawn
0.42 um violated it; the 0.42 -> 0.84 pair this section used to document was
the generator-floor stand-in, replaced grid-wide by #296) -- and takes the 2x
on W because that is the axis `sim/` already scales for the G axis
(`run_experiment.py` applies `sizing_multiplier` to `wcap` only, `lcap`
passed through unscaled, in `klt/mk_klt_requests.py`), so "G2x" means the same
thing in `sim/` and in `layout/`. Doubling `L` instead would have disagreed
with `sim/` and grown the block in x, reopening the pitch constraint below.

Drawn values: cap W 2.0 um x L 0.28 um, access W 0.42 um x L 0.55 um
(schematic `lacc`), capacitor area (extracted, `klt extract`) **0.56 um2** =
exactly 2.000 x the `Gmin` cell's 0.28 um2, extracted as `cap_pmos_03v3` --
which is the check that the resized MOS-capacitor marker still covers the
enlarged COMP island. Access width extracted 0.42 um.

| Cell | `klt stats` bbox | size |
|---|---|---|
| `cell_candidate3/` (`C3_Amin_Gmin`) | (-1.23,-1.23)-(7.31,3.65) | 8.54 x 4.88 um = 41.68 um2 |
| `cell_candidate3_Amin_G2x/` | (-1.23,-1.23)-(7.31,4.65) | 8.54 x 5.88 um = 50.22 um2 |

The G2x cell is exactly 1.0 um taller and exactly as wide: moving a device
width from W1 to W2 grows its block's `bbox` `y1` by exactly (W2 - W1) and
leaves every x coordinate untouched (measured on `klt gen mos_array` 0.8.0 at
exactly these parameters), so the pitch `DX = 4.8` carries over from
`cell_candidate3/` -- and is **proved** by this cell's own DRC report
(`nwell.space.1`/`nplus.space.1` clean, 0 violations), not inferred from the
block extents. 50.22 um2 is well under the floorplan's 110 um2 estimate row
for the C3 instances; re-budgeting that row from the measured numbers is the
floorplan record's follow-up, not this pass.

### Hand-placed shapes re-derived for the ratified levels

The blocks are composed by port *name*, so `pins=[...]` needs no coordinate
work. The `klt draw` rectangles are absolute in the composed frame and do
**not** follow the blocks. At the 2x capacitor this cell needs the same two
structural changes as the candidate-1 G2x cells (both derivations measured on
the generated blocks; the candidate-1 family shares them via
`layout/candidate1_points.py`, this cell keeps its own literals because its x
extents differ):

- **`CN` source/drain strap -- doglegged.** CN leaves each tap ring through
  that ring's metal1 exit gap, which rises with device width (measured spans:
  y -0.28..0.72 um at W = 0.42 access, y 0.51..1.51 um at W_CAP = 2.0). With
  the 0.23 um `metal1.space.1` clearance from every gap edge the legal windows
  (-0.05..0.49 and 0.74..1.28) are **disjoint** -- no single-rect CN exists
  (`spec/capacitor-geometry-decision.md`). The strap is a three-rect metal1
  dogleg: an access-side band through the access ring's gap (y 0.0..0.45), a
  riser across the inter-ring field (access ring metal edge x 2.77, capacitor
  ring metal edge DX - 1.07 = 3.73 -- field 0.96 um wide; riser x 3.02..3.48
  clears both by >= 0.25 um), and a capacitor-side band through the
  capacitor ring's gap (y 0.78..1.25, >= 0.26 um clear).
- **`VB` tap-ring strap -- stacked.** The capacitor's metal1 gate pad
  (x DX+0.43..DX+0.85, y 2.75..3.17) sits **between** the two rings' metal
  north bands (access 2.45..2.91, capacitor 4.03..4.49), so one flat band
  spanning both TAP_N pads would sweep through it and short PL to VB. Two
  stacked bands -- one per ring, each over its TAP_N pad -- joined by a riser
  at x 3.05..3.45 connect them instead.
- **`MOS_CAP_MK` capacitor marker -- grown with the island.** The cap COMP
  island is as tall as the device width, (DX,0)-(DX+1.28,2.0) at W = 2.0,
  so the marker grows to match, keeping `cell_candidate3/`'s 0.1 um margin.

The underlying tool gap (absolute `klt draw` rectangles silently going illegal
when a swept device parameter moves the blocks under them) is the one already
filed generically upstream as **2AMLogic/klayout-tools#5656**; no new gap was
hit drawing this cell.

### Well connection (stated, unchanged from `cell_candidate3/`)

Each device sits in its own N-well with an N+ tap ring; the two tap rings are
strapped on the north side as `VB`, so the access well and the capacitor well
are one net. Nothing connects `VB` to a supply here; it must be held at the
most positive potential the cell sees (array-level decision, deferred).
Well-junction breakdown, the known concern of this candidate, is **not**
examined by this layout or by DRC/LVS.

### Results

Toolchain as for the Candidate 1 variant cells: released `klt 0.8.0` with the
engine pinned to the build-tested version --
`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12` -- PDK `gf180mcuA`;
no tool was installed or changed. The 0.8.0 pin is the one that reproduces the
committed cells byte-for-byte (`0.9.1` drifts them), so it is the pin this
cell must share.

| | result |
|---|---|
| DRC (curated deck) | `klt drc --deck gf180mcu --top cell_candidate3_Amin_G2x`: `status: clean`, 0 violations, deck `released: true`, no waiver and no rule disabled |
| DRC (native runset) | `drc_crosscheck_report.json` (`klt drc --engine both --deck gf180mcu --top cell_candidate3_Amin_G2x --pdk gf180mcuA --deck-var decks=all,-mslot`, klayout-tools `0.9.2`, KLayout `0.30.13`): native `status: violations`, 11 findings -- **no `DF.1c`** (the ratified 2.0 um width clears it); `DF.4d_MV` x5 and `DV.6` x1 (#297's generator-owned set, in `mos_array$1`), `DBU` x1, density `M2.4`/`M3.4`/`MT30.7`/`PL.8` |
| LVS | `klt lvs lvs_request.json`: `status: match`, 0 errors; 5/5 nets, 2/2 devices, 4/4 pins paired; no `device_map`, no waiver, no substituted device |
| ERC | `klt erc ... layout/erc/supplies_region_iii.json` (the existing spec, unedited -- it derives the well from the drawn 21/0 layer, so no per-cell box edit was needed): `erc_status: clean`, 0 findings; antenna `not_checked` (no PDK antenna data), so the command exits non-zero on a clean run -- read `erc_status` |

The Candidate 1 caveats carry over unchanged (identical cell structure):
Dualgate is not modelled for the 6 V rules so the access device is checked
against the 3.3 V thresholds; the capacitor's geometry and capacitance are not
compared by LVS (`subckt-call` placeholder `C`, `A`/`P` secondary), so the
drawn capacitor size rests on `generate.py` and `klt extract`. The committed
cross-check above is the cell's second native run: the first, committed
pre-`#296` (`cfcd4d6a`, at the 0.42 um capacitor), still showed the
cell-level `DF.1c` among its 12 findings -- the carried-forward-verdict
problem #296 was filed to end. The re-signed run at the ratified geometry
confirms by measurement what `#294` could only
infer (the 2.0 um width clears `DF.1c`), and its remaining cell-level
findings are exactly `#297`'s set (`DF.4d_MV` x5, `DV.6` x1, all in the
`mos_array` blocks) plus `DBU` and the die-level density rules. The doglegged
CN and stacked VB this cell needs at the 2x width are DRC-proven by the same
run: no `metal1.space.1` or any other strap finding appears.

`klt drc --check drc_report.json` and `klt lvs --check lvs_report.json` run
from the cell directory exit 0. `klt erc --check erc_report.json` reports the
spec hash as drifted when run from the cell directory -- pre-existing
`klt 0.8.0` behaviour, byte-identical on the committed `cell_candidate3/`
report (its spec path is repo-relative; only `cell_candidate1/`'s
cell-relative spec verifies from its directory).

## cell_candidate2/ -- drawn at the ratified capacitor levels; LVS match; remaining native findings are the PCell's

`layout/cell_candidate2/` holds one bitcell of candidate 2 (`spec/cell-candidates.md`):
a 6.0 V thick-oxide NMOS capacitor (`cap_nmos_06v0`) in series with the 10 V
drain-extended `nfet_10v0_asym`, per `design/cells/cell_candidate2.sch`. One
cell, not the array; no breakdown claim. Files: `generate.py` (with `--check`),
`cell_candidate2.gds`, `drc_report.json`, `drc_crosscheck_report.json`,
`erc_report.json`, `lvs_request.json`, `lvs_reference.spice`, `lvs_report.json`.

**Result on klt 0.9.2 (regenerated 2026-11-17, #296): LVS `match`; the two
capacitor violations the native runset found (`DF.1c`, `PL.2_MV`) are gone at
the ratified capacitor levels; what remains native are the PDK PCell's own
findings (dispositioned by #299's scoped exception) and the die-level rules.**
`klt lvs` matches (0 errors) using the upstream-documented LDMOS fold recipe.
No waiver, no hand-edited PCell geometry and no substituted device was used
anywhere below.

Toolchain: released `klt 0.9.2` (`uvx --from klayout-tools==0.9.2`), KLayout
0.30.13 (the engine bundled with that wheel), PDK `gf180mcuA`
(`open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, from `~/.ciel`). No host
tool was installed or changed. Regenerate/verify with
`uvx --from klayout-tools==0.9.2 python3 layout/cell_candidate2/generate.py --check`
(the generator calls `klt` on PATH, so put a `klt` wrapper for the pinned
version on PATH).

`generate.py --check` passes on 0.9.2 against the GDS committed by the
2026-11-17 regeneration (which moved the capacitor to the ratified
W = 1.0 um, L = 0.70 um levels, grew its marker, re-placed the right Via1 onto
the pad's new x position, and re-pointed the PL label -- see "Geometry").

### Source/drain assignment (deliberate)

d -> BL, s -> CN, as in the schematic. In the PCell the **centre COMP stripe
(between the two gate fingers) is the drain** and carries BL; the two outer
COMP stripes are the sources, strapped together and to the capacitor's S and D
as CN with a Metal2 bar over Via1 (so it crosses the PCell's closed tap ring
without touching it). WL joins the two gate pads in Metal1; VB straps the
PCell ring to the capacitor ring. Labels are drawn by `klt draw` on 34/10 (the
PCell has no `klt` ports).

### Geometry

| Device | Drawn | Note |
|---|---|---|
| Access (`nfet_10v0_asym` PDK PCell) | W = 4 um per finger x 2 fingers (8 um total), L = 0.6 um | The PCell clamps any `w` below 4 um to 4 um and always draws two fingers sharing the centre drain. The schematic default `wacc` (25 um) is not what is drawn. |
| Capacitor (`mos_array`, Dualgate marker, S and D strapped on CN) | W = 1.0 um, L = 0.70 um | The ratified Minimum level for Region II (`spec/capacitor-geometry-decision.md`): W at the `DF.1c` MOSCAP COMP-width floor, L at the `PL.2_MV` 6 V n-gate minimum. Extracted area 0.70 um2 (`cap_nmos_06v0`). |

The capacitor's growth moved two hand-placed shapes, both measured off the
generated block (the MV `mos_array` block's metal1 shifts **in x with L**:
its D pad is x CX+1.14..CX+1.56 at L = 0.56, CX+1.28..CX+1.70 at L = 0.70):

- **Right Via1 re-placed** (x CX+1.22..1.48 -> CX+1.28..1.54): at the new L the
  via's left sliver hung off the D pad, and the native deck flagged it
  (`V1.3a` "metal1 overlap of via1", observed on the first generated cell).
  The moved via sits fully on the pad and still fully under the Metal2 CN bar.
- **`MOS_CAP_MK` marker top edge** now `CY + W_CAP + 0.1` (the COMP island is
  as tall as the device width), and the **`PL` label** moved to the gate pad's
  new centre (the gate pad's y tracks W: CY + W + 0.96).

### LVS -- `match`

`klt lvs lvs_request.json`: `status: match`, `error_count: 0`. Nets paired
`BL`, `WL`, `PL`, `VB` plus the internal strap CN; devices paired
`nfet_10v0_asym` (1) and `cap_nmos_06v0` (1).

**What changed from the 0.9.1 `mismatch`.** Nothing in the layout. The
gf180mcu extraction deck models `nfet_10v0_asym` as a MOS *flavour*, not a
device class, so the PCell extracts -- on 0.9.1 and on 0.9.2 alike -- as **two
per-finger plain `nfet` devices** sharing the drain (`klt extract` census:
`nfet: 2`, `cap_nmos_06v0: 1`, `unsupported_devices: []`). klayout-tools 0.9.2
ships the recipe for comparing exactly that against a one-device reference
(`docs/cli/lvs.md`, "gf180mcu LDMOS PCell against a single reference device",
upstream 2AMLogic/klayout-tools#5277):

- `lvs_request.json` sets `options.combine_devices: true`, which folds the two
  per-finger devices into one device of `w_um = 8.0` before the compare. This
  works only because the two fingers already share D, G, S and body -- the
  cell's Metal1 WL strap and Metal2 CN strap, drawn for the schematic's sake,
  are what make the fold legal.
- `lvs_reference.spice` resolves the access device to the drawn total width,
  `W=8u nf=2`, instead of the previous `W=4u nf=1`.

**The fold is a real comparison, not a relaxation** (both controls measured on
0.9.2, same layout and request):

| Control | Verdict |
|---|---|
| reference `W=8u`, `combine_devices: true` (committed) | `match`, 0 errors |
| reference `W=6u`, `combine_devices: true` | `mismatch`, `device.property` `w_um` layout 8.0 vs reference 6.0 |
| reference `W=8u`, `combine_devices: false` | `mismatch`, `device.unmatched` x3 |

So the folded width is genuinely compared, and the fold is not what produces
the match.

**What the match does not establish.** Four warnings bound it, the same three
classes as candidates 1 and 3 plus the flavour point:

- `device.geometry_not_compared` and `device.placeholder_value`: the
  capacitor's `A`/`P` are secondary parameters and the `subckt-call` form gives
  it a placeholder `C`, so **no** parameter of the capacitor was compared -- the
  two sides were paired on topology alone. Its drawn size rests on
  `generate.py` and `klt extract`, not on this LVS.
- two `topology` warnings for device classes with no devices on either side.
- KLayout's comparer compares `w_um`/`l_um` only; `nf` and `m` in the reference
  record the drawn finger count and are not compared. The access device is
  compared as one 8 um device, so LVS does **not** establish that the drain is
  the drift-extended terminal -- the `nfet_10v0_asym` flavour is not a device
  class the compare can key on. The source/drain assignment above rests on the
  PCell's geometry and the extraction's net pairing, not on this verdict.

### DRC -- curated deck: 17 findings

`klt drc --deck gf180mcu --top cell_candidate2`: `status: violations`, 17, deck
content hash `sha256:c3f2cce49000857a3a71cb65203aabf0eb27cd0ee6b1c60e29792355c455c4b1`,
input GDS `sha256:5cb4a64fa103f2b698aeaffedddfc28405931e6afbfec8f21cf8b90678462e7a`
(the GDS committed by the 2026-11-17 regeneration).
All 17 have `source_cell` `nfet_10v0_asym`, i.e. lie inside the PDK PCell:
16 x `comp.enclosing.contact.1` and 1 x `comp.width.mv.1`. Nothing is reported
in the capacitor, the straps or the labels. Layers in stream without rules:
34/10 (labels), 166/5 (MOS-capacitor marker). These are the same 17 findings
seen on 0.9.0 and 0.9.1 -- neither the 0.9.1 nor the 0.9.2 fix changed them.

### DRC -- native-deck cross-check: 25 findings (was 27; the capacitor's two are gone)

`drc_crosscheck_report.json` is
`klt drc --engine both --deck gf180mcu --top cell_candidate2 --pdk gf180mcuA --deck-var decks=all,-mslot`:
the curated deck and the PDK's **own** sign-off runset
(`~/.ciel/gf180mcuA/libs.tech/klayout/tech/drc/gf180mcu.drc`) run
on the same GDS. `--deck-var decks=all,-mslot` is required: with
the default deck selection the native script aborts in its metal-slotting
section on this 3LM variant (`NameError: undefined local variable or method
'metal4_drawn'`, upstream 2AMLogic/klayout-tools#5091). The slotting rules do
not apply to a cell drawing only Metal1 and Metal2.

Native deck: `status: violations`, 25. Classified by where the geometry lives:

| Where | Rules | Count |
|---|---|---|
| Inside the PDK `nfet_10v0_asym` PCell | `CO.4` x16, `DF.6_MV` x2, `PL.4_MV` x2 | 20 |
| **Our own capacitor block** (`cap__core`) | none | **0** |
| Die-level metal/poly density | `M1.4`, `M2.4`, `M3.4`, `MT30.7` | 4 |
| Database unit | `DBU` x1 | 1 |

**klt's own comparison is not usable here.** `comparison.state` is
`not_comparable` with `groups: []` and every rule on both sides listed under
`comparison.unmapped`, so `--engine both` produced no rule mapping at all. The
agreement/disagreement below is read off the two reports by hand, by rule and
by cell, not from klt's comparison block (filed upstream, see "Upstream").

**Where the two decks agree and disagree on the PCell.**

- `comp.enclosing.contact.1` x16 (curated) **reproduces** as `CO.4` x16
  (native), same cell, same 16 markers: "COMP overlap of contact, 0.07 um" on
  the PCell's 0.22 um drain stripe. klayout-tools' own `docs/cli/drc.md` lists
  these as *known false positives, not cross-checked against the foundry
  runset*. On this host they now are cross-checked, and they are **not** false
  positives -- the PDK's own runset flags the PDK's own PCell. The waiver that
  `drc.md` offers for them is therefore not applicable here, and was not used.
- `comp.width.mv.1` x1 (curated) is **not** reproduced: the native `DF.1a_MV`
  reports nothing on that drain stripe. This one curated finding *is* a false
  positive, consistent with `drc.md`'s note that the official `DF.1a_MV`
  exempts MVSD-marked drains and the curated transcription does not.
- `DF.6_MV` x2 (COMP extend beyond gate, 0.4 um) and `PL.4_MV` x2 (Poly2 end
  cap beyond COMP, 0.22 um) fire only on the native side, both inside the
  PCell. The curated deck discloses both as unmodelled
  (`coverage.unmodeled_rules`), so this is disclosed non-coverage, not a
  silent miss.

**Our own capacitor block is clean under the native runset.** The two findings
every earlier run reported there are gone at the ratified levels:

- `DF.1c` ("Min. COMP Width for MOSCAP: 1 um") -- the capacitor's COMP island
  under the 166/5 marker is now drawn **1.0 um** wide, the ratified Minimum
  (`spec/capacitor-geometry-decision.md`); the rule no longer fires.
- `PL.2_MV` ("Gate Width (Channel Length)", 0.7 um minimum for a 6 V n-gate) --
  the capacitor is drawn at **L = 0.70 um**, the process minimum the old
  0.56 um violated; the rule no longer fires.

The earlier framing ("neither can be fixed inside this cell alone") held until
the levels were ratified: `spec/capacitor-geometry-decision.md` fixed the
shared axis, and #296 moved every cell onto it in one pass.

**Die-level rules.** `M1.4`/`M2.4`/`M3.4`/`MT30.7` are whole-die metal-density
("coverage over the entire die shall be > 30%") rules. A standalone 11.60 um x 8.80 um bitcell
trips them by construction; they are not cell-level findings and
say nothing about this cell. They become meaningful only at chip assembly
(#211), with dummy fill.

**`DBU`.** "The design database unit must be 0.001". The composed GDS is
written with `dbu = 0.0005`. This is a `klt` writer default, not the PCell:
candidates 1 and 3, composed by klt 0.7.0 and 0.8.0 with no PCell involved,
also carry `dbu = 0.0005`. Filed upstream (see "Upstream"); the geometry is on
a 5 nm grid either way, so this is a stream-format matter, not a geometry one.

### ERC

`klt erc ... layout/erc/supplies.json` (the existing p-tap spec): `erc_status:
clean`, 0 findings, `erc.missing_tie` checked for the p-substrate tie. Antenna
checks `not_checked` (no antenna PDK data). Three warnings record that the
spec's `metal3`/`metal4`/`metal5` label layers carry no text in this cell,
which is expected for a cell drawn in Metal1 and Metal2.

### Status against the acceptance criteria

| Criterion | Verdict |
|---|---|
| Full artifact set, `generate.py --check` passes under the pinned klt | met (klt 0.9.2, 2026-11-17 regeneration) |
| Source/drain assignment stated | met (d -> BL, s -> CN; stated above and in `generate.py`) |
| LVS `match` | **met** on klt 0.9.2 |
| DRC clean | not met overall, and no longer for our own geometry: the capacitor block is **clean under the native runset** at the ratified levels (`DF.1c`/`PL.2_MV` gone, 2026-11-17); what remains is 20 findings inside the PDK's own PCell, dispositioned by #299's scoped exception, plus the die-level density rules and `DBU` |

### Upstream

Filed generically at `2AMLogic/klayout-tools` from this pass, as the friction
protocol requires (follow-ups to the closed `klayout-tools` #4949, #4568,
#4892 and #5277):

- **`klayout-tools#5719`** -- the curated-vs-native delta measured above:
  `DF.1c` neither checked nor listed in `coverage.unmodeled_rules`,
  `comp.width.mv.1` a false positive, and `comp.enclosing.contact.1`
  reproducing as native `CO.4` where `drc.md` calls that result unverified and
  offers a waiver for it.
- **`klayout-tools#5720`** -- `--engine both` returning `not_comparable` with
  `groups: []` and every rule unmapped on both sides, so the cross-check cannot
  tell agreement from disagreement even when both engines ran. The agreement
  table above was worked out by hand because of this.
- **`klayout-tools#5721`** -- the composed GDS carrying `dbu = 0.0005` against
  the runset's own `DBU` rule (which requires 0.001); no output-dbu option on
  the writing verbs.

### Follow-up

The capacitor-geometry violations this section used to track (`DF.1c` on all
three candidates, `PL.2_MV` on this one) are **resolved as of the 2026-11-17
pass**: the levels were ratified in `spec/capacitor-geometry-decision.md`
(#294) and #296 moved every cell onto them in one change, native-deck-proven
by the committed cross-checks. What remains native on this cell is inside the
PDK's own PCell; the 20 PCell-internal findings are dispositioned by the
scoped exception recorded in
`spec/pdk-pcell-drc-exception-decision.md` (operator ruling 2026-11-15, #299):
reported as measured, never waived, and outside the exception for every shape
this repo draws. Candidate 3's `DF.4d_MV`/`DV.6` remain #297's.
