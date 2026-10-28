# Comparison Record (PROPOSED): Program and Read Evidence at Sourced V_bd (Sensitivity Points)

**Status**: PROPOSED -- evidence for the operator. Nothing here is ratified, and
nothing here amends or relaxes a ratified spec. It answers issue #130 and
returns the lead-candidate question (`#127`) to the operator; it does not pick a
lead.
**Date**: 2026-10-28
**Scope**: Candidates 1-3 program-bias benches (`#90`/`#94`), the Candidate 3
gate/well-drive benches (`#129`) and the Candidate 3 read-bias bench (`#75`/`#92`),
re-run at the primary-sourced oxide breakdown voltages of
`docs/breakdown-vbd-sources.md` (`#128`). Antifuse physics, array and
program/sense-circuit content only.

## What these runs are, and are not

The operator ruled on `#130` (2026-10-27) that the re-run is a **labelled V_bd
sensitivity**, not a parameter update. Therefore:

- The shared `bd_ebd` in `design/breakdown/breakdown_params.spice` is **unchanged**
  (1.0e9 V/m, `assumed`; V_bd(1 us) = 8.0 / 15.2 / 7.9 V). Every other breakdown
  and filament parameter is unchanged and still `assumed`.
- Each sensitivity run overrides `bd_ebd` **per candidate, in the generated deck
  only** (`.param bd_ebd = V_bd / tox` after the wrapper include), with V_bd taken
  from the sourced BVox: `typ` = 9 / 16 / 8.8 V, `floor` = 7 / 12 / 7 V for
  Candidates 1 / 2 / 3. Stress levels (rated, 0.9x, 0.95x, 1x, 1.1x V_bd), the
  ballast (V_bd / 500 uA, placeholder) and the Weibull quantile instances follow
  that V_bd, so absolute voltages differ between cases; compare by level label.
- **Assumption**: the sourced BVox is read as the model's V_bd at t_ref = 1 us.
  BVox states no ramp or current condition, so that identification is not
  established; it is why these are sensitivity points. Measured V_bd from silicon
  replaces them later.
- No new bench was built. Records are append-only; the assumed-V_bd records are
  untouched and are the `assumed` column below.

## Evidence

| case | BL-driven `progc_*` (cell-breakdown-model) | re-tabulation (program-bias-scheme) | PL-driven `plb_*`, `plu_st` | gate/well drive (C3) | read bias `bias_op` (C3) |
|---|---|---|---|---|---|
| `assumed` | C1 `20261014-001717-86afd07`, C2 `20261014-001720-86afd07`, C3 `20261014-001723-86afd07` | C1 `20261015-081141-ece0130`, C2 `20261015-081143-ece0130`, C3 `20261015-081144-ece0130` | C1 `20261015-100043-ff07fee`, C2 `20261015-091611-ff07fee`, C3 `20261015-093632-ff07fee` | `20261021-031756-9f8fa78` | `20261014-104105-9220086` |
| `typ` | C1 `20261028-024005-84a7179`, C2 `20261028-024045-84a7179`, C3 `20261028-024125-84a7179` | C1 `20261028-035854-84a7179`, C2 `20261028-035856-84a7179`, C3 `20261028-035857-84a7179` | C1 `20261028-024025-84a7179`, C2 `20261028-024105-84a7179`, C3 `20261028-024145-84a7179` | `20261028-024205-84a7179` | `20261028-024225-84a7179` |
| `floor` | C1 `20261028-024245-84a7179`, C2 `20261028-024325-84a7179`, C3 `20261028-024405-84a7179` | C1 `20261028-035858-84a7179`, C2 `20261028-035859-84a7179`, C3 `20261028-035900-84a7179` | C1 `20261028-024305-84a7179`, C2 `20261028-024345-84a7179`, C3 `20261028-024425-84a7179` | `20261028-024445-84a7179` | `20261028-024505-84a7179` |

Every sensitivity run is 45 PVT corners per bench on the Spot batch fleet via `klt sim`
(3 moscap corners x 3 temperatures x 5 levels; `bias_op`: 5 process x 3 T x 3 rails).
The generated tables below come from `sim/program-bias-scheme/compare_vbd.py`
(reads the saved reports; no simulation), with run ids in
`sim/program-bias-scheme/vbd-sensitivity-runs.json`. Each record names the
parameter revision it used (sha256 of the unchanged parameter file plus the
per-candidate `bd_ebd` it injected) in its sensitivity bullet.

