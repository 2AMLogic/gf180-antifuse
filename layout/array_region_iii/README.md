# Region III cell matrix

The macro implements all 320 PMOS-access bitcells in columns 22–31 of the
32 × 32 schematic. Each column has a bit line. Each row has an active-low
word line and a plate line shared across ten cells. The high body supply
VDDH_III connects both N-wells of every cell. Each of the four geometry
splits occurs 80 times. The two new masters pair a 0.84 µm access width with
capacitor widths of 1.0 and 2.0 µm. [Array schematic](../../design/netlists/array_32x32.spice)

The 119.35 × 287.27 µm macro uses a 12 × 9 µm pitch. Bit lines run on Metal4,
word lines on Metal3 and plate lines on Metal5. The Metal2 well buses join
a Metal4 spine. The GDS uses the native deck's 0.001 µm grid. The checker
compares each imported mask to the original 0.0005 µm leaf stream.

## Measured results

| Check | Result |
| --- | --- |
| Released KLT 0.9.2 LVS | 395/395 nets, 640/640 devices and 75/75 public terminals match by name. |
| Physical electrodes | All 1,280 labeled cell terminals reach their respective public conductors. Each capacitor gate connects to its own access drain. Both capacitor diffusions reach the same plate, the access source reaches BL, and the access gate reaches WL. All 320 storage nodes are distinct and private. |
| Common plate open | A Metal5 cut in PL_7_III between columns 26 and 27 isolates precisely five cells, columns 27–31. LVS extracts 396 nets and rejects the open. |
| Crossed word lines | A Metal3 bridge joins only WL_7_III and WL_8_III. LVS extracts 394 nets and rejects the short. |
| Contact-qualified ERC | All 640 N-wells have an N+ active contact to a single VDDH_III island. Removing just the cuts on one well produces one missing-tie finding. The new masters each produce two missing-tie findings when their 14 well contacts are removed. |
| Curated GF180 DRC | Zero findings on both new masters and on the region. |
| Native GF180D DRC | Eight standalone density findings on the region, one each for `DCF.1b`, `M1.4` through `M5.4`, `MT.3` and `PL.8`. |

The source simulation uses 1.0 µm capacitor length and 0.30/0.60 µm access
widths. The physical cells use 0.28 µm and 0.42/0.84 µm respectively. The
checker measures both channels from the intersection of active and poly at
every placement. The LVS deck supplies a placeholder capacitor value. These
results cover physical topology. Capacitance, programming behavior and timing
require electrical evidence. [Geometry basis](../../design/geometry-basis.json)

The [Region II macro](../array_region_ii/README.md) completes the physical
cell population. The control interfaces, level shifters and pass gates remain.
Full-array analog signoff remains open.

Each new master also has a signed, extracted SPICE subcircuit and a body-biased
PEX report. They use the same GF180D extraction revision as the existing PMOS
bitcells, KLT `9d2780c5e1c842777519330943a5435b118c4437`. At 10 kHz and
V(CN)−V(PL) of −1 V / +1 V, the isolated extracted PMOS capacitors measured
1.03410 / 0.01064 fF for Gmin and 2.06820 / 0.02128 fF for G2x. The drawn
schematic references agreed. Swapping the capacitor terminals exchanged the
results at the two voltages. The extractor transposes the two dimension
names in its SPICE output. The mask comparison verifies their physical
orientation, and the signed sweep checks the terminal polarity and this model's
area-dependent capacitance at the two biases.
[Cell extraction procedure](../README.md#signed-mos-capacitors-in-the-drawn-cells)

## Reproduction

From the repository root, use KLT 0.8.0 on PATH for the two leaf generators.
The matrix scripts declare their own KLayout and KLT versions.

```sh
uv run --no-project --isolated --with klayout-tools==0.8.0 --with klayout==0.30.12 python layout/cell_candidate3_A2x_Gmin/generate.py --check
uv run --no-project --isolated --with klayout-tools==0.8.0 --with klayout==0.30.12 python layout/cell_candidate3_A2x_G2x/generate.py --check
uv run --no-project --script layout/array_region_iii/generate.py --check
uv run --no-project --script layout/array_region_iii/check.py
uv run --no-project --script scripts/check_analog_tap_contacts.py
# PDK_ROOT and KLT_NGSPICE_BINARY point to the pinned PDK and patched ngspice 47.
python3 sim/cell-device-characterization/klt/post-layout/check_signed_caps.py
```

From this directory, regenerate the physical reports with KLT 0.9.2 and
Python KLayout 0.30.13. Native DRC uses KLayout CLI 0.30.12 and the pinned
GF180D open_pdks commit `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`.

```sh
klt lvs lvs_request.json --format json
klt drc array_region_iii.gds --top array_region_iii --deck gf180mcu --format json
klt erc array_region_iii.gds supplies.json --top array_region_iii --format json
klt drc array_region_iii.gds --top array_region_iii --engine klayout --pdk gf180mcuD --deck-var decks=all,-mslot --format json
```

The ERC envelope records `erc_status: clean` for connectivity and exit 4 for
unavailable antenna limits. Native DRC returns exit 3 for the density findings.
