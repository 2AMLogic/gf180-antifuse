# cell_candidate1 signed post-layout extraction

The NMOS capacitor has CN on its gate and PL on diffusion. The access source reaches CN. The PEX report records a biased body and no floating devices. The GDS SHA-256 is `fa008179952e206211354a27a73dde172686dda6dba7c055cbefc1b82ec16de4`. The extracted SPICE SHA-256 is `7bb3d589554f9c64147b5a12e3444ead4312b76ebc685b76fb784f26121a796e`.

The signed regression, extractor revision, reproduction instructions and three-cell ±1 V controls are in [the layout verification record](../../README.md#signed-mos-capacitors-in-the-drawn-cells).

## Historical linear-capacitor extraction from issue #447

The following record describes the earlier GDS and extractor. The current netlist and report above supersede its input and output hashes.

T1 item-7-style probe extraction of the drawn Region I bitcell. Ungraded
supporting evidence only -- nothing here cites `7.analog` (see
`signoff/README.md`).

## Command, release, inputs

```sh
uvx --from "klayout-tools==0.9.2" klt pex cell_candidate1.gds \
  --deck gf180mcu --pdk gf180mcuD --extract-only \
  --reference-netlist lvs_reference.spice \
  -o pex/extracted.spice --outdir pex/.klt --format json > pex/pex_report.json
```

- klayout-tools `0.9.2` (released), KLayout `0.30.13` (report `provenance`)
- PDK: `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the
  repo pin); extraction deck `gf180mcu`
- GDS `cell_candidate1.gds`
  sha256 `d31a786ed748a9e3bf6e46dcec4d59ccdd3cd095ddace86714574e624d3305cd`
  (equals the report's `provenance.input.content_hash`)
- Reference (schematic leg) `lvs_reference.spice`, sha256 `5d91d01e20b0e42ec61d8f85644c5e60d82cf4a50345902eff568bba3aa96831`
  (report `reference_netlist_sha256`)
- Extracted netlist `extracted.spice`, sha256 `34ad48ab64c2bb1486ccb545d3f425b1961dee5c46b91d63dd6f0eaf8c6810aa`
  (equals the report's `extraction.netlist_sha256`)
- `measurement.mode: "extract-only"`, `status: "not_checked"` (exit 4) -- this
  step measures no electrical delta; the paired bench runs live under
  `sim/cell-device-characterization/klt/post-layout/`.

`--pdk gf180mcuD` is required for a simulable netlist: omitted, the same
extraction writes a bare `M` card with model `nfet`, which no section of the
PDK's `sm141064.ngspice` defines (measured; ngspice would reject it). With
`--pdk`, the device binds `nfet_06v0` as an `X` call.

## body_bias (quoted verbatim from `pex_report.json`)

```json
{
  "status": "biased",
  "unbiased_device_count": 0,
  "unbiased_nets": [],
  "unbiased_pmos_body_nets": []
}
```

`biased`: the extractor detected no unbiased body. The NMOS body terminal
resolves to the named `VB` net (drawn substrate tie), confirmed below by the
device card's fourth terminal.

## Extracted device inventory vs the LVS reference

| | LVS reference (`lvs_reference.spice`) | extracted (`extracted.spice`) |
|---|---|---|
| access | `XM1 BL WL CN VB nfet_06v0 L=0.70u W=0.42u nf=1 m=1` | `X$2 BL__t0 WL__t0 $3__t1 VB__t0 nfet_06v0 L=0.7U W=0.42U AS=0.21P AD=0.21P PS=1.84U PD=1.84U` |
| capacitor | `XC1 CN PL cap_nmos_03v3 c_width=1.0u c_length=0.28u m=1` | `C$1 PL__t0 $3__t0 1.232e-15` (linear, deck area law 4.4 fF/um^2) |

- Same device model, same drawn geometry (0.42 um x 0.70 um), same
  orientation: X$2 pin order (D G S B) = BL WL CN VB, identical to `XM1`; the
  storage node `$3` is the reference's `CN`. A previous LVS match does not
  establish this -- it is re-verified here from the card itself.
- Parasitics present: 12 `R`/`C` parasitic cards besides the devices (per-net
  lumped series R + substrate C, e.g. `RWL_t0` 47.25 ohm, `C_3` 0.578 fF) plus
  the `vsubs` DC tie; `extraction.parasitic_integrity`: 5 nets checked,
  0 findings.
- `.SUBCKT cell_candidate1 BL PL VB WL` -- pins promoted alphabetically, NOT
  the reference's `BL WL PL VB`. The bench pin map is recorded in
  `sim/cell-device-characterization/klt/post-layout/requests/c1/provenance.json`.

## model_mismatch (the finding)

`kind: "model_set"`, `reference_only: ["cap_nmos_03v3"]`,
`extracted_only: []`; counts `reference {cap_nmos_03v3: 1, nfet_06v0: 1}`,
`extracted {nfet_06v0: 1}`. The access device binds correctly; the drawn MOS
capacitor extracts as a linear `C` card (the deck's `moscap_extraction.lvs`
area law), not the PDK's nonlinear `cap_nmos_03v3` tanh C(V) subcircuit --
the access-device card is NOT affected. Tracked upstream:
2AMLogic/klayout-tools#7004. Consequence for the paired bench is recorded
per metric in `sim/cell-device-characterization/klt/post-layout/README.md`
(I_off is DC and unaffected; R_on at 10 MHz sees the linearised cap).
