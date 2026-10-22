# layout/erc/ -- `klt erc` supply spec

`supplies.json` is the `klt erc` spec derived from the supply-domain inventory
`spec/supply-domains-decision.md` (rows 1 to 17). It is an **input** only: no
ERC has been run on a layout and no evidence envelope exists. Item 11 stays
`unmet` until the layout-dependent half (issue #120) runs `klt erc` and cites
the result with item 4's LVS report.

Nothing here resolves an open item (OI-n) of the decision record. A row that
depends on an unresolved OI is a gap below, not a guessed net.

## Spec contents

| Block | Source |
|---|---|
| `stackup[]` (poly as `gate` with `active_layer`, Metal1 to Metal5 with label layers) and `vias[]` | gf180mcu GDS layer/datatype numbers: metals, vias and label datatypes from the PDK `gf180mcu.map` (`libs.tech/klayout/tech/gf180mcu.map`, ciel gf180mcu revision `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, identical in variants A to D); Comp 22/0, Poly2 30/0, Nwell 21/0, Pplus 31/0, Nplus 32/0, Contact 33/0 from the klayout-tools `gf180mcu` deck (`LAYER_NAMES`, klayout-tools `ff97d692`). |
| `ties[0]` `vb_nwell_region_iii` | Row 15. |

No `nets[]` entry is declared; see "Why no `nets[]`".

## Row mapping (exactly one disposition per row)

| # | Net | Disposition | Detail |
|---|---|---|---|
| 1 | Logic rail (`VDD_LOGIC`) | gap | Placeholder name, rating unchecked (OI-1), sourcing undecided (OI-2). |
| 2 | Logic ground (`VSS_LOGIC`) | gap | Placeholder name; relation to rows 12, 13 (OI-6), sourcing (OI-2). |
| 3 | `VPP`, Region I | gap | One physical net or three is OI-3. Declaring `VPP` would fix an island count. |
| 4 | `VPP`, Region II | gap | OI-3, as row 3. Rating of the ballast on this path is OI-5. |
| 5 | `VPP`, Region III | gap | OI-3, as row 3. |
| 6 | Level-shifter rail, 6 V tier | gap | Read-time bias unresolved (OI-7). |
| 7 | Level-shifter rail, Region II tier | gap | Device family and rail unspecified (OI-4). |
| 8 | Pass-gate gate-drive levels | gap | ON and OFF levels not stated; they are on-die driven levels, not rails with a settled name. |
| 9 | `GATE_BIAS` | gap | Placeholder name, value and source (OI-8). |
| 10 | `VREAD` | gap | Placeholder name, value and source (OI-8). |
| 11 | Sense-amp supply, `I_ref` | gap | Not stated in any record (OI-8). |
| 12 | `PL` | gap | Which array rail it ties to is OI-6. |
| 13 | `VSS_ANALOG` | gap | Placeholder name; separate from row 2 or not is OI-6. |
| 14 | `VB`, Regions I and II (p-substrate tie) | gap | Not expressible without layout geometry: a native-substrate tie needs `well_layer: null` plus asserted `well_boxes`, i.e. coordinates. Declared with the layout in #120. Not an OI and not a schema limit. |
| 15 | `VB`, Region III (n-well tie) | declared | `ties[0]`: Nwell 21/0, tap = Comp 22/0 intersect Nplus 32/0, wired to Metal1, net `VB`. |
| 16 | Pass-gate and level-shifter bulk/well ties | gap | Assignment is OI-3. |
| 17 | Capacitor body/well tie | gap | No separate tie net is defined; the second terminal is `PL` (row 12, OI-6). |

Region I, II and III stay distinct: rows 3 to 5 and 14/15 are separate rows and
none is averaged into another.

## Why no `nets[]`

The only rows with a non-placeholder name are `VPP` (rows 3 to 5) and `VB`
(rows 14, 15). A `nets[]` entry carries an `islands` count, so declaring
`VPP` would assert one of the topologies OI-3 leaves open, and a single `VB`
entry would assert that the p-substrate tie of rows 14 and the n-well tie of
row 15 are one net. Both would be guesses, so `erc.supply_short`,
`erc.unconnected_net` and the other net findings are not computed by this
spec. `ties[0]` names `VB` directly and does not need a `nets[]` entry.
Adding net entries needs OI-3 and OI-6 resolved through `spec/` with a
decision record.

The program-voltage domain is therefore covered only as the explicit gap of
rows 3 to 5 (OI-3); it is not dropped.

## Validation

`klt erc` has no spec-only mode, so the spec was checked by a one-off run
against `layout/cell_candidate1/cell_candidate1.gds` (klt `0.7.1.dev2419+ga7dfbc5ce95d`). It parsed, and
the tie was recorded as skipped (`empty_well_region`, the bitcell draws no
Nwell) with `erc_status: clean_partial`. That run is a schema check, not
evidence, and was not committed. The missing spec-only mode is filed as
2AMLogic/klayout-tools#4034.
