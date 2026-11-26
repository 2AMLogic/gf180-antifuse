# measurements/

Silicon results, recorded per grid region — never averaged across splits.

Definitions of the three recorded quantities (programming yield, read margin,
retention), their pass/fail criteria, SPI sequences and required fields live in
`spec/measurement-matrix.md`. This directory holds the evidence.

## Layout

- `TEMPLATE.md` — record template. Copy it; do not fill it in place.
- `records/<record-id>.md` — one file per record (create the file; the
  directory is kept by `records/.gitkeep`).
- `TEMPLATE-run3.md` — template for the Run 3 direct-pad chip (no SPI path).
- `run3/records/<record-id>.md` — one file per Run 3 record, one record per
  measurement cell M1..M8 and quantity (V_bd yield, resistance, read margin),
  keyed by PL pad name. Defined in `spec/run3-bench-plan.md`; the format check
  below does **not** cover this directory (it is SPI-specific). Results stay
  per measurement cell; no record or table pools cells.

## One record = one measurement cell

A record covers exactly one (region x capacitor geometry x access sizing x
pulse condition) combination, plus one read condition (read margin) or one
stress point (retention) and one expected state (programmed or unprogrammed)
where those apply. It states the replicate count `n`, lists every replicate's
raw outcome (excluded ones too), and names the confidence-interval method.
Every per-cell row repeats its own region, candidate, geometry, sizing and
condition tags, so a row pooled in from another split is detectable.
Cross-split comparisons are reports built from several records, never a
record. An aggregate across splits is a bug, not a result.

Retention stress points are OPEN (`spec/measurement-matrix.md`, OPEN-R1 to
OPEN-R5); no retention record can be written until they are set by a
follow-up decision record.

## Format check

```
python3 scripts/check_measurements.py                 # checks measurements/records
python3 scripts/check_measurements.py --base origin/main
python3 -m unittest tests.test_check_measurements     # the check's own tests
```

It fails on: a header field holding more than one value or a pooled word
(`all`, `pooled`, a list), a candidate not matching its region, any table row
whose tags differ from the record header, duplicate or out-of-range cells
(row/col 0..31, N=32 per `spec/split-axis-plan.md`), a replicate count or
declared counts or fraction not matching the table, unfilled template
placeholders, and (with `--base`) any modification, rename or deletion of a
record that exists at the base ref.

## Append-only

Same discipline as `sim/`: records are never edited or deleted once committed.
A re-measurement or correction is a new record whose `Supersedes` names the
earlier one.
