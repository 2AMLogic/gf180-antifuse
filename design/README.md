# design/

Schematics (xschem) and the SPICE netlists derived from them.

## What is captured

1. The three antifuse cell candidates ratified in
   [`spec/cell-candidates.md`](../spec/cell-candidates.md) (below).
2. The N = 32 array, its row/column local high-voltage pass-gate stage and the
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
names its two geometry levels "process-minimum" and "2x-area", but no ratified
spec document fixes what the process-minimum legal geometry actually is — that
is a PDK design-rule lookup, deliberately out of scope for this first drop of
sources. Choosing those numbers is follow-on work; nothing in this directory
should be read as asserting them.

## The array and addressing stage

Emitted by [`gen_array.py`](gen_array.py) (checked in; a generator rather than
1024 hand-placed symbols), netlisted by xschem like everything else here, and
guarded by [`check-array.py`](check-array.py). The `.sch`/`.sym` files under
`array/` and `mux/` are **generated** - edit the generator, not them.

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

### Decisions made here that the spec leaves open (flagged, not ratified)

These are conventions of the generator, written down so they can be overruled
by a spec decision record rather than discovered later:

1. **Numeric "process-minimum" geometry is still not fixed anywhere.** "min"
   above is the PDK-symbol-template placeholder carried since the cell drop, so
   *no claim in this directory or in `sim/array-slice-bench/` is about the
   process-minimum device*.
2. **Phase and pitch of the two interleaved sub-axes.** The plan says
   "checkerboarded" and "orthogonal" without fixing a pattern. The generator
   uses (band-relative column c'): capacitor level `(r + c') mod 2`
   (cell-pitch checkerboard), access level `(r//2 + c'//2) mod 2` (2 x 2-block
   checkerboard). That is balanced (88/88/80 per sub-combination) and satisfies
   the stated properties; `check-array.py` enforces the *properties*, not this
   exact formula, so another conforming pattern needs only a generator change.
3. **Band axis = column.** The region table says columns; the prose defers
   row/column orientation to the architecture record. Columns are the band axis
   here, and rows are shared across bands, hence the per-(row, band) row stage.
4. **Per-band buses.** Each band has its own `BLG`/`PLG` bus and `VDDH` rail so
   each region's program conditions are independently settable (the plan's
   per-region nominal points). Where the program/read legs attach is out of
   scope (below).
5. **Level shifters/pass-gates for Region II use the 10 V asymmetric pair.**
   `spec/architecture.md` §1.1 names `nfet_06v0`/`pfet_06v0` "for the 6 V tier";
   the asymmetric pair for the 10 V tier is this repo's reading of that.
6. **Pass-gate drain/source (Candidate 2 band).** `pg_n10` wires `d` to the node
   that must be blocked against the elevated voltage while the gate is off: the
   global `BLG` bus for a column gate, the array-side `PL` for a row return gate.
   Same rationale as the cell's own assignment above.
7. **NMOS pass-gate passing a high bit line.** With `VDDH` equal to the
   programming rail an NMOS column gate passes at most `VDDH - Vth` (plus body
   effect). Whether the real programming rail needs a boosted gate rail is a
   program-leg/pulse decision; the bench holds `BLG` well below `VDDH`.
8. **Transistor sizes** in `ls_*` / `pg_*` are placeholders, not a sized design.

## What is explicitly NOT captured

- **Program leg** - ballast resistor, active current limit, `PROG_EN`/`READ_EN`
  interlock, and the `VPP` pad/switch. The per-band `BLG`/`PLG` buses are the
  attachment points; nothing is attached.
- **Sense path** - sense amplifier and read leg (separate issue).
- **SPI slave and the global decode** - register map, address decode, control
  logic. The digital partition is the *source* of `RSEL_<r>` / `CSEL_<c>`; the
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
| `netlists/*.spice` | **Derived.** xschem's netlist export (cells, level shifters, pass-gates, array, slices). Do not edit; regenerate. |
| `tb/tb_cell_candidateN.spice` | Elaboration / parameter-propagation decks for `check-netlists.sh`. Not evidence, not cornered. |
| `xschemrc` | Project xschem config: PDK library path, this repo's cells, `split_files`. |
| `regen-netlists.sh` | Runs `gen_array.py`, then regenerates `netlists/` from `cells/` and `array/`. `--check` diffs instead of writing. |
| `check-netlists.sh` | Runs all five checks below. |

## Working with these sources

Everything below needs `PDK_ROOT` pointing at the open_pdks / volare install
root that contains `gf180mcuD/`, plus `xschem` and `ngspice` on `PATH`. The
scripts honour `$PDK_ROOT` first and fall back to `~/.volare` when it is unset
or does not contain `gf180mcuD/`; each prints the root it resolved before
running.

Open a cell:

```sh
PDK_ROOT=$HOME/.volare xschem --rcfile design/xschemrc design/cells/cell_candidate1.sch
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

which asserts, in order:

1. **Reproducibility** — the generated array/mux sources are byte-identical to
   a fresh `gen_array.py` run, and a fresh xschem export of every cell, mux,
   array and slice schematic is byte-identical to the committed netlist. This is the T1 "regenerated on
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

### Two things worth knowing about the flow

- **Netlists are generated through `cells/cell_library.sch`, not from the cell
  schematics directly.** xschem emits `.subckt` parameter defaults only for a
  schematic netlisted as a sub-schematic; netlisting a cell at top level gives a
  bare `.subckt <name> <pins>` line, and ngspice then rejects any attempt to
  override `wcap` on the instance line ("Undefined parameter"). `cell_library.sch`
  instantiates one of each cell so that `split_files` writes one properly
  parameterized netlist per cell.
- **`regen-netlists.sh` normalizes two comment lines.** xschem stamps the
  absolute filesystem path of each schematic and symbol into `** sym_path:` /
  `** sch_path:` comments, which would make a committed netlist depend on where
  the repo is checked out. The script rewrites that prefix to a repo-relative
  path, and does nothing else to xschem's output — no circuit content is
  touched, and `--check` re-runs the identical pipeline.

Also note that xschem 3.4.7 exits `10` after batch-netlisting *any* hierarchical
schematic, including the PDK's own `libs.tech/xschem/tests/0_top.sch`. It is not
an error signal; `regen-netlists.sh` validates the emitted files instead.
