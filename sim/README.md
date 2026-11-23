# sim/ — evidence record format

This directory holds simulation testbenches and their results. Results are
**append-only evidence**: once a record is written, it is never edited or
deleted. A re-run — even one that corrects a mistake — mints a new record
with a new ID; a correction references the record it supersedes rather than
overwriting it in place.

This convention exists because CLAUDE.md commits this repo to two rules that
need a concrete schema to be enforceable:

- **Verification is the product.** No claim without a testbench. PVT corners
  on every recorded result unless the record explicitly states why a subset
  was used, and claims about programming need yield-vs-condition curves, not
  a single transient.
- **`sim/` is append-only evidence.** Re-runs get new records; records are
  never edited or deleted.

The shape of this convention (record-id/corner-id format, the record field
set, the append-only rule) is ported from the public `gf180-bandgap` canary's
`sim/README.md` and `sim/harness/` — a flow-convention reference this repo's
`CLAUDE.md` explicitly allows citing (not for antifuse-specific content, only
for gf180mcu circuit/flow conventions). This repo does **not** port that
repo's spec-line test suite, its Monte Carlo/mismatch machinery, or any
circuit-specific content — only the runner/record machinery, trimmed to what
this repo's first experiment (`sim/cell-device-characterization/`) needs.

## Directory / naming convention

Each testbench topic gets its own experiment directory:

```
sim/
  harness/                            shared PDK-resolution / record-writer
                                       machinery (pdk.py, corners.py,
                                       report.py) -- stdlib only
  <experiment-slug>/                  e.g. cell-device-characterization
    testbench/                        testbench netlist(s) used (where static)
    netlist-snapshots/
      <record-id>.spice               frozen DUT netlist for this record
    corners/
      <record-id>/
        <corner-id>.log                raw ngspice output per PVT point
    records/
      <record-id>.md                  append-only summary record
    <driver>.py                       the experiment's own CLI driver:
                                       run_experiment.py, run_bench.py, or
                                       klt/run_klt_campaign.py for
                                       cell-device-characterization (see
                                       "Cold start")
```

- **`<experiment-slug>`** — short, descriptive, kebab-case name for what is
  being verified. One directory per distinct claim/family of claims being
  tested, not per run.
- **`<record-id>`** — unique and traceable:
  `<YYYYMMDD>-<HHMMSS>-<short-git-sha>` (e.g. `20260909-231507-b6035cb`).
  Re-runs simply mint a new `<record-id>`; nothing under `records/` is ever
  edited in place.
- **`<corner-id>`** — `<process>_<temp>c_<supply>`, e.g. `ss_-40c_bl0p90v`,
  `typical_27c_bl1p00v`, `moscap_ff_125c_nosupply`. The three fields are
  separated by the **last two** underscores, so the process field may itself
  contain one:
  - **`<process>`** — the gf180mcu model-section name the testbench selects
    for that point (`typical`, `ff`, `ss`, `fs`, `sf` for a MOS-family
    device; `moscap_typical`, `moscap_ff`, `moscap_ss` for a moscap). The
    vocabulary is open: it grows with whatever `.lib` sections a testbench
    touches.
  - **`<temp>`** — junction temperature in °C, signed, suffixed `c`: `-40c`,
    `27c`, `125c`.
  - **`<supply>`** — one of:
    - `<volts>v` — a swept main supply, e.g. `2.97v`;
    - `<node><volts>v` — a swept rail that is not the main supply, e.g. this
      repo's `bl1p00v` (the read-voltage rail on the cell's `BL` node, `p`
      standing in for the decimal point so the field stays one token);
    - `nosupply` — no external rail to sweep (a device-level bench whose
      swept quantity is an internal bias, not a rail).

## Summary record format

Each record carries these fields (a subset of `gf180-bandgap`'s nine —
**Statistical convention** applies only to records that make a Monte Carlo/
distribution claim, and is omitted from the others):

- **Record ID** — matches the filename.
- **Claim** — the ratified spec line/section this record substantiates
  (`spec/<file>.md#<section>`).
- **Netlist provenance** — `schematic` (`design/...`) or `extracted`
  (post-layout, `layout/...`), plus whether the working tree was clean at
  run time.
- **Statistical convention** (records that make a Monte Carlo claim; first
  used by `sim/programming-yield/`, issue #66) — the sampler (`klt sim`
  `monte_carlo` `n`, `seed`, `vary`; the per-process seed rule, if any), the
  success criterion, the confidence-interval method (95 % Wilson), how
  non-converged or half-formed samples are counted (never silently as a
  pass: a lower and an upper yield are both given), and a banner when the
  model parameters are `assumed`. Records without a distribution claim omit
  it.
- **Corner matrix run** — the explicit PVT grid actually executed, and any
  sub-configuration axes (e.g. this repo's access-sizing / capacitor-
  geometry levels) layered on top of it. Must be the full CLAUDE.md matrix
  (−40/27/125 °C, process corners, a supply/read-voltage axis or a stated
  `nosupply` justification) unless the record states why a subset was used.
- **Result** — per-corner and derived summary values, each tied to the spec
  sentence it answers.
- **Links** — paths to the testbench(es), the frozen netlist snapshot, and
  the raw per-corner logs.
- **Timestamp / author**.
- **Supersedes** — the prior `<record-id>` this record supersedes, or
  `(none)`.

## Multi-sub-configuration experiments

`sim/cell-device-characterization/` sweeps two extra axes (access-device
sizing, capacitor geometry) on top of the PVT grid, so its raw logs live one
level deeper than the bare `corners/<record-id>/<corner-id>.log` shape above:

