# layout/

The [Region I array core](array_region_i/README.md) routes all 352 Candidate 1 bitcells in the first 11 columns of the N=32 array and verifies the physical connectivity against the xschem source.

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

The routed 32-row array bands have their own connectivity and physical
verification results. [Region I](array_region_i/README.md) implements 352
Candidate 1 cells in columns 0–10. [Region III](array_region_iii/README.md)
implements 320 Candidate 3 cells in columns 22–31, including the two
0.84 µm access variants. [Region II](array_region_ii/README.md) implements the
remaining 352 cells with all four asymmetric-access geometry splits.

## Signed MOS capacitors in the drawn cells

The schematic assigns the capacitor gate to CN, the internal storage terminal of the access transistor. PL drives the diffusion electrode. The private gate pads of the bare C2 fallback are a separate probe contract. They retain two independent gates, PL_GMIN and PL_G2X, over shared diffusion BL.

Each access-cell generator reproduced its committed GDS with `--check`. C1 and C3 use klayout-tools 0.8.0 with the Python KLayout 0.30.12 wheel. Standard C2 and the top composer use klayout-tools 0.9.2 with KLayout 0.30.13. The GDS hashes below are SHA-256 prefixes. Each adjoining PEX report records the full input hash. Native counts use the pinned open_pdks f6eeac7 deck, gf180mcuA, `decks=all,-mslot`, and KLayout CLI 0.30.12.

| Cell | Previous GDS | Signed GDS | Native findings |
|---|---|---|---:|
| cell_candidate1 | `d31a786ed748` | `fa008179952e` | 5 |
| cell_candidate1_A2x_G2x | `eeba35dcb209` | `977bf49d703b` | 5 |
| cell_candidate1_A2x_Gmin | `c39f4556d4e9` | `e42ae36dfb05` | 5 |
| cell_candidate1_Amin_G2x | `cb7db0539a00` | `c291881ec1a5` | 5 |
| cell_candidate2 | `5cb4a64fa103` | `f2bb06eea53f` | 26 |
| cell_candidate2_fallback | `92b431518b22` | `92b431518b22` | 5 |
| cell_candidate3 | `4ee36d7b8e02` | `a388126da5fb` | 6 |
| cell_candidate3_Amin_G2x | `cd0e2feac496` | `a9c60259a4e2` | 5 |

LVS matches every cell reference. Structural ERC is clean on all seven access cells. The native standalone findings include die-level density and the generator DBU. In a same-deck comparison of the standard C2, both streams have the same 26 native findings including one `MDN.10c`. The diagnostic fd_pv#42 patch also produces 22 findings on the signed C2. The dated control reports in `cell_candidate2/` identify the earlier stream. The wide C3 retains a Metal1 landing on each side of its two ring gaps to preserve its standalone density.

The fully assembled top changed from `e231fe008290a62c343210bc29354ac3918a6eef3b67875f5cdb91198f1a63b7` to `2ff9138f63a8497075a9b8edf2833ac6504de0929820af074969750e5e41c7bd`. Its 31 placed instances match 72 nets and 67 devices. ERC reports zero structural findings across 35 gates. The same native gating deck produced 106 findings on both streams (80 CO.4, ten DF.6_MV, ten PL.4_MV, five MDN.10c and one DBU). The private-plate antenna findings fall from 31 to zero. The 29 shared-WL findings persist. The separate density stage records zero markers and its companion deck log reports success. See `run3_top/` for the machine-readable envelopes, ratio database and density log.

### Signed electrical control

The nonlinear PEX binding uses klayout-tools source `9d2780c5e1c842777519330943a5435b118c4437` and Python KLayout 0.30.14. Run the following from a cell directory with that extractor and the pinned PDK. Extract-only returns 4 and emits the netlist and report.

```sh
cell=$(basename "$PWD")
klt pex "$cell.gds" --deck gf180mcu --pdk gf180mcuD --extract-only \
  --reference-netlist lvs_reference.spice -o pex/extracted.spice --format json > pex/pex_report.json
```

The signed connectivity check collapses the extracted parasitic resistor network, matches each access finger to the schematic terminals and checks the oriented capacitor terminals. It covers the four C1 points, standard C2, all four C3 points and both bare probe capacitors. Tests swap the physical plates while retaining the model, geometry, hash and body-bias report and independently short the fallback gates.

At 10 kHz, with `moscap_typical` and V(CN)−V(PL) as shown, the checker measured these isolated small-signal capacitances in fF using ngspice 47 with the upstream bug 876 correction. For a replay set `PDK_ROOT` to the open_pdks installation and `KLT_NGSPICE_BINARY` to the simulator, then run `python3 sim/cell-device-characterization/klt/post-layout/check_signed_caps.py` from the repository root.

