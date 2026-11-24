# design/

Schematics (xschem) and the SPICE netlists derived from them.

## What is captured

1. The three antifuse cell candidates ratified in
   [`spec/cell-candidates.md`](../spec/cell-candidates.md) (below).
2. The program leg and read leg of
   [`spec/architecture.md`](../spec/architecture.md) §1.2, §2 and §4 (see
   "Program leg and read leg" below).
3. The N = 32 array, its row/column local high-voltage pass-gate stage and the
   level shifters of [`spec/architecture.md`](../spec/architecture.md) §1.1,
   generated from the region map in
   [`spec/split-axis-plan.md`](../spec/split-axis-plan.md) (see "The array and
   addressing stage" below).

Nothing else.

### The cell candidates

Each is the two-device series pair that record specifies — the MOS-capacitor
antifuse element plus the access/isolation device that gates the programming
current:

| Candidate | Schematic | Capacitor | Access device |
|---|---|---|---|
| 1 — baseline | [`cells/cell_candidate1.sch`](cells/cell_candidate1.sch) | `cap_nmos_03v3` (3.3 V thin oxide) | `nfet_06v0` (6.0 V thick oxide) |
| 2 — high-voltage | [`cells/cell_candidate2.sch`](cells/cell_candidate2.sch) | `cap_nmos_06v0` (6.0 V thick oxide) | `nfet_10v0_asym` (10 V LDNMOS) |
| 3 — polarity | [`cells/cell_candidate3.sch`](cells/cell_candidate3.sch) | `cap_pmos_03v3` (3.3 V thin oxide) | `pfet_06v0` (6.0 V thick oxide) |

### Cell interface

All three cells present the same four terminals, in this order:

| Port | Meaning |
|---|---|
| `BL` | Bit line. The array-side node: the program-voltage rail during a program pulse, the sense node during a read. |
| `WL` | Word line. The access device's gate. |
| `PL` | Plate line. The capacitor's body/well plate — the program return. |
| `VB` | The access device's bulk tie (p-substrate for Candidates 1 and 2, n-well for Candidate 3). |

`CN`, the internal cell node, is the capacitor's gate plate. It is reachable
from `BL` only through the access device, which is what isolates an
unselected cell's capacitor from a shared bit line.

Which array rails `PL` and `VB` tie to is an array-level decision, made in
"The array and addressing stage" below.

### Access-device source/drain assignment

The array/program-supply side terminal is, in every candidate, the one that
sits at the higher potential during a program pulse: the **drain** for an NMOS
access device, the **source** for a PMOS one. So `BL` wires to `M1`'s drain in
Candidates 1 and 2, and to `M1`'s source in Candidate 3.

For Candidates 1 and 3 that is a drawing convention only — `spec/cell-candidates.md`
records `nfet_06v0` / `pfet_06v0` as symmetric-drain/source devices.

**For Candidate 2 it is a real electrical decision, and it is made
deliberately here.** `spec/cell-candidates.md` flags `nfet_10v0_asym` as an
asymmetric drain-extended LDNMOS whose "array-side and program-supply-side
connections must be assigned deliberately when this device is used as an
access device, not left to symmetric pass-gate assumptions." The assignment
made is **drain → `BL`, source → `CN`**, on this basis, read out of the PDK
subcircuit in `libs.tech/ngspice/smbb000149.ngspice`:

- the drift resistance `rdrift` is in series with the `d` terminal only; the
  `s` terminal connects straight to the BSIM4 core device;
- the default diffusion parasitics are asymmetric in the same direction —
  `ad = W*1.48u` on the drain side against `as = W*0.48u` on the source side.

The drain is therefore the terminal built to stand off the elevated voltage,
so it faces `BL` — the bit line that sits at the program-supply rail during a
program pulse, and that an *unselected* cell in the same column must also
block. The rationale is repeated on-canvas in `cells/cell_candidate2.sch` so it
travels with the schematic. See also `spec/split-axis-plan.md`, which is what
puts this device in its own contiguous grid band rather than interleaving it.

### Capacitor geometry is a parameter, not a number

Each cell netlists as a parameterized subcircuit:

```
.subckt cell_candidate1 BL WL PL VB  wcap=1e-6 lcap=1e-6 wacc=0.30u lacc=0.70u
```

`wcap` / `lcap` are the capacitor's width and length, and `wacc` / `lacc` the
access device's — the two geometry split axes `spec/split-axis-plan.md`
requires at two levels each within every grid region. The array
instantiates the same cell source at several geometry levels by overriding
them per instance; no cell schematic edit is involved.

**The defaults above are placeholders, not design values.** They are the PDK
symbol template defaults, carried through verbatim. `spec/split-axis-plan.md`
names its two geometry levels "process-minimum" and "2x-area". For the
capacitor half those numbers are now fixed by
[`spec/capacitor-geometry-decision.md`](../spec/capacitor-geometry-decision.md)
(1.0 x 0.28 um / 2.0 x 0.28 um thin-oxide, 1.0 x 0.70 um / 2.0 x 0.70 um
6 V) — regenerating `design/` against them is authorised but not yet
performed, so the instances below still carry the placeholder values. The
access half (`wacc`/`lacc`) remains a PDK design-rule lookup, deliberately
out of scope for this first drop of sources; choosing those numbers is
follow-on work, and nothing in this directory should be read as asserting
either half's final values.

## Program leg and read leg

Added for the analog partition `spec/architecture.md` §1.2, §2 and §4 specify
but did not design. Rationale, the ballast sizing inequality and the
`ppolyf_u_2k_6p0` rating finding are in
[`spec/leg-design-record.md`](../spec/leg-design-record.md).

| Block | Schematic | Ports | Content |
|---|---|---|---|
| `leg_interlock` | [`cells/leg_interlock.sch`](cells/leg_interlock.sch) | `PROG_EN READ_EN VDD VSS PON RON` | Static CMOS: `PON = PROG_EN & ~READ_EN`, `RON = READ_EN & ~PROG_EN`. Both 0 when both enables are 1. |
| `program_leg` | [`cells/program_leg.sch`](cells/program_leg.sch) | `PROG_EN READ_EN VDD VSS BL VPP` | `VPP` -> `pfet_06v0` switch (VPP-referenced cross-coupled level shifter) -> `ppolyf_u_2k_6p0` ballast -> `BL`. |
| `read_leg` | [`cells/read_leg.sch`](cells/read_leg.sch) | `PROG_EN READ_EN VCLAMP IREF VDD VSS BL SENSE RDATA` | `BL` - `nfet_06v0` isolation switch - `nfet_03v3` clamp - `pfet_03v3` mirror vs `I_ref` mirror -> `SENSE` -> two inverters -> `RDATA`. |

Both legs instantiate `leg_interlock`, so a fault that asserts `PROG_EN` and
`READ_EN` together leaves both legs OFF at the shared bit line. Sizes are
subcircuit parameters (defaults on each `.sym`); `rb_w` / `rb_l` set the
ballast. Two interface constraints to honour upstream: `VPP` must idle at or
above `VDD` while the program leg is OFF, and the program leg is a 6 V-tier
design (no Candidate 2 / 10 V variant yet).

**These three schematics are generated**, by
[`tools/gen_leg_schematics.py`](tools/gen_leg_schematics.py): it holds the
net list once and, through the shared emitter `tools/xschem_emit.py`, computes every pin coordinate from the PDK
symbols, which a hand-typed `.sch` would have to do by eye. The output is an
ordinary xschem schematic and `regen-netlists.sh` derives the netlists from it
exactly as for the cells; edit in xschem and stop using the script, or edit
the script and re-run it -- but not both. The script does not draw wires (pins
connect by label), so the canvas is a connectivity diagram, not a laid-out
drawing.

`cells/leg_library.sch` is the netlist driver for these three blocks (same
purpose as `cell_library.sch`).

## The array and addressing stage

Emitted by [`gen_array.py`](gen_array.py) (checked in; a generator rather than
1024 hand-placed symbols), netlisted through `klt netlist` like everything else
here, and guarded by [`check-array.py`](check-array.py). The `.sch`/`.sym` files
under `array/` and `mux/` are **generated** - edit the generator, not them.

### Structure

| Piece | Source | Notes |
|---|---|---|
| `array_32x32` | `array/array_32x32.sch` | 1024 cell instances `Xc_<row>_<col>`, plus the addressing stage. Ports: `RSEL_<r>` / `CSEL_<c>` (single-ended one-hot selects from the digital partition), per-band buses `BLG_<band>` / `PLG_<band>`, per-band level-shifter rails `VDDH_<band>`, `VDDL`, `VSS`. |
| `slice_i_ii`, `slice_ii_iii` | `array/slice_*.sch` | Reduced 4 x 4 slices (rows 0-3; columns 9-12 straddling Region I\|II, columns 20-23 straddling II\|III) from the **same generator at the same absolute (row, column)**, so their cells are the full array's cells. Used by the bench in `sim/array-slice-bench/`. |
| `ls_hv06` / `ls_hv10` | `mux/ls_hv06.sch`, `mux/ls_hv10.sch` | Level shifter: 3.3 V thin-oxide inverter in the `VDDL` domain, then a cross-coupled PMOS latch with NMOS pull-downs on `VDDH`. Both outputs driven at all times (`spec/architecture.md` §3 item 1). `06` = `nfet_06v0`/`pfet_06v0`; `10` = `nfet_10v0_asym`/`pfet_10v0_asym`. |
| `pg_n06` / `pg_n10` | `mux/pg_n06.sch`, `mux/pg_n10.sch` | Local HV pass-gate: one `nfet_06v0` / `nfet_10v0_asym`. |

Per column: one level shifter + one pass-gate between the band's `BLG` bus and
the column bit line `BL_<c>`. Per **(row, band)** segment: one level shifter
driving the word line `WL_<r>_<band>` and one pass-gate between the cells' plate
line `PL_<r>_<band>` and the band's return bus `PLG_<band>`. A cell is selected
only when both its column pass-gate and its row segment are enabled; every other
select is driven (not floated) to its OFF level. The pass-gate/level-shifter
family is a per-band choice (`06` for Candidate 1/3 bands, `10`/asymmetric for
Candidate 2), as `spec/architecture.md` §1.1 requires.

Candidate 3 (PMOS access) is the mirror: its word line is active-low (taken from
the level shifter's complement output) and its cell `VB` (n-well) ties to the
band's `VDDH` rail. Candidates 1 and 2 tie `VB` to `VSS`.

### Region map in the generated cells

Candidate type comes from the ratified region map: columns 0-10 Candidate 1,
11-21 Candidate 2, 22-31 Candidate 3, all 32 rows. Per cell, `wcap`/`lcap`/
`wacc`/`lacc` take two levels per axis per band:

* **"min"** = the committed cell subcircuit's own parameter default (read from
  `netlists/cell_candidateN.spice`);
* **capacitor "2x"** = 2x `wcap` at the same `lcap` (2x area); **access "2x"** =
  2x `wacc` at the same `lacc` (width only - which is also all
  `spec/split-axis-plan.md` allows Region II).

`check-array.py` re-reads the region-map table out of `spec/split-axis-plan.md`
and fails if the generated netlists disagree with it (candidate type per cell,
the two levels per axis, a checkerboarded capacitor axis, an interleaved access
axis, all four level combinations present and evenly populated, 352/352/320
cells), if a slice differs from the same cells of the full array, and if the
Candidate 1/2/3 access-device orientation is not drain-to-BL / drain-to-BL /
source-to-BL.

### PROVISIONAL resolutions — open items for the operator

The ratified specs are ambiguous or silent on five points below. The
generator fixes a working convention so the sources stay buildable, marks
each one **PROVISIONAL** in the generated sources (`design/array/`,
`design/mux/`), and lists each here as a numbered open item for the
operator. None is decided in ratified text; overrule any of them in a spec
decision record and the generator + netlists regenerate.

1. **(a) Numeric "process-minimum" geometry — placeholder numbers.**
   Resolution: "min" is the committed cell subcircuit's own parameter
   default (the PDK symbol template placeholder carried since the cell
   drop); "2x" doubles `wcap` (2x area at fixed `lcap`) or `wacc`
   (fixed `lacc`). *No claim in this directory or in
   `sim/array-slice-bench/` is about the process-minimum device.*
   Alternative: fix the true process-minimum legal geometry from the PDK
   design rules, and (separately) whether "2x-area" means width-doubling,
   L-doubling, or both.
   Consequence: every cell instance's `wcap`/`lcap`/`wacc`/`lacc`
   re-scales, and the recorded bench numbers (path efficiency, isolation,
   leakage) scale with them — current results remain valid as structure
   evidence only; a re-run mints a new append-only record.
   **Decided (capacitor half), 2026-11-15**: fixed by
   [`spec/capacitor-geometry-decision.md`](../spec/capacitor-geometry-decision.md)
   — Minimum `wcap` x `lcap` = 1.0 x 0.28 um (`cap_nmos_03v3` /
   `cap_pmos_03v3`) and 1.0 x 0.70 um (`cap_nmos_06v0`); "2x" doubles
   `wcap` only. Decided in spec but not yet conformed: the committed
   sources here still carry the placeholder defaults until the authorised
   regeneration lands (scoped by closed #292, tracked by this open item);
   the drawn cells no longer wait — #296 redrew all seven at these levels
   (2026-11-17). Measured state: every
   drawn-vs-simulated divergence this placeholder numbering currently
   implies is recorded in
   [`geometry-basis.json`](geometry-basis.json) (validated by check 7,
   `check-geometry-basis.py`) with a per-entry `owner`/`status` derived
   from the ratified levels — drawn side stale → #296, simulated side
   stale → this item, both → both; the access half (`wacc`/`lacc`)
   remains PROVISIONAL (the section-3 axis) and stays `unresolved` there.

2. **(b) Phase and pitch of the two interleaved sub-axes.**
   Resolution: the plan says "checkerboarded" and "orthogonal" without
   fixing a pattern. The generator uses (band-relative column c'):
   capacitor level `(r + c') mod 2` (cell-pitch checkerboard), access
   level `(r//2 + c'//2) mod 2` (2×2-block checkerboard).
   Alternative: any conforming pattern — e.g. absolute (not band-relative)
   phase, or a different interleave pitch.
   Consequence: `check-array.py` enforces the *properties* (checkerboarded,
   orthogonal, balanced 88/88/80), not this formula, so another conforming
   pattern needs only a generator change + regenerate; per-cell geometry
   assignments move, per-region distributions and the balance do not.

3. **(c) Band axis = column; per-(row, band) row stage; per-band buses.**
   Resolution: the region table bands columns; rows span all three bands,
   so the row stage (level shifter + return pass-gate + word line) is
   instantiated per (row, band) segment, and each band has its own
   `BLG`/`PLG` bus and `VDDH` rail so each region's program conditions are
   independently settable (the plan's per-region nominal points).
   Alternative: rows as the band axis (the prose defers orientation to the
   architecture record); or shared global buses instead of per-band ones.
   Consequence: transposing the axis re-assigns every cell's candidate —
   `check-array.py` re-reads the ratified region table, so that requires a
   spec decision record, not just a generator edit; merging the buses
   couples the regions' programming conditions and removes the per-region
   split the measurement matrix depends on.

4. **(d) Region II level shifters / pass-gates use the 10 V asymmetric
   pair.**
   Resolution: `spec/architecture.md` §1.1 names `nfet_06v0`/`pfet_06v0`
   "for the 6 V tier" and says nothing about the 10 V tier; the generator
   uses `nfet_10v0_asym`/`pfet_10v0_asym` for Candidate 2's band, with the
   same deliberate drain-to-high-swing assignment as the Candidate 2 cell.
   Alternative: 6 V symmetric devices in all tiers (if the Region II rail
   stays within the 6 V SOA), or a different 10 V family.
   Consequence: the family sets Region II's standby leakage and isolation
   numbers and forces the d/s orientation rule; ruling 6 V devices instead
   collapses `ls_hv10`/`pg_n10` onto the 06 family with symmetric d/s and
   re-runs the Region II slice evidence.

5. **(e) NMOS pass-gate gate rail = VDDH.**
   Resolution: the pass-gate gate is driven by the level shifter whose
   rail is the band's `VDDH`, so with `VDDH` at the programming rail an
   NMOS column gate passes at most `VDDH − Vth` (plus body effect). The
   bench holds `BLG` 2 V below `VDDH` for exactly this reason.
   Alternative: a boosted gate rail above `VDDH` (charge pump / second
   rail), or transmission-gate (CMOS) pass-gates.
   Consequence: the program leg must either budget `Vth` + body-effect
   headroom into the pulse plan or land the boosted-rail decision first;
   the measured Region I idle-bus miss is placeholder-size leakage of
   these NMOS gates and moves with that family/sizing decision.

Other flagged conventions (not operator-open): the `pg_n10` drain/source
assignment (forced by the same PDK device asymmetry as the ratified
Candidate 2 cell record), and the `ls_*`/`pg_*` transistor sizes
(placeholders, not a sized design).

## What is explicitly NOT captured

- **Attachment of the legs to the array.** The program leg and read leg
  (above) are standalone blocks; nothing connects them to the per-band
  `BLG`/`PLG` buses yet, and the active compliance limit (the WL-bias second
  limit of `spec/architecture.md` §2, owned by the WL level shifter) and on-die
  `I_ref` generation are not designed.
- **SPI slave, gate level and the global decode** - the register map and
  sequencer RTL is captured (item 4 above); the synthesized netlist and the
  physical decode are not. The digital partition is the *source* of `RSEL_<r>` / `CSEL_<c>`; the
  level shifters here are the first analog stage.
- **Anything sized or timed.** No transistor in the addressing stage has been
  sized against a corner; the bench shows the structure conducts and isolates at
  placeholder sizes, not that it is correctly designed.
- **Post-breakdown behaviour.** No stock SPICE model exists
  (`spec/cell-candidates.md`); the bench uses a bench-only filament stand-in.
- Layout, DRC/LVS (`layout/`).

Corner sims, Monte Carlo programming-yield curves and read-margin work belong
in `sim/` as append-only evidence, per `CLAUDE.md`. The decks under `tb/` and
step 5 of `check-netlists.sh` are build-time checks on the netlists, not
evidence — see below. The cornered per-region bench for the array slices is
[`sim/array-slice-bench/`](../sim/array-slice-bench/README.md).

## Layout of this directory

| Path | What it is |
|---|---|
| `cells/cell_candidateN.sch` / `.sym` | The cell schematics and their symbols. |
| `cells/cell_library.sch` | Netlist driver, not a circuit — see its header comment. |
| `gen_array.py` | **Generator** for everything under `array/` and `mux/` (schematics, symbols, driver). `--check` diffs instead of writing. |
| `array/`, `mux/` | **Generated** xschem sources: the 32x32 array, the two slices, level shifters, pass-gates, and `array/array_library.sch` (netlist driver). |
| `check-array.py` | Region-map drift check (see above). stdlib only. |
| `check-geometry-basis.py` | Drawn-vs-simulated geometry-basis check (check 7 below; issue #292). stdlib only; validates `geometry-basis.json`. |
| `geometry-basis.json` | The acknowledged drawn-vs-simulated divergence record that `check-geometry-basis.py` validates (issue #292). |
| `cells/{leg_interlock,program_leg,read_leg}.sch` / `.sym` | Program-leg / read-leg blocks (generated, see above). |
| `cells/leg_library.sch` | Netlist driver for the leg blocks. |
| `tools/gen_leg_schematics.py` | Generator for the leg schematics and symbols. `--check` diffs instead of writing. |
| `tools/xschem_emit.py` | Shared xschem emission helpers (`Sch`, MOS attribute templates, PDK pin offsets, symbol drawing) used by both generators. |
| `tb/tb_legs.spice` | Leg elaboration + interlock truth-table deck for `check-netlists.sh`. |
| `netlists/*.spice` | **Derived.** xschem's netlist export (cells, level shifters, pass-gates, array, slices). Do not edit; regenerate. |
| `tb/tb_cell_candidateN.spice` | Elaboration / parameter-propagation decks for `check-netlists.sh`. Not evidence, not cornered. |
| `breakdown/` | Behavioral breakdown-augmented wrappers `cell_candidateN_bd` around the unmodified netlists, plus the labelled-parameter file. Hand-written, not derived; see [`breakdown/README.md`](breakdown/README.md). |
| `xschemrc` | Project xschem config: PDK library path, this repo's cells, `split_files`. |
| `regen-netlists.sh` | Runs `gen_array.py` and `tools/gen_leg_schematics.py`, then regenerates `netlists/` from `cells/` and `array/`. `--check` diffs instead of writing. |
| `check-netlists.sh` | Runs all seven checks below. |

## Working with these sources

Everything below needs `PDK_ROOT` pointing at the open_pdks / ciel install
root that contains `gf180mcuD/`, plus `klt` (klayout-tools) and `ngspice` on
`PATH`. Netlist exports go through `klt netlist`, which owns the xschem
invocation (nothing here calls `xschem` directly; `klt` still resolves
`xschem` on `PATH` as its backend). The exports need a `klt` whose
`klt netlist` has `--output-dir` split-output delivery — added after
klayout-tools v0.9.2 by 2AMLogic/klayout-tools#7147. The
scripts honour `$PDK_ROOT` first and fall back to `~/.ciel` when it is unset
or does not contain `gf180mcuD/`; each prints the root it resolved before
running. They also read `<root>/gf180mcuD/SOURCES` and refuse a tree
whose `open_pdks` hash is not the pin in `design/lib-pdk-root.sh`.

Open a cell:

```sh
PDK_ROOT=$HOME/.ciel xschem --rcfile design/xschemrc design/cells/cell_candidate1.sch
```

Regenerate the derived netlists after any schematic change, and commit the
result alongside the schematic:

```sh
design/regen-netlists.sh
```

Check everything:

```sh
design/check-netlists.sh
```

Check everything except netlist reproducibility (needs `ngspice` and the
pinned PDK, but no `klt`/`xschem`; the lightest entry point):

```sh
design/run_analog_cold_start.sh
```

It runs `check-netlists.sh --skip-regen`, which skips step 1 below (including
the generator `--check` runs inside `regen-netlists.sh`) and prints
`== 1. netlist reproducibility == SKIPPED (--skip-regen)` so the log never
implies it ran. Steps 2-7 are unchanged; it ends with
`ANALOG COLD START PASSED` or `FAILED`. Typical corner, elaboration and
mechanism only: not a result. With the step-1 exports now going through
`klt netlist` (bounded, real exit status, no raw xschem), the full
`check-netlists.sh` is itself safe to run on a worker; `--skip-regen` remains
for hosts without `klt`, not because step 1 is unsafe to automate.

which asserts, in order:

1. **Reproducibility** — the generated array/mux sources are byte-identical to
   a fresh `gen_array.py` run, and a fresh `klt netlist` export of every cell,
   mux, array and slice schematic is byte-identical to the committed netlist.
   This is the T1 "regenerated on
   design change" pass condition: the netlists are a derived artifact kept in
   sync, not a one-off drop.
2. **Elaboration** — each committed netlist elaborates cleanly in ngspice
   against the pinned PDK model files (`sm141064.ngspice` for all three cells'
   capacitors and the 6 V devices; `smbb000149.ngspice` additionally for
   Candidate 2's `nfet_10v0_asym`).
3. **Geometry parameter sweep** — each cell is elaborated at a base capacitor
   geometry and at 2x area, changing nothing but the injected parameter values,
   and the capacitor branch current must scale by exactly 2x. That is what
   proves `wcap` / `lcap` actually reach the device instance rather than being
   decorative. The two levels used are an arbitrary mechanism check, *not* the
   split-axis levels — see "Capacitor geometry is a parameter" above.
4. **Region-map drift** — `check-array.py` (above): generated per-cell
   candidate type and `wcap`/`lcap`/`wacc`/`lacc` match the region map re-read
   from `spec/split-axis-plan.md`; fails on any drift.
5. **Slice smoke** — the two slice netlists elaborate in ngspice at the typical
   corner; with one cell selected it conducts through its filament stand-in and
   every other cell does not. Typical corner only: not a result.
6. **Program leg / read leg** — the three leg netlists elaborate (with the
   `res_typical` section for the ballast) and `leg_interlock`'s truth table
   holds at the typical corner. Structure only; the PVT mutual-exclusion and
   margin benches are in `sim/program-read-legs/`.
7. **Geometry basis** — `check-geometry-basis.py` (above; issue #292): the
   drawn bitcell geometry (the `XM1`/`XC1` literals in
   `layout/cell_*/lvs_reference.spice`) against the geometry the committed
   SPICE evidence was run at (the `netlists/cell_candidateN.spice` `.subckt`
   defaults and the 2x split levels derived from them the same way check 4
   derives them). Every divergence must be recorded in
   [`geometry-basis.json`](geometry-basis.json) with both numbers, their
   ratio, a status and an owning issue; a recorded entry whose numbers no
   longer match the tree fails too, so the record cannot go silently stale.
   Needs no ngspice, PDK or `klt`. Green means the divergences are
   acknowledged and owned — **not** that the two worlds agree: a within-axis
   *relative* claim (exactly 2x per axis in both worlds) is unaffected, an
   *absolute* claim is not.

### Two things worth knowing about the flow

- **Netlists are generated through `cells/cell_library.sch`, not from the cell
  schematics directly.** xschem emits `.subckt` parameter defaults only for a
  schematic netlisted as a sub-schematic; netlisting a cell at top level gives a
  bare `.subckt <name> <pins>` line, and ngspice then rejects any attempt to
  override `wcap` on the instance line ("Undefined parameter"). `cell_library.sch`
  instantiates one of each cell so that `split_files` writes one properly
  parameterized netlist per cell.
- **`regen-netlists.sh` also joins `+` continuation lines.** xschem 3.4.4
  and 3.4.7 wrap long device lines at different columns (pure formatting), so
  a netlist exported on one failed `--check` against the other. Continuation
  lines are now joined onto their parent line, making the committed text
  independent of the xschem version (the three cell netlists were re-committed
  unwrapped; no circuit content changed).
- **`regen-netlists.sh` normalizes two comment lines.** xschem stamps the
  absolute filesystem path of each schematic and symbol into `** sym_path:` /
  `** sch_path:` comments, which would make a committed netlist depend on where
  the repo is checked out. The script rewrites that prefix to a repo-relative
  path, and does nothing else to xschem's output — no circuit content is
  touched, and `--check` re-runs the identical pipeline.

Also note that xschem 3.4.7 exits `10` after batch-netlisting *any* hierarchical
schematic, including the PDK's own `libs.tech/xschem/tests/0_top.sch`. It is
not an error signal: `klt netlist` judges the run by the emitted netlist, and
`regen-netlists.sh` additionally validates each expected split file by name.