Execution notes (not results): klt 0.8 rejects the old fixed `/opt/pdk` `.lib` path
in a batch body, so these runs name this host's variant dir with `PDK_ROOT`
exported (Candidates 2 and 3 load a second model file from the body). Failed
attempts before that fix produced no evidence and were discarded unstored.
`plu_st` has non-converging corners for Candidates 2 and 3 (timeouts), as in the
assumed-V_bd records; they stay in the denominators below.

## Per candidate, per stress level

Cell format: level voltage, programmed corners / converged corners (the 9 PVT
corners of that level), converged / attempted, and the access-device terminal
pairs whose largest |V| over the transient exceeds the ratified rating at the
worst corner of that level. Levels are never merged.

### Candidate 1 (Region I), access-device rating 6 V

**BL-driven `progc_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 8.10 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 6.30 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 7.60 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 8.55 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 6.65 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 1x | 8.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 9.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | no change |
| 1.1x | 8.80 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 9.90 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | no change |

**BL-driven `progc_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 8.10 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 6.30 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 7.60 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 8.55 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 6.65 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | no change |
| 1x | 8.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 9.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | no change |
| 1.1x | 8.80 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 9.90 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | no change |

**BL-driven `progc_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | no change |
| 0.9x | 7.20 V: 9/9 conv; over rating: cj, bj, gb | 8.10 V: 9/9 conv; over rating: cj, bj, gb | 6.30 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 7.60 V: 9/9 conv; over rating: cj, bj, gb | 8.55 V: 9/9 conv; over rating: cj, bj, gb | 6.65 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 1x | 8.00 V: 9/9 conv; over rating: cj, bj, gb | 9.00 V: 9/9 conv; over rating: cj, bj, gb | 7.00 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 1.1x | 8.80 V: 9/9 conv; over rating: cj, bj, gb | 9.90 V: 9/9 conv; over rating: cj, bj, gb | 7.70 V: 9/9 conv; over rating: cj, bj, gb | no change |

**PL-driven `plb_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: none | 3.30 V: prog 0/9; 9/9 conv; over rating: none | 3.30 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.9x | 7.20 V: prog 0/9; 9/9 conv; over rating: none | 8.10 V: prog 0/9; 9/9 conv; over rating: none | 6.30 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.95x | 7.60 V: prog 0/9; 9/9 conv; over rating: none | 8.55 V: prog 0/9; 9/9 conv; over rating: none | 6.65 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 1x | 8.00 V: prog 9/9; 9/9 conv; over rating: bc, cj | 9.00 V: prog 9/9; 9/9 conv; over rating: bc, cj | 7.00 V: prog 9/9; 9/9 conv; over rating: none | floor: over ['bc', 'cj']->[] |
| 1.1x | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj | 9.90 V: prog 9/9; 9/9 conv; over rating: bc, cj | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj | no change |

**PL-driven `plb_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: none | 3.30 V: prog 0/9; 9/9 conv; over rating: none | 3.30 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.9x | 7.20 V: prog 0/9; 9/9 conv; over rating: none | 8.10 V: prog 0/9; 9/9 conv; over rating: none | 6.30 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.95x | 7.60 V: prog 9/9; 9/9 conv; over rating: bc, cj | 8.55 V: prog 9/9; 9/9 conv; over rating: bc, cj | 6.65 V: prog 9/9; 9/9 conv; over rating: none | floor: over ['bc', 'cj']->[] |
| 1x | 8.00 V: prog 9/9; 9/9 conv; over rating: bc, cj | 9.00 V: prog 9/9; 9/9 conv; over rating: bc, cj | 7.00 V: prog 9/9; 9/9 conv; over rating: none | floor: over ['bc', 'cj']->[] |
| 1.1x | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj | 9.90 V: prog 9/9; 9/9 conv; over rating: bc, cj | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj | no change |

**PL-driven `plb_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 9/9 conv; over rating: none | 3.30 V: 9/9 conv; over rating: none | 3.30 V: 9/9 conv; over rating: none | no change |
| 0.9x | 7.20 V: 9/9 conv; over rating: none | 8.10 V: 9/9 conv; over rating: none | 6.30 V: 9/9 conv; over rating: none | no change |
| 0.95x | 7.60 V: 9/9 conv; over rating: none | 8.55 V: 9/9 conv; over rating: none | 6.65 V: 9/9 conv; over rating: none | no change |
| 1x | 8.00 V: 9/9 conv; over rating: none | 9.00 V: 9/9 conv; over rating: none | 7.00 V: 9/9 conv; over rating: none | no change |
| 1.1x | 8.80 V: 9/9 conv; over rating: none | 9.90 V: 9/9 conv; over rating: none | 7.70 V: 9/9 conv; over rating: none | no change |

