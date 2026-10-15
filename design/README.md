# design/

Schematics (xschem) and the SPICE netlists derived from them.

## What is captured

The three antifuse cell candidates ratified in
[`spec/cell-candidates.md`](../spec/cell-candidates.md), plus the program and
read legs described under "Program leg and read leg" below. Each cell is the two-device series pair that record specifies — the MOS-capacitor
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

Which array rails `PL` and `VB` actually tie to is an array-level decision and
is deferred with the rest of the array (below).

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
requires at two levels each within every grid region. Later array work
instantiates the same cell source at several geometry levels by overriding
them per instance; no schematic edit is involved.

**The defaults above are placeholders, not design values.** They are the PDK
symbol template defaults, carried through verbatim. `spec/split-axis-plan.md`
names its two geometry levels "process-minimum" and "2x-area", but no ratified
spec document fixes what the process-minimum legal geometry actually is — that
is a PDK design-rule lookup, deliberately out of scope for this first drop of
sources. Choosing those numbers is follow-on work; nothing in this directory
should be read as asserting them.

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
device table and net list once and computes every pin coordinate from the PDK
symbols, which a hand-typed `.sch` would have to do by eye. The output is an
ordinary xschem schematic and `regen-netlists.sh` derives the netlists from it
exactly as for the cells; edit in xschem and stop using the script, or edit
the script and re-run it -- but not both. The script does not draw wires (pins
connect by label), so the canvas is a connectivity diagram, not a laid-out
drawing.

`cells/leg_library.sch` is the netlist driver for these three blocks (same
purpose as `cell_library.sch`).

## What is explicitly deferred

Not captured here, and deliberately so:

- **Array top level** — the N×N grid, and the region banding from
  `spec/split-axis-plan.md`.
- **Row/column MUX** — decode, high-voltage pass-gate stage, level shifters.
- **SPI slave** — register map, address decode, control logic.
- **Active compliance limit** — the WL-bias second limit of
  `spec/architecture.md` §2 (owned by the WL level shifter above, not by the
  program leg).
- **On-die `I_ref` generation** — the read leg takes `I_ref` as a bench pin.

(The program leg's ballast and the read leg's sense amplifier are no longer
deferred: see "Program leg and read leg" below.)

`spec/architecture.md` specifies each of those at the block/interface level
only, and says so explicitly: "this record specifies the block and its
interface, not a transistor-level netlist — that is `design/`'s job." Turning
them into schematics is itself unresolved transistor-level design, so each
becomes its own increment once it has enough resolved detail to be
schematic-capture-ready.

Also out of scope for this directory: layout, DRC/LVS (`layout/`), and any
simulation result. Corner sims, Monte Carlo programming-yield curves and
read-margin work belong in `sim/` as append-only evidence, per `CLAUDE.md`.
The decks under `tb/` are build-time checks on the netlists, not evidence —
see below.

## Layout of this directory

| Path | What it is |
|---|---|
| `cells/cell_candidateN.sch` / `.sym` | The cell schematics and their symbols. |
| `cells/cell_library.sch` | Netlist driver, not a circuit — see its header comment. |
| `cells/{leg_interlock,program_leg,read_leg}.sch` / `.sym` | Program-leg / read-leg blocks (generated, see above). |
| `cells/leg_library.sch` | Netlist driver for the leg blocks. |
| `tools/gen_leg_schematics.py` | Generator for the leg schematics and symbols. |
| `tb/tb_legs.spice` | Leg elaboration + interlock truth-table deck for `check-netlists.sh`. |
| `netlists/cell_candidateN.spice` | **Derived.** xschem's netlist export. Do not edit; regenerate. |
| `tb/tb_cell_candidateN.spice` | Elaboration / parameter-propagation decks for `check-netlists.sh`. Not evidence, not cornered. |
| `breakdown/` | Behavioral breakdown-augmented wrappers `cell_candidateN_bd` around the unmodified netlists, plus the labelled-parameter file. Hand-written, not derived; see [`breakdown/README.md`](breakdown/README.md). |
| `xschemrc` | Project xschem config: PDK library path, this repo's cells, `split_files`. |
| `regen-netlists.sh` | Regenerates `netlists/` from `cells/`. `--check` diffs instead of writing. |
| `check-netlists.sh` | Runs all three checks below. |

## Working with these sources

Everything below needs `PDK_ROOT` pointing at the open_pdks / ciel install
root that contains `gf180mcuD/`, plus `xschem` and `ngspice` on `PATH`. The
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

which asserts, in order:

1. **Reproducibility** — a fresh xschem export of every cell schematic is
   byte-identical to the committed netlist. This is the T1 "regenerated on
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
4. **Program leg / read leg** — the three leg netlists elaborate (with the
   `res_typical` section for the ballast) and `leg_interlock`'s truth table
   holds at the typical corner. Structure only; the PVT mutual-exclusion and
   margin benches are in `sim/program-read-legs/`.

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
schematic, including the PDK's own `libs.tech/xschem/tests/0_top.sch`. It is not
an error signal; `regen-netlists.sh` validates the emitted files instead.