| Cell | Bias (V) | Reference (fF) | Physical (fF) | Swapped control (fF) |
|---|---:|---:|---:|---:|
| C1 | +1 | 1.10447524 | 1.10447524 | 0.00644000 |
| C1 | -1 | 0.00644000 | 0.00644000 | 1.10447524 |
| C2 | +1 | 1.50007223 | 1.50007223 | 0.02590000 |
| C2 | -1 | 0.02590000 | 0.02590000 | 1.50007223 |
| C3 | +1 | 0.01064000 | 0.01064000 | 1.03410075 |
| C3 | -1 | 1.03410075 | 1.03410075 | 0.01064000 |

The paired whole-cell access bench is in `sim/cell-device-characterization/klt/post-layout/`. Its C3 R_on discrepancy remains open. Array-level post-layout verification and the five unplaced wide C2 slots remain tracked separately.

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
| `generate.py` | Deterministic generator: names the `Amin_Gmin` entry of `layout/candidate1_points.py`, which holds this candidate's parameters (flavor, `L_ACC`, `DX`, placement, pin map) and the strap derivation shared by the whole candidate-1 family (CN, VB and the MOS-capacitor marker). The flow (`klt gen mos_array` x2, `klt draw` for the straps and marker, `klt gen-compose` explicit placement) and the `--check` byte-compare live in the shared `layout/bitcell_gen.py`; `--check` regenerates and compares the committed GDS byte-for-byte. |
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
each `generate.py`, except the candidate-1 points (`cell_candidate1` and
`cell_candidate1_{A2x_G2x,A2x_Gmin,Amin_G2x}`): their shared constants and
strap derivation live in `layout/candidate1_points.py`, and each of those
`generate.py` files names one `POINTS` entry. Only the flow and `--check`
live in `layout/bitcell_gen.py`.

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
  strapped together on net PL (a MOS capacitor). It is drawn as a plain
  transistor from `mos_array`, and `generate.py` adds the PDK MOS-capacitor
  marker (`MOS_CAP_MK`, 166/5) as a hand-placed rectangle over its COMP island,
  because `klt gen` has no MOS-capacitor primitive (upstream
  2AMLogic/klayout-tools#2953). Without that marker the extraction deck reads
  the gate as an `nfet` (see "LVS"). The marker is not drawn over the access
  device.
- Each device sits inside its own P+ tap ring (Metal1 over contacts), so
  neither body floats. The two rings are strapped on the north side (`VB`).
  Both devices are NMOS in the p-substrate; no well is needed or drawn.
- CN crosses the tap rings on Metal2 from the access source to the capacitor gate.
  `BL` (access drain), `WL` (access gate), `PL` (shorted capacitor diffusion) are pad
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
one shared derivation in `layout/candidate1_points.py` (`straps()`), which `cell_candidate1/` calls too:

- **Capacitor wiring.** CN connects the access transistor's storage terminal
  to the gate of the capacitor. A Via1 at each end connects the 0.50 µm
  Metal2 run to Metal1. A separate Metal1 strap connects both capacitor
  diffusion pads to PL. The transistor and capacitor taps share VB.
- **`VB` tap-ring strap -- flat at Minimum, stacked at 2x.** The `TAP_N` pad
  centre rises as W + 2.28 um (measured at all four widths the grid draws).
  At capacitor-1.0 points one band spanning both pads
  (`min(y) - 0.21` .. `max(y) + 0.21`) still clears the capacitor's metal1
  gate pad (y W + 0.75..W + 1.17) by >= 0.32 um. At capacitor-2.0 points that
  gate pad (y 2.75..3.17) overlaps the lower of the two rings' metal north
  bands (access 2.49..2.91 or 2.91..3.33, capacitor 4.07..4.49), so the flat band
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

Candidate 2 carries the same requirement, and until #373 did not meet it: it
ran `supplies.json` unchanged, and candidate 1's boxes cover only ~45 % of its
far larger drawn Comp (`uncovered_tap_fraction: 0.55393` on
`drawn_tap_area_um2: 28.9152`), so its `erc_status: clean` was a verdict over
the shared boxes' region only. #373 gave it `supplies_c2.json`, a copy of
`supplies.json` differing only in the tie's two `well_boxes` -- now the
extents of candidate 2's own two `Pplus` tap-ring outlines,
`[-2.83, -4.02, 2.83, 4.02]` (capacitor block) and `[4.27, -0.44, 8.43, 4.44]`
(`nfet_10v0_asym` PCell block) -- restoring `uncovered_tap_fraction: 0.0`
(`drawn_tap_area_um2: 28.9152`, `extent_uncovered_fraction: 0.355337`). See
`cell_candidate2/`'s ERC section for what the verdict does and does not cover.

## cell_candidate3/ -- bitcell of candidate 3 (PMOS polarity variant), one cell only

`layout/cell_candidate3/` holds one bitcell of candidate 3
(`spec/cell-candidates.md`): a thin-oxide PMOS capacitor (`cap_pmos_03v3`) in
series with a 6.0 V PMOS access device (`pfet_06v0`), per
`design/cells/cell_candidate3.sch`. Same artifact set as `cell_candidate1/`
(`generate.py` with `--check`, GDS, `drc_report.json`,
`drc_crosscheck_report.json`, `lvs_request.json`, `lvs_reference.spice`,
`lvs_report.json`, `erc_report.json`). One cell of one candidate, not the
array; no claim about breakdown behaviour.

Toolchain: released `klt 0.8.0` with the engine pinned
(`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12`; regenerated
2026-11-17, #296; acc-block ring padding and DX re-fitted 2026-11-17, #297),
PDK `gf180mcuA`; no tool was installed or changed. Geometry point as for
candidate 1 (Minimum x Minimum): cap W 1.0 um x L 0.28 um (the ratified
Minimum level, `spec/capacitor-geometry-decision.md`), access W 0.42 um x L
0.55 um (schematic `lacc`, clamped at the generator floor -- the same access
deviation as candidate 1), and the access block's tap ring drawn at the
generator's raised `ring_padding_um` 1.29 (see the ring-padding bullet below).
`lvs_reference.spice` carries drawn values.

- **Terminals.** BL is the access **source**, CN the access **drain** (as in
  the schematic, mirror of the NMOS candidates). The access gate is WL. CN reaches the capacitor gate and PL joins its source and drain. The MOS-capacitor marker
  (166/5) is hand-placed over the cap COMP island, as for candidate 1
  (2AMLogic/klayout-tools#2953).
- **Well connection (stated).** Each device sits in its own N-well with an N+
  tap ring (Metal1 over contacts). The two tap rings are strapped on the north
  side as `VB`, so the access well and the capacitor well are one net, `VB`.
  Nothing connects `VB` to a supply here; it must be held at the most positive
  potential the cell sees (array-level decision, deferred). Well-junction
  breakdown, the known concern of this candidate, is **not** examined by this
  layout or by DRC/LVS.
- **Ring padding (#297).** The generator's default `ring_padding_um` 0.5
  draws the access block (the only pfet + medium-voltage marker block) with
  its N-well 0.15 um inside the N+ tap ring -- the native deck's
  `DF.4d_MV` "Min. Nwell overlap of NCOMP outside DNWELL: 0.16 um" misses by
  10 nm -- and with the Dualgate marker missing COMP enclosure (`DV.6`,
  0.24 um). Both are generator-owned geometry, so the fix is the generator
  parameter, not drawn edits: the shared flow (`layout/bitcell_gen.py`) grew a
  `ring_padding_acc_um` keyword (default 0.5, byte-stable for the other five
  cells) and this cell sets it to **1.29 um, acc block only** -- the smallest
  value that clears both rules on the composed cell with no new cell-level
  finding. Measured on the composed cell (`klt drc --engine both`, native
  rule counts): 0.5 -> `DF.4d_MV` x5 + `DV.6` x1; 1.0 -> x9 + x1 (worse);
  1.05-1.28 -> both clear but **`DV.3` x5 appears** ("Min. Dualgate to COMP
  space [unrelated]: 0.24 um" -- the raised ring's N+ escapes the
  core-anchored Dualgate marker; `DF.4d_MV` runs 5 -> 9 -> 0 across
  0.5/1.0/1.05, then `DV.3` runs 5 -> 0 across 1.28/1.29); **1.29 -> clean of
  all three**; 1.28, one step below, still reports `DV.3` x5 (minimality
  evidence). The capacitor block keeps the default: it draws no Dualgate
  marker and its well overlap is legal. The generator response is filed
  upstream (public tracker, generic description):
  2AMLogic/klayout-tools#6503.
- **Pitch.** The first placement at 4.2 um (candidate 1's pitch) violated
  `nwell.space.1` and `nplus.space.1`; the committed cell used 4.8 um. With
  the raised acc-ring padding the access ring moves out on all four sides by
  0.79 um, so the placement grows to **5.59 um** (= 4.8 + the padding delta),
  keeping the proven 0.79 um ring-to-ring gap (4.2's 0.19 um gap is what
  violated `nwell.space.1`). Not waived. The VB strap's access-side edge
  tracks the raised ring and keeps the band at the 0.23 um metal1 minimum
  width (`M1.1` fired at 1.3 um padding without that floor -- measured); the
  CN strap and the capacitor marker track DX. CN crosses the Metal1 ring on Metal2.
- **DRC.** `klt drc --deck gf180mcu --top cell_candidate3`: `status: clean`,
  0 violations. Layers in stream without rules: 34/10 (labels), 166/5 (cap
  marker). The candidate-1 caveat applies: Dualgate is not modelled for the
  6 V rules, so the access device is checked against the 3.3 V thresholds.
  This `clean` is the **curated deck's**; the native runset's verdict is the
  next bullet, committed in `drc_crosscheck_report.json`.
- **The native runset's cell-level findings are cleared (#297).**
  `drc_crosscheck_report.json` (`klt drc --engine both --deck gf180mcu --top
  cell_candidate3 --pdk gf180mcuA --deck-var decks=all,-mslot`, klayout-tools
  `0.9.2`, KLayout `0.30.13`, re-signed 2026-11-17 at the padded geometry) had
  reported 11 native findings on the committed GDS -- **`DF.4d_MV` x5** and
  **`DV.6` x1**, both generator-owned and in `mos_array$1`, plus `DBU` x1 and
  the die-level density rules `M2.4`/`M3.4`/`MT30.7`/`PL.8`. At the 1.29 um
  acc-ring padding the generator-owned set is **gone** (see the ring-padding
  bullet), and what remains native is `DBU` x1 and the die-level density
  rules, now including **`M1.4`** ("Metal1 coverage over the entire die
  >30%"): the grown cell's standalone bbox dilutes metal1 coverage below the
  30 % window, the same die-level density class as `M2.4`/`M3.4`/`MT30.7`/
  `PL.8`, which fire on any standalone cell and are disclosed, not fixed --
  die-level assembly settles them (`spec/run3-test-chip-floorplan.md`).
  The **`DF.1c`** (MOSCAP COMP width) every earlier run reported is **gone**
  since #296: the capacitor is drawn at the ratified 1.0 um Minimum. The
  curated deck discloses `DF.4d_MV` and `DV.6` as unmodelled and reports
  `clean` (0 violations) on the padded geometry too. Candidate 3's well
  connection is stated above; the N-well overlap it is drawn with now meets
  the rule.
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
| `cell_candidate3/` (`C3_Amin_Gmin`) | (-2.02,-2.02)-(8.10,3.86) | 10.12 x 5.88 um = 59.50 um2 (grown from 41.68 um2 by #297's raised acc-ring padding) |
| `cell_candidate3_Amin_G2x/` | (-2.02,-2.02)-(8.10,4.65) | 10.12 x 6.67 um = 67.50 um2 (50.22 um2 before this cell took the same padding; the growth is the access ring, see the ring-padding bullet below) |

At the generator default this cell was exactly as wide as the unpadded
`Gmin` cell: moving a device width from W1 to W2 grows its block's `bbox`
`y1` by exactly (W2 - W1) and leaves every x coordinate untouched (measured
on `klt gen mos_array` 0.8.0 at exactly these parameters), which is why
`DX = 4.8` carried over from `cell_candidate3/`. With the raised acc-ring
padding both cells' access rings move out on all four sides, so both bboxes
are 10.12 um wide and this cell's pitch is `DX = 4.8 + (RING_PAD_ACC - 0.5)`
= 5.59 um -- the expression `cell_candidate3/` already documents -- keeping
the proven 0.79 um ring-to-ring n-well gap. That the re-fit holds is
**proved** by this cell's own DRC, not inferred from the block extents: no
`nwell.space.1`/`nplus.space.1` at any padding of the 1.05-1.40 sweep, and 0
curated violations at the committed 1.29. 67.50 um2 replaces the floorplan's
C3 estimate row with measured numbers (`spec/run3-test-chip-floorplan.md`,
re-measured this pass).

### Hand-placed shapes re-derived for the ratified levels

The blocks are composed by port *name*, so `pins=[...]` needs no coordinate
work. The `klt draw` rectangles are absolute in the composed frame and do
**not** follow the blocks. At the 2x capacitor this cell needs the same two
structural changes as the candidate-1 G2x cells (both derivations measured on
the generated blocks; each family shares them once -- candidate 1 via
`layout/candidate1_points.py`, candidate 3 via `layout/candidate3_points.py`
since #397 consolidated the two candidate-3 generators -- because the two
families' x extents differ):

- **Capacitor wiring.** CN connects the access transistor's storage terminal
  to the gate of the capacitor. A Via1 at each end connects the 0.50 µm
  Metal2 run to Metal1. A separate Metal1 strap connects both capacitor
  diffusion pads to PL. The transistor and capacitor taps share VB.
- **`VB` tap-ring strap -- stacked.** One flat band spanning both TAP_N pads
  (y 3.28..4.49 at the committed padding) would fail `metal1.space.1`
  (0.23 um) against the capacitor's metal1 gate pad (x DX+0.43..DX+0.85,
  y 2.75..3.17): the band overlaps the pad in x (band right edge DX+0.79 =
  6.38 > pad left 6.02) but its bottom edge (3.28, the raised access band's
  level) clears the pad top (3.17) by only **0.11 um** -- measured on a
  scratch single-flat-band variant through `klt drc --deck gf180mcu`:
  exactly one `metal1.space.1` finding, bbox (5.818,3.170)-(6.440,3.280) um
  (the committed GDS is clean on the same rule). The pad is **not between**
  the two rings' metal north bands (access 3.28..3.70 = 2.49 + DPAD ..
  2.91 + DPAD at the raised ring, capacitor 4.07..4.49, both measured off
  the committed GDS): the access band sits entirely above the pad top 3.17,
  so the constraint is spacing, not the sweep-through short the
  default-padding geometry had. Two stacked bands -- one per ring, each
  over its TAP_N pad (the access one riding the raised ring via
  `Y_TAP_ACC = 2.70 + DPAD` = 3.49, measured off `klt gen mos_array`) -- joined
  by a riser at x 3.05 + DPAD .. 3.45 + DPAD = 3.84..4.24 connect them
  instead.
- **`MOS_CAP_MK` capacitor marker -- grown with the island.** The cap COMP
  island is as tall as the device width, (DX,0)-(DX+1.28,2.0) at W = 2.0,
  so the marker grows to match, keeping `cell_candidate3/`'s 0.1 um margin.

The underlying tool gap (absolute `klt draw` rectangles silently going illegal
when a swept device parameter moves the blocks under them) is the one already
filed generically upstream as **2AMLogic/klayout-tools#5656**; no new gap was
hit drawing this cell.

### Ring padding: #297's parameter, re-bisected on this cell

The generator's default `ring_padding_um` 0.5 draws the access block (the
only pfet + medium-voltage marker block) with its N-well 0.15 um inside the
N+ tap ring -- the native deck's `DF.4d_MV` "Min. Nwell overlap of NCOMP
outside DNWELL: 0.16 um" misses by 10 nm -- and with the Dualgate marker
missing COMP enclosure (`DV.6`, 0.24 um). This variant pairs pfet with
medium_voltage exactly like `cell_candidate3/`, so it carried the identical
generator defect (2AMLogic/klayout-tools#6503) after #297 cleared the base
cell: the shared flow's `ring_padding_acc_um` keyword (default 0.5,
byte-stable for every cell that omits it) applies here too, acc block only.
The value is **not** copied from #297's 1.29 -- the response is
non-monotonic and rule-swapping, so it was re-bisected on this composed cell
in 0.01 um steps at `DX = 4.8 + (RING_PAD_ACC - 0.5)` (native rule counts,
`klt drc --engine klayout`, klayout-tools `0.9.2`, KLayout `0.30.13`):

| padding (um) | `DF.4d_MV` | `DV.6` | `DV.3` | `nwell.space.1` class |
|---|---|---|---|---|
| 0.5 (default) | 5 | 1 | 0 | clean |
| 1.0 | 9 | 1 | 0 | clean |
| 1.05-1.28 | 0 | 0 | 5 | clean |
| **1.29 (committed)** | 0 | 0 | 0 | clean |
| 1.30-1.40 | 0 | 0 | 0 | clean |

1.0 is *worse* than the default (`DF.4d_MV` 5 -> 9, plus a `DV.7` x1 this
base cell did not show); 1.05-1.28 trades both findings for **`DV.3` x5**
("Min. Dualgate to COMP space [unrelated]: 0.24 um" -- the raised ring's N+
escapes the core-anchored Dualgate marker), the same window #297 measured on
`cell_candidate3/`; **1.29 clears all three**, 1.28 -- one 0.01 um step below
-- still reports `DV.3` x5 (minimality evidence), and 1.30-1.40 stay clean,
so 1.29 is the floor of the clean region, not a window edge. The whole sweep
is `nwell.space.1`/`nplus.space.1`-clean at the tracked pitch, so the `DX`
re-fit holds across the range, and the grown cell trips **no new die-level
density rule** (the density set below is unchanged -- no `M1.4`, which
`cell_candidate3/` itself picked up when #297 grew its bbox). The capacitor
block keeps the default: it draws no Dualgate marker and its well overlap is
legal.

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
cell must share. (Acc-block ring padding, `DX`/`Y_TAP_ACC` and the strap
x-extents re-fitted 2026-11-18, #382.)

| | result |
|---|---|
| DRC (curated deck) | `klt drc --deck gf180mcu --top cell_candidate3_Amin_G2x`: `status: clean`, 0 violations, deck `released: true`, no waiver and no rule disabled |
| DRC (native runset) | `drc_crosscheck_report.json` (`klt drc --engine both --deck gf180mcu --top cell_candidate3_Amin_G2x --pdk gf180mcuA --deck-var decks=all,-mslot`, klayout-tools `0.9.2`, KLayout `0.30.13`, re-signed 2026-11-18 at the padded geometry): native `status: violations`, **5 findings** -- `DBU` x1 and the die-level density rules `M2.4`/`M3.4`/`MT30.7`/`PL.8`, the same set as before the padding; **`DF.4d_MV` and `DV.6` are gone** (#297's generator-owned set, cleared by the re-bisected 1.29 um acc-ring padding, see the ring-padding bullet), no `DF.1c` (the ratified 2.0 um width clears it), and **no new density rule** -- no `M1.4` despite the growth |
| LVS | `klt lvs lvs_request.json`: `status: match`, 0 errors; 5/5 nets, 2/2 devices, 4/4 pins paired; no `device_map`, no waiver, no substituted device |
| ERC | `klt erc ... layout/erc/supplies_region_iii.json` (the existing spec, unedited -- it derives the well from the drawn 21/0 layer, so no per-cell box edit was needed): `erc_status: clean`, 0 findings; antenna `not_checked` (no PDK antenna data), so the command exits non-zero on a clean run -- read `erc_status` |

The Candidate 1 caveats carry over unchanged (identical cell structure):
Dualgate is not modelled for the 6 V rules so the access device is checked
against the 3.3 V thresholds; the capacitor's geometry and capacitance are not
compared by LVS (`subckt-call` placeholder `C`, `A`/`P` secondary), so the
drawn capacitor size rests on `generate.py` and `klt extract`. The committed
cross-check above is the cell's third native run: the first, committed
pre-`#296` (`cfcd4d6a`, at the 0.42 um capacitor), still showed the
cell-level `DF.1c` among its 12 findings -- the carried-forward-verdict
problem #296 was filed to end; the second, at the ratified geometry, carried
exactly `#297`'s generator-owned set (`DF.4d_MV` x5, `DV.6` x1, all in the
`mos_array` blocks) plus `DBU` and the die-level density rules. The
re-signed run at the padded geometry confirms by measurement that what #297
cleared on the base cell clears here too: the cell-level findings are
**gone** (see the ring-padding bullet), leaving `DBU` and the die-level
density rules -- the same disclosed, die-level-assembly class as on every
other cell -- and no new density rule appeared despite the bbox growing
50.22 -> 67.50 um2. The Metal2 CN route and stacked Metal1 VB bands pass spacing checks. LVS pairs all five nets.

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
`erc_report.json`, `lvs_request.json`, `lvs_reference.spice`, `lvs_report.json`,
plus #521's dated fixed-deck diagnostic comparison artifacts
(`drc_native_pinned_control_20261125.json`, `drc_native_fd_pv_42.json`,
`fd_pv_42_rule_decks.patch` -- not sign-off verdicts; see
`spec/pdk-pcell-drc-exception-decision.md` § "Fixed-deck comparison
(2026-11-25, #521)").

**Result on klt 0.9.2 (regenerated 2026-11-17, #296): LVS `match`; the two
capacitor violations the native runset found (`DF.1c`, `PL.2_MV`) are gone at
the ratified capacitor levels; what remains native are the PDK PCell's own
findings (dispositioned by #299's scoped exception) and the die-level rules.**
`klt lvs` matches (0 errors) using the upstream-documented LDMOS fold recipe.
No waiver, no hand-edited PCell geometry and no substituted device was used
anywhere below.

Toolchain: released `klt 0.9.2` (`uvx --from klayout-tools==0.9.2`), KLayout
0.30.13 (the engine bundled with that wheel), PDK `gf180mcuA`
(`open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, from `~/.ciel`).
(Exception: `drc_native_pinned_control_20261125.json` and
`drc_native_fd_pv_42.json` were recorded 2026-11-25 on the worker's
`klt 0.9.3.dev5587+g945e94f0` / KLayout `0.30.12`, with the latter run against a
scratch copy of the native deck carrying `fd_pv#42`. Both historical reports identify the pre-#539 GDS in their provenance. They are a diagnostic comparison
only, not the project deck.) No host
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
COMP stripes are the sources, strapped together and to the capacitor gate
as CN with a Metal2 bar over Via1 (so it crosses the PCell's closed tap ring
without touching it). WL joins the two gate pads in Metal1; VB straps the
PCell ring to the capacitor ring. Labels are drawn by `klt draw` on 34/10 (the
PCell has no `klt` ports).

### Geometry

| Device | Drawn | Note |
|---|---|---|
| Access (`nfet_10v0_asym` PDK PCell) | W = 4 um per finger x 2 fingers (8 um total), L = 0.6 um | The PCell clamps any `w` below 4 um to 4 um and always draws two fingers sharing the centre drain. The schematic default `wacc` (25 um) is not what is drawn. |
| Capacitor (`mos_array`, Dualgate marker, S and D strapped on PL) | W = 1.0 um, L = 0.70 um | The ratified Minimum level for Region II (`spec/capacitor-geometry-decision.md`): W at the `DF.1c` MOSCAP COMP-width floor, L at the `PL.2_MV` 6 V n-gate minimum. Extracted area 0.70 um2 (`cap_nmos_06v0`). |

Both source stripes connect to the capacitor gate through a Metal2 jog at
y = 1.85 µm. This clears the PL landing on the capacitor diffusion at
(5.71, 1.00) µm and the via on the substrate ring. The MOS capacitor marker
covers the capacitor COMP island with a 0.1 µm margin.

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

`klt erc layout/cell_candidate2/cell_candidate2.gds layout/erc/supplies_c2.json
--top cell_candidate2 --format json` (from the repo root; klt 0.9.2, KLayout
0.30.13): `erc_status: clean`, 0 findings, `erc.missing_tie` checked for the
p-substrate tie. Antenna checks `not_checked` (no antenna PDK data; the run is
not `--findings-only`, so the antenna half reports per-level gate areas with
verdict `unchecked` -- read `erc_status`, not `status`, per the exit-code
contract). Four warnings record that the spec's `metal2`/`metal3`/`metal4`/
`metal5` label layers carry no text in this cell -- every net is labeled on
Metal1 (34/10, 4 texts) -- expected for a cell routed in Metal1 and Metal2
whose Metal2 shapes are all straps driven from Metal1.

**The tie is asserted against this cell's own boxes (#373).** Until #373 this
cell ran candidate 1's `supplies.json`, whose two `well_boxes` (fitted to
candidate 1's rings) miss both of this cell's tap rings almost entirely:
measured per polygon (Comp 22/0, merged), the capacitor-block ring
`(-2.67, -3.86)-(2.67, 3.86)` and the PCell's closed ring
`(4.43, -0.28)-(8.27, 4.28)` fall outside the shared boxes together with the
capacitor's own COMP islands, leaving `uncovered_tap_area_um2: 16.017` of
`drawn_tap_area_um2: 28.9152` (`uncovered_tap_fraction: 0.55393`) unchecked --
the `clean` above was a verdict over ~45 % of the cell's drawn tap area, the
carried-forward-verdict problem #296 was filed to end. `supplies_c2.json`
is a copy of `supplies.json` differing only in the tie's `well_boxes`, now the
extents of this cell's two `Pplus` 31/0 tap-ring outlines:
`[-2.83, -4.02, 2.83, 4.02]` (capacitor-block ring) and
`[4.27, -0.44, 8.43, 4.44]` (`nfet_10v0_asym` PCell ring).

What the `missing_tie` verdict now covers: all 28.9152 um2 of drawn Comp
22/0 -- `uncovered_tap_area_um2: 0.0`, `uncovered_tap_fraction: 0.0`. The
metric's "tap area" is the merged `tap_layer` (Comp) area *before* the
`tap_requires` Pplus and Contact narrowing, so the device diffusion enclosed by each ring
counts as covered; the tie check itself requires a Contact in Comp and Pplus
wired to Metal1 on `VB`. `extent_uncovered_fraction: 0.355337` is the cell
extent (11.60 x 8.80 um) outside both boxes -- the margin between the Pplus
outlines and the cell edge, where no tap is drawn. The regenerated report
verifies: `klt erc --check layout/cell_candidate2/erc_report.json` (from the
repo root) returns `status: match`; `supplies.json` itself is byte-unchanged,
so the four candidate-1 reports still verify against it.

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
this repo draws. Candidate 3's `DF.4d_MV`/`DV.6` were cleared by #297 (base
cell) and #382 (the `Amin_G2x` variant).

## cell_candidate2_fallback/ -- the Run 3 C2-fallback variant, bare capacitor, native census clean at cell level

`layout/cell_candidate2_fallback/` holds the fallback variant ruled on
2026-11-17 (#372, `spec/run3-c2-fallback-proposed.md`): Candidate 2 with its
`nfet_10v0_asym` access device removed, drawn as two bare `cap_nmos_06v0`
capacitors -- one per ratified capacitor-geometry level
(`spec/capacitor-geometry-decision.md` Region II: Gmin W 1.0 um x L 0.70 um,
G2x W 2.0 um x L 0.70 um), gate private per block (`PL_GMIN`/`PL_G2X`), S/D
strapped on the shared `BL`, tap rings tied on `VB`. This is the unit the
chip replicates five times per level (M5/M6); there is no PCell and no
access device anywhere in the cell. The generator passes only literal
parameters to `klt gen mos_array`; the hand-drawn shapes are the BL dogleg
strap (the two ring-gap heights differ, and the vertical join needs metal1
minimum width 0.23 um, M1.1 -- the first native run flagged the original
0.14 um join), the two-part VB strap (one straight band would short
`PL_G2X` -- the first LVS run found exactly that), and the two MOS-capacitor
markers. Files: `generate.py` (with `--check`), `cell_candidate2_fallback.gds`,
`drc_crosscheck_report.json`, `lvs_request.json`, `lvs_reference.spice`,
`lvs_report.json`. Full evidence, the cost comparison and the work left to
GDS: `spec/run3-c2-fallback-proposed.md`.

Toolchain: released `klt 0.9.2` (`uvx --from klayout-tools==0.9.2`), KLayout
0.30.13 (bundled) for the curated deck and LVS, standalone 0.30.12 for the
native deck, PDK `gf180mcuA`. Regenerate/verify with
`uvx --from klayout-tools==0.9.2 klt` reachable as `klt` on PATH, then
`python3 -I layout/cell_candidate2_fallback/generate.py --check`
(GDS `sha256:92b431518b22a3c8067b31442b2c91792df72b9358bb5362b111121a994f7a16`).

**Result: curated deck `clean`; native runset `violations`, 5 findings, all
die-level** (`DBU` x1 -- the writer default, upstream
2AMLogic/klayout-tools#5721; `M2.4`/`M3.4`/`MT30.7`/`PL.8` -- whole-die
density rules, expected on any standalone cell and judged at #211). By cell:
**zero findings** in `cap_gmin`, `cap_g2x` or the straps. The PCell-internal
`CO.4`/`DF.6_MV`/`PL.4_MV` findings that make the primary Candidate 2 cell
unsubmittable are **absent**, and so are the old-geometry capacitor findings
`DF.1c`/`PL.2_MV` -- W >= 1.0 um and L = 0.70 um clear them, as the
capacitor-geometry record derived. LVS: `match`, 0 errors, 4 nets paired
(capacitor `A`/`P` are secondary parameters and are not compared -- the
drawn dimensions rest on the generator parameters and the `--check` hash,
as in every sibling cell). klt's cross-check `comparison.state` is
`not_comparable` (upstream 2AMLogic/klayout-tools#5720); the census is read
off the two per-engine reports by rule, not from klt's comparison block.
The `--deck-var decks=all,-mslot` var is the standard one (the metal-slotting
deck aborts on this 3LM variant regardless of content, upstream
2AMLogic/klayout-tools#5091); no rule was turned off, nothing waived, no
shape hand-edited.

## run3_top/ -- the Run 3 chip assembly (issue #211, part of #203)

`layout/run3_top/` holds the chip-level artifacts: the #275 reference netlist
and pad table (`run3_top.spice`, `pad_table.json`, `generate_run3_top.py` --
see that directory's README for their provenance), and, since #211, the
**assembled chip**: `assemble_run3_top.py` builds `run3_top.gds` (quarter-slot
outline, 48-slot pad ring + the template's 8 power pads, the 31 placed cell
instances, HV plate routes and the shared/tie routing) plus
`lvs_reference_drawn.spice`, deterministically, with `--check` byte-compare.
Its README records the physical pad mapping, the template-page provenance
(read 2026-11-18; page stamped "Generated: 24 Oct 2026 01:02 UTC"), the
routing planes, and the evidence table: `compose_report.json` (every routing
leg routed and landed), `lvs_request.json`/`lvs_report.json` (inline
extraction, flattened compare against the derived 31-instance reference:
**`match`**), `drc_report.json` (curated deck: 80 findings, all
`comp.enclosing.contact.1` inside the unmodified `nfet_10v0_asym` PCell
instances -- the geometry class `spec/pdk-pcell-drc-exception-decision.md`
scopes), the three stage reports at the precheck's own binding
configuration `gf180mcuD` (#404: `drc_stage_report.json` — nothing drawn by
this assembly, PCell findings, five `MDN.10c` findings, and `DBU`;
`drc_antenna_report.json` — 29 shared-WL findings, with zero private-plate findings after the signed capacitor routing fix;
`drc_density_report.json` + `drc_density_stage.log` — every density rule
above its floor after the fill, `DRC RESULT: SUCCESS`; the variant-A
`drc_native_report.json` per #287 is withdrawn — its `MT30.*`/`CUP.2` rows
are answered at the binding configuration),
`supplies.json`/`erc_report.json` (chip ERC extending the `layout/erc/`
convention: `erc_status: clean`), and `economy_report.json` (density).
The five instances of `cell_candidate2_Amin_G2x` are excluded from the
retained assembly and from the LVS reference, named in the reference header.
The C2-Amin-G2x master is now drawn
([`cell_candidate2_Amin_G2x/`](cell_candidate2_Amin_G2x/), landed with the
352-cell [Region II](array_region_ii/README.md) macro in #551 on 2026-11-26),
but the assembly is still the signed 31-instance GDS of 2026-11-25
(`70dbef5f`): its `match` applies to that assembly and its 31-instance
reference, while the design reference `run3_top.spice` holds 36. Placing and
routing the five instances at their reserved private-plate pads L22–L26 and
verifying the resulting direct-pad assembly are pending, so no 36-instance
match has been reported. Before 2026-11-26 the cell had no drawn master and
the five instances were excluded for that reason.
