# Addressed 32 × 32 antifuse array

The 2,769.16 × 1,852.99 µm macro implements the 75-pin analog array in
`design/netlists/array_32x32.spice`. Its three routed regions contain 352
C1, 352 C2 and 320 C3 cells. Each of the 32 column paths and 96 band-specific
row paths has a physical level shifter and pass gate. The generator follows
the original terminal order, including the complementary Region III word
lines and the drain/source orientation of the asymmetric devices.

The four addressing masters use native asymmetric PCells and KLT GF180
conventional MOS devices. Metal1 reaches the contacted terminals, Metal2
escapes the devices, and Metal3 carries separate local nets. The complete
macro breaks long gate-connected Metal4 runs near their source with a short
Metal5 jumper. Row- and column-select, word-line and internal gate channels
run on Metal3. Public selects retain a separate Metal5 landing. Bit-line,
program and supply channels stay on Metal5. Each region's original
masks are compared on import. For all 704 NMOS capacitors, the assembly
adds LVPWELL (204/0) matching the capacitor active island. This follows the
outside-DNWELL `cap_nmos` PCell in the pinned GF180 PDK
(`draw_cap_mos.py:cap_mos_inst`). Without that layer, the native LVS deck
recognizes only the 320 PMOS capacitors.

## Verification

| Check | Result |
| --- | --- |
| Native GF180D LVS, 5LM, flat, combined fingers | All 2,944 devices, 1,611 nets and 75 same-named external pins match the as-drawn reference. The full cross-reference is in `native.lvsdb.gz`. |
| KLayout physical probe | All 459 interface nets reach their intended endpoints across 256 control macros, three regions and 75 public pins. Instance masks are XOR-compared to their source masters. |
| Duplicate physical placements | Two separate GDS controls use a two-copy array reference for column pass gate XPC_11 or memory region Xregion_III. The probe rejects each extra placement under its original instance ID. |
| Transformed physical placements | A half-scale row shifter and a non-orthogonal Region III are independently written and reread. Each is rejected before the terminal probe. Unit-scale orthogonal transforms retain their physical pin positions. |
| Row-select short | A Metal5 bridge physically shorts RSEL_0/RSEL_1. Both the probe and native deck reject it. |
| Column-select open | A Metal4 cut disconnects the CSEL_7 pin. The probe finds the open. The native circuit summary still says Match because the isolated pin is purged. The native cross-reference pairs reference CSEL_7 with no layout pin. The same-name check rejects it. A separate physical control cuts the near-source Metal5 jumper on CSEL_7. The conductor probe detects the open. |
| One missing NMOS capacitor well | Removing one LVPWELL shape loses one native capacitor. The deck rejects the comparison after matching the other 2,943 devices. |
| 10 V shifter body | In native LVS both LDPMOS bodies and sources reach VDDH. Removing the 52 CONTACTs from one inner N+ ring leaves just its body anonymous. The outer guard and original labels remain. Native LVS rejects it. |
| 10 V shifter size | The official LDPMOS PCell draws two 4 µm fingers at minimum. Native LVS matches 8 µm total and rejects the original 5 µm source width. |
| KLT 0.9.2 LVS | The released deck finds 3,511 devices on each side with fingers separate. It leaves 86 additional body nets on the 43 asymmetric shifters. Its LVS remains mismatched. |
| Curated DRC | 16,849 markers. The report assigns every marker to an asymmetric device or cell master. |
| Native GF180D DRC | All 771 expected categories were checked. The parent reports 948 antenna markers. The regenerated macro reports zero in two runs. There are 263–266 other markers on both layouts; three MDP.4b markers in the imported ls_hv10 master vary between repeats. The archived report contains 266. No waiver is applied. |

The native comparison uses the twelve as-drawn bitcell geometries. Twenty-four
drawn-versus-simulated bitcell dimensions still differ. The shifter's 5/8 µm
pull-up discrepancy is an additional periphery design decision. The standalone
addressed macro has no pad frame, SPI decoder, sense amplifier or programming
source integrated. The representative Run 3 die and the signoff manifest
continue to describe their existing inputs.
[Bitcell geometry record](../../design/geometry-basis.json)

## Level-shifter measurements

At 27 °C, typical process, 3.3/5.5 V supplies and 100 fF on each output, the
original 5 µm schematic has 2.074 ns rising and 1.259 ns falling delay.
Changing only the schematic pull-up to 8 µm gives 1.899/1.329 ns. The native
extracted 8 µm shifter gives 1.907/1.339 ns. Each variant switched both
outputs at all 90 combinations of five process corners, three temperatures,
three supply multipliers and two loads. Worst-case native rise/fall were
5.549/2.512 ns. The bench uses lumped 100/500 fF test loads and native
device diffusion geometry. Full array interconnect parasitics, read/program
margin, and oxide-antifuse behavior require separate measurements.
[Corner measurements](../array_addressing/shifter_corners.csv)

## Reproduction

Set `PDK_ROOT` to open_pdks revision
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. The native runs used KLayout
CLI 0.30.14 and the comparison database was read with Python KLayout 0.30.13.
The native deck uses Linux `pmap` for its memory-usage log. This macOS run
supplied process RSS from `ps` for that log field.
The shifter bench used the repository's ngspice 47p1 build.

```sh
uv run --no-project --script layout/array_addressing/generate.py --check
uv run --no-project --script layout/array_32x32/generate.py --check
uv run --no-project --script layout/array_32x32/check.py
uv run --no-project --script layout/array_32x32/native_lvs.py --output /tmp/array-native
python3 layout/array_addressing/check_shifter.py \
  --native-cir /tmp/array-native/shifter/ls_hv10.cir --output /tmp/shifter.csv
cd layout/array_32x32
uvx --from klayout-tools==0.9.2 klt lvs lvs_request.json --format json
uvx --from klayout-tools==0.9.2 klt drc array_32x32.gds --deck gf180mcu --top array_32x32 --format json
uvx --from klayout-tools==0.9.2 klt drc array_32x32.gds --engine klayout --pdk gf180mcuD --top array_32x32 \
  --deck-var variant=D --deck-var decks=all --deck-var threads=1 \
  --expect-rule-categories-file native_drc_categories.txt --format json
```

`native_results.json` records strict pin matching and the native verdict
separately for each control. The native inventory contains the 763 base categories and eight data-dependent
density categories observed on both versions of this macro. Both DRC reports retain their complete marker
coordinates in gzip-compressed JSON.
