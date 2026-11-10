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
- **LVS.** `status: match`, 0 errors (`klt lvs --check lvs_report.json` run
  from the cell directory exits 0). Same bounds as candidate 1: the capacitor's
  geometry and capacitance are not compared.
- **ERC.** `klt erc ... layout/erc/supplies_region_iii.json` (the existing
  n-well tie spec): `erc_status: clean`, 0 findings, `erc.missing_tie` for the
  n-well tie checked. Antenna checks were skipped (no antenna PDK data).

## cell_candidate2/ -- drawn, DRC and LVS NOT clean (klt 0.9.1 gaps)

`layout/cell_candidate2/` holds one bitcell of candidate 2 (`spec/cell-candidates.md`):
a 6.0 V thick-oxide NMOS capacitor (`cap_nmos_06v0`) in series with the 10 V
drain-extended `nfet_10v0_asym`, per `design/cells/cell_candidate2.sch`. One
cell, not the array; no breakdown claim. Files: `generate.py` (with `--check`),
`cell_candidate2.gds`, `drc_report.json`, `erc_report.json`, `lvs_request.json`,
`lvs_reference.spice`, `lvs_report.json`.

**Result: the criteria "DRC clean" and "LVS match" are NOT met.** Recorded as
measured, with no waiver, no hand-edited PCell geometry and no substituted
device. Toolchain: released `klt 0.9.1` (`uvx --from klayout-tools==0.9.1`,
klayout 0.30.13 resolved at run time, PDK `gf180mcuA`); regenerate/verify with
`uvx --from klayout-tools==0.9.1 python3 layout/cell_candidate2/generate.py --check`
(the generator calls `klt` on PATH, so put a `klt` wrapper for the pinned
version on PATH).

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
| Access (`nfet_10v0_asym` PDK PCell) | W = 4 um, L = 0.6 um | The PCell clamps any `w` below 4 um to 4 um (a request for 0.42 um draws the identical cell). The schematic default `wacc` is not reachable. |
| Capacitor (`mos_array`, Dualgate marker, S and D strapped on CN) | W = 0.42 um, L = 0.56 um | 6 V minimum L; MOS-capacitor marker (166/5) added by hand as in candidate 1. |

### DRC

`klt drc --deck gf180mcu --top cell_candidate2`: `status: violations`, 17.
**All 17 have `source_cell` `nfet_10v0_asym`, i.e. lie inside the PDK PCell**:
16 x `comp.enclosing.contact.1` and 1 x `comp.width.mv.1` (the 0.22 um drain
stripe). Nothing is reported in the capacitor, the straps or the labels. The
native deck could not be cross-checked here (host KLayout is older than it
needs). These are the same 17 findings seen on 0.9.0; the 0.9.1 fix did not
remove them.

### LVS

`klt lvs`: `status: mismatch`. The layout nets are right (BL = drain, WL = both
gates, CN = sources + capacitor S/D, VB = bodies; the 0.9.0 floating-drain
defect is gone), but the access device extracts as **two parallel plain `nfet`**
devices (`klt extract` census: `nfet: 2`, `cap_nmos_06v0: 1`) because the
`gf180mcu` extraction deck declares no `nfet_10v0_asym` class, so it cannot pair
with the reference's single `nfet_10v0_asym`. The capacitor pairs
(its geometry is not compared, as for candidates 1 and 3).

### ERC

`klt erc ... layout/erc/supplies.json` (the existing p-tap spec): `erc_status:
clean`, 0 findings.

### Upstream

The gap is filed generically as 2AMLogic/klayout-tools#5277 (follow-up to the
closed #4949). Candidate 2 closes out once a klt release carries the fix: re-run
`generate.py --check`, `klt drc`, `klt extract`, `klt lvs` and replace this
section with the clean results.
