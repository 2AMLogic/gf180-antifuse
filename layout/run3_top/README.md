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

`cell_candidate2_Amin_G2x` has **no drawn cell** (#296 is the redraw;
#299 is the open operator ruling on whether Candidate 2's `nfet_10v0_asym`
PCell can be drawn at all). It is still emitted: access literals from
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
  built by this generator.
- No layout, pad ring, physical slot order or routing — #211.
- `klt lvs` is **not** run here and no pass is asserted: whether klt resolves
  this hierarchical `subckt-call` reference is first exercised at chip
  assembly (#211).