**unselected cell `plu_st`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 9/9 conv; over rating: none | 3.30 V: 9/9 conv; over rating: none | 3.30 V: 9/9 conv; over rating: none | no change |
| 0.9x | 7.20 V: 9/9 conv; over rating: none | 8.10 V: 9/9 conv; over rating: none | 6.30 V: 9/9 conv; over rating: none | no change |
| 0.95x | 7.60 V: 9/9 conv; over rating: none | 8.55 V: 9/9 conv; over rating: none | 6.65 V: 9/9 conv; over rating: none | no change |
| 1x | 8.00 V: 9/9 conv; over rating: none | 9.00 V: 9/9 conv; over rating: none | 7.00 V: 9/9 conv; over rating: none | no change |
| 1.1x | 8.80 V: 9/9 conv; over rating: none | 9.90 V: 9/9 conv; over rating: none | 7.70 V: 9/9 conv; over rating: none | no change |

### Candidate 2 (Region II), access-device rating 10 V

**BL-driven `progc_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 13.68 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 14.40 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 10.80 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 14.44 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 15.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 11.40 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 1x | 15.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 16.00 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 12.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | floor: programmed 0->9; over ['cj', 'bj', 'gb']->['wc', 'wb', 'cj', 'bj', 'gb'] |
| 1.1x | 16.72 V: prog 0/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 17.60 V: prog 0/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 13.20 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | floor: programmed 0->9;  |

**BL-driven `progc_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | 6.00 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 13.68 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 14.40 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 10.80 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 14.44 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 15.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 11.40 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | floor: programmed 0->9; over ['cj', 'bj', 'gb']->['wc', 'wb', 'cj', 'bj', 'gb'] |
| 1x | 15.20 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 16.00 V: prog 0/9; 9/9 conv; over rating: cj, bj, gb | 12.00 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | floor: programmed 0->9; over ['cj', 'bj', 'gb']->['wc', 'wb', 'cj', 'bj', 'gb'] |
| 1.1x | 16.72 V: prog 0/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 17.60 V: prog 0/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | 13.20 V: prog 9/9; 9/9 conv; over rating: wc, wb, cj, bj, gb | floor: programmed 0->9;  |

**BL-driven `progc_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: 9/9 conv; over rating: gb | 6.00 V: 9/9 conv; over rating: gb | 6.00 V: 9/9 conv; over rating: gb | no change |
| 0.9x | 13.68 V: 9/9 conv; over rating: cj, bj, gb | 14.40 V: 9/9 conv; over rating: cj, bj, gb | 10.80 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 0.95x | 14.44 V: 9/9 conv; over rating: cj, bj, gb | 15.20 V: 9/9 conv; over rating: cj, bj, gb | 11.40 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 1x | 15.20 V: 9/9 conv; over rating: cj, bj, gb | 16.00 V: 9/9 conv; over rating: cj, bj, gb | 12.00 V: 9/9 conv; over rating: cj, bj, gb | no change |
| 1.1x | 16.72 V: 9/9 conv; over rating: wc, wb, cj, bj, gb | 17.60 V: 9/9 conv; over rating: wc, wb, cj, bj, gb | 13.20 V: 9/9 conv; over rating: cj, bj, gb | floor: over ['wc', 'wb', 'cj', 'bj', 'gb']->['cj', 'bj', 'gb'] |

**PL-driven `plb_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: prog 0/9; 9/9 conv; over rating: none | 6.00 V: prog 0/9; 9/9 conv; over rating: none | 6.00 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.9x | 13.68 V: prog 0/9; 9/9 conv; over rating: none | 14.40 V: prog 0/9; 9/9 conv; over rating: none | 10.80 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.95x | 14.44 V: prog 0/9; 9/9 conv; over rating: none | 15.20 V: prog 0/9; 9/9 conv; over rating: none | 11.40 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 1x | 15.20 V: prog 9/9; 9/9 conv; over rating: none | 16.00 V: prog 9/9; 9/9 conv; over rating: none | 12.00 V: prog 9/9; 9/9 conv; over rating: none | no change |
| 1.1x | 16.72 V: prog 9/9; 9/9 conv; over rating: none | 17.60 V: prog 9/9; 9/9 conv; over rating: none | 13.20 V: prog 9/9; 9/9 conv; over rating: none | no change |

