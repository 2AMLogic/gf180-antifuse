# sim/characterization-report/

Reproducible per-split **device characterization** report. Pure
post-processing of committed `sim/cell-device-characterization/` evidence: no
simulation, no PDK, no ngspice, stdlib Python only.

**Scope.** This first report covers cell *device* characterization only
(access-device OFF leakage and ON resistance, pre-breakdown capacitance, the
stock-model leakage floor). It is not a whole-block report. **Programming
yield, full sense margin and retention are `unmeasured`** and are emitted as
such in every bundle until a supported input type exists (#63 and #66 would
supply native corner envelopes and yield curves; neither is required here).

## Files

| Path | Role |
|---|---|
| `inputs.json` | The explicit input manifest: selected record ids, per-record sha256 pins (record file, netlist snapshot, digest over every raw log), the expected PVT/sub-configuration grid, stimulus levels, and the pinned PDK revision. |
| `build_report.py` | The generator. |
| `bundles/<bundle-id>/report.json`, `report.md` | The emitted bundle. `bundle-id` is the first 12 hex digits of the sha256 of `inputs.json`; content is deterministic (no timestamps). |
| `tests/test_build_report.py` | Unit tests on a synthetic tree (two regions with different values, missing/failed/stale/superseded/incompatible/hash-mismatch inputs) plus a byte-for-byte check of the committed bundle. |

## Use

```sh
python3 sim/characterization-report/build_report.py --check      # clean checkout reproduces the bundle
python3 sim/characterization-report/build_report.py              # write a bundle (refuses to overwrite a differing one)
python3 sim/characterization-report/build_report.py --print-pins # current hashes, for editing inputs.json
python3 -m unittest discover -s sim/characterization-report/tests
```

Bundles are append-only. Changing any selection or pin in `inputs.json` mints
a new bundle id; old bundles stay. Changing generator output for an existing
`inputs.json` requires bumping `generator_version` in both places.

## Policies

- **Input selection.** Explicit only: a record is consumed solely because
  `inputs.json` lists it, pinned by hash. No globbing, no "latest wins".
- **Supersession.** A selected record is stale if another committed record's
  `Supersedes` field names it, or if its netlist snapshot no longer equals the
  current `design/netlists/cell_candidateN.spice`. A stale, missing,
  hash-mismatched or incompatible (PDK revision, record id, region claim) record
  is excluded from the values and disclosed; a corner whose log is missing or
  has unparsed measurements is disclosed as `missing_corner` / `failed_corner`.
  Any such disclosure, and any unmeasured quantity, keeps `status` at
  `incomplete`.
- **No pooling.** Values are keyed region x access-sizing x capacitor-geometry
  x corner, each with a `log#measurement` source locator. The only reductions are
  worst-case selections *within* one sub-configuration, which name the corner and
  source of the extreme. The record headlines (which take a worst case across
  the four sub-configurations) are recomputed from the raw logs as a consistency
  check only.
- **Caveats carried through.** I_off is a gmin-floor upper bound; capacitor
  "leakage" is the stock model's structural zero, not oxide leakage; sizing and
  geometry levels are netlist defaults and doubling, not the ratified split-axis
  levels; the source runs recorded a dirty working tree.

## T1 item 8

The generator can print a generic item-8 envelope (`--emit-envelope`) but
refuses unless the report is `complete` and its item-8 contract is met. Neither
holds (programming yield, sense margin and retention are unmeasured, and there
is no digital-partition content), so no envelope exists and `signoff/` is
unchanged: item 8 stays `unmet`.
