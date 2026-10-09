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
| `generate.py` | Deterministic generator (`klt gen mos_array` x2, `klt draw` for two Metal1 straps, `klt gen-compose` explicit placement). `--check` regenerates and compares the committed GDS byte-for-byte. |
| `cell_candidate1.gds` | Generated layout, top cell `cell_candidate1`, pins/labels `BL`, `WL`, `PL`, `VB`. |
| `drc_report.json` | `klt drc --deck gf180mcu --top cell_candidate1` report (status `clean`, 0 violations). |
| `lvs_request.json`, `lvs_reference.spice` | The LVS request and its reference netlist. **No `lvs_report.json` exists**: see "LVS: stopped at a tool gap". |

Toolchain: every artifact here was produced by `klt 0.7.0+g4cbdfa769875`
(klayout 0.30.12, PDK `gf180mcuA`, open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`),
the host-installed build; no tool was installed or changed. Regenerate with
`python3 layout/cell_candidate1/generate.py` and verify with `--check`.

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
  transistor from `mos_array`: **it carries no PDK MOS-capacitor marker
  layer**, because `klt gen` has no MOS-capacitor primitive (upstream
  2AMLogic/klayout-tools#2953).
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
input GDS `sha256:796faa12f1c28f5c3ce7aebbee173bb9052abc2e0f31333c28dedbf142a1c6c6`
(the report's `provenance.input.content_hash`). A first placement at 3.9 um
pitch drew a Pplus spacing violation between the two tap rings; the committed
cell uses a 4.2 um pitch. The rule was not waived.

Coverage block quoted from `drc_report.json` (`coverage.deck_scope`,
`coverage.layers_in_stream_without_rules`, `coverage.rules_skipped`). The 34
skipped rules are all reported as `no_applicable_geometry` in
`coverage.inapplicable` (no such layers are drawn), which includes
`pplus.enclosing.comp.1`; layer 34/10 is the Metal1 label purpose.

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
    "34/10"
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

### LVS: stopped at a tool gap

`lvs_request.json` runs `klt lvs` with the gf180mcu extraction deck against
`lvs_reference.spice`, which is the schematic's netlist
(`design/netlists/cell_candidate1.spice`, unchanged) with its subcircuit
parameters resolved to the drawn literals. `klt lvs` exits 1 and writes no
report:

    subcircuit 'cap_nmos_03v3' is not a known device for the requested deck
    (known: cap_mim_2f0_m4m5_noshield, nfet_03v3, nfet_06v0, pfet_03v3, pfet_06v0, ppolyf_u, ...)

Two upstream gaps stop it. The gf180mcu extraction deck has no MOS-capacitor
device class (already filed: 2AMLogic/klayout-tools#2919). Running the
original netlist directly fails earlier, because the `subckt-call` reference
form rejects parametrised values (`parameter 'L' value 'lacc' is not a plain
numeric literal`); that and the missing generator primitive are in
2AMLogic/klayout-tools#2953. Per the issue's stop-and-file path, no waiver or
`device_map` workaround was applied: mapping the capacitor onto a MOSFET with
tied source and drain would make the compare pass by substituting the device
under test.

For information only (this is not LVS evidence): `klt extract` reads the
drawn cell as two NMOS devices, `nfet_03v3` (L=0.28 W=0.42, gate `PL`, S and D
both on one net, body `VB`) and `nfet_06v0` (L=0.7 W=0.42, gate `WL`, drain
`BL`, source on that same net, body `VB`), which is the intended topology.