**PL-driven `plb_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: prog 0/9; 9/9 conv; over rating: none | 6.00 V: prog 0/9; 9/9 conv; over rating: none | 6.00 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.9x | 13.68 V: prog 0/9; 9/9 conv; over rating: none | 14.40 V: prog 0/9; 9/9 conv; over rating: none | 10.80 V: prog 0/9; 9/9 conv; over rating: none | no change |
| 0.95x | 14.44 V: prog 9/9; 9/9 conv; over rating: none | 15.20 V: prog 9/9; 9/9 conv; over rating: none | 11.40 V: prog 9/9; 9/9 conv; over rating: none | no change |
| 1x | 15.20 V: prog 9/9; 9/9 conv; over rating: none | 16.00 V: prog 9/9; 9/9 conv; over rating: none | 12.00 V: prog 9/9; 9/9 conv; over rating: none | no change |
| 1.1x | 16.72 V: prog 9/9; 9/9 conv; over rating: none | 17.60 V: prog 9/9; 9/9 conv; over rating: none | 13.20 V: prog 9/9; 9/9 conv; over rating: none | no change |

**PL-driven `plb_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: 9/9 conv; over rating: none | 6.00 V: 9/9 conv; over rating: none | 6.00 V: 9/9 conv; over rating: none | no change |
| 0.9x | 13.68 V: 9/9 conv; over rating: none | 14.40 V: 9/9 conv; over rating: none | 10.80 V: 9/9 conv; over rating: none | no change |
| 0.95x | 14.44 V: 9/9 conv; over rating: none | 15.20 V: 9/9 conv; over rating: none | 11.40 V: 9/9 conv; over rating: none | no change |
| 1x | 15.20 V: 9/9 conv; over rating: none | 16.00 V: 9/9 conv; over rating: none | 12.00 V: 9/9 conv; over rating: none | no change |
| 1.1x | 16.72 V: 9/9 conv; over rating: none | 17.60 V: 9/9 conv; over rating: none | 13.20 V: 9/9 conv; over rating: none | no change |

**unselected cell `plu_st`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 6.00 V: 6/9 conv; over rating: none | 6.00 V: 6/9 conv; over rating: none | 6.00 V: 6/9 conv; over rating: none | no change |
| 0.9x | 13.68 V: 6/9 conv; over rating: none | 14.40 V: 6/9 conv; over rating: none | 10.80 V: 6/9 conv; over rating: none | no change |
| 0.95x | 14.44 V: 6/9 conv; over rating: none | 15.20 V: 6/9 conv; over rating: none | 11.40 V: 6/9 conv; over rating: none | no change |
| 1x | 15.20 V: 6/9 conv; over rating: none | 16.00 V: 6/9 conv; over rating: none | 12.00 V: 6/9 conv; over rating: none | no change |
| 1.1x | 16.72 V: 6/9 conv; over rating: none | 17.60 V: 6/9 conv; over rating: none | 13.20 V: 6/9 conv; over rating: none | no change |

### Candidate 3 (Region III), access-device rating 6 V

**BL-driven `progc_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: prog 0/9; 9/9 conv; over rating: gb | 7.92 V: prog 0/9; 9/9 conv; over rating: gb | 6.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: prog 0/9; 9/9 conv; over rating: gb | 8.36 V: prog 0/9; 9/9 conv; over rating: gb | 6.65 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 1x | 7.90 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1.1x | 8.69 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 9.68 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | floor: over ['wc', 'bc', 'cj', 'gb']->['bc', 'cj', 'gb'] |

**BL-driven `progc_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: prog 0/9; 9/9 conv; over rating: gb | 7.92 V: prog 0/9; 9/9 conv; over rating: gb | 6.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.36 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 6.65 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1x | 7.90 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1.1x | 8.69 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 9.68 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | floor: over ['wc', 'bc', 'cj', 'gb']->['bc', 'cj', 'gb'] |

