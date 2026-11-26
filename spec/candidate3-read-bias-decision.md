# Decision Record: Candidate 3 Read Bias

**Status**: Proposed by the Builder for issue #75; ratified only when this PR is merged by the operator's
normal review path. It chooses a read-bias arrangement for Region III (Candidate 3) and changes no
ratified text: `spec/architecture.md`, `spec/cell-candidates.md`, `spec/program-voltage-decision.md`,
`spec/split-axis-plan.md` and `spec/supply-domains-decision.md` are untouched. It fills values that those
records leave open (supply-domains rows 6, 10, 15; OI-3, OI-7, OI-8).
**Date**: 2026-10-14
**Scope**: Region III only (`cap_pmos_03v3` + `pfet_06v0`). Regions I and II keep the #62 read bias
(BL = 1.0 V +-10 %, WL fully on, PL = 0), and their committed #62 requests and decks regenerate byte-identically
from the new code (`tests/test_c3_read_bias.py`, see Reproducing); no Candidate 1 or 2 result is re-simulated here.
**Evidence**: `sim/cell-breakdown-model/records/20261014-104105-9220086.md` (fleet job
`klt-sim-e568d2d9e4e6`, 45 PVT corners, all `pass`). Every programmed-cell current is **conditional on the
assumed filament parameters** (`design/breakdown/breakdown_params.spice`: rf_med 10 kOhm, rf_wc 81.7 kOhm).
Nothing here is a gf180 silicon measurement, and nothing establishes a safe read-disturb limit.
**PDK revision**: the record was produced under open_pdks `c6d73a3` (gf180mcu_fd_pr `faef89e`), the pin in force
on 2026-10-14; the repo has since pinned `f6eeac7` (fd_pr `b6866b8`, `spec/pdk-pin-decision.md`). The `pfet_06v0`
model card and the `cap_pmos_03v3` subcircuit are textually identical in `models/ngspice/sm141064.*` at both fd_pr
commits (checked 2026-10-20), so the re-pin does not change these results; the record keeps its revision, as
`pdk-pin-decision.md` requires. The "6.0 V" and "3.3 V" figures used as limits here are the PDK's device voltage
classes (the model-file header: "6.0V PMOS", "3.3v inversion-mode PMOS capacitor"), not published absolute-maximum
terminal ratings, which the open PDK does not provide. `cap_pmos_03v3` is a two-terminal voltage-dependent
capacitor in the model, with no junction or leakage element, so every capacitor-side leakage term is outside
the model by construction.

## Problem

At the #62 placeholder bias (WL on = 0 V, n-well `VB` = 3.3 V) a programmed Candidate 3 cell reads
4.9e-15 A at `typical_27c_bl1p00v` and 2.4e-13 A at `ss_-40c_bl0p90v`, below the unprogrammed
`I_sneak_max` of 1.4e-11 A, so `spec/architecture.md` Section 4's `I_sneak_max < I_ref < I_prog_min` has no
solution. The new record reproduces both numbers exactly (scenario `s0_placeholder`).

Cause: once the filament pulls CN to PL = 0, BL is the PMOS source at about 1 V. V_GS is about -1 V, and the
3.3 V well adds about 2.3 V of reverse body bias, which raises |V_th|. The small-signal R_on of about
1.1 kOhm does not show this, because it is taken with CN floating above BL (CN is then the source).

## Alternatives compared

Each was simulated with the programmed and the unprogrammed cell at the **same** bias, in the same deck, over
all 45 corners and 4 sub-configurations (access sizing x capacitor geometry; per-sub-config values are in the
record and are not averaged). The leakage bound was recomputed at each bias, including the programmed-OFF
cell (CN pulled to PL), which is the worst sneak case.

