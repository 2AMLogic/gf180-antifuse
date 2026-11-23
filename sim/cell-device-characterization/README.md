# sim/cell-device-characterization/

First `sim/` experiment in this repo. Answers the "required design input"
`spec/architecture.md` §3 item 2 flags as not resolved by that record:
per-device access-device OFF-state leakage and ON-state series resistance,
plus the pre-breakdown capacitor C-V and leakage floor §3 item 2 and
§4 also need, for all three ratified cell candidates
(`spec/cell-candidates.md`), instantiated exactly as committed
(`design/netlists/cell_candidate{1,2,3}.spice`) — no device lines
hand-copied anywhere in this experiment.

## Scope and what this does NOT do

- Does **not** build or use the breakdown-augmented cell model
  `spec/cell-candidates.md` flags as missing. Everything measured here (OFF
  leakage, ON resistance, pre-breakdown C-V) is within the stock models'
  rated-voltage validity.
- Does **not** compute `I_prog_min`, a programming-yield Monte Carlo, or the
  ballast `I_target_max` (`spec/architecture.md` §2) — all downstream of the
  breakdown model.
- Does **not** perform the process-minimum design-rule lookup that would
  fix `spec/split-axis-plan.md`'s ratified split-axis geometry levels.
  **The `wcap`/`wacc` values used here are the committed netlists' own
  subcircuit-parameter defaults** (read out of
  `design/netlists/cell_candidateN.spice` at run time, not hand-copied) and
  their doublings — `design/README.md` is explicit that these defaults "are
  placeholders, not design values," and every record produced here repeats
  that caveat next to the numbers.
- Does **not** touch any array/MUX/sense/SPI schematic, and does not edit
  any ratified `spec/` record. `spec/architecture.md`'s `I_ref` inequality
  stays symbolic; this experiment only supplies the two numbers §3/§4 name
  as inputs to it.

## What is measured, and how

Three testbenches share the same underlying trick: hold the cell's access
device (`X1`, instantiated straight from the committed netlist) fully ON so
its internal node (`X1.CN`) has no DC drop relative to `BL`, then read the
quantity of interest off whichever external terminal makes it observable.
This is the same technique `design/check-netlists.sh` already uses (its
`mag(i(vpl))` capacitor-current check) — this experiment extends it to a
full PVT/bias sweep and adds the OFF-state and ON-resistance measurements
`check-netlists.sh` doesn't need.

### 1. Access-device OFF-state leakage (`I_off`)

`testbench/tb_access_device.spice`, `.op` at a 3-point OFF-gate-bias sweep
(0 V, ±0.3 V around the logic rail for NMOS access devices; the logic rail
and ±0.3 V for PMOS), `BL` at the read-voltage rail, `WL` held OFF. Current
into `BL` is the OFF-state leakage.

