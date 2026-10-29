# Record <record-id>

<!-- Run 3 direct-pad chip only (spec/run3-bench-plan.md). Not checked by scripts/check_measurements.py. -->
<!-- Copy to measurements/run3/records/<record-id>.md and fill every field. -->
<!-- One record = ONE measurement cell M1..M8 (spec/run3-bench-plan.md section 1). -->
<!-- Never edit a committed record; supersede it with a new one. -->

- **Record ID**: <record-id>
- **Quantity**: <vbd_yield | resistance | read_margin>
- **Claim**: <spec section cited, e.g. spec/run3-bench-plan.md#4-vbd-distribution>
- **Measurement cell**: <M1 | ... | M8, exactly one>
- **Group**: <C1-Amin | C1-A2x | C2-Amin | C3-Amin>
- **Candidate**: <1 | 2 | 2F (C2-fallback, no access device) | 3, must match the group>
- **Capacitor geometry**: <Gmin | G2x>
- **Access sizing**: <Amin | A2x>
- **Expected state**: <resistance and read_margin only: programmed | unprogrammed | partial_conduction>
- **Source vbd_yield record**: <resistance and read_margin only: record id>
- **Die**: <die identifier>
- **Temperature**: <measured, with unit>
- **Ramp rate**: <single bench value, with unit; same for every instance>
- **Compliance current**: <source setting, with unit>
- **V_max**: <ramp ceiling, with unit>
- **I_det / I_prog_thr / I_unprog_hi / drift criterion**: <values and the record that set them>
- **Read condition**: <bias, temperature, unselected-PL policy (a) hi-Z | (b) driven to BL>
- **Group sneak stage**: <resistance and read_margin only: fraction of group programmed at read time>
- **I_floor**: <WL-off floor reading, with unit>
- **R_route correction**: <interval, source, OPEN-B6 status>
- **Replicate count**: <n, equals the number of rows in the table below>
- **CI method**: <e.g. Clopper-Pearson exact, two-sided, 95%>
- **Counts**: <outcome=int, ... for every outcome that occurs>
- **Fraction**: <programmed/n_eff, and (programmed+partial_conduction)/n_eff>
- **CI**: <[lo, hi], or undefined when n_eff = 0>
- **Notes**: <instance order, reads and exposure per instance, anomalies>
- **Supersedes**: <earlier record id, or "(none -- first record for this measurement cell)">
- **Timestamp / author**: <ISO-8601 UTC, author>

## Per-instance outcomes

<!-- Outcomes: programmed, not_programmed, partial_conduction, no_breakdown_at_vmax (V_bd censored, counts as not_programmed), -->
<!--           excluded_preread_high, excluded_setup_error. A partially conducting cell is never programmed or not_programmed. -->
<!-- I_pre / I_post1 / I_post2: floor-subtracted read currents, with unit. V_bd: voltage at I_det, or ">V_max". -->

| pl_pad | measurement_cell | candidate | geometry | sizing | ramp_rate | compliance | V_bd | I_pre | I_post1 | I_post2 | outcome |
|---|---|---|---|---|---|---|---|---|---|---|---|
| <PL_...> | <M#> | <candidate> | <geometry> | <sizing> | <ramp_rate> | <compliance> | <V_bd> | <I_pre> | <I_post1> | <I_post2> | <outcome> |
