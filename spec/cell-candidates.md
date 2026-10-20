# Decision Record: Antifuse Cell Candidates

**Status**: Ratified
**Date**: 2026-08-20
**Scope**: Sub-issue A of the decomposition of #1 — cell candidate survey and
selection only. Grid size / split-axis plan, program/read architecture, and
the on-die-vs-off-die programming-supply decision are separate decision
records that build on the candidates ratified here.

## Context

Per `CLAUDE.md`, the cell is a thin-oxide MOS capacitor programmed by
gate-oxide breakdown, behind a thick-oxide access/isolation device rated for
the programming voltage. gf180mcu's dual gate-oxide device set (3.3 V thin
oxide, 5/6/10 V thick oxide) is what makes that pairing possible on this PDK:
the capacitor plate uses the thinner, lower-breakdown oxide flavor as the
programmable element, while the series device gating the programming current
uses a thicker-oxide flavor so it survives the elevated voltage without
becoming a second, unintended fuse.

This record selects 2–3 candidate cell variants from the devices gf180mcu
actually offers, states each candidate's expected programming voltage
regime, and records what is and is not known about post-breakdown behavior
in the stock PDK models — the last point gates whether Monte Carlo
programming-yield simulation is possible with stock models alone (relevant
to the program/read architecture record that follows this one).

## Method

Device inventory and SPICE model presence were verified directly against
the locally checked-out PDK rather than assumed from prior notes:

```
$ klt pdk list
root: /home/ubuntu/.volare  (search root: ~/.volare)
  gf180mcuD  open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b
  ...

$ find -L ~/.volare/gf180mcuD/libs.tech/xschem/symbols -iname "*.sym"
```

