# sim/hv-pad-protection/

Program-voltage (plate, `PL`) pad and protection paths of the Run 3 direct-pad
chip, simulated at PVT corners (issue #210, part of #203). The decision these
results support is the **proposed**
[`spec/hv-pad-protection-decision.md`](../../spec/hv-pad-protection-decision.md);
nothing here changes a ratified spec.

Everything is CONDITIONAL ON THE ASSUMED breakdown parameters
(`design/breakdown/breakdown_params.spice`: V_bd = 8.0 / 15.2 / 7.9 V for
Candidates 1 / 2 / 3), which are not gf180 numbers. The filament here is a
threshold switch (closes at V_bd, opens at 0.1 V_bd, 10 kOhm), not the
stochastic model: this is a pad-path rating bench, **not a programming-yield
claim** (that is `sim/programming-yield`).

## Benches (one `klt sim` request each, 45 corners, batch fleet)

Per candidate. 45 corners = 3 process (`typical`, `ff`, `ss`, with the matching
moscap, resistor and diode sections) x 3 temperatures (-40, 27, 125 C) x 5 pad
levels (0.5, 0.95, 1.05, 1.10 x V_bd, and 17.6 V = 16 V + 10 % bench overshoot).
Candidate 3 is driven negative, as in `sim/cell-breakdown-model`.

| Bench | Path from bond pad to the cell plate | Role in the decision |
|---|---|---|
| `astd_f` | standard analog pad cell `gf180mcu_fd_io__asig_5p0`: ESD diodes to `DVDD` (5.5 V, 0.5 ohm) and `DVSS`, copied verbatim | rejected alternative A |
| `c1_f` | bare pad + on-die `ppolyf_u_2k_6p0` ballast (2 um x 7.5 um, the committed program-leg geometry) | rejected alternative B |
| `c0_f` | bare pad straight to the plate, bench source impedance only | reference |
| `cx_f`, `cx_s` | bare pad straight to the plate, **off-die** 10 kOhm series resistor at the socket; fast (100 ns) / slow (100 us) ramp | **chosen** |
| `jn_<m>_f` | `cx_f` plus PDK junction `m` on the plate node (`nd2ps`, `nw2ps`, `dw2ps`; Candidate 3: `pd2nw` over a +3.3 V well tie, `nw2ps`). Which one a layout has is #207's question; one bench per possibility | constraint on the plate node |
| `nbh_f`, `nbh_s` | `cx` on the selected cell AND an unprogrammed neighbour on the same BL / WL whose own PL pad is high-impedance (policy a of the floorplan record) | failure case |
| `nbd_f` | the same with the neighbour PL pad driven to 0 V (policy b) | failure case |

Path netlists: [`design/hv-pad/hv_pad_path.spice`](../../design/hv-pad/hv_pad_path.spice),
inlined into each deck at run time.

Measured per corner (max over the transient): `vpad_max`, `vpl_max` (|V|),
`vox_max` (|V| across the cell capacitor), `ifil_max` (filament current;
> 1 uA = programmed), `ipad_max` (source current), `vr_max` (ballast terminal
pair, `c1_f` only), `idvdd_max` (current into the shared rail, `astd_f`),
`ijn_max` (junction current), `voxj_max` / `ifilj_max` (neighbour).

Rules: [`verdicts.py`](verdicts.py), each limit cited in that file. `rating:`
codes mean a device passed a cited limit; `function:` codes mean the cell did not
see the intended voltage or its programmed state is wrong (programs iff
level >= V_bd).

## Layout

- [`model.py`](model.py) defines the benches and pad levels, builds SPICE decks and `klt sim` requests, and collects graded corner results.
- [`verdicts.py`](verdicts.py) applies the rating and function limits to each corner.
- [`render.py`](render.py) formats graded results into Markdown records.
- [`run_experiment.py`](run_experiment.py) runs the fleet, smoke and saved-report commands and exposes the model and rendering helpers to library callers.

## Running

```
python3 sim/hv-pad-protection/run_experiment.py --candidates 1,2,3   # batch fleet, 10-11 benches x 45 corners per candidate
python3 sim/hv-pad-protection/run_experiment.py --smoke 2:cx_f       # ONE local corner, debug only, records nothing
python3 sim/hv-pad-protection/run_experiment.py --check RECORD_ID --candidates N   # re-apply verdicts.py to a saved run
python3 -I -m unittest discover -s tests -p test_hv_pad_protection.py -q   # offline rules, decks and records
```

A failed submit writes `submit-error.txt` and no fallback local grid is run.
Raw outputs go to the artifact store; the record and a manifest are committed.

Committed per-corner reports (`corners/<rid>/c<n>/<bench>/report.json`) have
their `coverage.checked` / `coverage.inapplicable` id lists replaced by their
counts (`harness.report.elide_coverage`); every measurement value, corner
status, diagnostic, `environment`, `provenance` and coverage counter is kept,
and the sha256 of the full klt report is committed alongside it as
`report.json.sha256`. `--check` re-applies verdicts.py to these elided reports
— grading reads only what the elision keeps.

## Limits of these benches

- **Placeholders, not measurements**: bench source + cable 100 ohm / 100 pF,
  die pad 1 pF, plate shunt 100 fF (needed for the `uic` start, as in
  `sim/program-bias-scheme`), access path 1 kOhm, filament 10 kOhm, route
  coupling between adjacent plates 100 fF (an estimate: ~0.1 fF/um over an
  ~800 um run at 5 um pitch), high-impedance pad leakage 1 GOhm (an estimate),
  off-die resistor 10 kOhm (its value is the bench plan's OPEN item).
- The access device's own terminal pairs are not re-rated here
  (`sim/program-bias-scheme`); the access path is a resistor.
- The stock `cap_*` macros are two-terminal C(V) with no junction. Plate-node
  junctions are therefore added explicitly (`jn_*`); in the PDK diode models
  the **breakdown branch does not scale with area**, so the plate-node clamp
  strength is the model's, not a layout-area prediction.
- **ESD is not simulated.** The PDK has no model of a high-voltage ESD event
  and no characterised high-voltage clamp; see the decision record.
- Process corners only; no Monte Carlo, no mismatch.
