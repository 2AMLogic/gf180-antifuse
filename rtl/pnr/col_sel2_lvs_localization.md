# `col_sel[2]` gate-level LVS split: localization (issue #436)

Evidence note, append-only. Outcome: **extraction artifact; no layout defect.**
The routed GDS is connected as the DEF and `antifuse_digital_top_routed.v` say.

## Reproduction

`klt` = klayout-tools `main` @ `94950eeee19e4219d938b81cf742065bd333d750`
(`0.9.3.dev1789`), KLayout 0.30.13, via a throwaway `uvx --from git+...@<sha>`.

    klt extract rtl/pnr/antifuse_digital_top.gds --deck gf180mcu --pdk gf180mcuD \
      --abstract-cells 'gf180mcu_fd_sc_mcu7t5v0__*' --def-net-names \
      --top antifuse_digital_top

Result matches the issue: 552 nets, 544 pins; `col_sel[2]` is net 1463 (pin
label at 146.16, 232.835 um on Metal2) and the anonymous net `$1170` is net 1170.

## Localization

Connectivity was re-derived directly from the GDS (Metal1..Metal5 plus
Via1..Via4, flood fill from each pin access point). Coordinates in um.

| net | pins reached | Metal1 pad on `u_col_dec/_38_` (`inv_4`, placed at 134.4, 176.4) |
|---|---|---|
| `col_sel[2]` | top pin, `u_col_dec` `_51_`/`_46_`/`_36_`/`_24_` loads, `_38_` `I` | pad B: x 134.77-136.35, y 178.14-178.55 (Via1 at 136.08, 178.36) |
| `$1170` | `u_regs/_657_` Q, `u_regs/_526_` I0, `u_regs/_482_` B2, then Metal2 x=138.32 up to y=178.36 | pad A: x 137.435-138.715, y 178.14-178.55 (Via1 at 138.32, 178.36) |

- The DEF route for `col_sel[2]` ends one Metal2 branch (x=138.32, from the
  register side) in a Via1 at (138.32, 178.36) and the other branch (x=136.08,
  toward the decoder loads) in a Via1 at (136.08, 178.36). There is **no Metal1
  wire** between them in the DEF. The router treated them as landing on the
  same pin.
- They do: both Via1s land on the `I` pin of `u_col_dec/_38_`. That `inv_4`
  draws `I` as two disjoint Metal1 pads, 1.085 um apart (x 136.35 to 137.435).
- Each pad carries three contacts, and all six contacts land on one merged
  poly shape (x 135.02-138.98, y 176.52-180.2): the two pads are one gate,
  tied together only inside the cell.
- `--abstract-cells` extracts the cell as a black box with a pin at the single
  label point (pad B). Poly inside the cell is not extracted, so pad A has no
  path to pad B and becomes anonymous net `$1170`, which also carries the
  Metal2 wire from the register side. Metal is not physically missing; it is
  present and joined through the cell's own gate poly.

## Disposition

- No routing or flow change; PnR artifacts and `drc.json` are untouched
  (`rtl/pnr/run_drc.sh` not re-run, because nothing was regenerated).
- Tool gap filed at `2AMLogic/klayout-tools#6742` (generic wording).
- Gate-level LVS of this GDS will keep reading `mismatch` on this one net
  until that gap is closed; it must not be read as a layout open. No LVS
  option or `power_connectivity` setting was relaxed.
- No new LVS report path exists to cite on #176; this note is the evidence.