| Scenario | Arrangement | min I_prog [A] (corner) | max I_zero,f [A] | window | Notes |
|---|---|---|---|---|---|
| `s0_placeholder` | WL on 0 V, well 3.3 V, BL 1.0 V | 4.9e-15 (`typical_27c_bl1p00v`) | 3.2e-11 | 1.5e-4 | infeasible at 38 of 45 corners |
| `s1_wl_neg1` | WL on -1.0 V, well 3.3 V | 4.96e-7 (`ss_27c_bl0p90v`) | 3.2e-11 | 1.6e4 | needs a negative WL rail |
| `s2_wl_neg2` | WL on -2.0 V, well 3.3 V | 3.99e-6 (`ss_125c_bl0p90v`) | 3.2e-11 | 1.3e5 | needs a negative rail; gate-to-well 5.3 V against 6.0 V rating |
| **`s3_vb_track`** | **WL on 0 V, well tied to the read rail** | **1.25e-9 (`ss_-40c_bl0p90v`)** | **3.2e-11** | **39** | **no new rail; chosen** |
| `s4_vb_fix1v` | WL on 0 V, well fixed 1.0 V | 3.97e-10 (`ss_-40c_bl0p90v`) | 3.4e-11 | 11.5 | well not tracking the +-10 % rail: weaker |
| `s5_rail1v8` | rail 1.8 V, WL on 0 V, well 3.3 V | 1.81e-7 (`ss_-40c_bl0p90v`) | 3.2e-11 | 5.7e3 | new Region III read rail |
| `s6_rail1v8_vb_track` | rail 1.8 V, well tied to rail | 2.33e-6 (`ss_125c_bl0p90v`) | 3.2e-11 | 7.3e4 | new read rail; cell oxide 1.98 V |
| `s7_vb_track_p0v3` | tracking, well 0.3 V above rail | 3.8e-11 (`ss_-40c_bl0p90v`) | 3.2e-11 | 1.2 | sensitivity: window almost closed |
| `s8_vb_track_m0v3` | tracking, well 0.3 V below rail | 2.7e-8 (`ss_-40c_bl0p90v`) | 1.2e-8 | 2.2 | sensitivity: forward-biased source junction leaks |

`I_zero,f` = (N-1) x max(I_off, abstol) + max(selected-unprogrammed current, abstol) with N = 32 and
abstol = 1e-12 A. This is a solver resolution floor, (N-1+1) x abstol, not a bound on physical leakage and not a prediction.
The PDK model's own leakage at the chosen bias is **unresolved, below about 1e-12 A per cell**: the raw
`i_off_s3*`, `i_offp_s3*` and `i_un_s3*` values are exactly 0.0 A or small multiples of 2^-54 of both signs
(machine-epsilon residue, e.g. 31 x 1.11e-16 = 3.4e-15 A for the (N-1) sum), so they are solver roundoff, not
model output, and `abs()` in the derivation hides the sign. The window of 39 is measured against this
resolution floor. The window column is the single-common-`I_ref`
ratio: the minimum `I_prog` over all corners divided by the maximum `I_zero,f` over all corners.

All scenarios except `s0_placeholder` satisfy `I_prog > I_zero,f` at 45/45 corners with no failed or
non-converged corner. `s0_placeholder` fails at 38 of 45 corners. The 7 that pass are all at the 125 degC or
1.1 V end of the matrix with a fast or typical device (`ff_125c_bl1p00v`, `ff_125c_bl1p10v`, `ff_27c_bl1p10v`,
`sf_125c_bl1p00v`, `sf_125c_bl1p10v`, `sf_27c_bl1p10v`, `typical_125c_bl1p10v`), so no common `I_ref` exists.

## Decision

Candidate 3 is read with the arrangement `s3_vb_track`:

| Terminal / rail | Read value | Source |
|---|---|---|
| BL (selected column, access-device source when conducting) | the common read rail, 1.0 V +-10 % (0.9 to 1.1 V) | supply-domains row 10, unchanged |
| WL, selected row | 0 V (ground, `VSS_ANALOG`) | the existing "fully on" state; no new level |
| WL, unselected rows | 3.0 to 3.6 V (logic-compatible, `VDD_LOGIC` +-0.3 V) | supply-domains row 6 / OI-7 |
| PL | 0 V | unchanged |
| `VB` (Region III n-well) | **the read-rail node itself** (VB = BL rail, offset 0 V) | supply-domains row 15 |
| Unselected BLs | at or below `VB` (0 V assumed) | see the unselected-cell paragraph below |

