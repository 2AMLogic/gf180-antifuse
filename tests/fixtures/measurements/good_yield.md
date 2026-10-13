# Record fixture-good-yield (format fixture, not data)

- **Record ID**: fixture-good-yield
- **Quantity**: yield
- **Claim**: spec/measurement-matrix.md#2-programming-yield
- **Region**: I
- **Candidate**: 1
- **Capacitor geometry**: min
- **Access sizing**: min
- **Pulse condition**: V1
- **Die**: fixture
- **Temperature**: fixture
- **VPP**: fixture
- **PULSE_WIDTH code**: fixture
- **Replicate count**: 5
- **CI method**: Clopper-Pearson exact, two-sided, 95%
- **Counts**: programmed=3, not_programmed=1, excluded_protocol_error=1
- **Fraction**: 3/4
- **CI**: [0.19, 0.99]
- **Supersedes**: (none)
- **Timestamp / author**: 2026-10-09T00:00:00Z, fixture

## Per-cell outcomes

| row | col | region | candidate | geometry | sizing | pulse_condition | outcome |
|---|---|---|---|---|---|---|---|
| 0 | 0 | I | 1 | min | min | V1 | programmed |
| 0 | 2 | I | 1 | min | min | V1 | programmed |
| 1 | 1 | I | 1 | min | min | V1 | programmed |
| 2 | 0 | I | 1 | min | min | V1 | not_programmed |
| 2 | 2 | I | 1 | min | min | V1 | excluded_protocol_error |
