# Decision Record (PROPOSED): Program-Voltage Pad and Protection Approach, Run 3 Test Chip

**Status**: PROPOSED for operator ratification. Relaxes and amends nothing in
`spec/program-voltage-decision.md` (off-die `VPP` through a dedicated pad stays
as ratified), `spec/supply-domains-decision.md`, `spec/cell-candidates.md` or
any other ratified record. It fills the gap `spec/program-voltage-decision.md`
left: what pad and protection makes the `VPP` pad survive, and keeps an
unprogrammed neighbour intact.
**Date**: 2026-10-29
**Scope**: Issue #210, part of #203. The pad / protection path of the 36 private
plate (`PL`) pads reserved as "HV" in `spec/run3-test-chip-floorplan.md`. Not in
scope: cell layouts (#207), floorplan (#206), on-die `VPP` generation (ratified
off-die). Antifuse physics and program-circuit content only.

**Conditionality.** Every number is CONDITIONAL ON THE ASSUMED breakdown
parameters (`design/breakdown/breakdown_params.spice`: V_bd = 8.0 / 15.2 / 7.9 V
for Candidates 1 / 2 / 3). The filament is a threshold switch, not the
stochastic model; the benches rate a path, they make **no yield claim**. Source,
cable, coupling, access and filament values are placeholders, listed in
`sim/hv-pad-protection/README.md`. Candidates are never merged below.

## Answer (proposed)

1. **Pad: a bare bond pad per `PL`, wired straight to the instance's plate, on
   no shared rail.** No standard pad cell, no clamp to `DVDD`/`DVSS`, and no
   on-die series element between pad and plate.
2. **Current limiting is off-die**: a series resistor at the bench socket plus
   the source's current compliance (the bench plan's OPEN-B1). It is the
   program current-limiting element of `spec/architecture.md` §2 for this
   chip, which has no on-die mux path to host the on-die ballast.
3. **Neighbour protection is bench policy (b)**: unselected `PL` pads are driven
   to 0 V, not left high-impedance. Both policies are within rating; (b) has
   3 to 4.5x less stress on the neighbour (table below).
4. **Constraints this places on the plate node** (for #207 and the bench plan,
   not decided here): see "Plate-node junction" below.
5. **ESD**: a bare pad has no on-die ESD structure. That is accepted for this
   private characterization die and handled by bench discipline; the open PDK
   cannot demonstrate any high-voltage ESD protection (see "What is not
   demonstrated").

**Principal dependency (OPEN, operator / shuttle offering).** The slot template
page says "The IO ring contains the pad cells" and says nothing on whether a
slot's pad cell can be omitted or bypassed, on pad voltage, or on ESD (read
2026-10-29, `https://mith.ro/gf180mcu-project-template/`). The answer above
requires that the `PL` route can reach a bond pad that has **no** pad-cell
diodes on it. If the ring's pad cells are fixed and every `PL` must go through
one, then the "standard pad" result below applies and no program voltage above
about 6.5 V can reach a cell on this chip. That is the "no approach is
demonstrable" outcome of this issue's fourth criterion for that case.

## Rated limits of each device in the path (from the PDK files)

| Device / structure | Limit | Source |
|---|---|---|
| Standard pad cell, `gf180mcu_fd_io__asig_5p0` | characterised to the 5.50 V corner; clamp `D3` pad-to-`DVDD` is `diode_pd2nw_06v0`, `D2` is `diode_nd2ps_06v0` to `DVSS` | `libs.ref/gf180mcu_fd_io/lib/*_5v50.lib`; `spice/gf180mcu_fd_io.spice` (cell netlist, copied verbatim into `design/hv-pad/hv_pad_path.spice`). `bi_t` / `bi_24t` carry the same `pfet_06v0_dss` / `nfet_06v0_dss` drain junctions to `DVDD` / `DVSS` |
| `ppolyf_u_2k_6p0` (on-die ballast alternative) | "6.0V area" is an area designation; voltage rating **OPEN** (field-oxide limit not stated anywhere) | `sm141064.ngspice` line 78; `spec/leg-design-record.md` §3 |
| Junction n+/p-substrate, `diode_nd2ps_06v0` | `bv` = 11 V | `sm141064.ngspice` `.model diode_nd2ps_06v0` |
| Junction n-well/p-substrate, `diode_nw2ps_06v0` | `bv` = 14 V | same, `.model diode_nw2ps_06v0` |
| Junction deep n-well/p-substrate, `diode_dw2ps` | `bv` = 30.48 V | same, `.model diode_dw2ps` |
| Junction p+/n-well, `diode_pd2nw_06v0` | `bv` = 10.5 V | same, `.model diode_pd2nw_06v0` |
| Cell capacitor oxide | the intended breakdown; the no-disturb limit for a neighbour is the rated 3.3 V (Candidates 1, 3) / 6.0 V (Candidate 2) | `spec/cell-candidates.md` |
| Bond pad, metal route | no device; no rating in the PDK models | n/a |