**The decisive change is the well: during read, the Region III n-well is tied to the read-rail node instead
of the 3.3 V logic rail.** Zero source-to-body bias removes the body effect, so the V_GS = -0.9 to -1.1 V
that WL = 0 V provides is the full gate drive. The word-line levels, and therefore the level-shifter
rails, are unchanged.

### Why this one

- **No new rail and no level-shifter change.** WL on = 0 V is ground, and WL off is the logic-compatible
  3.3 V bias that `spec/architecture.md` Section 1.1 already assumes for read. WL below ground (`s1`, `s2`)
  needs a negative rail, which no ratified record or inventory row provides. A negative-going level-shifter
  output also needs the NMOS pull-down in an isolated p-well (deep n-well) and a negative supply source,
  neither of which is characterized or inventoried. I do not declare that safe by inspection. It is kept
  as a fallback (below), not as the choice.
- **No change to the shared read rail.** Raising the Region III read rail to 1.8 V (`s5`, `s6`) widens the
  window most (7.3e4 for `s6`), but it moves the cell oxide to 1.98 V (60 % of the 3.3 V rating, against
  1.1 V now), changes the sense-amplifier input range, and moves a value that supply-domains row 10 lists
  as unresolved for all regions. The behavioral model cannot establish a read-disturb limit, so a
  higher rail should be taken only if the lower-rail window proves insufficient.
- **The window is open at every corner.** `I_prog` is at least 1.25 nA (`ss_-40c_bl0p90v`, access-device
  limited: the median- and worst-filament currents agree to 3 digits there, so this number does not
  depend on the assumed filament resistance) and `I_zero,f` is at most 3.2e-11 A, which is the solver
  resolution floor. Model leakage is unresolved below that floor; no ratio against it is claimed.
- **A well switch is needed anyway.** Programming drives BL at `VPP` through the PMOS source, which a 3.3 V
  n-well cannot tolerate (junction forward-biased by the difference). So the Region III well net must
  already switch between a program level and a read level. That program level is #90's question.
  Choosing the read level adds a mode to a switch the design needs regardless.

### Rails, polarity, junctions (from the record's measured voltages)

- Well polarity: n-well to p-substrate reverse-biased (well at 0.9 to 1.1 V, substrate at 0 V). The
  source (BL) p+/n-well junction sees 0.00 V (zero bias) and the drain (CN) p+/n-well junction sees at least
  +0.75 V reverse over every corner for the programmed cell. Nothing is forward-biased.
- Gate stress, against the 6.0 V `pfet_06v0` rating: gate-to-well at most 2.7 V (selected WL 0 V / unselected
  3.6 V against a 1.1 V well), gate-to-BL at most 2.7 V. The cell oxide (BL-PL) is at most 1.1 V,
  against the 3.3 V `cap_pmos_03v3` rating. The table is in the record.
- Unselected cells on the same bit-line: WL at 3.0 to 3.6 V with source and well at the read rail, so
  V_SG is -1.9 to -2.7 V (firmly off). The OFF current was measured for both the unprogrammed and the
  programmed (CN pulled to PL) cell, at all three OFF levels: both are below ngspice's resolution. The
  `s3` OFF current is smaller than the placeholder's (the placeholder's 1e-13 A-class values are the
  `gmin` floor acting on the 2.3 V source-to-well voltage; with zero source-to-well voltage there is no such term).
- Unselected cells in the selected row on other columns: WL 0 V with BL (unselected) at 0 V gives V_GS = 0 V
  (off), and the well is at the read rail, so their junctions are also reverse-biased. This assumes
  unselected bit-lines are held at or below `VB`; it was not simulated beyond the single-bit-line bench.
- Level-shifter impact (`spec/architecture.md` Section 1.1): none for the WL/read path. The shifter's
  read-time high-side rail is the same logic-compatible bias as before (OI-7 still needs its value), and
  its low side is ground. The consequence is on the well-bias network, not the shifters.

### Tolerances this choice imposes

The sensitivities show the arrangement is tight in one direction each way:

| Well minus rail | Effect (record, scenarios `s7`, `s3`, `s8`) |
|---|---|
| +0.3 V | `I_prog` drops 33x to 3.8e-11 A: window 1.2, effectively closed |
| 0 V | window 39 (this decision) |
| -0.3 V | forward-biased source junction leaks 1.2e-8 A (31 cells): window 2.2 |

