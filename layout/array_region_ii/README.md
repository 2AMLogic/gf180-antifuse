# Region II asymmetric-access matrix

Region II implements 352 cells in rows 0–31 and columns 11–21 of the 32 × 32
array. Each of the four splits occurs 88 times. The 6 V NMOS capacitor is
1.0 or 2.0 µm wide at 0.70 µm length. The 10 V LDNMOS access PCell draws
two 4.0 or two 8.0 µm fingers at 0.60 µm channel length. Both outer sources
reach the capacitor gate. The central drift-extended drain reaches BL. The
cap diffusion stripes reach the shared plate. The original schematic uses
25/50 µm total access width and a 1.0 µm capacitor length.
[Geometry basis](../../design/geometry-basis.json)

The 292.68 × 1,006.11 µm macro uses a 28 × 32 µm pitch. All 76 public terminals and each of the
1,408 cell terminals are probed from physical metal, vias and CONTACT.
The probe verifies the two physical LDNMOS fingers using active, poly and
the MVSD drain-extension marker. A second independent comparison of every
mask in the four original access subcells against a fresh
`gf180mcu_klayoutapi/nfet_10v0_asym` PCell generation has zero XOR.

| Verification | Result |
| --- | --- |
| KLT 0.9.2 LVS | 428/428 nets, 1,056/1,056 devices and 76/76 same-named pins. Both LDNMOS fingers are compared separately. |
| Shared plate cut | Cutting Metal5 on row 7 between columns 15 and 16 isolates six rightmost cells. LVS rejects 429 physical nets against 428. |
| Crossed word lines | The Metal3 bridge joins exactly WL_7_II and WL_8_II. LVS rejects 427 nets against 428. |
| P-substrate contacts | All 704 explicit access/capacitor tap windows pass, with one connected VSS island. Opening 50 contact cuts in a single access ring produces precisely one missing tie. |
| Curated DRC | 8,800 COMP/contact-enclosure findings and 352 minimum-width findings on the narrow central active stripes. The same two rules fire on the individual PCells. |
| Native GF180D DRC | 100 CO.4, 8 DF.6_MV, 8 PL.4_MV, 4 MDN.10c and 1 MDN.5c, plus eight standalone density findings. All non-density markers also appear in the individual unmodified PCell streams. Counts in the hierarchical native report can cover one master used by many instances. |

The native MDN.5c finding is on the outer active edge of the 8 µm-finger
access in the minimum-capacitor split. The standalone PDK report places it
in `nfet_10v0_asym`. Its numeric marker and the four MDN.10c markers remain
open. The operator's earlier exception covers named PCell rules only.
[Exception scope](../../spec/pdk-pcell-drc-exception-decision.md)

Each new master's signed PEX connects both sources to the capacitor gate,
the drain to BL and both transistor gates to WL. KLT PEX uses revision
`9d2780c5e1c842777519330943a5435b118c4437`. The released LVS uses a
placeholder capacitor value. The cell populations do not establish read,
program or address-control performance.

The three regional macros now contain 1,024 physical cells. Integration of
the row and column level shifters, pass gates and common addressing remains
separate. The representative direct-pad assembly retains its measured
31-instance stream. The new C2-Amin-G2x master is available for its five
unpopulated sites.

## Reproduction

Set PDK_ROOT to the installed GF180MCU open_pdks tree at
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. Cell generators use KLT
0.9.2 and Python KLayout 0.30.13. The native deck uses KLayout CLI 0.30.12.

```sh
for cell in cell_candidate2 cell_candidate2_Amin_G2x cell_candidate2_A2x_Gmin cell_candidate2_A2x_G2x; do
  uv run --no-project --isolated --with klayout-tools==0.9.2 --with klayout==0.30.13 python "layout/$cell/generate.py" --check
done
uv run --no-project --script layout/array_region_ii/generate.py --check
uv run --no-project --script layout/array_region_ii/check.py
uv run --no-project --script scripts/check_analog_tap_contacts.py
```

From this directory, run the following commands with KLT 0.9.2. The full
curated DRC and structural ERC outputs are stored as gzip-compressed JSON.

```sh
klt lvs lvs_request.json --format json
klt drc array_region_ii.gds --top array_region_ii --deck gf180mcu --format json
klt drc array_region_ii.gds --top array_region_ii --engine klayout --pdk gf180mcuD --deck-var decks=all,-mslot --format json
klt erc array_region_ii.gds supplies.json --top array_region_ii --format json
```
