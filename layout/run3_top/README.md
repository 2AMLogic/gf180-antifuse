# run3_top — chip-level reference netlist and pad table

The retained 31-instance GDS and its as-measured reference predate the new
C2-Amin-G2x master. [Region II](../array_region_ii/README.md) now supplies
it for the five pending direct-pad sites. The direct-pad assembly still
requires placement, routing and fresh whole-chip verification of those sites.


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

## The one geometry point pending direct-pad integration

`cell_candidate2_Amin_G2x` is drawn. The C2-Amin-G2x master is
[`cell_candidate2_Amin_G2x/`](../cell_candidate2_Amin_G2x/), landed with the
352-cell [Region II](../array_region_ii/README.md) macro in #551 (merged
2026-11-26): `cell_candidate2_Amin_G2x.gds`, LVS `match` against its
`lvs_reference.spice` (5/5 nets, 0 errors). That reference carries the same
`XM1` and `XC1` literals the `cell_candidate2_Amin_G2x` subcircuit of
`run3_top.spice` already held, so #551 changed that subcircuit's provenance
comment only, not its numbers.

The master is not yet in this directory's chip assembly. The signed
`run3_top.gds` of 2026-11-25 (`70dbef5f`) places 31 instances, seven of the
eight geometry points, and predates the master. The reported LVS `match`
(`lvs_report.json`) applies to that assembly: it compares the GDS against
`lvs_reference_drawn.spice`, which instantiates the 31 placed instances,
whereas the design reference `run3_top.spice` holds 36. The five missing
instances `Xinst_C2_Amin_G2x_1..5` and their reserved private-plate pads
**L22–L26** are named in that reference's header. The reference was
committed 2026-11-18 (`59c21b11`), before the master, and its header still
reads `no drawn cell`: the assembler's wording for a cell in its
`PENDING_ASSEMBLY` set, not the master's state. Placing those five
instances, routing their plates to L22–L26 and verifying the resulting
direct-pad assembly are still pending, and no 36-instance compare is on
record.

