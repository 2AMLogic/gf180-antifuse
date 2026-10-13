# Record <record-id>

<!-- Copy to measurements/records/<record-id>.md and fill every field. -->
<!-- One record = ONE measurement cell (spec/measurement-matrix.md section 1). -->
<!-- Never edit a committed record; supersede it with a new one. -->
<!-- Delete the lines of this block that do not apply to the quantity. -->

- **Record ID**: <record-id>
- **Quantity**: <yield | read_margin | retention>
- **Claim**: <spec section cited, e.g. spec/measurement-matrix.md#2-programming-yield>
- **Region**: <I | II | III>
- **Candidate**: <1 | 2 | 3, must match the region>
- **Capacitor geometry**: <min | 2x>
- **Access sizing**: <min | 2x>
- **Pulse condition**: <condition id from the campaign plan, one value>
- **Read condition**: <read_margin and retention only: one condition id>
- **Stress point**: <retention only: one stress-point id>
- **Expected state**: <read_margin and retention only: programmed | unprogrammed>
- **Source yield record**: <read_margin and retention only: record id of the yield record>
- **Die**: <die identifier>
- **Temperature**: <measured, with unit>
- **VPP**: <bench level used to program, with unit>
- **PULSE_WIDTH code**: <register value used to program>
- **Replicate count**: <n, equals the number of rows in the table below>
- **CI method**: <e.g. Clopper-Pearson exact, two-sided, 95%>
- **Counts**: <outcome=int, ... for every outcome that occurs>
- **Fraction**: <k/n_eff>
- **CI**: <[lo, hi], or undefined when n_eff = 0>
- **Notes**: <program order, array fraction programmed at read time, anomalies>
- **Supersedes**: <earlier record id, or "(none -- first record for this measurement cell)">
- **Timestamp / author**: <ISO-8601 UTC, author>

## Per-cell outcomes

<!-- Columns depend on Quantity; see spec/measurement-matrix.md section 5. -->
<!-- yield:       row | col | region | candidate | geometry | sizing | pulse_condition | outcome -->
<!-- read_margin: ... | pulse_condition | read_condition | expected | outcome -->
<!-- retention:   ... | pulse_condition | stress_point | expected | outcome -->
<!-- Outcomes: yield: programmed, not_programmed, excluded_preread_high, excluded_protocol_error -->
<!--           read_margin: read_agree, read_flip, excluded_protocol_error -->
<!--           retention: retained, lost, excluded_protocol_error, excluded_pre_stress_mismatch -->

| row | col | region | candidate | geometry | sizing | pulse_condition | outcome |
|---|---|---|---|---|---|---|---|
| <row> | <col> | <region> | <candidate> | <geometry> | <sizing> | <pulse_condition> | <outcome> |
