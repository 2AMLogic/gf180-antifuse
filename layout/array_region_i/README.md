# Region I cell matrix

The routed macro contains the 352 Candidate 1 cells at rows 0–31 and columns
0–10 of the 32×32 array. It exposes the cell-side nets needed by the addressing
stage: 11 column bit lines, 32 word lines, 32 plate lines and the VSS body bus.
Each selected row shares its word and plate lines across all 11 columns. Each
column shares its bit line across all 32 rows. The four split points each occur
88 times. [Array source](../../design/netlists/array_32x32.spice)

The generator places the signed Candidate 1 GDS variants using the Run 3 pin
landing offsets. BL uses Metal4, WL uses Metal3, PL uses Metal5 and the VSS
tap bus uses Metal2 with a Metal4 spine. Cell pitch is 12 × 9 µm. The macro
occupies 130.38 × 286.48 µm. Its GDS grid is 0.001 µm. The check compares
every imported mask against its original cell on the finer 0.0005 µm grid.

## Results

| Check | Result |
| --- | --- |
| Released KLT 0.9.2 LVS | 428/428 nets, 704/704 devices and 76/76 public pins match. The reference uses the original array's BL/WL/PL/VB connections and the four leaf references at their drawn dimensions. |
| Physical connectivity | All 1,408 cell terminals reach the intended top-level conductor. KLayout builds islands from physical metals and vias; text identifies the probe sites. |
| Open control | A Metal4 cut on BL_3 between rows 15 and 16 disconnects exactly the upper 16 cells from the labeled terminal. LVS extracts 429 nets against 428 in the reference and returns mismatch. |
| Short control | A Metal4 bridge between BL_3 and BL_4 joins exactly those two columns. LVS extracts 427 nets against 428 and returns mismatch. |
| Curated GF180 DRC | Zero findings. |
| Native GF180D DRC | Eight density findings on the standalone macro: `DCF.1b`, `M1.4`–`M5.4`, `MT.3` and `PL.8`. No DBU or routing-rule finding. |

The simulated geometry in the array schematic uses a 1.0 µm capacitor length
and access widths of 0.30/0.60 µm. The drawn lengths and widths are 0.28 µm
and 0.42/0.84 µm respectively. Both use capacitor widths of 1.0/2.0 µm and
access length 0.70 µm. The physical check measures the gate crossing Comp,
using MOS_CAP_MK to distinguish capacitor and access channels, at every
placement. The LVS deck uses a placeholder capacitor value and omits secondary
geometry parameters; the comparison supports topology. Absolute capacitance,
programming yield, and voltage/timing behavior require separate evidence.
[Geometry basis](../../design/geometry-basis.json)

Completing the array requires the remaining Candidate 2/3 split masters and
the other two regions, plus their control connections, level shifters and
pass gates. This macro is supporting work for item 2.analog. The current
Bronze signoff manifest continues to require full-array coverage.

## Reproduction

From the repository root:

```sh
uv run --no-project --script layout/array_region_i/generate.py --check
uv run --no-project --script layout/array_region_i/check.py
```

Omit `--check` to regenerate the GDS and projected SPICE. The two scripts
pin the KLayout Python binding at 0.30.13. To reproduce the committed reports
from this directory:

```sh
uvx --from klayout-tools==0.9.2 --with klayout==0.30.13 klt lvs lvs_request.json --format json
uvx --from klayout-tools==0.9.2 --with klayout==0.30.13 klt drc array_region_i.gds --top array_region_i --deck gf180mcu --format json
uvx --from klayout-tools==0.9.2 --with klayout==0.30.13 klt drc array_region_i.gds --top array_region_i --engine klayout --pdk gf180mcuD --deck-var decks=all,-mslot --format json
```

The native run used KLayout CLI 0.30.12 and the repository's pinned open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. It returns a violations verdict
on the eight density rules. The native report's deck path was normalized with
the repository's `rtl/scrub_report_paths.py`.