**Methodology finding: gmin-floor-limited, not fully resolved.** The stock
`cap_*` models are a pure voltage-dependent capacitance with no DC branch at
all (`spec/cell-candidates.md`'s flagged post-breakdown-model gap). That
means the cell's internal node (`X1.CN`) has no DC path to anywhere except
the access device's own OFF-state channel conduction and its source/body
junction. A gmin sweep during development (`.options gmin` from `1e-12`
down to `1e-16`, holding everything else fixed) showed the `.op` leakage
current at deep cutoff (0 V gate bias, room temperature) tracking `gmin *
V_read` almost exactly at every tested value — i.e. the *true* subthreshold
current at that bias is below `1e-16` A, and the simulator's numerical floor
is what the testbench actually reports. Below `gmin=1e-17` the solver failed
to converge in a reasonable time (a real robustness concern across
hundreds of corners, not something to chase further for this experiment).

`gmin=1e-13` was fixed for the whole experiment: fast, converges cleanly at
every corner tried, and low enough that the fast/hot corner (where
subthreshold leakage should be largest) shows real, corner-dependent
movement rather than a flat floor value (compare `sim/cell-device-
characterization/corners/<record-id>/*/ff_125c_bl1p10v.log` across
candidates — the numbers differ candidate-to-candidate and are well above
`gmin * V_read`, unlike the cold/typical corners). Every `I_off` figure in
every record is therefore reported explicitly as **an upper bound set
jointly by the true device leakage and this numerical floor**, not a fully
resolved subthreshold current. This is the conservative direction for
`I_ref > I_sneak_max`: overestimating sneak leakage only makes the derived
bound safer, never falsely reassuring — consistent with the issue's own
instruction to state the result as a lower bound on `I_ref`, not a final
number.

### 2. Access-device ON-state series resistance (`R_on`)

Same testbench, continued: `WL` altered to the candidate's "fully on" bias
(matching `design/tb/tb_cell_candidateN.spice`'s own convention — 3.3 V for
Candidates 1/3's 6 V devices, 5.0 V for Candidate 2's 10 V LDMOS), then a
small-signal AC excitation on `BL`. For an ideal access-device resistance in
series with an ideal capacitor, `Re(V(BL)/I(BL))` equals the resistive term
exactly, independent of frequency and of the capacitor's value — which is
what lets `R_on` be measured through the same capacitor that blocks the DC
path `I_off` needs.

**Methodology finding: needs a high enough measurement frequency.** The
first version of this testbench measured at 1 kHz (matching
`check-netlists.sh`'s frequency) and got a series resistance three to five
orders of magnitude too high. Root cause: `gmin`'s tiny conductance, in
*parallel* with the capacitor's own admittance at the node between the
access device and the capacitor, is not a small correction to `Re(Z)` — for
a mostly-reactive parallel admittance, adding a parallel conductance `G`
injects a *new* real term, `Re(1/(G+jB)) = G/(G²+B²)`, which is large
precisely when the capacitor's own susceptance `B = ωC` is small (i.e. at
low frequency or small `C`). Verified with a synthetic ideal-R+C-plus-
parallel-leak testbench (not committed) reproducing the same effect exactly.
Raising the measurement frequency to 10 MHz, and confirming with a `gmin`
sweep down to `1e-15` S that the extracted `R_on` stops moving once
frequency is high enough, gives a value independent of both — that stable
value is what every record reports.

**This independence is only approximate, not exact.** Once the `gmin`/
frequency effect above is settled, `R_on` still shows a small (single-digit-
percent to ~10%, checked by comparing the `min` and `2x` capacitor-geometry
sub-configurations at a fixed access-sizing level and corner) sensitivity to
the capacitor's own geometry — because the real circuit is not a pure
isolated series R+C: the access device's own parasitic `Cgd`/`Cdb` sit in
parallel with the `BL` node, unaffected by the capacitor's geometry, so the
network `R_on` is extracted from is `R_on + C_moscap` in series, *loaded* by
those fixed parasitics in parallel — not a clean two-element pair. `R_on` is
therefore reported per (access-sizing, capacitor-geometry) sub-configuration
rather than asserted geometry-invariant, and the record's headline number is
the worst (largest) value across all four sub-configurations at the named
corner, which is the conservative choice for a series-resistance term.

### 3. Pre-breakdown capacitor C-V and leakage

`testbench/tb_moscap_cv.spice`: same fully-ON access device, but here `BL`
is held **fixed at 0 V** and the capacitor's own gate(`CN`)-to-plate(`PL`)
bias is swept by driving `PL` instead, across `{-V_rated, -V_rated/2, 0,
+V_rated/2, +V_rated}` (with the opposite sign, since `V(CN) - V(PL) ≈ 0 -
V(PL)`). A small-signal AC probe on `PL` (matching `check-netlists.sh`'s
`mag(i(vpl))` technique) gives the incremental capacitance at each bias
point; a `.op` at the same point gives the DC "leakage" (expected to be a
`gmin`-floor value again, for the same reason as `I_off` — the stock model
has no leakage branch to measure).

**Methodology finding: why `PL`, not `BL`, is the swept terminal.** The
first version of this testbench swept `BL` directly across the rated range.
For the NMOS-access candidates this drove `BL` (the access device's drain)
well below the grounded p-substrate at the negative end of the sweep,
forward-biasing the drain/body junction diode — a large, real diode current
completely unrelated to the capacitor, dominating the "leakage" measurement
by many orders of magnitude. `PL` has no such junction in the stock model
(it is a bare two-terminal capacitor node), so sweeping it instead reaches
the identical relative bias without ever stressing the access device.

**Methodology finding: `WL`'s "fully on" bias is polarity- and reference-
dependent.** With `BL` now fixed at 0 V, reusing Candidate 3's access-
testbench "on" bias (0 V, chosen against that testbench's `BL ≈ V_read ≈
1 V`) left `V_gs = V(WL) - V(BL) = 0 - 0 = 0` — not on at all, and `X1.CN`
floated away from `BL` instead of tracking it (confirmed by printing
`V(X1.CN)`, which came out near 3.3 V instead of near 0 V). Candidate 3's
moscap-bench "on" bias is `-3.3 V` instead, mirroring how the NMOS
candidates use a large *positive* `WL` against their `BL = 0 V` reference.
`run_experiment.py`'s `Candidate.moscap_wl_on` field carries this
distinction explicitly rather than reusing `wl_on` for both testbenches.

### Corner grid

- **Access-device bench**: `typical, ff, ss, fs, sf` MOS process sections
  (`sm141064.ngspice` for Candidates 1/3; `smbb000149.ngspice` for
  Candidate 2's `nfet_10v0_asym`, which defines the identical five section
  names) × `{-40, 27, 125} °C` × read-voltage rail at `{0.9, 1.0, 1.1} ×
  V_read_nominal` (nominal ±10%, named `bl<v>v` per `sim/README.md`'s
  node-supply convention) = 45 points, ×4 (access-sizing × capacitor-
  geometry) sub-configurations = 180 raw logs per candidate.
- **Capacitor bench**: `moscap_typical, moscap_ff, moscap_ss` × `{-40, 27,
  125} °C` = 9 points (`nosupply` — the swept quantity is the capacitor's
  own internal bias, not an external rail), ×4 sub-configurations = 36 raw
  logs per candidate. The access device's own MOS section is fixed at
  `typical` here (its ON conduction is not the quantity under test).
- **216 raw logs per candidate, 648 total** — well above the 15-point-per-
  device-family floor the acceptance criteria set (5 process × 3 temp = 15
  already, before the ×3 supply and ×4 sub-configuration multipliers).
- **PDK revision**: `open_pdks c6d73a35f524070e85faff4a6a9eef49553ebc2b`
  (`gf180mcuD`), verified present via `klt pdk list` at build time (the pin
  then in force; the forward-looking pin is now `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, see
  `spec/pdk-pin-decision.md`; this record's runs are not re-qualified here). Re-verify before trusting a record produced on a different
  machine.

### Placeholder stimulus values (not ratified spec numbers)

None of the following are fixed by any ratified `spec/` record; they are
this experiment's own reasonable choices, documented so a later record can
supersede them once real numbers exist:

- **Read-voltage rail nominal**: 1.0 V (±10% swept, per the corner grid
  above). `spec/architecture.md` §4 requires the read voltage to be "well
  below any disturb/breakdown threshold" but does not fix a number.
- **Logic-rail level for the OFF-bias sweep**: 3.3 V, matching
  `spec/architecture.md` §5's assumed SPI-side digital I/O voltage.
- **`WL` "fully on" bias**: 3.3 V (Candidates 1/3's access testbench), 5.0 V
  (Candidate 2), matching the bias `design/tb/tb_cell_candidateN.spice`
  already uses for the identical purpose; -3.3 V for Candidate 3's
  capacitor-bench "on" bias (see the methodology finding above for why it
  differs from the access-bench value).
- **Access-device sizing / capacitor geometry "min"/"2x" levels**: the
  committed netlist's own subcircuit-parameter defaults (`wcap`, `lcap`,
  `wacc`, `lacc`, parsed out of `design/netlists/cell_candidateN.spice` at
  run time) and a ×2 width (same length) doubling — matching
  `design/check-netlists.sh`'s own "arbitrary base geometry, doubled"
  convention. **These are explicitly not** `spec/split-axis-plan.md`'s
  ratified "process-minimum"/"2x" split-axis levels; every record says so.

### A finding worth flagging for future overdrive/level-shifter work

At the `sf` process corner (slow-N/fast-P is the read-out for Candidates
1/2; the `pfet_06v0_sf` section skews Candidate 3's PMOS access device),
Candidate 3's access-testbench overdrive (`V_gs = WL(0V) - BL(V_read) ≈
-1.0 to -1.1 V`) sits close enough to that corner's threshold voltage to
produce `R_on` in the 1–10 MΩ range — two to four orders of magnitude above
every other corner for that candidate (confirmed not a numerical artifact:
sweeping `WL` further negative at that exact corner recovers a smooth,
expected decrease in `R_on`, e.g. ~20 kΩ at `V_gs = -1.4 V`; see the
`sf_27c_bl1p10v.log` raw logs). This does not contaminate the record's
headline `R_on` figure (drawn from the slow/cold/low-supply corner, `ss` not
`sf`), but it is a real, useful signal that a flat placeholder gate
overdrive is not uniformly "fully on" across every process corner — exactly
the kind of number `spec/architecture.md` §1.1's "controlled overdrive" /
§3 item 1's "actively driven to a defined level" level-shifter design work
will need once it starts sizing real overdrive margins.

## Derived bounds

Per candidate (= per `spec/split-axis-plan.md` region):

- **`I_sneak_max = (N-1) × I_off = 31 × I_off`** (N=32, ratified
  2026-08-20), evaluated at the **fast/hot/high-supply** corner (`ff`,
  125 °C, `V_read × 1.1`) — the corner `spec/architecture.md` §4 names for
  the aggregate unselected-device leakage term, using the worst (maximum)
  `I_off` across the four access-sizing/capacitor-geometry sub-
  configurations at that corner. Reported as the `I_ref > I_sneak_max`
  **lower bound only** — `I_ref < I_prog_min` stays open, out of scope.
- **Selected-cell `R_on`** at the **slow/cold/low-supply** corner (`ss`,
  −40 °C, `V_read × 0.9`) — the corner §4 names for the selected-cell series
  resistance term, using the worst (maximum) `R_on` across the same four
  sub-configurations. Not itself a pass/fail (no ratified threshold exists
  yet); it is the number a future decision record needs to size `I_ref`'s
  other side against.

## Running it

The PVT grid runs as a `klt sim` campaign (next section); with
`KLT_SIM_BACKEND=batch` exported (as on a dispatch worker), it goes to the Spot
batch fleet and is never looped locally (with `KLT_SIM_BACKEND` unset on a
fresh shell, `klt` defaults to `local`):

```bash
export KLT_SIM_BACKEND=batch
python3 sim/cell-device-characterization/klt/run_klt_campaign.py
python3 sim/cell-device-characterization/klt/run_klt_campaign.py --candidates 1,2,3
```

The legacy local-ngspice driver (one `ngspice -b` per corner, `-j 8`) was
retired by operator ruling (#158). Its committed `corners/`, `netlist-snapshots/`
and `records/` remain as append-only evidence, and `run_experiment.py` is kept
as the shared candidate/parameter library that
`sim/cell-breakdown-model/run_experiment.py` loads. Every klt run mints a
fresh run id and never overwrites existing evidence, per `sim/README.md`'s
append-only rule.

## klt sim campaign (issue #63)

The access-device bench (sections 1 and 2 above: `I_off`, `R_on`) is also
expressed as a checked-in `klt sim` request set, so the PVT corner grid goes to
the Spot batch fleet as a request instead of being looped locally. The legacy
local-ngspice driver is retired (#158); the klt campaign is now the way to
regenerate this bench, and the committed legacy logs/records remain the
append-only reproduction baseline.

```bash
python3 sim/cell-device-characterization/klt/mk_klt_requests.py        # regenerate klt/requests/ (deterministic)
python3 sim/cell-device-characterization/klt/run_klt_campaign.py       # submit (backend from $KLT_SIM_BACKEND) + ingest
python3 sim/cell-device-characterization/klt/run_klt_campaign.py --resume klt/runs/<run-id> --candidates 1,3   # re-submit only requests with no usable report
python3 sim/cell-device-characterization/klt/run_klt_campaign.py --ingest-only klt/runs/<run-id>
```

Submissions go through the shared `sim/harness/klt.py` wrapper: while the
campaign is still running, a fleet refusal (`BATCH_MAX_CONCURRENT_INSTANCES`,
`batch_no_capacity`) is retried as the same request with bounded backoff
(`K.BACKOFF`), never replayed locally. If the run is interrupted anyway (or
the retry budget runs out), `--resume` re-submits only the requests whose run
directory holds no usable report -- completed reports and their sidecars are
kept as committed, and ingest reuses the same run ID. `--ingest-only`
submits nothing.

- **Requests**: `klt/requests/c<N>_access-<sizing>_cap-<geometry>/{body.spice,ioff.json,ron.json}`.
  The cell is the committed `design/netlists/cell_candidate<N>.spice`,
  `.include`d unchanged; the testbench sources and `gmin=1e-13` match the
  legacy template.
- **Axes expressed as `klt sim` corners**: access-device MOS process (a bundle
  with `moscap_typical`, as in the legacy deck; Candidate 2 additionally binds
  `smbb000149`), temperature (-40/27/125), read voltage on BL
  (0.9/1.0/1.1 V, `corners.supply_v: vbl`). For `I_off` the three OFF-gate
  biases are enumerated alongside the read voltage in the same `supply_v`
  lists (`vbl` and `vwl` move by index, so the 3x3 product is spelled out).
- **Axes not expressed as corners**: access sizing and capacitor geometry. They
  are sub-circuit instance parameters, which `alter` cannot re-evaluate, so each
  (sizing, geometry) pair is its own `body.spice` and request pair. This is the
  "no parameter corner axis" gap already open on the klayout-tools tracker;
  a generic comment was added there.
- **Two requests per sub-configuration** (one analysis per request): `ioff`
  (single-point `dc` sweep standing in for `.op`, 135 units) and `ron` (`ac`
  at 10 MHz, 45 units). `.meas` cards return raw quantities (signed `i(vbl)`;
  real/imaginary parts of the branch current and BL voltage); `|I_off|` and
  `R_on = Re(V/(-I))` are computed at ingest. `measurements[].expr` was tried
  first and abandoned: on the batch backend the fleet runner rejected every
  multi-unit request using it (single-unit passed), so the `.meas` form is
  used.
- **Capacitor C-V bench (section 3) is not migrated.** It needs two analyses
  (`op` + `ac`) per point and five swept bias points; it remains in the legacy
  harness.
- **Output**: a new run directory `klt/runs/<run-id>/<sub-config>/<ioff|ron>/report.json`
  (the `-o` klt report, with its `coverage.checked` / `coverage.inapplicable` id
  lists replaced by their counts -- `harness.report.elide_coverage`; every
  measurement value, corner status, diagnostic, `environment`, `provenance` and
  coverage counter is kept, and the sha256 of klt's full stdout is committed
  beside it as `report.json.sha256`) and one append-only per-region record
  `records/<run-id>-c<N>.md`. Records list every sub-configuration separately
  with the full process x temperature x read-voltage grid; the region headline
  is a worst case across that region's own four sub-configurations, never an
  average, and nothing aggregates across regions.

### Result of run `20261009-014137-8d6e70b`

Reproduction against the legacy records, stated tolerance **1 % relative**
(every one of 180 grid values per region, plus the two headline numbers):

| Region / candidate | `I_sneak_max` klt vs legacy | `R_on` klt vs legacy | max deviation, grid I_off / R_on | within tolerance |
|---|---|---|---|---|
| I / 1 | 9.8192e-12 A vs 9.8191e-12 A | 1.4466e+04 ohm vs 1.4466e+04 ohm | 6.1e-04 / 6.1e-06 | yes |
| II / 2 | not resolved | not resolved | n/a | **no** |
| III / 3 | 1.3956e-11 A vs 1.3956e-11 A | 1.0981e+03 ohm vs 1.0980e+03 ohm | 5.8e-04 / 5.2e-04 | yes |

(The sub-0.1 % residual is the legacy logs' 7-significant-figure print; both
sides are the same ngspice 46 bench.)

**Candidate 2 failed on the fleet in this run; no local fallback was run.**
Every Candidate 2 request came back as `batch_job_failed` ("finished 'failed'
without a usable report: job command exited 1") for every unit. Isolation
probes at the time (each a tiny batch or single-corner local request): the same
request passed as a single unit on the fleet, passed multi-unit on
`local-parallel`, and returned an ordinary per-corner netlist error when the
per-section model library (`smbb000149`) was removed. Candidate 2 is closed
out by the follow-up runs below.

Separately, the first submission attempt hit the fleet's shared concurrency
cap for several Candidate 1 / Candidate 3 requests (verbatim in
`klt/runs/<run-id>/submit-errors.attempt1.txt`: "8 instance(s) already running
+ 1 requested exceeds BATCH_MAX_CONCURRENT_INSTANCES=8"); those requests were
re-submitted to the batch backend one at a time with `--resume` and all
passed.

### Follow-up runs: Candidate 2 (2026-10-13)

The installed client is `klt 0.7.1.dev256`; the fleet runner image runs
`klt 0.7.0` and **refuses a newer client**. Run `20261013-165427-b0bb935`
(client 0.7.1.dev256, backend `batch`, all 8 Candidate 2 requests) therefore
failed on every unit with, verbatim: `batch job ... finished 'failed' (job
command exited 87): the job's klt reported: the fleet runner runs klt 0.7.0 but
the submitting client is 0.7.1.dev256+gaf7a43de415a -- the request was not run
(update the runner image or use a compatible client)`. That run and its record
(`records/20261013-165427-b0bb935-c2.md`, all sub-configurations "NOT RESOLVED")
are kept as append-only evidence. The same warning also reported that the
requests exceed the fleet's 3600 s whole-job ceiling on the conservative serial
bound (135 and 45 units x 300 s); the jobs nevertheless completed (see below),
so it is advisory, but `request.remote.hosts` sharding is the stated remedy if
a run ever times out.

Run `20261013-170230-b0bb935` re-submitted the identical checked-in Candidate 2
requests to the batch backend with a version-matched client
(`KLT_CMD='uvx --from klayout-tools==0.7.0 klt' python3 klt/run_klt_campaign.py --candidates 2 --parallel 1`;
`KLT_CMD` is a launcher override added to the script, default `klt`). All 8
requests passed: ioff 135/135 and ron 45/45 corners per sub-configuration,
no errored or missing corner. Record:
`records/20261013-170230-b0bb935-c2.md` (job ids in the record and in each
report's `environment.remote`). This also means the earlier "per-section
library fails multi-unit on the fleet" diagnosis was not reproduced with a
matching client; the cause of the earlier exit-1 failures was not re-isolated
and should not be assumed to be version skew.

| Region / candidate | `I_sneak_max` klt vs legacy | `R_on` klt vs legacy | max deviation, grid I_off / R_on | within 1 % |
|---|---|---|---|---|
| II / 2 | 7.2887e-09 A vs 7.2887e-09 A | 6.5490e+01 ohm vs 65.49 ohm | 7.0e-05 / 4.1e-07 | yes (180 grid values) |

With this, the access-device bench reproduces the legacy `I_sneak_max`
(31 x I_off at `ff_125c_bl1p10v`) and `R_on` (`ss_-40c_bl0p90v`) for all three
candidates within 1 % relative (Candidates 1/3 from run `20261009-014137-8d6e70b`,
Candidate 2 from `20261013-170230-b0bb935`). These are the named fast/hot and
slow/cold corners, maximised within each region only; not a global maximum and
not an average across regions or sub-configurations. No absolute floor was
needed: every legacy value is far above zero (gmin-floor-limited I_off,
>= 1e-13 A scale, compared relatively). The capacitor C-V bench remains
unmigrated.

## Post-layout probe (issue #447)

`klt/post-layout/` re-runs the same bench (I_off, R_on, at the two named bound
corners only) as **paired** `klt sim` requests: one leg on the cell's
fixed-geometry `layout/<cell>/lvs_reference.spice`, one leg on the
`klt pex`-extracted netlist of the drawn GDS (`layout/<cell>/pex/`). It is a
separate probe with its own README, request generator and run records -- see
`klt/post-layout/README.md` (this section is only the pointer). Nothing in it
grades or cites a T1 row; it exists to find out whether the item-7 route works
for these devices at all.