**BL-driven `progc_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: 9/9 conv; over rating: gb | 7.92 V: 9/9 conv; over rating: gb | 6.30 V: 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: 9/9 conv; over rating: gb | 8.36 V: 9/9 conv; over rating: gb | 6.65 V: 9/9 conv; over rating: gb | no change |
| 1x | 7.90 V: 9/9 conv; over rating: gb | 8.80 V: 9/9 conv; over rating: gb | 7.00 V: 9/9 conv; over rating: gb | no change |
| 1.1x | 8.69 V: 9/9 conv; over rating: gb | 9.68 V: 9/9 conv; over rating: gb | 7.70 V: 9/9 conv; over rating: gb | no change |

**PL-driven `plb_b1m`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: prog 0/9; 9/9 conv; over rating: gb | 7.92 V: prog 0/9; 9/9 conv; over rating: gb | 6.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: prog 0/9; 9/9 conv; over rating: gb | 8.36 V: prog 0/9; 9/9 conv; over rating: gb | 6.65 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 1x | 7.90 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1.1x | 8.69 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 9.68 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | floor: over ['wc', 'bc', 'cj', 'gb']->['bc', 'cj', 'gb'] |

**PL-driven `plb_b1l`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | 3.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: prog 0/9; 9/9 conv; over rating: gb | 7.92 V: prog 0/9; 9/9 conv; over rating: gb | 6.30 V: prog 0/9; 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.36 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 6.65 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1x | 7.90 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 8.80 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 7.00 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | no change |
| 1.1x | 8.69 V: prog 9/9; 9/9 conv; over rating: wc, bc, cj, gb | 9.68 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | 7.70 V: prog 9/9; 9/9 conv; over rating: bc, cj, gb | typ: over ['wc', 'bc', 'cj', 'gb']->['bc', 'cj', 'gb']; floor: over ['wc', 'bc', 'cj', 'gb']->['bc', 'cj', 'gb'] |

**PL-driven `plb_st` (intact cell)** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | 3.30 V: 9/9 conv; over rating: gb | no change |
| 0.9x | 7.11 V: 9/9 conv; over rating: gb | 7.92 V: 9/9 conv; over rating: gb | 6.30 V: 9/9 conv; over rating: gb | no change |
| 0.95x | 7.50 V: 9/9 conv; over rating: gb | 8.36 V: 9/9 conv; over rating: gb | 6.65 V: 9/9 conv; over rating: gb | no change |
| 1x | 7.90 V: 9/9 conv; over rating: gb | 8.80 V: 9/9 conv; over rating: gb | 7.00 V: 9/9 conv; over rating: gb | no change |
| 1.1x | 8.69 V: 9/9 conv; over rating: gb | 9.68 V: 9/9 conv; over rating: gb | 7.70 V: 9/9 conv; over rating: gb | no change |

**unselected cell `plu_st`** -- one row per stress level; each cell: level voltage, programmed corners / converged, converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).

| Level | assumed | typ | floor | what changed vs assumed |
|---|---|---|---|---|
| rated | 3.30 V: 4/9 conv; over rating: none | 3.30 V: 4/9 conv; over rating: none | 3.30 V: 4/9 conv; over rating: none | no change |
| 0.9x | 7.11 V: 5/9 conv; over rating: none | 7.92 V: 5/9 conv; over rating: none | 6.30 V: 5/9 conv; over rating: none | no change |
| 0.95x | 7.50 V: 5/9 conv; over rating: none | 8.36 V: 5/9 conv; over rating: none | 6.65 V: 5/9 conv; over rating: none | no change |
| 1x | 7.90 V: 5/9 conv; over rating: none | 8.80 V: 5/9 conv; over rating: none | 7.00 V: 5/9 conv; over rating: none | no change |
| 1.1x | 8.69 V: 5/9 conv; over rating: none | 9.68 V: 5/9 conv; over rating: none | 7.70 V: 5/9 conv; over rating: none | no change |

### Candidate 3 gate/well-drive benches (`gwa`: WL -3.3 V, VB 0 V; `gwb`: WL -6.0 V, VB 0 V), rating 6 V

Cells are corners with ALL six access-device pairs within the rating / attempted corners (a non-converged corner is never in rating). Per stress level; the `_b1m` / `_b1l` rows are the program-event rows.

**`gwa_st`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 9/9 | 9/9 | 9/9 |
| 0.9x | 9/9 | 9/9 | 9/9 |
| 0.95x | 9/9 | 9/9 | 9/9 |
| 1x | 9/9 | 9/9 | 9/9 |
| 1.1x | 9/9 | 9/9 | 9/9 |

**`gwa_b1m`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 9/9 | 9/9 | 9/9 |
| 0.9x | 9/9 | 9/9 | 9/9 |
| 0.95x | 9/9 | 9/9 | 9/9 |
| 1x | 0/9 | 0/9 | 0/9 |
| 1.1x | 0/9 | 0/9 | 0/9 |

**`gwa_b1l`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 9/9 | 9/9 | 9/9 |
| 0.9x | 9/9 | 9/9 | 9/9 |
| 0.95x | 0/9 | 0/9 | 6/9 |
| 1x | 0/9 | 0/9 | 0/9 |
| 1.1x | 0/9 | 0/9 | 0/9 |

**`gwb_st`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 0/9 | 0/9 | 0/9 |
| 0.9x | 0/9 | 0/9 | 0/9 |
| 0.95x | 0/9 | 0/9 | 0/9 |
| 1x | 0/9 | 0/9 | 0/9 |
| 1.1x | 0/9 | 0/9 | 0/9 |

**`gwb_b1m`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 0/9 | 0/9 | 0/9 |
| 0.9x | 0/9 | 0/9 | 0/9 |
| 0.95x | 0/9 | 0/9 | 0/9 |
| 1x | 0/9 | 0/9 | 0/9 |
| 1.1x | 0/9 | 0/9 | 0/9 |

**`gwb_b1l`**

| Level | assumed | typ | floor |
|---|---|---|---|
| rated | 0/9 | 0/9 | 0/9 |
| 0.9x | 0/9 | 0/9 | 0/9 |
| 0.95x | 0/9 | 0/9 | 0/9 |
| 1x | 0/9 | 0/9 | 0/9 |
| 1.1x | 0/9 | 0/9 | 0/9 |

### Candidate 3 read bias (`bias_op`, 45 PVT corners, 4 sizing x geometry sub-configs)

Programmed (worst filament rf_wc, `I_prog`, minimum over corners) and unprogrammed (`I_zero,f`, maximum over corners, solver-floor-limited) read currents at the sense path's worst-case corner, per read-bias scenario. The read bench has no stress level; V_bd enters only through the breakdown element's field at the read bias.

| Scenario | case | min I_prog [A] (corner) | max I_zero,f [A] (corner) | window | corners I_prog > I_zero,f | failed corners | feasible |
|---|---|---|---|---|---|---|---|
| `s0_placeholder` | assumed = typ = floor | 4.8572e-15 (`typical_27c_bl1p00v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 0.000152 | 7/45 | 0 | **NO** |
| `s1_wl_neg1` | assumed = typ = floor | 4.9626e-07 (`ss_27c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 1.55e+04 | 45/45 | 0 | **yes** |
| `s2_wl_neg2` | assumed = typ = floor | 3.9884e-06 (`ss_125c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 1.25e+05 | 45/45 | 0 | **yes** |
| `s3_vb_track` | assumed = typ = floor | 1.2477e-09 (`ss_-40c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 39 | 45/45 | 0 | **yes** |
| `s4_vb_fix1v` | assumed = typ = floor | 3.9701e-10 (`ss_-40c_bl0p90v`) | 3.4428e-11 (`ss_125c_bl1p10v`) | 11.5 | 45/45 | 0 | **yes** |
| `s5_rail1v8` | assumed = typ = floor | 1.8130e-07 (`ss_-40c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 5.67e+03 | 45/45 | 0 | **yes** |
| `s6_rail1v8_vb_track` | assumed = typ = floor | 2.3344e-06 (`ss_125c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 7.29e+04 | 45/45 | 0 | **yes** |
| `s7_vb_track_p0v3` | assumed = typ = floor | 3.8312e-11 (`ss_-40c_bl0p90v`) | 3.2000e-11 (`ff_-40c_bl0p90v`) | 1.2 | 45/45 | 0 | **yes** |
| `s8_vb_track_m0v3` | assumed = typ = floor | 2.7376e-08 (`ss_-40c_bl0p90v`) | 1.2261e-08 (`ss_125c_bl1p10v`) | 2.23 | 45/45 | 0 | **yes** |

Scenarios whose `min I_prog` or `max I_zero,f` differs from the assumed-V_bd record: **none** (read evidence is unchanged by V_bd at the digits recorded).



## What changed against the assumed-V_bd records

- **Read (Candidate 3): nothing.** Every scenario's `min I_prog`, `max I_zero,f`,
  window and per-corner count are identical to the assumed-V_bd record at the
  digits recorded, including the adopted `s3_vb_track` (window 39, 45/45 corners).
  The read bias shows no V_bd dependence in this model (the unprogrammed element
  is read at a bias far below any V_bd tested; the programmed instances are
  forced programmed). Still
  conditional on the assumed filament resistances.
- **Candidate 2:** PL-driven (`plb_*`) programs 9/9 corners at 1x and 1.1x and has
  **0 access-device pairs over rating at every level** at assumed, typ and floor
  V_bd. The BL-driven leg does not program at assumed or typ V_bd (0/9 even at
  1.1x) and programs 9/9 at floor (12 V) with `wc, wb, cj, bj, gb` over the 10 V
  rating. So the PL-driven Candidate 2 result holds across the sourced range; the
  BL-driven leg is V_bd-dependent.
- **Candidate 3:** at the program levels (1x, 1.1x) PL-driven `plb_*` still has
  `bc, cj, gb` over the 6 V rating at assumed, typ and floor V_bd; at 1.1x the
  extra `wc` excess drops out at floor (and, for the low-quantile instance
  `plb_b1l`, at typ). The gate/well-drive benches change little:
  `gwa` keeps all six pairs in rating at rated to 0.95x on the intact cell but
  not once the element programs (0/9 at 1x and 1.1x in all three cases); `gwb`
  is out of rating at every level in all three cases. The only movement is
  `gwa_b1l` at 0.95x: 0/9 (assumed, typ) to 6/9 (floor). No tried scheme holds at
  a programming level at any V_bd tested.
- **Candidate 1:** PL-driven `plb_b1m`/`plb_b1l` have `bc, cj` over the 6 V rating
  at the programming level (1x; also 0.95x for the low-quantile instance) at
  assumed and typ V_bd, and **none over at floor (7 V)**; at 1.1x they are
  over rating in all three cases. The BL-driven leg is over rating at the programming level in all three
  cases (`wc, wb, cj, bj, gb`).
- **Programming levels:** in the PL-driven and Candidate 1/3 BL-driven benches the
  programmed-corner counts move with the shifted levels (the median instance
  programs from 1x, the low-quantile one from 0.95x, in every case); this follows
  from the model's construction on a shifted V_bd and is not independent
  evidence of where silicon breaks down. The Candidate 2 BL-driven leg is the
  exception noted above.

## Limits

- All conditional on: BVox = V_bd(t_ref = 1 us) (assumption), `bd_gam`, `bd_beta`,
  filament parameters (assumed), the 500 uA placeholder ballast, the 100 fF PL
  shunt, process corners only (no Monte Carlo, no yield curve), single cell per
  deck, and the stock capacitor macros (no plate-to-well junction modelled).
- Typ-to-floor is a specification band, not a standard deviation; no
  distribution is implied.
- Candidate 3 well-junction breakdown during program mode (the `#94` reviewer
  flag, `bv` 10.5 V) is not modelled by these benches.
- Nothing here is a silicon measurement. The lead-candidate call stays with the
  operator and, per `#127`, is conditional on measured V_bd.

## Decision handoff

The lead-candidate question is returned to the operator as a ranked decision
(`loom-daemon operator-decision apply`), citing this record. This record does not
rank candidates.