The junction `bv` branch does not scale with area in these models (checked
2026-10-29: a 1 um^2 `nd2ps` diode conducts 0.4 mA at 12 V, none at 11 V), so
the knee voltages above are the model's, not a layout-area prediction.

## Evidence

All under `sim/hv-pad-protection/` (README there). Each bench is 45 corners:
3 process (typical, ff, ss) x 3 temperatures (-40, 27, 125 C) x 5 pad levels
(0.5, 0.95, 1.05, 1.10 x V_bd and 17.6 V = 16 V + 10 % bench overshoot), run
with `klt sim` on the batch fleet; 45/45 corners converged on every bench.
Records (artifact manifests under `manifests/artifacts/`):

| Candidate | Records |
|---|---|
| 1 / Region I | `20261029-070350-2431fbc` (all benches); `20261029-073858-f2a1299` (re-run: `astd_f` and `jn_*`, rule corrected) |
| 2 / Region II | `20261029-070354-2431fbc`; `20261029-074603-f2a1299` |
| 3 / Region III | `20261029-070358-2431fbc`; `20261029-075207-f2a1299` |

The first records' `astd_f` and `jn_*` tables carry `rail-injection` /
`junction-conducts` flags from the start-up and edge-charging peak currents; the
re-run records judge the late-hold current (append-only: the first records stay,
the re-run supersedes their `astd_f` / `jn_*` verdicts). Numbers below are the
worst corner within one level.

### Rejected A: standard pad cell on the plate (`astd_f`)

| Candidate | Level | Cell sees (max) | Programmed | Into `DVDD` / `DVSS` (hold) | Pad over 5.5 V |
|---|---|---|---|---|---|
| 1 (V_bd 8.0) | 7.6 V / 8.4 V / 17.6 V | 6.44 / 6.46 / 6.57 V | 0/9 at every level >= 8.4 V | 14 mA / 22 mA / 112 mA into `DVDD` | 9/9 corners |
| 2 (V_bd 15.2) | 14.44 V / 15.96 V / 17.6 V | 6.54 / 6.56 / 6.57 V | 0/9 | 81 / 96 / 112 mA into `DVDD` | 9/9 |
| 3 (V_bd 7.9, negative) | -7.5 V / -8.29 V / -17.6 V | 1.01 / 1.02 / 1.07 V | 0/9 | 67 / 75 / 168 mA into `DVSS` | n/a (pad is pulled to about -1 V) |

The cell's own clamp holds the plate at about `DVDD` + 1 V (positive) or one
diode drop below `DVSS` (negative) and dumps the bench current into the rail
shared with the logic and every other pad. No candidate programs. Any
"standard pad plus protection" variant keeps `D2`/`D3` on the pad, so it is
covered by this result; raising `DVDD` to the program voltage is excluded by
the 5.5 V rating of everything else on that rail.

### Rejected B: bare pad + on-die `ppolyf_u_2k_6p0` ballast (`c1_f`)

The cell is programmed at every level >= 1.05 x V_bd. But after breakdown the
resistor carries the pad-to-plate difference: Candidate 2 7.8 / 8.2 / 8.6 V at
15.96 / 16.72 / 17.6 V (above the 6.0 V area designation in 7 to 8 of 9 corners
per level), Candidate 1 and 3 8.6 V at 17.6 V (8/9 corners; 4.3 V at the
intended 8.4 and 8.8 V levels, within the designation). The rating is OPEN, so
Candidate 2's 7.8 to 8.6 V cannot be called in-rating; and it did not reduce
the programmed-filament current materially against `c0_f` (Candidate 2:
1.1 mA with the ballast, 1.5 mA bare, at 15.96 V). An unverifiable device on
the path with little benefit is rejected.

### Chosen: bare pad + off-die series resistor (`cx_f`, `cx_s`)

