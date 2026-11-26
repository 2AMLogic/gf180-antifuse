# Addressed-array density fill

This filled GDS removes the eight chip-area density findings from the 32 × 32 addressed macro. The fill occupies the existing 5.1312 mm² outline. The filled view and the parent layout have identical device masks, conductors, labels and instance properties. The generator checks this by removing the dedicated dummy-fill cell and comparing the complete hierarchy at zero database-unit tolerance before flattening those masks into the top. [Filled stream](array_32x32.gds.gz) · [Verification results](evidence.json)

| Mask | Drawn and dummy coverage |
|---|---:|
| COMP | 51.61% |
| Poly2 | 61.07% |
| Metal1 | 69.35% |
| Metal2 | 69.01% |
| Metal3 | 59.82% |
| Metal4 | 55.97% |
| Metal5 | 66.63% |

The previous native GF180D report listed 266 markers, including one each for DCF.1b, PL.8, M1.4, M2.4, M3.4, M4.4, M5.4 and MT.3. None of these eight remains on the filled stream. The native run with an explicit category inventory reports 258 markers on device or cell masters and no antenna marker. GF180D declares eight density output categories conditionally on detecting those failures. The filled run covers all 763 categories from the deck enumeration; the unfilled run covers those categories plus eight. The curated deck still reports 16,849 markers. Both marker reports include coordinates. [Native DRC](native-drc.json.gz) · [Curated DRC](curated-drc.json.gz)

Native LVS matches all 2,944 devices, 1,611 nets and 75 same-named pins. A select open changes a pin name, a row short mismatches four nets and a missing p-well mismatches one device and two nets. [Native LVS cross-reference](native.lvsdb.gz) The physical connectivity probe reaches the expected 459 named nets and rejects its seven open, short, duplicate placement and transform controls. The curated LVS run finds 3,511 devices per side and 86 additional extracted body nets on the asymmetric shifters. [Curated comparison](curated-lvs.json.gz) Programming behavior, coupling to the added dummy masks and any full-die density result require integration and extraction. The pinned project signoff continues to identify its original array input. [Unfilled array and comparison records](../README.md)

## Replay

Use the parent array's GF180D open_pdks revision, native KLayout executable and Python tools. The generator fetches one SHA-256-pinned fill implementation and also accepts an offline copy via `--fill-script`. Run from the repository root.

```bash
work=$(mktemp -d)
gzip -dc layout/array_32x32/density/array_32x32.gds.gz > "$work/delivered.gds"
uv run --script layout/array_32x32/density/build.py --output "$work/rebuilt.gds"
cmp "$work/rebuilt.gds" "$work/delivered.gds" || exit 1
uv run --script layout/array_32x32/check.py --array-layout "$work/delivered.gds"
uv run --script layout/array_32x32/native_lvs.py --array-layout "$work/delivered.gds" --output "$work/native" --case array --case select_open --case row_short --case missing_pwell

klt=(uvx --from klayout-tools==0.9.2 klt)
native=(--engine klayout --pdk gf180mcuD --pdk-root "$PDK_ROOT" --deck-var variant=D --deck-var decks=all --deck-var threads=1)
"${klt[@]}" drc "${native[@]}" --list-rule-categories > "$work/categories.txt" || exit 1
"${klt[@]}" drc "$work/delivered.gds" --top array_32x32 "${native[@]}" --expect-rule-categories-file "$work/categories.txt" --format json > "$work/native-drc.json"
"${klt[@]}" drc "$work/delivered.gds" --top array_32x32 --deck gf180mcu --format json > "$work/curated-drc.json"
jq --arg gds "$work/delivered.gds" --arg cdl "$PWD/layout/array_32x32/reference.spice" ' .layout.file = $gds | .reference.netlist = $cdl ' layout/array_32x32/lvs_request.json | "${klt[@]}" lvs - --format json > "$work/curated-lvs.json"
```

Both DRC commands currently return findings. Compare their counts and rule names with the recorded results. The curated LVS run also returns a mismatch. The native DRC archive uses a PDK-relative deck filename.
