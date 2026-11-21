# cell_candidate3 -- klt pex extraction (issue #447 probe)

T1 item-7-style probe extraction of the drawn Region III bitcell. Ungraded
supporting evidence only -- nothing here cites `7.analog` (see
`signoff/README.md`).

## Command, release, inputs

```sh
uvx --from "klayout-tools==0.9.2" klt pex cell_candidate3.gds \
  --deck gf180mcu --pdk gf180mcuD --extract-only \
  --reference-netlist lvs_reference.spice \
  -o pex/extracted.spice --outdir pex/.klt --format json > pex/pex_report.json
```

- klayout-tools `0.9.2` (released), KLayout `0.30.13` (report `provenance`)
- PDK: `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the
  repo pin); extraction deck `gf180mcu`
- GDS `cell_candidate3.gds`
  sha256 `4ee36d7b8e0227a2e73535cbe8a2e232238105de057673eaeb770b1970092d9d`
  (equals the report's `provenance.input.content_hash`)
- Reference (schematic leg) `lvs_reference.spice`, sha256 `c385fa9855ce420855f8f5c8f2bfb0bffb4110ada7f6d54b500ec24fb29e9566`
  (report `reference_netlist_sha256`)
- Extracted netlist `extracted.spice`, sha256 `8304ab363c4b265bcacaa4309db99d0f2b1210276384a59e38a01d3d3adc2112`
  (equals the report's `extraction.netlist_sha256`)
- `measurement.mode: "extract-only"`, `status: "not_checked"` (exit 4) -- this
  step measures no electrical delta; the paired bench runs live under
  `sim/cell-device-characterization/klt/post-layout/`.

`--pdk gf180mcuD` is required for a simulable netlist (without it the MOS
card names the undefined default model; see cell_candidate1's README).

## body_bias (quoted verbatim from `pex_report.json`)

```json
{
  "status": "biased",
  "unbiased_device_count": 0,
  "unbiased_nets": [],
  "unbiased_pmos_body_nets": []
}
```

`biased`: no unbiased body. This is the cell where it could have failed -- the
PMOS body is the drawn `Nwell` island. The deck's derived well tie
(`Nplus`-covered `Comp` inside the `Nwell`, issue #1084 upstream) resolves the
body to the named `VB` net: `unbiased_pmos_body_nets` is empty and the device
card's fourth terminal is `VB__t0`, wired through `RVB_t0` (7.34 ohm) to the
`VB` pin.

## Extracted device inventory vs the LVS reference

| | LVS reference (`lvs_reference.spice`) | extracted (`extracted.spice`) |
|---|---|---|
| access | `XM1 CN WL BL VB pfet_06v0 L=0.55u W=0.42u nf=1 m=1` | `X$2 $3__t1 WL__t0 BL__t0 VB__t0 pfet_06v0 L=0.55U W=0.42U AS=0.21P AD=0.21P PS=1.84U PD=1.84U` |
| capacitor | `XC1 CN PL cap_pmos_03v3 c_width=1.0u c_length=0.28u m=1` | `C$1 PL__t0 $3__t0 1.232e-15` (linear, deck area law 4.4 fF/um^2) |

- Same device model, same drawn geometry (0.42 um x 0.55 um), same
  orientation: X$2 pin order (D G S B) = CN WL BL VB -- the PMOS source is
  `BL`, matching the reference `XM1 CN WL BL VB` (and `design/README.md`'s
  source/drain assignment note); storage node `$3` is the reference's `CN`.
  Re-verified from the card, not from the prior LVS match.
- Parasitics present: 12 `R`/`C` parasitic cards besides the device (e.g.
  `RWL_t0` 39.49 ohm, `CVB` 3.097 fF) plus the `vsubs` DC tie;
  `extraction.parasitic_integrity`: 5 nets checked, 0 findings.
- `.SUBCKT cell_candidate3 BL PL VB WL` -- pins promoted alphabetically, NOT
  the reference's `BL WL PL VB`. The bench pin map is recorded in
  `sim/cell-device-characterization/klt/post-layout/requests/c3/provenance.json`.

## model_mismatch (the finding)

`kind: "model_set"`, `reference_only: ["cap_pmos_03v3"]`,
`extracted_only: []`; counts `reference {cap_pmos_03v3: 1, pfet_06v0: 1}`,
`extracted {pfet_06v0: 1}`. The access device binds correctly; the drawn MOS
capacitor extracts as a linear `C` card, not the PDK's nonlinear
`cap_pmos_03v3` tanh C(V) subcircuit. Tracked upstream:
2AMLogic/klayout-tools#7004. **This is the cell where that divergence bites
the bench**: at the R_on bias the drawn pmos capacitor sits in deep depletion
(effective ~0.1 fF from the tanh law) while the extracted linear card is
1.232 fF, so the paired R_on comparison is withheld as
representation-dominated -- see
`sim/cell-device-characterization/klt/post-layout/README.md`.