No device in the path other than the cell. 45/45 converged, **no violation at
any level or corner, fast (100 ns) or slow (100 us) ramp**, all three
candidates: the cell sees the intended voltage (`vox_max` = min(level, V_bd)
within 2 %: Candidate 2 14.4 V at 14.44 V level, 15.1 V at >= 15.96 V), is
unprogrammed at 0.5 and 0.95 x V_bd (0/9) and programmed at >= 1.05 x V_bd
(9/9). After breakdown the plate falls to 7.8 to 9.2 V (Candidates 1, 3) and
15.0 to 15.2 V (Candidate 2) because the 10 kOhm resistor takes the difference;
that resistor is off-die, so its voltage rating is the part's. Its 10 kOhm
value is a placeholder (the bench plan's OPEN-B1).

### Failure case: unprogrammed neighbour (`nbh_f`, `nbh_s`, `nbd_f`)

Selected cell programmed with an unprogrammed cell on the same BL and WL (WL on,
so the neighbour's cell node is held to BL) and 100 fF of plate-route coupling
between them (an estimate). Maximum neighbour oxide voltage over 45 corners and
all 5 levels, against the neighbour's rating:

| Candidate | `nbh_f` (hi-Z, fast) | `nbh_s` (hi-Z, slow) | `nbd_f` (driven 0 V) | Rating | Neighbour programmed |
|---|---|---|---|---|---|
| 1 | 0.76 V | 0.71 V | 0.25 V | 3.3 V | never (<= 7.6e-10 A) |
| 2 | 1.26 V | 1.22 V | 0.28 V | 6.0 V | never (<= 1.3e-9 A) |
| 3 | 0.76 V | 0.71 V | 0.25 V | 3.3 V | never (<= 7.6e-10 A) |

What protects the neighbour is (i) no electrical path between pads on this chip
(no shared rail, no mux, no shared plate) and (ii) the shared access path
holding its cell node at BL while the plate couples only a fraction of the
swing. Both pad policies pass; driven (b) is chosen for the margin and because
a hi-Z pad's stress depends on a coupling capacitance that is an estimate here.

### Plate-node junction (`jn_*`): a constraint on #207, not a pad choice

The stock capacitor macros have no junction, so a junction from the plate to the
substrate or a well was added explicitly, one bench per possibility. Worst
corner within a level:

| Candidate | Junction on the plate | Result at the programming levels |
|---|---|---|
| 1 | `nd2ps` (11 V), `nw2ps` (14 V), `dw2ps` (30.5 V) | plate stays <= 9.2 V; programmed 9/9 at >= 1.05 x V_bd; no violation; late-hold leakage <= 4.4 nA |
| 2 | `nd2ps` | **plate clamped at 12.0 to 12.1 V; 0/9 programmed at every level; 0.3 to 0.6 mA hold current** |
| 2 | `nw2ps` | **clamped at 14.8 to 14.9 V; 0/9 programmed at >= 15.96 V; 0.14 to 0.3 mA** |
| 2 | `dw2ps` | programmed 9/9; no violation; late-hold leakage <= 7.6 nA |
| 3 | `pd2nw` (p+ plate over a well tied at +3.3 V, the #62 bias) | **conducts: programmed only 3/9 at -8.29 V and 6/9 at -8.69 V**; 55 to 93 uA hold current |
| 3 | `nw2ps` (plate on an n-well; negative drive forward-biases it) | **plate held at -1.0 to -1.3 V; 0/9 programmed at every level; 0.3 to 1.6 mA** |

So, as a constraint to carry into #207 and the bench plan: Candidate 2's plate
node must sit on a junction with a knee above the program voltage (here only the
deep n-well, 30.5 V, qualifies); Candidate 3's negatively driven plate must not
be an n-type region over the substrate, and a p+ plate over a well needs the
well tied low enough that tie + program voltage stays under 10.5 V. These
depend on the same plate-isolation question `spec/program-bias-scheme-proposed-decision.md`
left open; this record does not decide it.

Pad leakage with nothing powered (the bare pad has no rail): the late-hold
junction leakage in the table (picoamps to nanoamps in the unprogrammed and
programmed states for the qualifying junctions), at the 0.5 and 0.95 x V_bd levels about 1 to 3 pA.

## What is not demonstrated

- **ESD.** No ESD event is simulated and the PDK carries no characterised
  high-voltage clamp or ESD data. A stack of the `nd2ps`/`pd2nw` diodes cannot
  stand off 16 V and conduct at 10.5 to 11 V. A bare pad is therefore
  unprotected; this is accepted for a private characterization die, not
  demonstrated safe. The generic tool gap met while rating the path is `2AMLogic/klayout-tools#4592` (no ESD claim is made from it).
- Whether the slot template permits a pad without a pad cell (principal
  dependency above).
- The off-die resistor's value and the source compliance (bench plan OPEN-B1).
- The access device's own terminal pairs (`sim/program-bias-scheme`) and the
  real coupling capacitance (layout).
- Stochastic breakdown: no yield claim here (`sim/programming-yield`).

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Standard pad cell on `PL` (with or without added protection) | Cell clamps the plate to about 6.5 V (or -1 V), no candidate programs, injects up to 168 mA into the shared rail |
| Bare pad + on-die `ppolyf_u_2k_6p0` ballast | Rating OPEN and above the 6.0 V area designation after breakdown on Candidate 2; little current benefit |
| `DVDD` raised to the program voltage | Every other device on the rail is rated 5.5 V |
| On-die HV pad with clamp | No characterised device in the PDK; `bv` 10.5 to 11 V diodes conduct inside the program range |
| Hi-Z unselected pads | Passes, but 3 to 4.5x more neighbour stress and depends on an estimated coupling |

## Reconsideration triggers

- The slot template is found to fix the pad cell on every signal pad.
- A measured V_bd differs from the assumed values (re-run, do not rescale).
- #207's layouts fix the plate-node junction.
- A characterised high-voltage ESD structure becomes available in the PDK.
