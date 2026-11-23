# cell_candidate2 -- klt pex extraction (issue #447 probe)

T1 item-7-style probe extraction of the drawn Region II bitcell (the
`nfet_10v0_asym` LDMOS cell). Ungraded supporting evidence only -- nothing
here cites `7.analog` (see `signoff/README.md`).

## Command, release, inputs

```sh
uvx --from "klayout-tools==0.9.2" klt pex cell_candidate2.gds \
  --deck gf180mcu --pdk gf180mcuD --extract-only \
  --reference-netlist lvs_reference.spice \
  -o pex/extracted.spice --outdir pex/.klt --format json > pex/pex_report.json
```

- klayout-tools `0.9.2` (released), KLayout `0.30.13` (report `provenance`)
- PDK: `gf180mcuD`, open_pdks `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (the
  repo pin); extraction deck `gf180mcu`
- GDS `cell_candidate2.gds`
  sha256 `5cb4a64fa103f2b698aeaffedddfc28405931e6afbfec8f21cf8b90678462e7a`
  (equals the report's `provenance.input.content_hash`)
- Reference (schematic leg) `lvs_reference.spice`, sha256 `0e67f23274f1298bb48e0a8bb65e589fdaacb1c116b5aba9a847215091f87812`
  (report `reference_netlist_sha256`)
- Extracted netlist `extracted.spice`, sha256 `8ba7938916fe741eb25cffb1de38fd19ffa6e808e16ff8afcf1533666697fe7c`
  (equals the report's `extraction.netlist_sha256`)
- `measurement.mode: "extract-only"`, `status: "not_checked"` (exit 4) -- this
  step measures no electrical delta; the paired bench runs live under
  `sim/cell-device-characterization/klt/post-layout/`.

## body_bias (quoted verbatim from `pex_report.json`)

```json
{
  "status": "biased",
  "unbiased_device_count": 0,
  "unbiased_nets": [],
  "unbiased_pmos_body_nets": []
}
```

`biased`: no unbiased body. The LDMOS body is the `DNWELL` island; both
per-finger cards' fourth terminal is a `VB` net (`VB__t0`/`VB__t1`, joined
through `RVB_t0`/`RVB_t1`, 4.67 ohm each, to the `VB` pin).

## Extracted device inventory vs the LVS reference

| | LVS reference (`lvs_reference.spice`) | extracted (`extracted.spice`) |
|---|---|---|
| access | `XM1 BL WL CN VB nfet_10v0_asym L=0.60u W=8u nf=2 m=1` (single 2-finger call) | `X$2 BL__t0 WL__t0 $3__t1 VB__t0 nfet_10v0_asym L=0.6U W=4U AS=1.76P AD=1.6P ...` and `X$3 BL__t1 WL__t1 $3__t2 VB__t1 nfet_10v0_asym L=0.6U W=4U AS=1.76P AD=1.6P ...` |
| capacitor | `XC1 CN PL cap_nmos_06v0 c_width=1.0u c_length=0.70u m=1` | `C$1 PL__t0 $3__t0 1.61e-15` (linear, deck area law 2.3 fF/um^2) |

- **Both 4 um fingers represent the asymmetric 10 V device with the correct
  drain orientation**: each per-finger `X` card names `nfet_10v0_asym` with
  `L=0.6U W=4U` (total 8.0 um over two fingers, the drawn geometry), and in
  both cards the drain (first terminal) is a `BL` net while the source is a
  `$3` (storage-node) net -- the `MVSD` drain marker fixes the drain side,
  matching the reference `XM1 BL WL CN VB ...` (drain on BL). The two
  per-finger devices share the drain net exactly as the deck's LDMOS
  documentation describes; `klt lvs` reconciled them into the reference's
  single `W=8u nf=2` call with `options.combine_devices` (see
  `lvs_request.json`).
- Parasitics present: 17 `R`/`C` parasitic cards besides the devices,
  including two vertical-overlap coupling capacitors (`Ccc__3_BL` 0.011 fF,
  `Ccc__3_VB` 0.012 fF); `extraction.parasitic_integrity`: 5 nets checked,
  0 findings.
- `.SUBCKT cell_candidate2 BL PL VB WL` -- pins promoted alphabetically, NOT
  the reference's `BL WL PL VB`. The bench pin map is recorded in
  `sim/cell-device-characterization/klt/post-layout/requests/c2/provenance.json`.

## model_mismatch (the finding)

`kind: "model_set"`, `reference_only: ["cap_nmos_06v0"]`,
`extracted_only: []`; counts `reference {cap_nmos_06v0: 1, nfet_10v0_asym: 1}`,
`extracted {nfet_10v0_asym: 2}`. Two separate divergences, both disclosed:

1. The MOS capacitor extracts as a linear `C` card, not the PDK's nonlinear
   `cap_nmos_06v0` subcircuit (same class as the other two cells; tracked
   upstream: 2AMLogic/klayout-tools#7004).
2. The `nfet_10v0_asym` instance count differs (1 reference call vs 2
   extracted per-finger devices). This is the documented LDMOS finger
   decomposition the LVS run already reconciled with `combine_devices`; the
   per-finger `count_only` case is neutral per `klt pex`'s own model_mismatch
   documentation, and the representation difference (per-finger AS/AD/PS/PD
   measured, reference call at subcircuit defaults) is folded into the paired
   bench result rather than hidden.
