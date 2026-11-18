# run3_top — chip-level reference netlist and pad table

Generated artifacts for the run3 test chip (issue #275, part of #203):

- `run3_top.spice` — chip-level SPICE reference netlist: the 8 per-geometry
  cell subcircuits plus the top `run3_top` subckt instantiating 36 cells in
  4 groups (C1-Amin 8, C1-A2x 8, C2-Amin 10, C3-Amin 10; shared BL and WL per
  group, private PL per instance). 45 signal ports. Self-contained (no
  `.include`), written to the `klt lvs` `reference.form = "subckt-call"`
  shape with `top = "run3_top"`.
- `pad_table.json` — machine-readable pad table: 48 logical slots `L01`-`L48`
  (pad id, signal, direction, slot type, voltage class).

Both files are **generated — do not edit**. Regenerate and verify:

```sh
python3 -I layout/run3_top/generate_run3_top.py          # write both files
python3 -I layout/run3_top/generate_run3_top.py --check  # byte-compare vs committed
python3 -I scripts/check_run3_pad_table.py               # spec-source check (in check:ci)
```

`scripts/check_run3_pad_table.py` re-derives each committed artifact against
the source that binds it: the pad table against `spec/run3-test-chip-floorplan.md`,
the netlist's capacitor geometry against `spec/capacitor-geometry-decision.md`,
and its access geometry against the drawn `XM1` literals of
`layout/cell_*/lvs_reference.spice`. It runs in the repo's `check:ci` gate.

## Status of the inputs this generator reads

- **The floorplan record is Proposed, not ratified.**
  `spec/run3-test-chip-floorplan.md` is "Proposed for operator ratification".
  If the operator changes it, regenerate; the check script fails on drift
  between the record and the committed artifacts.
- **The HV terminal follows the unratified program-bias record.**
  `spec/program-bias-scheme-proposed-decision.md` is PROPOSED and recommends
  the PL-driven program leg, so the HV pad class (voltage class `HV` **and**
  slot type `bidir`) rides the 36 `PL_` pads. If the operator ratifies
  **BL-driven** programming instead, the floorplan's wiring section says the
  HV terminal moves to BL and the private/shared roles of PL and BL swap:
  pad **counts** are unchanged, the slot types are not ("HV on bidirectional,
  standard on analog" — for the HV-pad sibling to confirm). **What changes in
  the generator:** flip the one named constant `HV_TERMINAL = "PL"` to `"BL"`
  in `generate_run3_top.py`; both derived fields move with it in
  `terminal_pad_fields()` (one-line change), then regenerate. Nothing else
  changes: the WL, `VBW_C3` and UNUSED pads are not program terminals.
- **The capacitor levels are ratified.** `spec/capacitor-geometry-decision.md`
  is binding: Minimum `1.0 x L` µm, 2x-area `2.0 x L` µm, with L = 0.28 µm
  (regions I/III) and 0.70 µm (region II; its drawn `c_length=0.56u` violates
  `PL.2_MV` independently of width, so C2 moves in both dimensions).

## Geometry basis

Stated here once: **capacitor W/L** comes from the ratified
`spec/capacitor-geometry-decision.md`; **access W/L** comes from the drawn
`XM1` literals of the committed `layout/cell_*/lvs_reference.spice` (the
access-device sizing axis is unratified — the decision record explicitly
leaves it "untouched" — so the drawn literals are the only committed physical
basis). The netlist therefore holds exactly the geometry the post-#296 die
will contain: #296 redraws the capacitor only, so this artifact **leads**
#296 rather than needing regeneration when it lands.

**The capacitor half knowingly disagrees with all seven committed drawn
cells** (which still carry the superseded 0.42/0.84 µm levels) until #296
lands. That is the expected state, not drift: `design/check-geometry-basis.py`
with `design/geometry-basis.json` (landed with #292) owns the
design ↔ layout geometry divergence record; this issue does not re-check it,
and `scripts/check_run3_pad_table.py` keys each half to its own binding
source instead.

## The one geometry point with no drawn cell

`cell_candidate2_Amin_G2x` has **no drawn cell** (#296 is the redraw; the
2026-11-15 #299 operator ruling on the `nfet_10v0_asym` PCell's native-deck
findings is decided and recorded in
`spec/pdk-pcell-drc-exception-decision.md`).
It is still emitted: access literals from
`cell_candidate2` (same `Amin` level), capacitor from the ratified record —
only its layout is missing, not its numbers. That absence blocks #211's LVS,
not this issue.

## Placeholder substrate net

The C1/C2 bodies tie on-die to `VSS_ANALOG`, and C3's n-well tie is the
`VBW_C3` pad net (L45). `VSS_ANALOG` is the **generator's placeholder**, not a
ratified name: `spec/supply-domains-decision.md` rows 2/13/14 leave the
return/ground topology open (OI-2, OI-6). No `spec/` record is added for it
here.

## Not built here

- The floorplan record's **C2-fallback variant** (bare `cap_nmos_06v0`
  capacitors if `nfet_10v0_asym` is not offered) is noted by the record, not
  built by this generator; the assembler takes its cell list from the shared
  instance table, so swapping candidate 2 for the fallback is a table change
  (#372/#377) followed by one regeneration.
- The **undrawn cell** still blocks nothing here: the assembly excludes its
  five instances and says so (see "Chip assembly" below).
- `klt lvs` is **not** run here and no pass is asserted for `run3_top.spice`
  itself: the chip assembly's compare runs against
  `lvs_reference_drawn.spice` (see "Chip assembly" below).

---

## Chip assembly (#211)

`assemble_run3_top.py` builds the chip layout, `run3_top.gds` (top cell
`run3_top`, die 1936 x 2531 um), from two inputs: `pad_table.json` (the 48
logical slots) and the shared instance table in `generate_run3_top.py`
(imported). It is deterministic; `--check` byte-compares both artifacts it
writes (`run3_top.gds`, `lvs_reference_drawn.spice`) against the committed
copies on sha256, like `generate_run3_top.py`:

```sh
python3 -I layout/run3_top/assemble_run3_top.py            # write both
python3 -I layout/run3_top/assemble_run3_top.py --check    # byte-compare
```

Stdlib only; geometry comes from calling `klt draw` (pad ring, outline) and
`klt gen-compose` (placement + routing). Every routing leg is explicitly
waypointed and pairwise keep-clear checked before the request is written, and
the compose response is asserted all-routed / all-landed before anything is
written; it is committed as `compose_report.json`.

### Template provenance

Quarter slot `0p5x0p5_def_all` of the shuttle template page
(`https://mith.ro/gf180mcu-project-template/`, "GF180MCU Slot Sizes -
wafer.space"), **read 2026-11-18**; the page carries no revision number — its
stamp ("Generated: 24 Oct 2026 01:02 UTC"; `slots.json`
`generated_at 2026-10-24T01:02:29Z`) is the only revision identifier. Quarter
slot: die 1936 x 2531 um, usable silicon 1.884 x 2.479 mm (seal ring 26 um per
edge, added by the shuttle flow, not drawn), core 1.052 x 1.647 mm, 48 signal
I/O (38 bidir / 6 input-only / 4 analog — the pad table's slot types exactly)
plus 8 power pads (4 DVDD + 4 DVSS). The page lists **no** antenna/density/ERC
check requirements; the checks recorded here are the repo's own
(`supplies.json` ERC + antenna, `klt economy` density, the native runset's
die-level density and antenna rules).

### Physical pad mapping (this file records it; the assembler holds it)

- **L01-L24** (24 private-plate pads): left edge, x = 130 um, y = 240 + 85*i.
- **L25-L36** (12 private-plate pads): right edge, x = 1806 um, same y pitch.
- **L37-L45** (shared BL/WL, C3 n-well tie): bottom edge, y = 130 um,
  x per pad id: L37 540, L38 450, L39 360, L40 760, L41 270, L42 180,
  L43 90, L44 880, L45 640. The x order along the edge is not the pad-id
  order: each bundle's trunk rises from its own pad, ordered so same-plane
  paths never cross (the assembler asserts keep-clear pairwise).
- **L46-L48** (unused): bottom edge, x = 1150 / 1260 / 1370, unlabelled.
- **8 power pads** (4 DVDD + 4 DVSS): top edge, y = 2401, unlabelled,
  unconnected (the template provides the slots; this chip is all-passive and
  has no DVDD/DVSS nets).

Bond pads are drawn bare: an 80 um Metal5 square with a 60 um pad opening
(37/0), enclosure 10 um — the #210 record's bare-pad choice (no pad cell, no
ESD structure, off-die current limiting) at the template's pad footprint, with
`PAD.4` (2 um Metal5 overlap of the opening) satisfied. The 40 connected pads
carry their signal name on Metal5 label 81/10; the 16 unconnected pads (5
reserved private-plate slots of the undrawn cell, 3 UNUSED, 8 power) are drawn
unlabelled, so extraction reports them as dead metal rather than as named
floating nets.

### Placement and routing

The 31 placed instances sit in two columns (left-edge instances at x = 600,
right-edge at x = 1000), each at its own pad's y so **every private-plate
(HV) route is one straight Metal5 run** — the #210 bare-pad path. The five
excluded instances (undrawn `cell_candidate2_Amin_G2x`) leave their five pads
unconnected. Shared nets route on dedicated lower-metal planes so no two nets
share a plane where their paths would cross: BL on Metal4, WL on Metal3,
VBW_C3 and the C1/C2 substrate strap (`VSS_ANALOG`, internal — no pad) on
Metal2; each bundle trunk rises from its own bottom-edge pad to its group's
band and stubs to each pin at 0.42 um width. Every pin gets a via ladder from
its route plane down to its Metal1 pad (Metal5 routes: 4 hops; Metal4: 3;
Metal3: 2; Metal2: 1), sized exactly as the router draws them; the landing
points are the committed cells' true pad centres (for the substrate taps: a
point on each cell's tap-ring metal verified to keep `metal1.space.1`
clearance), held in the assembler's `PIN_OFFSET_UM` table with provenance in
its comment and asserted by `tests/test_run3_top_assembly.py`.

### Evidence (regenerate and re-check)

| File | What it is | Regenerate |
|---|---|---|
| `run3_top.gds` | the assembled chip | `python3 -I assemble_run3_top.py` (`--check` byte-compares) |
| `lvs_reference_drawn.spice` | LVS reference for THIS assembly: the seven drawn cells' subcircuits verbatim from the #275 generator + a top instantiating exactly the 31 placed instances over the 40 connected ports; the five excluded instances/ports are named in the header, never silently dropped | same run |
| `compose_report.json` | `klt gen-compose` response: every net routed, every leg `landed_on_block` (asserted by the assembler before it writes) | same run |
| `lvs_request.json`, `lvs_report.json` | `klt lvs`, inline extraction, reference `subckt-call` against `lvs_reference_drawn.spice`, flattened both sides, `combine_devices` on (the LDMOS extracts as two per-finger devices, #5277): **status `match`** | `klt lvs lvs_request.json --format json > lvs_report.json` |
| `drc_report.json` | curated deck `klt drc --deck gf180mcu`: `violations`, 80 findings — **all** `comp.enclosing.contact.1` inside the unmodified `nfet_10v0_asym` PCell instances (16 per C2 cell), the geometry class the ratified `spec/pdk-pcell-drc-exception-decision.md` scopes; nothing drawn by this assembly appears | `klt drc run3_top.gds --deck gf180mcu --top run3_top -o drc_report.json --format json` |
| `drc_native_report.json` | native runset (`--pdk gf180mcuA --deck-var decks=all,-mslot`, per #287): 1089 findings — MT30.\* die-level TopMetal1 density (the die is ~89 % whitespace, `economy_report.json`), CO.4/DF.6_MV/PL.4_MV inside the same PCell instances (ratified exception class), 29 ANT.16_ii_ANT.4 antenna-ratio findings on the shared WL nets (long word lines over few gates — inherent to this all-passive addressing; fixes would be antenna diodes or gate replication, a design change, not a reroute), CUP.2, DCF.1b global COMP density, DBU (klt's canonical dbu is 0.0005, the same finding the committed cell native reports carry). None waived | `klt drc run3_top.gds --engine klayout --top run3_top --pdk gf180mcuA --deck-var decks=all,-mslot -o drc_native_report.json --format json` |
| `supplies.json`, `erc_report.json` | chip-level ERC spec extending the `layout/erc/` convention: p-substrate tie over the left column (net `VSS_ANALOG`), n-well tie over the right column (net `VBW_C3`); `erc_status: clean`, all 35 gates float-checked; antenna-ratio verdicts stay `unchecked` here (the build ships no gf180mcu limit table for `klt erc`) — the antenna verdict of record is the native runset's ANT findings above | `klt erc run3_top.gds supplies.json --top run3_top --pdk gf180mcu --deck gf180mcu --format json > erc_report.json` (exit 4 = not-checked verdict, not a tool failure) |
| `economy_report.json` | `klt economy` density/utilisation: 4.90 mm2 die, 11 % drawn | `klt economy run3_top.gds --format json > economy_report.json` |

Toolchain: assembled and checked with the host dev build
(`klt 0.9.3.dev1136+g81926eccba7b`, KLayout 0.30.x, PDK `gf180mcuA`); the
committed artifacts reproduce from the pinned commands above. The template
page's antenna/density/ERC list is empty (see provenance above); the
operator's chip-level checklist is not yet provided and remains tracked on
the issue.

### Manual check list (operator, pre-submission)

The GDS opens; pad names/positions match `pad_table.json` per the mapping
above (labelled pads carry their signal text on 81/10); the HV pads occupy the
bidirectional slots the floorplan reserves. The invention-firewall check and
the operator's chip-level checklist stay explicit operator steps.
