# Decision Record: Program-Leg and Read-Leg Design Choices

**Status**: Design-stage record. It **instantiates** `spec/architecture.md`
sections 1.2, 2 and 4 at transistor level and carries forward the open items
that record deferred to `design/`. It does not amend, relax or reinterpret any
ratified line; where a number below is an assumption it says so.
**Scope**: the program leg (`design/cells/program_leg.sch`), the read leg
(`design/cells/read_leg.sch`) and their shared interlock block
(`design/cells/leg_interlock.sch`). Nothing about the cell candidates, N, the
region map, `VPP` generation or the SPI register map is decided here.

## 1. What the legs are

- **Program leg**: `VPP` -> high-side `pfet_06v0` switch -> `ppolyf_u_2k_6p0`
  ballast -> bit line. The switch gate comes from a cross-coupled `pfet_06v0`
  level shifter referenced to `VPP`, driven by `PON`.
- **Read leg**: bit line -> `nfet_06v0` isolation switch -> `nfet_03v3`
  source-follower clamp -> diode-connected `pfet_03v3` mirror input. The mirror
  copy meets `I_ref` (bench-supplied current into an `nfet_03v3` mirror) at
  node `SENSE`; two inverters give `RDATA` (1 = bit-line current above
  `I_ref`).
- **Interlock** (inside both legs): `PON = PROG_EN & ~READ_EN`,
  `RON = READ_EN & ~PROG_EN`. This is a second, local line of defence behind
  the upstream `READ_EN = NOT(PROG_EN OR PROG_ARM)` of `spec/architecture.md`
  1.2 (which is unchanged and still required): if both enables are ever
  asserted, both legs are OFF at the bit line.

### Interface constraints this design introduces (to be honoured upstream)

1. **`VPP` must idle at or above `VDD`** whenever the program leg is OFF. The
   switch's drain-to-well junction would otherwise be forward biased by the
   bit-line read level. `spec/program-voltage-decision.md` (bench-supplied
   `VPP`) allows this; the bench must hold it.
2. **The active compliance limit (`spec/architecture.md` 2, item 2) is not in
   the leg.** It is the WL bias set by the level shifter of 1.1, which is not
   designed here. This record covers the primary (ballast) limit only.
3. **6 V device tier only.** `pfet_06v0`/`nfet_06v0` give a program leg for
   Candidate 1/3 regions. A Candidate 2 (10 V tier) variant is not captured.
4. **The read voltage is not a rail.** The clamp sets the bit line at about
   `VCLAMP - Vgs`, so it moves with PVT and with the cell's own current; the
   margin bench reports the resulting bit-line voltage next to every current.

## 2. Ballast sizing (acceptance: choice recorded with the inequality)

The inequality, from `spec/architecture.md` 2:

    R_ballast >= (VPP - V_compliance) / I_target_max

`I_target_max` is **not fixed by the ratified record** and no measurement or
breakdown model exists. The numbers used here are therefore **assumptions**:

| Input | Value | Status |
|---|---|---|
| `VPP` (top of the 6 V tier) | 6.0 V | assumed bench rail |
| `V_compliance` (voltage left across filament + access device after breakdown) | 1.0 V | **assumed** |
| `I_target_max` | 1 mA | **assumed** |
| Required `R_ballast` | (6.0 - 1.0) / 1 mA = **5.0 kohm** | derived from the above |

The inequality has to hold at the **lowest** ballast resistance over PVT, so
the resistor is sized from the model's own corner parameters (hand
calculation from `sm141064.ngspice`: `rsh_ppolyf_u_2k_6p0` = 1600 / 2000 /
2400 ohm/sq for ff / typical / ss, `r_dw` = 0.02256 um, `r_dl` = -0.0932 um,
`r_tc1` = -1.6698e-3, `r_tc2` = 3.743e-6, `r_tnom` = 25 C; end-terminal
resistance ignored, it is a few tens of ohm):

| `rb_w` / `rb_l` | ff, 125 C | typical, 27 C | ss, -40 C | Meets 5.0 kohm at ff/125 C? |
|---|---|---|---|---|
| 2 um / 6.0 um | 4407 ohm | 6308 ohm | 8539 ohm | **no** |
| 2 um / **7.5 um (chosen)** | **5476 ohm** | 7838 ohm | 10610 ohm | yes, 9.5 % headroom |

**Choice: `ppolyf_u_2k_6p0`, `rb_w = 2 um`, `rb_l = 7.5 um`** (the committed
defaults of `program_leg`). A typical-corner single-point debug probe of the
elaborated netlist gave 7.87 kohm (7.84 kohm hand-calculated), which supports
the formula at one point only. The PVT evidence for this choice is the
`ballast` bench of `sim/program-read-legs/`; **it has not been run on the
batch fleet yet** (see that directory's README), so this sizing is
**provisional and unverified across PVT**. If `measurements/` later fixes
`I_target_max`, only the assumed row above changes; `rb_l` is the one
parameter to retune, and the table's method carries over.

Other lower bounds follow from the same inequality: VPP = 5.0 V needs 4.0
kohm, VPP = 4.0 V needs 3.0 kohm; both are met by the chosen resistor.

## 3. `ppolyf_u_2k_6p0` voltage-rating question

`spec/architecture.md` carries this forward as an open question: is `_6p0` a
6.0 V rating? What the locally installed PDK (open_pdks
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`; re-pinned 2026-10-15, see [`pdk-pin-decision.md`](pdk-pin-decision.md)) can and cannot settle:

- **Settled (naming):** `sm141064.ngspice` describes `ppolyf_u_2k_6p0` as a
  "2k high-Rs p+ poly resistor on field oxide **(6.0V area)**", its sibling
  `ppolyf_u_2k` as "(3.3V area)", and `ppolyf_u_3k` as usable in "both 3.3V &
  6.0V area". The klayout LVS deck (`libs.tech/klayout/lvs/rule_decks/
  res_derivations.lvs`) derives the device as `poly2 & res_mk & resistor &
  dualgate` -- it is the resistor drawn **inside the dual-gate-oxide (thick
  oxide) region**. So `_6p0` is an **area designation** (which gate-oxide
  domain the resistor is placed in), not a stated voltage limit.
- **Not settled (rating):** no file in the PDK tree states a maximum voltage
  across, or from, the poly body. The resistor sits on field oxide over the
  substrate, so the voltage the field oxide tolerates is the real limit, and
  it is documented nowhere locally. The reading "6.0 V-class" is consistent
  with the area designation but remains an **inference**.

**Resolution: the rating question stays OPEN.** The area-designation finding
narrows what `_6p0` means; it does not confirm a voltage. The leg is therefore
limited to the 6 V tier (constraint 3 above), and the resistor must not be
relied on in a Candidate 2 (higher-voltage) program path until a reliability
document or measurement closes this.

## 4. Items carried forward unchanged

- `I_ref > I_sneak_max` is honoured by the bench `I_ref` values; the lower
  bound comes from `sim/cell-device-characterization/`.
- `I_ref < I_prog_min` is **unchecked**: `I_prog_min` does not exist until a
  breakdown-augmented cell model or silicon data does. The programmed-state
  resistance used by the margin bench is an **assumed placeholder**.
- Mismatch/offset of the sense mirror is not evidenced (process corners only,
  no Monte Carlo).
- Level shifter, decoder and WL-bias design (1.1) and the settling times of
  1.x/5 remain open design-stage items.
