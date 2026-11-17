# spec/

Ratified targets, the split-axis plan, and decision records. Spec changes land here with a DR; agents never relax a ratified spec to make results pass.

## Decision records

- [`cell-candidates.md`](cell-candidates.md) — cell candidates
- [`split-axis-plan.md`](split-axis-plan.md) — grid size N and split-axis plan
- [`architecture.md`](architecture.md) — program/read architecture
- [`program-voltage-decision.md`](program-voltage-decision.md) — on-die vs. off-die program voltage
- [`supply-domains-decision.md`](supply-domains-decision.md) — supply-domain inventory (supply and return nets, domain-crossing rule, open items)
- [`pdk-pin-decision.md`](pdk-pin-decision.md) — open_pdks pin and fail-visible PDK revision check
- [`candidate3-read-bias-decision.md`](candidate3-read-bias-decision.md) — Candidate 3 (Region III) read bias: n-well tied to the read rail
- [`run3-test-chip-floorplan.md`](run3-test-chip-floorplan.md) — Run 3 quarter-slot test chip: instance counts, pad budget, core-area budget (proposed)
- [`run3-bench-plan.md`](run3-bench-plan.md) — Run 3 test chip bench plan: V_bd, resistance and read-margin extraction for direct-pad cells (proposed)
- [`run3-bench-fixture-requirements.md`](run3-bench-fixture-requirements.md) — Run 3 bench fixture needs on the pad ring, delivery form (open) and measurement route (proposed)
- [`run3-c2-fallback-proposed.md`](run3-c2-fallback-proposed.md) — Run 3 fallback variant: bare-capacitor Candidate 2 (`2F`), native-runset census and cost comparison (proposed)
- [`capacitor-geometry-decision.md`](capacitor-geometry-decision.md) — capacitor-geometry split levels: Minimum and 2x-area W/L per moscap device (implements the ratified "process-minimum legal W/L")
- [`pdk-pcell-drc-exception-decision.md`](pdk-pcell-drc-exception-decision.md) — scoped DRC exception for findings inside unmodified PDK PCell geometry only (operator ruling 2026-11-15, #299)