Before 2026-11-26 the master did not exist, and this netlist emitted the
point with access literals borrowed from `cell_candidate2` (same `Amin`
level) and the capacitor from the ratified record.

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
- The **five pending direct-pad sites** block nothing here: the netlist
  carries `cell_candidate2_Amin_G2x` at its drawn master's literals, and the
  retained assembly excludes those five instances and says so (see "Chip
  assembly" below).
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
check requirements; the checks recorded here are the shuttle precheck's own
gating stages, reproduced at its pinned configuration (see "Precheck
applicability" below), plus the repo's curated-deck cross-check.

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
carry their signal name on Metal5 label 81/10; the 16 unconnected pads (the 5
reserved private-plate pads L22–L26 of the pending C2-Amin-G2x sites, 3
UNUSED, 8 power) are drawn unlabelled, so extraction reports them as dead
metal rather than as named floating nets.

### Placement and routing

The 31 placed instances sit in two columns (left-edge instances at x = 600,
right-edge at x = 1000), each at its own pad's y so **every private-plate
(HV) route is one straight Metal5 run** — the #210 bare-pad path. The five
excluded instances (`cell_candidate2_Amin_G2x`, a drawn master not yet
integrated here) leave their five private-plate pads L22–L26 unconnected.
Shared nets route on dedicated lower-metal planes so no two nets
share a plane where their paths would cross: BL on Metal4, WL on Metal3,
VBW_C3 and the C1/C2 substrate strap (`VSS_ANALOG`, internal — no pad) on
Metal2; each bundle trunk rises from its own bottom-edge pad to its group's
band and stubs to each pin at 0.42 um width. Every pin gets a via ladder from
its route plane down to its Metal1 pad (Metal5 routes: 4 hops; Metal4: 3;
Metal3: 2; Metal2: 1), sized exactly as the router draws them; the landing
points are the committed cells' true pad centres (for the substrate taps: a
point on each cell's tap-ring metal verified to keep `metal1.space.1`
clearance), held in the assembler's `PIN_OFFSET_UM` table with provenance in
its comment. `tests/test_run3_top_assembly.py` asserts that table's key set
and the PL pad-y alignment; it does not read the cell GDS, so the offset
values themselves are verified by the compose `landed_on_block` assertion and
by the LVS compare (`lvs_report.json`: 72/72 nets paired, 0 errors) rather
than by that test.

### Evidence (regenerate and re-check)

| File | What it is | Regenerate |
|---|---|---|
| `run3_top.gds` | the assembled chip: placement + routing + the C3 substrate tap, the MetalTop landing patches, and the density fill (all measured, see "Precheck applicability" below) | `python3 -I assemble_run3_top.py` (`--check` byte-compares) |
| `lvs_reference_drawn.spice` | LVS reference for THIS assembly: the seven drawn cells' subcircuits verbatim from the #275 generator + a top instantiating exactly the 31 placed instances over the 40 connected ports; the five excluded instances/ports are named in the header, never silently dropped | same run |
| `compose_report.json` | `klt gen-compose` response: every net routed, every leg `landed_on_block` (asserted by the assembler before it writes) | same run |
| `lvs_request.json`, `lvs_report.json` | `klt lvs`, inline extraction, reference `subckt-call` against `lvs_reference_drawn.spice`, flattened both sides, `combine_devices` on (the LDMOS extracts as two per-finger devices, #5277): **status `match`** — the substrate tap extracts as no device (tied to `VSS_ANALOG`, never to a signal net) | `klt lvs lvs_request.json --format json > lvs_report.json` |
| `drc_report.json` | Curated DRC counts 80 `comp.enclosing.contact.1` and five `comp.width.mv.1` findings in the five standard C2 instances. | `klt drc run3_top.gds --deck gf180mcu --top run3_top --format json` |
| `drc_stage_report.json` | Native DRC counts 80 `CO.4`, 10 `DF.6_MV`, 10 `PL.4_MV`, five `MDN.10c` and one `DBU`. The five `MDN.10c` findings also occur on individual standard C2 cells. | `klt drc run3_top.gds --engine klayout --top run3_top --pdk gf180mcuD --deck-var decks=all,-antenna,-density,-cup --format json` |
| `drc_antenna_report.json`, `drc_antenna_stage.lyrdb`, `drc_antenna_stage.log` | The native antenna run records 29 shared-WL `ANT.16_ii_ANT.4` findings and zero private-plate findings. The RDB contains each measured ratio. | `klt drc run3_top.gds --engine klayout --top run3_top --pdk gf180mcuD --deck-var decks=antenna --format json` |
| `drc_density_report.json`, `drc_density_stage.log` | the precheck's gating density stage (decks `density`): klt's JSON carries `rule_counts` `{}` (0 findings) with `status: coverage_unknown` — a native deck run that finds nothing declares no categories, so klt cannot prove execution from the RDB alone (`--expect-rule-categories` refuses 0); the companion `.log` is the deck's own stdout: every coverage ratio logged well above its floor (COMP 51.3 %, Poly2 15.7 %, Metal1–4 48.9–50.9 %, Metal5/MetalTop 53.0 %) and `DRC RESULT: SUCCESS (0 violations)` | `klt drc run3_top.gds --engine klayout --top run3_top --pdk gf180mcuD --deck-var decks=density -o drc_density_report.json --format json` + the `klayout -b` invocation recorded in the log |
| `supplies.json`, `erc_report.json` | chip-level ERC spec extending the `layout/erc/` convention: p-substrate tie over the left column (net `VSS_ANALOG`, now reaching the C3 substrate tap), n-well tie over the right column (net `VBW_C3`); `erc_status: clean`, all 35 gates float-checked; antenna-ratio verdicts stay `unchecked` here (the build ships no gf180mcu limit table for `klt erc`) — the antenna verdict of record is `drc_antenna_report.json` above | `klt erc run3_top.gds supplies.json --top run3_top --pdk gf180mcu --deck gf180mcu --format json > erc_report.json` (exit 4 = not-checked verdict, not a tool failure) |
| `economy_report.json` | `klt economy` density/utilisation: 4.90 mm2 die, ~78 % drawn after fill | `klt economy run3_top.gds --format json > economy_report.json` |

Toolchain: assembled and checked with the host dev build
(`klt 0.9.3.dev1370+g30969f578991`, KLayout 0.30.12); the committed artifacts
reproduce from the pinned commands above. The template page's
antenna/density/ERC list is empty (see provenance above); the operator's
chip-level checklist is not yet provided and remains tracked on the issue.

### Precheck applicability (issue #404)

Whether each chip-level finding gates the submission is settled against the
shuttle precheck's public configuration, reusing the source set #338 recorded
(`docs/wafer-space-precheck-sources.md` on `feature/issue-338`; all reads
below re-verified 2026-11-18 against the same pinned revisions):

- **S2** `wafer-space/gf180mcu-precheck` `precheck.py` @ `9b4e7dab`: the flow
  runs `KLayout.DRC` (decks `all,-antenna,-density,-cup`, "disable CUP for
  now"), then **separate** `KLayout.Density` and `KLayout.Antenna` stages
  with decks `density` / `antenna`; only `ERROR_ON_MAGIC_DRC` is disabled.
- **PDK config** (installed at the pinned open-pdks build, `libs.tech/
  librelane/config.tcl`): `KLAYOUT_DENSITY_RUNSET`/`KLAYOUT_ANTENNA_RUNSET`
  point at the same `gf180mcu.drc` with decks `density` / `antenna`;
  LibreLane's `Checker.KLayoutDensity`/`Checker.KLayoutAntenna` default
  `ERROR_ON_*` true (steps `klayout.py`/`checker.py` @ LibreLane `99148a9`).
- **Deck registry** (the runset's `options.rb`): decks are subtractive from
  `all`; variants select metal stack only (`VARIANTS`: A = 3LM + 30 K top,
  D = 5LM + 11 K top). The precheck hard-pins `PDK=gf180mcuD` (S2).

Measured dispositions, per group:

1. **Antenna (WL trunks) — applies, evaluated, deferred (needs operator).**
   `ANT.16_ii_ANT.4` (Metal3 perimeter area vs thick gate oxide, 400) fired
   on all four shared WL trunks (ratios 428.958–1035.402, per-finding `#RATIO` in
   `drc_antenna_stage.lyrdb`). The numeric remedy is
   one n-diode clamp per WL net (COMP-in-NPLUS outside NWELL, the deck's
   own `n_diode` definition); the deck's diode filtering divides the ratio
   by `gate + 15·(n_diode + p_diode + nwell)`, so a 0.6 µm COMP body clears
   the worst net (needs ≥ 0.245 µm²) with margin — evaluated in
   `assemble_run3_top.py`'s constant block and **measured** in the #416
   round that drew the clamps (`9f5dc932`, superseded when the clamp was
   un-drawn for deferral): that round's report is re-committed as
   `drc_antenna_after_wl_diode_clamp_report.json` — its input is the earlier, pre-#539
   diode-drawn GDS (sha256 `79bc8414…`, recoverable as
   `9f5dc932:layout/run3_top/run3_top.gds`), and its `rule_counts` carry
   no `ANT.16_ii_ANT.4` (after: 0) with the private-plate group unchanged.
   The clamp is deliberately **not drawn** in the committed layout.
   Splitting the M3 trunks was rejected arithmetically: the ratio is per
   net, and a net keeps its whole Metal3 perimeter however the trunks are
   cut. Not drawn for the same reason as group 2: the WL pads (L41–L44,
   bench-driven inputs) are program-path pads whose bias record is
   unratified (`spec/run3-bench-plan.md` OPEN-B3; the proposed gate/well-
   drive benches hold WL at −3.3 V and −6.0 V), and the clamp is an
   n+/p-substrate junction over `VSS_ANALOG` — `diode_nd2ps_06v0`, **bv
   11 V** (`spec/hv-pad-protection-decision.md`), forward-conducting for
   any WL below the substrate. On silicon it would hold WL to roughly
   −0.6 … +11 V and sink bench current into the substrate beside the C3
   column, removing the negative-WL gate/well-drive axis by a layout edit.
   Per the #210 standard applied to the plate pads below, whether a
   junction may hang on a program pad is an operator decision, not a
   layout edit; the 29 shared-WL findings remain open.
2. **Private plates.** The signed-capacitor routing in #539 puts the private
   Metal5 pad on capacitor diffusion. The native antenna stage now reports
   zero private-plate markers across the 31 placed instances. The historical
   gate-connected layout had 26 thin-oxide and five thick-oxide private-plate
   markers. No diode was added to the program path.
3. **Die-level density — applies, fixed.** The gating density stage demands
   COMP ≥ 25 % (`DCF.1b`), Poly2 ≥ 14 % (`PL.8`), Metal1–5 ≥ 30 % each
   (`M1.4`/`M2.4`/`M3.4`/`M4.4`/`M5.4`) and MetalTop ≥ 30 % (`MT.3`; the
   11 K analogue of `MT30.7`). `M4.4`/`M5.4`/`MT.3` do not exist at the
   3LM variant the retired A-variant report ran — new at `gf180mcuD`, all
   satisfied by the fill (measured ratios above; deck log `SUCCESS`).
   The fill keeps off the cell columns (±25 µm bands), the pads, and the
   C3 n-well strip; dummy COMP at 30 µm squares (`COMP_FILL_SIZE_UM`; 1.9 µm
   gap ≥ `DCF.2b`, 3.5 µm to drawn COMP ≥ `DCF.4`); the dummy-Poly2 grid
   rides **inside** the dummy COMP squares on the
   drawing layer, because the deck's `DPF.1` — measured on a
   fully-enclosed-squares fixture (2026-11-18) — flags *every* `Poly2
   dummy` shape it sees, enclosed ones included, so no dummy-layer pattern
   can pass it while `PL.8` demands the coverage. The closest rule to its
   floor is `PL.8` (Poly2 15.69 % against 14 %, deck log; every other rule
   clears by ≥ 19 pp) — a later fill change should re-check that ratio
   first. The keep-outs above do not cover the 36 private-plate Metal5
   routes or the BL/WL/VB trunks outside the column bands: the floating
   dummy metal (no contact anywhere in the fill) parks 3 µm
   (`FILL_SPACING_UM`) off them on all five fill layers. Floating fill
   cannot inject DC into a sense node; the residual risk is capacitive
   (fringe coupling onto the fA-scale BL sense path), which the committed
   evidence does not quantify — flagged for the operator here rather than
   waived; a route keep-out is the fallback if the operator wants the
   coupling bounded in geometry.
4. **`CUP.2` — does not apply.** The precheck disables the `cup` deck in
   its KLayout DRC selection ("disable CUP for now", S2) and no separate
   stage runs it: `CUP.2` cannot gate the submission. (The rule's own text
   — "Minimum width of Metal3 line used for bond pads" — also does not
   describe a WL trunk nowhere near a pad opening.)
5. **`MT30.1a`–`MT30.8` (952 findings) — variant artifacts, corrected.**
   They live in the `metaltop_30k` deck, which loads only at
   `metal_top == '30K'` (variant A), where `top_metal` **is Metal3** — the
   deck was checking the 0.42 µm WL trunks against 30 K thick-metal rules.
   At the precheck's `gf180mcuD` the deck does not load; the 11 K metaltop
   rules check Metal5, which flagged 40 sub-minimum landing pads
   (`MT.1`, 0.44 µm floor) — fixed by the landing patches. The retired
   `drc_native_report.json` (variant A, `--deck-var decks=all,-mslot`, per
   #287) recorded all of this honestly at A; its `MT30.*`/`CUP.2` rows are
   answered here at the binding configuration, so the file is withdrawn
   rather than left reporting findings that no longer exist.

No finding is waived. The PCell-internal class (`CO.4`/`DF.6_MV`/
`PL.4_MV`, ratified exception, #338/#299) and `DBU`
(`2AMLogic/klayout-tools#5721`) stay out of scope as before.

### Manual check list (operator, pre-submission)

The GDS opens; pad names/positions match `pad_table.json` per the mapping
above (labelled pads carry their signal text on 81/10); the HV pads occupy the
bidirectional slots the floorplan reserves. The invention-firewall check and
the operator's chip-level checklist stay explicit operator steps.
