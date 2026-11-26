# layout/erc/ -- `klt erc` supply spec

`supplies.json` is the `klt erc` spec for the first drawn bitcell
(`cell_candidate1`, Region I), derived from the supply-domain inventory
`spec/supply-domains-decision.md` (rows 1 to 17). The run on the first bitcell is
`layout/cell_candidate1/erc_report.json` (issues #120, #196), cited with item
4's LVS report as `11.analog` (see `signoff/README.md`).
`supplies_c1_Amin_G2x.json`, `supplies_c1_A2x_Gmin.json` and
`supplies_c1_A2x_G2x.json` are the same Region I spec for the other three
Candidate 1 split points (`layout/cell_candidate1_*/`), differing from
`supplies.json` in **only** the tie's two asserted `well_boxes` `y1` values.
They exist as separate files rather than one parameterized spec because this
tie's `well_boxes` are hardcoded absolute geometry (see "The one declared net")
that a device-width doubling invalidates, and because `klt erc --check`
validates `provenance.spec.content_hash` -- so editing `supplies.json` in place
would drift `cell_candidate1`'s ratified ERC evidence. Per-cell values and the
coverage numbers they produce are tabulated in `layout/README.md`.

`supplies_c2.json` is the same Region I spec for `cell_candidate2/` (the
`nfet_10v0_asym` bitcell, issue #373): a copy of `supplies.json` differing
only in the tie's two `well_boxes`, which are the extents of that cell's own
two `Pplus` 31/0 tap-ring outlines (`[-2.83, -4.02, 2.83, 4.02]` capacitor
block, `[4.27, -0.44, 8.43, 4.44]` access block). Until #373 candidate 2 ran
`supplies.json` and its report's `clean` covered only ~45 % of its drawn tap
area (`uncovered_tap_fraction: 0.55393`); with its own spec the uncovered
fraction is 0.0. The same separate-file reasoning applies: the boxes are
absolute geometry at candidate 2's coordinates, and the run is
`layout/cell_candidate2/erc_report.json`.

`supplies_region_iii.json` checks the drawn n-wells on both Candidate 3
bitcells. It declares only a Region III tie and no `nets[]`. Running it against
`cell_candidate1`, which draws no Nwell, yields a skipped `empty_well_region` tie. Unlike the
Region I spec it declares a real `well_layer` (`21/0`) and carries no
`well_boxes`, so it is geometry-independent and needs no per-cell copies.

Nothing here resolves an open item (OI-n) of the decision record. A row that
depends on an unresolved OI is a gap below, not a guessed net.

## Digital partition

`supplies_digital.json` checks the VDD and VSS labels on the routed
`antifuse_digital_top` GDS. These are the power and ground net names in
`rtl/pnr/antifuse_digital_top.pnr.json`. Rows 1 and 2 of the
[supply-domain inventory](../../spec/supply-domains-decision.md) describe
their functions. The voltage, supply source and relationship to the analog
return are open chip-level decisions.

The P&R report records 220 `gf180mcu_fd_sc_mcu7t5v0__filltie` tapcells and
straps on Metal1, Metal4 and Metal5. The ERC stack spans Metal1 through Metal5
and their intervening vias. Both supplies share these routing layers. Each
supply must form one island and the two supplies must be separate.

The n-well tie requires an actual Contact cut (33/0) in Comp (22/0) and Nplus
(32/0) inside drawn Nwell (21/0), reaching VDD through Metal1. The substrate
tie requires a Contact cut in Comp and Pplus (31/0) outside Nwell reaching VSS.
The substrate region is the declared complement of Nwell within the top-cell
bounds. The report records this under `checked_by_well_assertion`.
ERC requires at least one connected tap per merged well or substrate region.
Tap spacing and continuity of every individual tap are separate checks.

From the repository root, reproduce the committed report with the pinned tool:

```sh
uvx --from klayout-tools==0.8.0 klt erc --check layout/erc/digital_erc_report.json --rerun
```

`digital_erc_report.json` records one island per supply, both ties checked and
zero ERC findings. The generation command below returns 4 when connectivity is
clean and antenna grading was omitted. The full replay above returns 0 on match.

```sh
uvx --from klayout-tools==0.8.0 klt erc rtl/pnr/antifuse_digital_top.gds \
  layout/erc/supplies_digital.json --top antifuse_digital_top --deck gf180mcu \
  --findings-only --compact --omit-antenna-tables --format json
```

To exercise the polarity check, swap just the requested tie destinations on a
scratch copy of the spec and use its path in the generation command. The
routed GDS then yields 27 missing VSS ties on the n-wells and one missing VDD
tie on the substrate. Both metal rails still have one island.

```sh
jq '(.ties[] | .net) |= (if . == "VDD" then "VSS" else "VDD" end)' \
  layout/erc/supplies_digital.json > /tmp/antifuse-swapped-ties.json
```

Issue #177 also requires the accepted digital LVS evidence from #176 to grade
the compound power-delivery row.

## Analog spec contents

| Block | Source |
|---|---|
| `stackup[]` (poly as `gate` with `active_layer`, Metal1 to Metal5 with label layers) and `vias[]` | gf180mcu GDS layer/datatype numbers: metals, vias and label datatypes from the PDK `gf180mcu.map` (`libs.tech/klayout/tech/gf180mcu.map`, ciel gf180mcu revision `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, identical in variants A to D); Comp 22/0, Poly2 30/0, Nwell 21/0, Pplus 31/0, Nplus 32/0, Contact 33/0 from the klayout-tools `gf180mcu` deck (`LAYER_NAMES`, klayout-tools `ff97d692`). |
| `nets[0]` `VB` (`kind: supply`, `islands: 1`) | Row 14, Region I only; see "The one declared net". |
| `ties[0]` `vb_psub_region_i` | Row 14. p-substrate tie: `well_layer: null`, asserted `well_boxes`, tap = Contact 33/0 in Comp 22/0 and Pplus 31/0, wired to Metal1, net `VB`. |
| `supplies_c1_*.json` `ties[0]` `vb_psub_region_i` | Row 14, same tie, asserted `well_boxes` re-derived for each `layout/cell_candidate1_*/` split point. |
| `supplies_c2.json` `ties[0]` `vb_psub_region_i` | Row 14, same tie, asserted `well_boxes` fitted to `cell_candidate2/`'s own two `Pplus` tap-ring outlines (issue #373). |
| `supplies_region_iii.json` `ties[0]` `vb_nwell_region_iii` | Row 15, exercised on both Region III bitcells. |

No other analog `nets[]` entry is declared; see "The one declared net".

### Contact-only fault controls

Run `uv run --no-project --script scripts/check_analog_tap_contacts.py` to
exercise the seven drawn bitcells with ERC reports and the 31-instance Run 3
die. The regression uses KLayout 0.30.13 and KLT 0.9.2. It checks each
unchanged GDS, then opens only Contact 33/0 on the selected tap polarity in
a temporary GDS. It compares every finding to the affected body's bounding
box and verifies the island count on each declared rail.

On the Run 3 die, opening 510 substrate contacts produces one missing
`VSS_ANALOG` tie in the asserted substrate box. Opening 140 n-well contacts
produces 20 missing `VBW_C3` ties, one per drawn well. A separate fault opens the seven contacts of
just the leftmost well and produces one finding at that well. The two metal rails each retain one island. These
controls cover the committed macros and the Run 3 test die.

## Analog-spec coverage of the supply-domain inventory

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
| 14 | `VB`, Region I (p-substrate tie) | declared | `nets[0]` and `ties[0]` of `supplies.json`, checked on `cell_candidate1` (issue #196), of the three `supplies_c1_*.json`, checked on the three `cell_candidate1_*` split points (issue #273), and of `supplies_c2.json`, checked on `cell_candidate2` (issue #373). Region II is not drawn: still a gap. |
| 15 | `VB`, Region III (n-well tie) | checked on both Candidate 3 bitcells | `supplies_region_iii.json` checks a Contact 33/0 in Comp 22/0 and Nplus 32/0, wired to Metal1 on `VB`, for each drawn Nwell 21/0. |
| 16 | Pass-gate and level-shifter bulk/well ties | gap | Assignment is OI-3. |
| 17 | Capacitor body/well tie | gap | No separate tie net is defined; the second terminal is `PL` (row 12, OI-6). |

Region I, II and III stay distinct: rows 3 to 5 and 14/15 are separate rows and
none is averaged into another.

## The one declared net

`nets[0]` is `VB` with `islands: 1`, scoped to the Region I cells that run a
Region I spec (row 14): `cell_candidate1`, its three split points and
`cell_candidate2`. It asserts only that the two p-tap rings of the cell the
spec runs against are strapped into one `VB` island; it does **not** assert
that rows 14 and 15 are one net (the Region III n-well tie lives in the
separate `supplies_region_iii.json`). Every other net stays a gap in the analog table
above: `VPP` (rows 3 to 5) would fix an island count that OI-3 leaves open,
and the placeholder-named rails and `PL` wait on OI-1, OI-2, OI-6 and OI-8.
Adding any of them needs those OIs resolved through `spec/` with a decision
record.

`well_boxes` is a caller **assertion** (a native p-substrate has no drawn well
layer): the two boxes are the extents of the cap-block and access-block tap
rings (`Pplus` 31/0 outlines) -- of the cell the spec runs against. Each cell
carries its own fitted boxes and numbers: the `supplies.json`, `supplies_c1_*`
and `supplies_c2.json` figures (drawn tap area, `uncovered_tap_fraction` and
`extent_uncovered_fraction` from `erc_coverage.well_assertion_coverage`) are
tabulated per cell in `layout/README.md`. The result is therefore
a tie check against the asserted substrate region (`checked_by_well_assertion`),
not against a drawn tub.

The program-voltage domain is covered only as the explicit gap of rows 3 to 5
(OI-3); it is not dropped.

Regenerate (klayout-tools `0.8.0`, from `layout/cell_candidate1/`):
`uvx --from klayout-tools==0.8.0 klt erc cell_candidate1.gds ../erc/supplies.json --top cell_candidate1 --findings-only --format json > erc_report.json`.
Each split point is the same command from its own directory against its own
spec, e.g. from `layout/cell_candidate1_A2x_G2x/`:
`uvx --from klayout-tools==0.8.0 --with klayout==0.30.12 klt erc cell_candidate1_A2x_G2x.gds ../erc/supplies_c1_A2x_G2x.json --top cell_candidate1_A2x_G2x --findings-only --format json > erc_report.json`
(the extra `--with klayout==0.30.12` pins the engine the `0.8.0` build was
tested against, keeping `provenance.klayout_version_mismatch` `false`).
The run is `--findings-only` (no gf180mcu antenna table), so `status` stays
`not_checked`; `erc_status` is `clean`, `erc_finding_count: 0`.
`cell_candidate2/` is regenerated against its own spec from the repo root,
**without** `--findings-only` (its committed report is a full run whose
antenna half is `not_checked` for missing PDK antenna data, so per-level gate
areas are reported with verdict `unchecked`), on the same klt 0.9.2 toolchain
as the cell's other artifacts:
`uvx --from klayout-tools==0.9.2 klt erc layout/cell_candidate2/cell_candidate2.gds layout/erc/supplies_c2.json --top cell_candidate2 --format json > layout/cell_candidate2/erc_report.json`.
`erc_status` is `clean`, `erc_finding_count: 0`, `uncovered_tap_fraction: 0.0`
(issue #373; the report echoes the spec repo-relative, so
`klt erc --check layout/cell_candidate2/erc_report.json` is also run from the
repo root).

## Validation

`klt erc` has no spec-only mode, so the spec was checked by a one-off run
against `layout/cell_candidate1/cell_candidate1.gds` (klt `0.7.1.dev2419+ga7dfbc5ce95d`). It parsed, and
the tie was recorded as skipped (`empty_well_region`, the bitcell draws no
Nwell) with `erc_status: clean_partial`. That run is a schema check, not
evidence, and was not committed. The missing spec-only mode is filed as
2AMLogic/klayout-tools#4034.
