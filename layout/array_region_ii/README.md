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
| Native GF180D DRC | The original macOS report records 100 CO.4, 8 DF.6_MV, 8 PL.4_MV, 4 MDN.10c and 1 MDN.5c, plus eight standalone density findings. All non-density markers also appear in the individual unmodified PCell streams. Counts in the hierarchical report can cover one master used by many instances. Fresh Linux and macOS replays both record 124 items, with zero in both MDN categories. [Replay evidence](#native-mdn-replay) |

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

### Native MDN replay

The input is the sole top cell `array_region_ii` in the GDS committed at
`dcf5b370` (SHA-256 `149b171ef157fb84105f5aeaad5344e620b471f215cbc9c55c1b829c8df9d466`).
KLT 0.9.2 used the KLayout **Python wheel 0.30.13** to read the layout and a
separate **native CLI 0.30.12** to run the GF180D deck.

| Macro run | Total items | MDN.10c | MDN.5c | Evidence |
| --- | ---: | ---: | ---: | --- |
| Original macOS report at `dcf5b370` | 129 | 4 | 1 | [KLT JSON](drc_native_report.json) |
| Ubuntu 24.04.5, x86-64, `klayout 0.30.12-1 amd64` | 124 | 0 | 0 | [Build and hashes](replays/linux/package.txt) · [Raw RDB](replays/linux/native.lyrdb.gz) · [Native log](replays/linux/native.log.gz) · [KLT JSON](replays/linux/klt.json.gz) |
| macOS 26.7.2, arm64, KLayout 0.30.12 Tahoe C32 Qt5/MacPorts build | 124 | 0 | 0 | [Build and hashes](replays/macos/package.txt) · [Raw RDB](replays/macos/native.lyrdb.gz) · [Native log](replays/macos/native.log.gz) · [KLT JSON](replays/macos/klt.json.gz) |

The two live runs used `variant=gf180mcuD`, `decks=all,-mslot`, deep mode,
one worker, MIM B, five metal levels and 11K top metal. Both loaded
`rule_decks/ldnmos.rb` with SHA-256 `f026a12c91807f846a0ad0da2966c2f7a4da8c1188fd58f5136aaf884ad19ca4`.
Both logs record execution of MDN.10c and MDN.5c. The two raw RDBs contain
the same 124 items by rule, cell and geometry. Each host's KLT JSON agrees
with its raw database on every rule count. Both KLT commands exited 3.
[Hosted macOS run](https://github.com/2AMLogic/gf180-antifuse/actions/runs/45864681527)

The hosted Mac used three DRC threads and Linux used 16. Switching only the
Linux thread count to one produced a byte-identical RDB. The native databases
rule out loss during KLT JSON conversion on these runs. The macOS replay
shows that running on macOS alone is insufficient to reproduce the five
extra markers. Their cause remains open. The original capture supplies
the JSON and CLI path, but lacks a raw RDB, run log, package fingerprint
and separate LDNMOS file hash for that installation.
[Single-thread log](replays/linux/one-thread.log.gz) · [Single-thread RDB](replays/linux/one-thread.lyrdb.gz)

**Marker locations.** Coordinates below are cell-local bounding boxes in µm.
The macro GDS uses 0.001 µm per DBU. The three standalone streams use
0.0005 µm per DBU. Each listed bounding box has zero width, so a single
x and a y range identify it. Standalone totals count items in a separate
run of each GDS.

| Rule | Cell in original macro report | Macro x | Macro y range | Standalone x and y range in `nfet_10v0_asym` |
| --- | --- | ---: | --- | --- |
| MDN.10c | `cell_candidate2` | 0.270 | −1.818 to 1.818 | Outside the three standalone comparisons |
| MDN.10c | `cell_candidate2_Amin_G2x` | 0.270 | −1.818 to 1.818 | 0.270, −1.813 to 1.813 |
| MDN.10c | `cell_candidate2_A2x_G2x` | 0.270 | −3.818 to 3.818 | 0.270, −3.813 to 3.813 |
| MDN.10c | `cell_candidate2_A2x_Gmin` | 0.270 | −3.818 to 3.818 | 0.270, −3.813 to 3.813 |
| MDN.5c | `cell_candidate2_A2x_Gmin` | 1.910 | −3.960 to 3.960 | 1.910, −3.960 to 3.960 |

| Standalone stream | Original macOS (total / MDN.10c / MDN.5c) | Linux replay (total / MDN.10c / MDN.5c) |
| --- | --- | --- |
| `cell_candidate2_A2x_Gmin` | [47 / 1 / 1](../cell_candidate2_A2x_Gmin/drc_native_report.json) | [45 / 0 / 0](replays/linux/cell_candidate2_A2x_Gmin.json.gz) |
| `cell_candidate2_A2x_G2x` | [46 / 1 / 0](../cell_candidate2_A2x_G2x/drc_native_report.json) | [45 / 0 / 0](replays/linux/cell_candidate2_A2x_G2x.json.gz) |
| `cell_candidate2_Amin_G2x` | [29 / 1 / 0](../cell_candidate2_Amin_G2x/drc_native_report.json) | [28 / 0 / 0](replays/linux/cell_candidate2_Amin_G2x.json.gz) |

The input and deck hashes match within each pair of standalone runs. All
other rule counts agree. Both MDN rules remain open for signoff.

**Repeat the capture.** From this directory, set `PDK_ROOT` to the pinned
installation and `KLT_KLAYOUT_BINARY` to the native executable. Run the
native CLI directly to preserve the RDB and log, then repeat through KLT to
obtain its JSON. The deck loads `rule_decks/*.rb` relative to its own
directory, including `rule_decks/ldnmos.rb`. The successful macOS build
used Ruby 3.4.13. The macOS 0.30.12 build with system Ruby stopped at
the method definitions in `rule_framework.rb` before checking any rules.
[System-Ruby run](https://github.com/2AMLogic/gf180-antifuse/actions/runs/45864204840)

```sh
set -e
export PDK_ROOT KLT_KLAYOUT_BINARY
drc="$PDK_ROOT/gf180mcuD/libs.tech/klayout/tech/drc"
shasum -a 256 array_region_ii.gds "$drc/gf180mcu.drc" "$drc/rule_decks/ldnmos.rb"
"$KLT_KLAYOUT_BINARY" -b -r "$drc/gf180mcu.drc" -rd input=array_region_ii.gds \
  -rd "report=$PWD/native.lyrdb" -rd decks=all,-mslot -rd variant=gf180mcuD > native.log 2>&1
rc=0
uv run --no-project --isolated --with klayout-tools==0.9.2 --with klayout==0.30.13 \
  klt drc array_region_ii.gds --top array_region_ii --engine klayout --pdk gf180mcuD \
  --deck-var decks=all,-mslot --format json > klt.json || rc=$?
test "$rc" -eq 3
```

Compare raw XML items to the JSON, giving empty MDN categories explicit zeros.

```python
from collections import Counter
import json
import xml.etree.ElementTree as ET

rdb = ET.parse("native.lyrdb")
counts = Counter(item.findtext("category").strip("'") for item in rdb.findall("items/item"))
with open("klt.json") as stream:
    report = json.load(stream)
assert sum(counts.values()) == report["violation_count"]
assert dict(counts) == report["rule_counts"]
print(sum(counts.values()), counts["MDN.10c"], counts["MDN.5c"])
```