All device names cited below have a corresponding `.sym` file at that path
and a corresponding `.subckt`/`.model` in
`~/.volare/gf180mcuD/libs.tech/ngspice/sm141064.ngspice` (the 10 V
LDMOS/LDPMOS models live in the adjacent
`~/.volare/gf180mcuD/libs.tech/ngspice/smbb000149.ngspice`), checked
2026-08-20 against `open_pdks` commit `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
Re-verify against whatever PDK version is actually checked out before relying
on these names, since PDK/tooling versions can drift.

*Re-pin (2026-10-15):* the forward-looking pin is now open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (fetched with ciel 2.6.1, `~/.ciel`); the 2026-08-20 check above
was against `c6d73a3…` and is not re-dated. See [`pdk-pin-decision.md`](pdk-pin-decision.md).

### Verified MOS-capacitor (antifuse element) devices

| Symbol | Oxide | Pins | Notes |
|---|---|---|---|
| `cap_nmos_03v3` | 3.3 V thin (`toxe = 8e-9 m`, from `nfet_03v3.0` model bin) | G, B (2-terminal) | Baseline thin-oxide NMOS moscap |
| `cap_nmos_03v3_b` | 3.3 V thin | G, B | Same pinout as above; SPICE model (`sm141064.ngspice`) uses different C–V tanh-fit coefficients (`cvar1..4`) than the plain variant, implying a different well/isolation configuration. The PDK device docs that would confirm the exact structural difference are not covered by this survey — flagged as an open question below, not assumed. |
| `cap_pmos_03v3` | 3.3 V thin | G, B | PMOS polarity counterpart to `cap_nmos_03v3` |
| `cap_pmos_03v3_b` | 3.3 V thin | G, B | Body-tap PMOS variant, same caveat as `cap_nmos_03v3_b` |
| `cap_nmos_06v0` | 6.0 V thick (`toxe = 1.52e-8 m` on the `nfet_06v0.0` model bin; `pfet_06v0` is comparable at `toxe = 1.56e-8 m`) | G, B | Thick-oxide NMOS moscap — roughly 2x the physical oxide thickness of the 3.3 V devices |
| `cap_nmos_06v0_b` | 6.0 V thick | G, B | Body-tap variant |
| `cap_pmos_06v0` | 6.0 V thick | G, B | PMOS polarity counterpart |
| `cap_pmos_06v0_b` | 6.0 V thick | G, B | Body-tap variant |

### Verified access/isolation (series-device) candidates

| Symbol | Rating | Notes |
|---|---|---|
| `nfet_06v0` / `pfet_06v0` | 6.0 V, thick oxide (`toxe = 1.52e-8`/`1.56e-8 m`) | Standard thick-oxide logic device, symmetric source/drain — usable as a bidirectional pass device |
| `nfet_10v0_asym` / `pfet_10v0_asym` | 10 V, from a dedicated HV process module (`smbb000149.ngspice`, document `SM-BB-000149`, "0.18um MCU 10V high voltage process") | BSIM4-based **LDNMOS/LDPMOS** ("asym" = asymmetric drain/source construction, drain-extended for high-voltage blocking). Highest-voltage access option found, but the asymmetric construction means source and drain are not interchangeable the way they are on `nfet_06v0`/`pfet_06v0` — the array-side and program-supply-side connections must be assigned deliberately when this device is used as an access device, not left to symmetric pass-gate assumptions. That assignment is an array/layout-stage decision, out of scope here. |

Full oxide-flavor family present for completeness (not all used below):
`nfet_03v3`/`pfet_03v3` (3.3 V), `nfet_05v0`/`pfet_05v0` (5.0 V, `nfet_05v0`
documented in the model file as electrically identical to `nfet_06v0` with a
shorter minimum gate length), `nfet_06v0`/`pfet_06v0` (6.0 V),
`nfet_06v0_nvt` (6.0 V native/high-Vt, NMOS only — no PMOS counterpart was
found), `nfet_10v0_asym`/`pfet_10v0_asym` (10 V asymmetric).

### Post-breakdown model behavior — explicitly flagged

The stock `cap_nmos_*`/`cap_pmos_*` SPICE subcircuits in
`sm141064.ngspice` implement the capacitor as a single voltage-dependent
capacitance element:

```
.subckt cap_nmos_03v3 1 2 c_length=l c_width=w dtemp=0
.param cvar1=0.002003
.param cvar2=0.00198
.param cvar3=6.25
.param cvar4=-3.9375
c_moscap 1 2 c='cap_nmos_03v3_corner*c_length*c_width*(cvar1+cvar2*tanh(cvar3*v(1,2)+cvar4))' dtemp=dtemp
.ends cap_nmos_03v3
```

This is a nominal (pre-breakdown), continuous `tanh`-shaped C–V curve valid
for the device operated as a capacitor within its rated voltage. **There is
no breakdown event, no post-breakdown resistive branch, and no leakage-path
element in this model** — nothing switches the element from capacitive to
resistive behavior at any bias. The same holds for all eight `cap_*`
variants found (`03v3`/`06v0`, NMOS/PMOS, plain/`_b`); only the four `cvar1..4`
coefficients differ between them.

**Consequence**: the stock PDK moscap models cannot be driven past their
nominal C–V curve to observe a breakdown transition in ngspice — attempting
to sweep bias past the rated voltage in simulation will not produce a
programmed (low-resistance) state, only extrapolation of the pre-breakdown
capacitance formula. A custom breakdown-augmented model or subcircuit
(e.g., a voltage-controlled switch or behavioral resistor gated on an
accumulated-stress or bias threshold, added on top of the stock element) is
required for any `sim/` work that needs to reproduce a programmed cell's
read-path resistance or a programming-yield curve. **This blocks the
program/read architecture sub-issue (#1 item 3) from simulating the sense
path against a programmed-cell model using stock PDK parts alone** — that
sub-issue needs to either build a custom breakdown model or scope its
verification around measured (silicon) resistance data instead of
simulation, and should treat this as a known input rather than rediscovering
it.

## Candidates

### Candidate 1 — Thin-oxide NMOS moscap + 6.0 V NMOS access (baseline)

- **MOS-capacitor**: `cap_nmos_03v3` (3.3 V thin oxide, `toxe = 8 nm`)
- **Access/isolation device**: `nfet_06v0` (6.0 V thick oxide, `toxe ≈ 15.2 nm`)
- **Pairing rationale**: the access device's own oxide is roughly 2x thicker
  than the capacitor's, so at the programming bias needed to break down the
  thin-oxide capacitor the access device's gate oxide is operating well
  below its own stress point — it gates the current path without itself
  becoming a second, unintended fuse. `nfet_06v0` is a standard
  symmetric-drain/source logic device, so it behaves as a conventional pass
  transistor in the row/column MUX without the asymmetric-terminal caveat
  that applies to the 10 V LDMOS option.
- **Programming voltage regime**: thin 3.3 V oxide. The programming voltage
  needed to break down an 8 nm gate oxide is not given by the stock PDK
  model files (SPICE models are valid only up to rated voltage; see the
  post-breakdown flag above) and is not asserted here as a specific number —
  it is expected to be several times the 3.3 V rated voltage, consistent
  with published gate-oxide-breakdown antifuse literature for thin-oxide
  logic-CMOS capacitors of comparable oxide thickness (single-digit-volt
  programming voltages for sub-10 nm oxides is the general shape reported in
  that literature; the actual number for this process is an empirical
  question for the split-axis / measurement plan, not something this survey
  invents). The 6.0 V access device rating comfortably exceeds the expected
  programming voltage while remaining well under its own breakdown, which is
  the basis for calling this pairing achievable.

### Candidate 2 — Thick-oxide NMOS moscap + 10 V asymmetric access (high-voltage regime)

- **MOS-capacitor**: `cap_nmos_06v0` (6.0 V thick oxide, `toxe ≈ 15.2 nm`,
  roughly 2x the Candidate 1 capacitor's oxide thickness)
- **Access/isolation device**: `nfet_10v0_asym` (10 V LDNMOS, drain-extended
  high-voltage device from the dedicated `SM-BB-000149` HV process module)
- **Pairing rationale**: a thicker capacitor oxide is expected to need a
  correspondingly higher programming voltage to reach breakdown (oxide
  breakdown field scales primarily with thickness, so roughly 2x the oxide
  thickness of Candidate 1 implies materially higher programming voltage,
  not a fixed multiple asserted here). None of the standard-drain 6.0 V
  devices are rated to gate that voltage safely as a series access element;
  the 10 V LDMOS device's drain-extended construction exists specifically to
  block higher voltages, making it the only verified device in this PDK
  with headroom above the 6.0 V access device used in Candidate 1. This
  candidate exercises a materially different point in the programming
  design space (thicker cell oxide, higher voltage, different access-device
  class) rather than a minor variant of Candidate 1 — the kind of distinct
  grid region CLAUDE.md's split-axis framing calls for.
- **Programming voltage regime**: thick 6.0 V oxide, expected to require a
  higher absolute programming voltage than Candidate 1's thin-oxide cell.
  The access device's 10 V rating is chosen specifically because it is the
  only option in the verified inventory with margin above the 6.0 V devices
  used to gate Candidate 1's lower-voltage cell. As noted in the device
  table, the asymmetric drain/source construction of `nfet_10v0_asym` means
  its use as an access device requires deliberate source/drain assignment
  at the array/layout stage (out of scope for this cell-candidate record).

### Candidate 3 — Thin-oxide PMOS moscap + 6.0 V PMOS access (polarity variant)

- **MOS-capacitor**: `cap_pmos_03v3` (3.3 V thin oxide, PMOS polarity
  counterpart to Candidate 1)
- **Access/isolation device**: `pfet_06v0` (6.0 V thick oxide, PMOS
  counterpart to Candidate 1's `nfet_06v0`)
- **Pairing rationale**: same oxide-thickness margin argument as Candidate
  1, applied to the PMOS device family. Published antifuse literature notes
  that NMOS and PMOS gate-oxide breakdown behavior is not symmetric
  (inversion-layer polarity and carrier-injection differences affect
  breakdown statistics), so an NMOS/PMOS pair sharing the same nominal
  oxide thickness and programming voltage target is a legitimate,
  low-incremental-cost split axis for this grid rather than a redundant
  variant of Candidate 1 — it isolates polarity as a variable while holding
  oxide thickness and target programming voltage approximately constant.
- **Programming voltage regime**: thin 3.3 V oxide, same expected regime as
  Candidate 1 (single-digit-volt-class programming voltage, not asserted
  precisely — see Candidate 1). `pfet_06v0`'s 6.0 V rating gives the same
  access-device margin argument as `nfet_06v0` does for Candidate 1.

## Open questions carried forward (not resolved here)

- **`_b` (body-tap) moscap variants**: `cap_nmos_03v3_b` / `cap_pmos_03v3_b`
  / `cap_nmos_06v0_b` / `cap_pmos_06v0_b` have identical two-terminal
  (gate/body) pinouts to the plain variants but different C–V model
  coefficients, which points to a different well/isolation structure. This
  likely matters once cells share rows/columns in an array (isolation
  between adjacent cells' body/well connections), but confirming the exact
  structural difference requires PDK device documentation not reviewed in
  this survey. Left as a candidate refinement for the split-axis plan
  (sub-issue B) or array/layout stage, not decided here.
- **Actual gate-oxide breakdown voltages** for the 3.3 V and 6.0 V oxide
  flavors are not present in the SPICE model files (models are specified
  only up to rated operating voltage) and were not found in a
  reliability/characterization document in the locally checked-out PDK
  tree. This is expected to be either sourced from public gf180mcu process
  literature or determined empirically via the measurement plan this test
  vehicle exists to produce — it is a split-axis / measurement question,
  not a gap in this survey.
- **Post-breakdown resistance modeling** (see flagged section above): stock
  `cap_*` models have no breakdown branch. Any `sim/` work targeting
  programmed-cell read-path behavior needs either a custom
  breakdown-augmented model or a measurement-based approach.

## References

- **Public gf180 canary repos** (`gf180-bandgap`, `gf180-temp-por`) — cited
  for this fleet's established gf180mcu circuit/flow conventions (xschem +
  ngspice design/verification flow, PVT-cornered results, spec changes
  landing as decision records). Not cited for antifuse-specific content —
  those repos are not antifuse designs.
- **GlobalFoundries gf180mcu open PDK** (`open_pdks`, commit
  `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7` (re-pinned 2026-10-15; originally checked against
  `c6d73a3…`), `sm141064.ngspice` and
  `smbb000149.ngspice` model files, `libs.tech/xschem/symbols`) — primary
  source for the verified device inventory and SPICE model behavior in this
  record.
- **Published gate-oxide-breakdown antifuse OTP literature** (general
  logic-CMOS antifuse memory literature, e.g. industry OTP IP describing
  single-transistor gate-oxide-as-fuse cells and two-transistor
  capacitor-plus-isolation-device cells, and foundry/academic reliability
  literature on NMOS-vs-PMOS gate-oxide breakdown asymmetry) — cited
  generically for the 1T-vs-2T topology framing and the
  NMOS/PMOS-asymmetry rationale behind Candidate 3. No specific paper is
  quoted for a numeric breakdown-voltage value in this record; see "Open
  questions" above for why that number is deferred rather than asserted.

## Decision

Ratify Candidates 1, 2, and 3 above as the cell candidate set for this
project. Candidate 1 (thin NMOS moscap + 6.0 V NMOS access) is the baseline
cell; Candidate 2 exercises a distinct thick-oxide / higher-voltage regime;
Candidate 3 exercises polarity as a split axis at the same oxide thickness
as Candidate 1. Sub-issues B (split-axis plan), C (program/read
architecture), and D (on-die/off-die programming-supply decision) build on
this set.