```
corners/<record-id>/access-<sizing>_cap-<geometry>/<corner-id>.log
```

one full corner-id grid per (access-sizing, capacitor-geometry)
sub-configuration. This is the same accommodation `gf180-bandgap` makes for
its `sim/device-*/` experiments (that repo's README: "several DUTs measured
simultaneously per corner ... does not fit today's single-grid `tb.json`
contract" — the experiment still owns its own runner and record). One
`records/<record-id>.md` is written per experiment run (here: per candidate/
region), summarizing every sub-configuration and corner it covers, not one
record per sub-configuration.

## Experiments that run through `klt sim`

`sim/array-slice-bench/` expresses its PVT grid as a `klt sim` request (so with
`KLT_SIM_BACKEND=batch`, as on the dispatch workers, it goes to the batch
fleet). It still keeps this directory's record / append-only conventions; see
its README.

## Evidence store (new runs)

Runs adopting the fleet artifact store (`sim/harness/evidence_store.py`) do
not commit raw outputs. They are staged in the git-ignored
`sim/.artifact-scratch/`, stored with `klt artifact put`, and only
`manifests/artifacts/<bench>-<run-id>.manifest.json` plus the usual
`records/<record-id>.md` (with a name/size/sha256 table per object, entry
names keeping the `<corner-id>` and any region/sub-configuration path) are
committed. The writer fails closed: no `$KLT_ARTIFACT_BROKER`, a `klt` without
`artifact put`, or an unreachable broker exits nonzero and writes nothing.
`scripts/check_artifact_manifests.py` validates manifests (`artifact:` URIs
only, no storage locators, no stored object also committed). Once the manifest
is in place the staged-from run-directory copies are deleted and emptied
directories pruned, so a successful store leaves nothing committable under the
run directory — the store holds the only copy. Re-render paths (`--render`,
`--check`, `--retabulate`) read committed bytes where they still exist and
otherwise fetch sha256-verified copies back into git-ignored scratch
(`evidence_store.fetch_run`, `klt artifact get MANIFEST#NAME`). Pre-adoption
records keep their committed bytes; nothing already under `sim/` is modified,
moved or deleted.

## Append-only rule

`records/*.md`, `netlist-snapshots/*.spice` and the committed
`corners/**/*.log` are never edited or deleted after creation. A re-run or a
correction always creates a new record with a new `<record-id>` and references
the prior one via **Supersedes** rather than overwriting it in place. This
applies even to typo fixes. (Unstaged run-dir copies of a stored run are not
part of that trail — the store holds the only copy; see "Evidence store".)

There is no automated CI enforcement of this yet (unlike `gf180-bandgap`'s
`sim/check_records.py`) — a follow-on is welcome, but standing this
convention up and its first consumer up is this issue's scope; adding a
linter is not.

## Cold start

Each experiment is run directly by its own driver, stdlib Python only, no
venv. Every one of them expresses its corner grid as `klt sim` requests
submitted through `klt`, so the drivers need `klt` on `PATH` and a
gf180mcuD install the PDK resolver finds (`PDK_ROOT` or `GF180_PDK_PATH`;
`sim/harness/pdk.py`); `ngspice` itself is needed only for local runs and
debug modes.

For fleet runs on a fresh shell, select the Spot batch backend before running a
campaign (dispatch workers already export this; without it, `klt` defaults to
`local` for the four drivers whose requests omit `"backend"` —
`array-slice-bench`, `cell-device-characterization`, `integrated-transition`,
and `program-read-legs` — while the other four pin `"backend": "batch"` in
their requests):

```bash
export KLT_SIM_BACKEND=batch
```

With that set, every campaign's grid goes to the Spot batch fleet (job id in
each report's `environment.remote`) instead of looping ngspice locally.
Commands are copyable from the repository root:

| Experiment | Command from the repository root |
|---|---|
| [array-slice-bench](array-slice-bench/README.md) | `python3 sim/array-slice-bench/run_bench.py` |
| [cell-breakdown-model](cell-breakdown-model/README.md) | `python3 sim/cell-breakdown-model/run_experiment.py` |
| [cell-device-characterization](cell-device-characterization/README.md) | `python3 sim/cell-device-characterization/klt/run_klt_campaign.py` |
| [hv-pad-protection](hv-pad-protection/README.md) | `python3 sim/hv-pad-protection/run_experiment.py` |
| [integrated-transition](integrated-transition/README.md) | `python3 sim/integrated-transition/run_bench.py` |
| [program-bias-scheme](program-bias-scheme/README.md) | `python3 sim/program-bias-scheme/run_experiment.py` |
| [program-read-legs](program-read-legs/README.md) | `python3 sim/program-read-legs/run_experiment.py` |
| [programming-yield](programming-yield/README.md) | `python3 sim/programming-yield/run_experiment.py` |

Each experiment owns its own corner grid, flags and record format rather
than being forced through one generic contract (see the
"multi-sub-configuration experiments" note above); `--help` on any driver
lists its surface, and each experiment's README covers its prerequisites
and local modes (`--probe`, `--smoke`, `--backend local`).

See [`sim/cell-device-characterization/README.md`](cell-device-characterization/README.md)
for that experiment's methodology, the two PDK/ngspice findings that shaped
its testbench design, and how to read its records.

## Derived reports

`sim/characterization-report/` holds a deterministic, hash-pinned generator that
summarizes selected committed records per region and sub-configuration without
editing them (see its README). Its bundles are append-only like records.
