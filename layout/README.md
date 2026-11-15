# layout/

Layout and DRC/LVS signoff via klayout-tools.

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
| `generate.py` | Deterministic generator: this candidate's parameters (flavor, `L_ACC`, `DX`, strap/marker rectangles, placement, pin map) plus a call into the shared `layout/bitcell_gen.py`, which runs the flow (`klt gen mos_array` x2, `klt draw` for two Metal1 straps, `klt gen-compose` explicit placement). `--check` regenerates and compares the committed GDS byte-for-byte. |
| `cell_candidate1.gds` | Generated layout, top cell `cell_candidate1`, pins/labels `BL`, `WL`, `PL`, `VB`. |
| `drc_report.json` | `klt drc --deck gf180mcu --top cell_candidate1` report (status `clean`, 0 violations). |
| `lvs_request.json`, `lvs_reference.spice` | The LVS request and its reference netlist. |
| `lvs_report.json` | `klt lvs lvs_request.json` report (status `match`, 0 errors); see "LVS". |

Toolchain: `cell_candidate1.gds` and `drc_report.json` were produced with the
released `klt 0.7.0` (`uvx --from klayout-tools==0.7.0`), klayout 0.30.12, PDK
`gf180mcuA`. `lvs_report.json` and `erc_report.json` were produced by the released
`klt 0.8.0` (`uvx --from klayout-tools==0.8.0`, issue #196); `0.7.0` has no
MOS-capacitor device class and cannot run this LVS, and the report was first
produced by a dev build. No tool was installed or changed. Regenerate with
`python3 layout/cell_candidate1/generate.py` and verify with `--check`. The generators
need `klt` on PATH; to pin it without touching the host tool, run
`uvx --from klayout-tools==0.8.0 python3 layout/cell_candidate1/generate.py --check`
(`0.8.0` reproduces both committed GDS files; `0.7.0` drifts). Per-candidate
geometry stays in each `generate.py`; only the flow and `--check` live in
`layout/bitcell_gen.py`.

### Geometry point

`spec/split-axis-plan.md` sections 2-3 define levels, not numbered
sub-combinations. This cell is the **Minimum x Minimum** point (capacitor
geometry Minimum, access sizing Minimum) of a thin-oxide region. This is a
choice of sub-combination, not a spec change.

| Device | Drawn | Note |
|---|---|---|
| Capacitor (thin oxide NMOS, S and D strapped) | W = 0.42 um, L = 0.28 um | L is the 3.3 V minimum drawn length. |
| Access (`nfet_06v0`, Dualgate marker) | W = 0.42 um, L = 0.70 um | L matches the schematic's `lacc`. |

**Deviation to read before relying on it.** `klt gen mos_array` refuses
`w_um < 0.42` (a generator-side contact-fit floor above the PDK's own minimum
widths), so both widths are clamped to 0.42 um. The schematic's `wacc` default
is 0.30 um, and its `wcap`/`lcap` defaults are 1 um x 1 um placeholders. The
drawn point is therefore "minimum the generator can draw", not necessarily the
process minimum. `lvs_reference.spice` carries the drawn values, not the
schematic defaults.

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
deck `gf180mcu` content hash
`sha256:9babf6fd5d623fea50d380168ebf8f7c0f0f6e70eb7d89b221476dc47c7f6a85`,
input GDS `sha256:4fa502d0b9775f4dd8ba42fd2292c0a70edf83e3c528f52550a2ba4d1d9f44de`
(the report's `provenance.input.content_hash`). A first placement at 3.9 um
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
  Dualgate marker), except for the missing capacitor marker above.
- Layout-versus-programming-voltage suitability (thin-oxide device in a
  program path) is a design-intent matter this deck cannot judge.
- **The `clean` verdict is the curated deck's, and the PDK's own runset
  disagrees.** The native-deck cross-check could not be run when this section
  was written (the host KLayout predated the deck's 0.30.9 floor); it can now.
  Run on the committed GDS with klt 0.9.2
  (`--engine klayout --pdk gf180mcuA --deck-var decks=all,-mslot`), the PDK
  runset reports 6 findings: **`DF.1c` x1** ("Min. COMP Width for MOSCAP",
  1 um, in `mos_array` -- the capacitor's COMP island under the 166/5 marker is
  drawn 0.42 um), plus `DBU` x1 and the die-level density rules
  `M2.4`/`M3.4`/`MT30.7`/`PL.8`. The `DF.1c` finding is a real cell-level
  violation that the curated deck neither checks nor discloses; the density
  rules fire on any standalone cell. Tracked as #287 with the candidate 2 and
  3 runs; this section's `clean` means "clean under the curated deck", not
  signed off.

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
and DRC (`clean`) did not change.

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

The capacitor's drawn size (W 0.42 um, L 0.28 um) therefore rests on
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

**The 2x is relative to the drawn Minimum of 0.42 um, which is the generator's
width floor, not the process minimum.** `klt gen mos_array` refuses
`w_um < 0.42` (a contact-fit floor above the PDK's own minimum widths), so the
Minimum level is clamped, exactly as for `cell_candidate1/`. "2x" therefore means
2x the drawn Minimum (0.42 -> 0.84 um), not 2x a process minimum.

**The absolute widths differ from `sim/`'s, and that is pre-existing and
deliberate.** `sim/` scales the *schematic* defaults in
`design/netlists/cell_candidate1.spice` (`wacc=0.30u`, `wcap=1e-6`), so its 2x
points are 0.60 um and 2.0 um; `layout/` is clamped to 0.42 um, so its 2x point
is 0.84 um. The **convention** (which dimension carries the factor, and that the
factor is exactly 2) matches; the absolute geometry does not. Reconciling them
would mean editing `design/`, which is out of scope here.

### Geometry, as drawn and as extracted

Drawn values are from each `generate.py`; the capacitor area and access width
columns are **extracted** (`klt extract`, device parameters), so the 2x on each
axis is measured rather than asserted. Bounding boxes are `klt stats`.

| Cell | Access W x L (drawn) | Access W (extracted) | Capacitor W x L (drawn) | Capacitor area (extracted) | `klt stats` bbox |
|---|---|---|---|---|---|
| `cell_candidate1/` (`C1_Amin_Gmin`) | 0.42 x 0.70 um | 0.42 um | 0.42 x 0.28 um | 0.1176 um2 | (-1.23,-1.23)-(7.13,3.07), 8.36 x 4.30 um = 35.95 um2 |
| `cell_candidate1_Amin_G2x/` | 0.42 x 0.70 um | 0.42 um | **0.84** x 0.28 um | **0.2352** um2 | (-1.23,-1.23)-(7.13,3.49), 8.36 x 4.72 um = 39.46 um2 |
| `cell_candidate1_A2x_Gmin/` | **0.84** x 0.70 um | **0.84** um | 0.42 x 0.28 um | 0.1176 um2 | (-1.23,-1.23)-(7.13,3.49), 8.36 x 4.72 um = 39.46 um2 |
| `cell_candidate1_A2x_G2x/` | **0.84** x 0.70 um | **0.84** um | **0.84** x 0.28 um | **0.2352** um2 | (-1.23,-1.23)-(7.13,3.49), 8.36 x 4.72 um = 39.46 um2 |

The two split axes move independently and each by exactly 2, which is the point
of the grid: extracted capacitor area is 0.2352 / 0.1176 = **2.000** across the
`G` axis at constant `A`, and extracted access width is 0.84 / 0.42 = **2.000**
across the `A` axis at constant `G`. Capacitor drawn length is held at 0.28 um
and access drawn length at 0.70 um in all four cells.

All three new cells land at the **same** bounding box, which is expected rather
than a mistake: doubling either device width grows that block in y only and
leaves every x coordinate untouched (measured on `klt gen mos_array`: a block's
`bbox` `y1` moves 3.07 -> 3.49 um, every x unchanged), and the cell top is set by
the taller of the two blocks. So the x pitch `DX = 4.2` carries over unchanged
from `cell_candidate1/` -- and is **proved** by each cell's own DRC report, not
inferred from the block extents. 39.46 um2 is well under the floorplan's 72 um2
estimate row for these instances; replacing that estimate is a later change.

### Results

Toolchain for all three: released `klt 0.8.0` with the engine pinned to the
version that build was tested against --
`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12` -- PDK `gf180mcuA`.
No tool was installed or changed. The pin matters twice: `0.8.0` is the release
that reproduces `cell_candidate1.gds` and `cell_candidate3.gds` byte-for-byte
(`0.9.1` drifts both), and pinning `klayout==0.30.12` keeps
`provenance.klayout_version_mismatch` `false` on every report (an unpinned run
resolves klayout `0.30.13` and sets it `true`, which the tool warns may shift
report counts). Regenerate or verify any cell with:

```
uvx --from klayout-tools==0.8.0 --with klayout==0.30.12 \
  python3 layout/cell_candidate1_A2x_G2x/generate.py --check
```

| Cell | DRC | LVS | ERC |
|---|---|---|---|
| `cell_candidate1_Amin_G2x/` | `status: clean`, 0 violations | `status: match`, 0 errors | `erc_status: clean`, 0 findings |
| `cell_candidate1_A2x_Gmin/` | `status: clean`, 0 violations | `status: match`, 0 errors | `erc_status: clean`, 0 findings |
| `cell_candidate1_A2x_G2x/` | `status: clean`, 0 violations | `status: match`, 0 errors | `erc_status: clean`, 0 findings |

- **DRC.** `klt drc --deck gf180mcu`, deck `released: true`, no waiver and no
  rule disabled. Layers in stream without rules are 34/10 (labels) and 166/5
  (capacitor marker), as for `cell_candidate1/`.
- **LVS.** `klt lvs lvs_request.json` against each cell's own
  `lvs_reference.spice`, which keeps `cap_nmos_03v3` for the capacitor: **no
  `device_map`, no waiver, no substituted device**. 5/5 nets, 2/2 devices and
  4/4 pins paired in each cell. `klt extract` reads the capacitor as
  `cap_nmos_03v3` (not an `nfet`), which is the check that the resized
  MOS-capacitor marker still covers the enlarged COMP island.
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

### Two hand-placed shapes had to be re-derived (and one of them had to change)

The blocks are composed by port *name*, so `pins=[...]` needs no coordinate work.
The `klt draw` rectangles are absolute in the composed frame and do **not** follow
the blocks, so each had to be re-derived per cell:

- **`VB` tap-ring strap.** The `TAP_N` pad centre rises with the device width
  (y = 2.70 um at W = 0.42, y = 3.12 um at W = 0.84), so in the two mixed cells
  the two rings' `TAP_N`s sit 0.42 um apart in y and `cell_candidate1/`'s single
  flat 0.42 um band cannot overlap both. Each new cell uses one band spanning
  both pads (`min(y) - 0.21` to `max(y) + 0.21`), which degenerates to a pure
  +0.42 um shift of the committed rect in `A2x_G2x` where both pads move
  together. The strap **overlaps** both pads rather than abutting them.
- **`CN` source/drain strap -- this one is a real constraint, not bookkeeping.**
  CN leaves each tap ring through that ring's metal1 exit gap, and the gap is
  centred on the device, so it rises with the width too: measured `GAP_E`/`GAP_W`
  span y -0.28..0.72 um at W = 0.42 and y -0.07..0.93 um at W = 0.84.
  `cell_candidate1/`'s band (y 0.06..0.36) is 0.34 um clear of the gap edge at
  the Minimum width but only **0.13 um** clear once a block is doubled, and it
  **does** fail `metal1.space.1` (0.23 um) -- observed as a real DRC violation on
  the first generated cell, not predicted. The three new cells raise CN to
  y 0.18..0.48, which clears both rings' gaps by >= 0.24 um in every cell. The
  S/D pads are as tall as the device width, so the raised band lies inside a
  doubled pad (y 0..0.84); over a pad still at the Minimum width it overhangs
  the pad's top edge (y 0.42) by 0.06 um, which is metal over field and DRC
  clean, and it still overlaps every pad by >= 0.24 um in y.
- **`MOS_CAP_MK` capacitor marker.** The cap COMP island is as tall as the device
  width -- measured (0,0)-(1.28,0.42) at W = 0.42 and (0,0)-(1.28,0.84) at
  W = 0.84, x unchanged -- so the marker grows with it, keeping
  `cell_candidate1/`'s 0.1 um margin. It is unchanged in `A2x_Gmin`, whose
  capacitor is at Minimum. Under-covering the island would make the deck read the
  gate as an `nfet` and LVS would stop matching, so the clean LVS above is what
  confirms each marker.

The underlying tool gap -- absolute `klt draw` rectangles silently going illegal
when a swept device parameter moves the blocks under them, with DRC as the only
signal -- is filed generically upstream as
**2AMLogic/klayout-tools#5656** (a port-anchored drawn shape, or a
machine-readable keep-out for the ring's exit gap).

### Per-cell ERC specs (`layout/erc/supplies_c1_*.json`)

Each new cell gets its **own** ERC spec, and `layout/erc/supplies.json` is left
untouched. This is forced, not stylistic: the Region I tie declares
`well_layer: null` (native p-substrate, no drawn well layer) and therefore
asserts **hardcoded absolute** `well_boxes` -- the extents of the two tap rings.
A width doubling moves a ring's `y1` from 3.07 to 3.49 um, so reusing
`supplies.json` would assert a substrate region that no longer covers the grown
ring. Editing it in place is not an option either, because `klt erc --check`
validates `provenance.spec.content_hash` and `cell_candidate1/erc_report.json` is
ratified signoff evidence (`signoff/manifest.json`, `signoff/README.md` rows
`3.analog`/`4.analog`/`11.analog`). Each new file is a copy of `supplies.json`
with only the tie's two `well_boxes` `y1` values changed:

| Spec | Capacitor-ring box `y1` | Access-ring box `y1` |
|---|---|---|
| `supplies.json` (`cell_candidate1/`, unchanged) | 3.07 | 3.07 |
| `supplies_c1_Amin_G2x.json` | **3.49** | 3.07 |
| `supplies_c1_A2x_Gmin.json` | 3.07 | **3.49** |
| `supplies_c1_A2x_G2x.json` | **3.49** | **3.49** |

**Reading the coverage numbers.** In all three new cells the assertion covers
**100 % of the drawn tap area** (`uncovered_tap_area_um2: 0.0`,
`uncovered_tap_fraction: 0.0`), which is the figure that says the asserted
substrate region still covers the grown rings. The *extent* figure moves, and
only for the mixed cells:

| Cell | `drawn_tap_area_um2` | `uncovered_tap_fraction` | `extent_uncovered_fraction` |
|---|---|---|---|
| `cell_candidate1/` | 11.7852 | 0.0 | 0.055024 |
| `cell_candidate1_Amin_G2x/` | 12.6756 | 0.0 | 0.099303 |
| `cell_candidate1_A2x_Gmin/` | 12.8520 | 0.0 | 0.094832 |
| `cell_candidate1_A2x_G2x/` | 13.7424 | 0.0 | 0.055024 |

`extent_uncovered_fraction` is the fraction of the **cell extent** no asserted
box covers, so in a mixed cell it necessarily rises: the cell top is set by the
doubled block (y1 = 3.49) while the Minimum block's box correctly stops at
y1 = 3.07, leaving a ~4.16 x 0.42 um strip beside the taller block that is
genuinely outside both tap rings. `A2x_G2x`, where both boxes rise together,
returns to the committed cell's 0.055024 exactly. The rise is geometry, not an
under-covering ring -- `uncovered_tap_fraction` staying 0.0 is what rules that
out.

## cell_candidate3/ -- bitcell of candidate 3 (PMOS polarity variant), one cell only

`layout/cell_candidate3/` holds one bitcell of candidate 3
(`spec/cell-candidates.md`): a thin-oxide PMOS capacitor (`cap_pmos_03v3`) in
series with a 6.0 V PMOS access device (`pfet_06v0`), per
`design/cells/cell_candidate3.sch`. Same artifact set as `cell_candidate1/`
(`generate.py` with `--check`, GDS, `drc_report.json`, `lvs_request.json`,
`lvs_reference.spice`, `lvs_report.json`, `erc_report.json`). One cell of one
candidate, not the array; no claim about breakdown behaviour.

Toolchain: released `klt 0.8.0` (`uvx --from klayout-tools==0.8.0`), PDK
`gf180mcuA`; no tool was installed or changed. Geometry point as for candidate
1 (Minimum x Minimum, generator width floor 0.42 um): cap W 0.42 um x L 0.28 um,
access W 0.42 um x L 0.55 um (schematic `lacc`). The same clamp deviation
applies (schematic `wacc` is 0.30 um); `lvs_reference.spice` carries drawn
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
- **The PDK's own runset disagrees with that `clean`.** The native-deck
  cross-check, impossible on this host when this section was written and
  possible now (standalone KLayout 0.30.12), reports 12 findings on the
  committed GDS under klt 0.9.2
  (`--engine klayout --pdk gf180mcuA --deck-var decks=all,-mslot`): **`DF.4d_MV`
  x5** ("Min. Nwell overlap of NCOMP outside DNWELL", 0.16 um), **`DV.6` x1**
  ("Min. Dualgate enclose COMP", 0.24 um) and **`DF.1c` x1** (MOSCAP COMP
  width, as for candidate 1) -- all in the `mos_array` blocks, so all in our
  own geometry -- plus `DBU` x1 and the die-level density rules
  `M2.4`/`M3.4`/`MT30.7`/`PL.8`. The curated deck discloses `DF.4d_MV` and
  `DV.6` as unmodelled; it does not disclose `DF.1c`. Candidate 3's well
  connection is stated below, but the Nwell overlap it is drawn with does not
  meet the rule. Tracked as #287 with the candidate 1 and 2 runs; this
  section's `clean` means "clean under the curated deck", not signed off.
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

**The 2x is taken on the capacitor's width, at held drawn length: W 0.42 ->
0.84 um, L 0.28 um, exactly doubling the drawn area (0.84 x 0.28 = 0.2352 um2
against 0.42 x 0.28 = 0.1176 um2).** `spec/split-axis-plan.md` section 2
ratifies "double the minimum capacitor area (via W and/or L scaling)" and
leaves the split open; width is taken here because that is the axis `sim/`
already scales for the G axis (`run_experiment.py` applies
`sizing_multiplier` to `wcap` only, `lcap` passed through unscaled, in
`klt/mk_klt_requests.py`), so "G2x" means the same thing in `sim/` and in
`layout/` -- the same convention the Candidate 1 variant cells document. As
there, the 2x is 2x the **drawn** Minimum of 0.42 um (the generator's width
floor), not 2x a process minimum, and `sim/`'s absolute widths differ
pre-existingly. Doubling `L` instead would have disagreed with `sim/` and
grown the block in x, reopening the pitch constraint below.

Drawn values: cap W 0.84 um x L 0.28 um, access W 0.42 um x L 0.55 um
(schematic `lacc`), capacitor area (extracted, `klt extract`) **0.2352 um2** =
exactly 2.000 x the `Gmin` cell's 0.1176 um2, extracted as `cap_pmos_03v3` --
which is the check that the resized MOS-capacitor marker still covers the
enlarged COMP island. Access width extracted 0.42 um.

| Cell | `klt stats` bbox | size |
|---|---|---|
| `cell_candidate3/` (`C3_Amin_Gmin`) | (-1.23,-1.23)-(7.31,3.07) | 8.54 x 4.30 um = 36.72 um2 |
| `cell_candidate3_Amin_G2x/` | (-1.23,-1.23)-(7.31,3.49) | 8.54 x 4.72 um = 40.31 um2 |

The new cell is 0.42 um taller and exactly as wide: doubling a device width
grows its block in y only and leaves every x coordinate untouched (measured on
`klt gen mos_array` 0.8.0 at exactly these parameters), so the pitch
`DX = 4.8` carries over from `cell_candidate3/` -- and is **proved** by this
cell's own DRC report (`nwell.space.1`/`nplus.space.1` clean, 0 violations),
not inferred from the block extents. 40.31 um2 is well under the floorplan's
110 um2 estimate row for the C3 instances; replacing that estimate row is a
later change, not this one.

### Hand-placed shapes had to be re-derived (and one of them changed)

The blocks are composed by port *name*, so `pins=[...]` needs no coordinate
work. The `klt draw` rectangles are absolute in the composed frame and do
**not** follow the blocks. The same three derivations as the Candidate 1
variant cells apply, with the same outcome:

- **`VB` tap-ring strap -- reshaped.** With only the cap block doubled, the
  two rings' `TAP_N` pads sit at different heights (y = 2.70 um access,
  y = 3.12 um cap, each pad 0.42 um across). `cell_candidate3/`'s flat band
  (y 2.49..2.91) would end edge-touching the cap pad with zero overlap, so
  this cell uses one band spanning both pads (`min(y) - 0.21` to
  `max(y) + 0.21` = y 2.49..3.33), x extents unchanged from `cell_candidate3/`.
- **`CN` source/drain strap -- raised.** Same constraint as measured on the
  Candidate 1 variant cells: CN leaves each tap ring through that ring's
  metal1 exit gap, which rises with device width (y -0.28..0.72 um at
  W = 0.42, y -0.07..0.93 um at W = 0.84), and the inherited 0.06..0.36 band
  leaves only 0.13 um below the doubled ring's gap -- under the 0.23 um
  `metal1.space.1` clearance, observed as a real DRC violation on the
  Candidate 1 equivalents. CN is raised to y 0.18..0.48, clearing both gaps by
  >= 0.24 um; it lies inside the doubled cap pads (y 0..0.84), overhangs the
  Minimum access pad's top edge by 0.06 um (metal over field), and still
  overlaps every pad by >= 0.24 um in y.
- **`MOS_CAP_MK` capacitor marker -- grown with the island.** The cap COMP
  island is as tall as the device width, (DX,0)-(DX+1.28,0.84) at W = 0.84,
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
| DRC | `klt drc --deck gf180mcu --top cell_candidate3_Amin_G2x`: `status: clean`, 0 violations, deck `released: true`, no waiver and no rule disabled |
| LVS | `klt lvs lvs_request.json`: `status: match`, 0 errors; 5/5 nets, 2/2 devices, 4/4 pins paired; no `device_map`, no waiver, no substituted device |
| ERC | `klt erc ... layout/erc/supplies_region_iii.json` (the existing spec, unedited): `erc_status: clean`, 0 findings; antenna `not_checked` (no PDK antenna data), so the command exits non-zero on a clean run -- read `erc_status` |

The Candidate 1 caveats carry over unchanged (identical cell structure):
Dualgate is not modelled for the 6 V rules so the access device is checked
against the 3.3 V thresholds; the capacitor's geometry and capacitance are not
compared by LVS (`subckt-call` placeholder `C`, `A`/`P` secondary), so the
drawn capacitor size rests on `generate.py` and `klt extract`. The curated-deck
`clean` is not signed off: the PDK's native-deck cross-check findings tracked
as **#287** for `cell_candidate3/` can be expected here too (same blocks, same
rules); running that cross-check on this cell is follow-up work, not part of
this issue.

`klt drc --check drc_report.json` and `klt lvs --check lvs_report.json` run
from the cell directory exit 0. `klt erc --check erc_report.json` reports the
spec hash as drifted when run from the cell directory -- pre-existing
`klt 0.8.0` behaviour, byte-identical on the committed `cell_candidate3/`
report (its spec path is repo-relative; only `cell_candidate1/`'s
cell-relative spec verifies from its directory).

## cell_candidate2/ -- drawn, LVS match on klt 0.9.2, DRC NOT clean

`layout/cell_candidate2/` holds one bitcell of candidate 2 (`spec/cell-candidates.md`):
a 6.0 V thick-oxide NMOS capacitor (`cap_nmos_06v0`) in series with the 10 V
drain-extended `nfet_10v0_asym`, per `design/cells/cell_candidate2.sch`. One
cell, not the array; no breakdown claim. Files: `generate.py` (with `--check`),
`cell_candidate2.gds`, `drc_report.json`, `drc_crosscheck_report.json`,
`erc_report.json`, `lvs_request.json`, `lvs_reference.spice`, `lvs_report.json`.

**Result on klt 0.9.2: LVS `match`, DRC NOT clean.** `klt lvs` now reaches
`match` (0 errors) using the upstream-documented LDMOS fold recipe; the DRC
criterion is still not met, and this run establishes for the first time *which*
of the findings are real, because the PDK's own native runset could finally be
run as a cross-check on this host. No waiver, no hand-edited PCell geometry and
no substituted device was used anywhere below.

Toolchain: released `klt 0.9.2` (`uvx --from klayout-tools==0.9.2`), KLayout
0.30.13 (the engine bundled with that wheel) for the curated deck and the
extraction, standalone KLayout 0.30.12 for the native deck, PDK `gf180mcuA`
(`open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, from `~/.ciel`). No host
tool was installed or changed. Regenerate/verify with
`uvx --from klayout-tools==0.9.2 python3 layout/cell_candidate2/generate.py --check`
(the generator calls `klt` on PATH, so put a `klt` wrapper for the pinned
version on PATH).

`generate.py --check` passes on 0.9.2: GDS `sha256:c8bc23f9d6057ccb3df2d7ee2ab3ff603a302c3ed7817646c8ab39aaaea9118d`,
byte-identical to the GDS committed from the 0.9.1 run. **No layout geometry
changed in the 0.9.2 pass** -- only the LVS request/reference and the reports.

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
| Capacitor (`mos_array`, Dualgate marker, S and D strapped on CN) | W = 0.42 um, L = 0.56 um | W is the `mos_array` generator floor. **L = 0.56 um is below the process minimum** -- see "What the native deck found in our own geometry". |

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
input GDS `sha256:c8bc23f9d6057ccb3df2d7ee2ab3ff603a302c3ed7817646c8ab39aaaea9118d`.
All 17 have `source_cell` `nfet_10v0_asym`, i.e. lie inside the PDK PCell:
16 x `comp.enclosing.contact.1` and 1 x `comp.width.mv.1`. Nothing is reported
in the capacitor, the straps or the labels. Layers in stream without rules:
34/10 (labels), 166/5 (MOS-capacitor marker). These are the same 17 findings
seen on 0.9.0 and 0.9.1 -- neither the 0.9.1 nor the 0.9.2 fix changed them.

### DRC -- native-deck cross-check: 27 findings (new on this host)

`drc_crosscheck_report.json` is
`klt drc --engine both --deck gf180mcu --top cell_candidate2 --pdk gf180mcuA --deck-var decks=all,-mslot`:
the curated deck and the PDK's **own** sign-off runset
(`~/.ciel/gf180mcuA/libs.tech/klayout/tech/drc/gf180mcu.drc`, tree hash
`sha256:8af3b4875893f3ffbff639bd7e2966c5e3b9b27f70d03e86d6da46ca9510fbc4`) run
on the same GDS. **Earlier passes recorded this cross-check as impossible
because the host KLayout was older than the deck's 0.30.9 floor; the host now
carries 0.30.12, so it runs.** `--deck-var decks=all,-mslot` is required: with
the default deck selection the native script aborts in its metal-slotting
section on this 3LM variant (`NameError: undefined local variable or method
'metal4_drawn'`, upstream 2AMLogic/klayout-tools#5091). The slotting rules do
not apply to a cell drawing only Metal1 and Metal2.

Native deck: `status: violations`, 27. Classified by where the geometry lives:

| Where | Rules | Count |
|---|---|---|
| Inside the PDK `nfet_10v0_asym` PCell | `CO.4` x16, `DF.6_MV` x2, `PL.4_MV` x2 | 20 |
| **Our own capacitor block** (`cap__core`) | `DF.1c` x1, `PL.2_MV` x1 | 2 |
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

**What the native deck found in our own geometry** -- the finding that matters
most here, because it is not the PCell's and not waivable:

- `DF.1c` x1, "Min. COMP Width for MOSCAP: 1 um", in `cap__core`. The rule is
  `comp AND mos_cap_mk` width >= 1 um. The capacitor's COMP island under the
  166/5 marker is drawn **0.42 um** wide (the `mos_array` generator floor), so
  it is under the foundry minimum by more than a factor of two. The curated
  deck neither checks this rule nor lists it in `coverage.unmodeled_rules`; it
  reports 166/5 under `layers_in_stream_without_rules`, which reads as "no rule
  applies" rather than "a rule applies and is not modelled".
- `PL.2_MV` x1, "Gate Width (Channel Length)", in `cap__core`. For a 6 V
  n-gate the native deck's minimum channel length is **0.7 um**; the capacitor
  is drawn at L = 0.56 um. The comment in `generate.py` calling 0.56 um "the
  6 V minimum drawn length" is wrong. The curated deck discloses `PL.2_MV` as
  unmodelled.

Both are real violations of the drawn capacitor, and **neither can be fixed
inside this cell alone**: the 0.42 um COMP width is the `mos_array` floor that
candidates 1 and 3 also sit on, so changing it moves the capacitor-geometry
split-axis level shared by all three candidates. Tracked as its own issue (see
"Follow-up") rather than changed here.

**Die-level rules.** `M1.4`/`M2.4`/`M3.4`/`MT30.7` are whole-die metal-density
("coverage over the entire die shall be > 30%") rules. A standalone 11.5 um x 8.7 um bitcell
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
| Full artifact set, `generate.py --check` passes under the pinned klt | met (klt 0.9.2) |
| Source/drain assignment stated | met (d -> BL, s -> CN; stated above and in `generate.py`) |
| LVS `match` | **met** on klt 0.9.2 |
| DRC clean | **not met**: 2 real violations in our own capacitor (`DF.1c`, `PL.2_MV`) and 20 in the PDK PCell, confirmed against the PDK's own runset |

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

The capacitor-geometry violations (`DF.1c` on all three candidates, `PL.2_MV`
on this one, plus `DF.4d_MV` x5 and `DV.6` on candidate 3) are tracked as
**#287**, with the candidate 1 and candidate 3 native runs that found them.
`DF.1c` cannot be fixed per cell: the 0.42 um COMP width is the `mos_array`
floor shared through `layout/bitcell_gen.py`, so raising it moves the
capacitor-geometry split-axis level for every candidate at once -- a `spec/`
decision, not a layout edit.

Candidate 2 cannot reach "DRC clean" until #287 is settled, and even then the
20 PCell-internal findings need an operator decision of their own: the PDK's
own cell is what violates them, this repo does not hand-edit PCell geometry,
and `CO.4` x16 is now confirmed against the foundry runset rather than being
the false positive klayout-tools' docs call it.