So `VB` must be the **same electrical node as the read rail** (or follow it within about +-0.1 V), not a
separate supply set to the same nominal value. `s4_vb_fix1v` (a fixed 1.0 V well against a +-10 % rail)
already shows the cost of tolerating the rail swing separately: 11.5 against 39.

## What this does not establish

- The window of 39 is set at one corner (`ss_-40c_bl0p90v`) where the gate drive is V_SG = 0.9 V, near or
  below |V_th|, so `I_prog` there is a sub-threshold-class current (about 1 nA). An ASSUMED rule of thumb is a decade per
  about 100 mV of threshold shift; it was not measured here. **Local mismatch and within-die variation are not in the corner set**, and
  neither is Monte Carlo. A mismatch Monte Carlo of this bias belongs with the sense-path work (#65, #66).
- `I_ref` is not set. The valid interval for `I_ref` is `(3.2e-11, 1.2e-9)` A under this bias, per the
  assumptions above, for the placeholder geometry levels, not the ratified split-axis levels. #65
  consumes it. The interval is per Region III; it says nothing for Regions I and II.
- Read disturb is not established. The selected unprogrammed cell's oxide sees at most 1.1 V (a 3.3 V
  rated cap); the E-model parameters are assumed.
- Junction leakage, GIDL and well-to-substrate terms beyond the PDK model are not characterized, and the
  resolution floor does not stand in for them.
- Well-junction current through the sensed node is not measured. The bench drives `VB_s3_vb_track` from an
  ideal B-source and measures only `i(vm_*)` in the BL branch. At s3 the well is fed by the reverse-biased
  drain p+ to n-well junctions of every unselected programmed cell (about 1 V) and the Region III
  n-well-to-substrate junction. If `VB_III` is tied on the sensed side of the read leg, that current adds to
  `I_zero` and is not in 3.2e-11 A. This decision therefore requires `VB_III` to connect on the rail-source
  side, outside the sensed current path (see Downstream).
- The program-phase well level, and whether a Region III program leg is feasible at all, is #90.

## Fallback ladder (if the window proves insufficient)

1. Raise the Region III read rail with the tied well (`s6`, window 7.3e4). It needs a new decision on
   supply-domains row 10 and a read-disturb argument first.
2. WL below ground with the well at the read rail or at 3.3 V (`s1`/`s2`, windows 1.6e4 / 1.3e5). It needs a
   negative rail and level-shifter devices that tolerate it; each is its own decision.

Neither is adopted. Taking either one requires a new record.

## Downstream

- #64 (array, MUX, level shifters): Region III read uses WL 0 V / 3.3 V-class OFF, the well net `VB_III`
  tied to the Region III read-rail node in read mode on the rail-source side, outside the sensed current
  path (well current must not flow through the sense element). The sense-element drop (rail minus BL) must
  stay within about 0.1 V (`s7`/`s8`: a 0.3 V well-to-source offset closes the window), and `VB_III` switched by the (undecided, #90)
  program-mode level. There is no negative rail. Unselected bit-lines must sit at or below `VB_III`.
- #77 (supply inventory): row 15 (`VB`, Region III) gains a read-mode value (the read rail); row 10 is
  unchanged; row 6's read bias keeps its OI-7 status.
- #65 (read leg, I_ref): window `(3.2e-11, 1.2e-9)` A for Region III at the placeholder geometry. The lower
  edge is a solver resolution floor, not a measured leakage. The sense element must not carry well current
  and its drop (rail minus BL) must stay within about 0.1 V.
- #90: the read choice does not constrain the program-mode well level, but program mode must not leave the
  well below the BL source potential; this record needs no change from #90's outcome except the well-switch
  design.

## Reproducing

```bash
python3 sim/cell-breakdown-model/run_experiment.py --candidates 3 --benches bias_op
python3 -m unittest tests.test_c3_read_bias
```

The first goes to the batch fleet (never a local ngspice grid). The second runs no simulator: it checks that
the bias configuration reaches the generated deck, that failed, missing or non-converged corners cannot
pass, and that the Candidate 1/2 decks and requests regenerate byte-for-byte as committed by #62.
