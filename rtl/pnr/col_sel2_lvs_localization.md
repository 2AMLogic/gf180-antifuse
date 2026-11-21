# `col_sel[2]` gate-level LVS split: localization (issue #436)

> Geometry quoted here is not CI-pinned; valid for the klt build disclosed below and GDS content `sha256:03876d4efa5f4deb8a6f551f8fd63b0e35ca522e31790d5eba7c0c53bf9422a9` (as recorded in `rtl/pnr/antifuse_digital_top.attest.json`); see `scripts/check_layout_geometry_claims.py` scope.

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

## Reproducer retrieval (issue #446, 2026-11-21)

Issue #446 re-routes `antifuse_digital_top` (slow-corner optimization
liberty) and replaces the routed GDS this note was pinned to. The last
commit on `main` that carries the reproducer GDS
`sha256:03876d4efa5f4deb8a6f551f8fd63b0e35ca522e31790d5eba7c0c53bf9422a9`
is `9f2193ac8d9451e3c3272ce7663516d243da3ccb` ("fix: clear routed-GDS DRC
by tightening tapcell pitch and dropping PDN split cuts", 2026-10-27); the
geometry above is retrievable from that commit. This section is history:
the localization and disposition above describe that GDS, not its
replacement. The new route's own multi-pad pin split status is recorded in
the addendum below and reported on #176.

## Addendum: the replacement route (issue #446, 2026-11-21)

The #446 re-route (slow-corner optimization liberty) replaced the routed GDS
with `sha256:dae02f43855fda9b7c8f880fa62be529f3479af070dc34a82cbab4b140373bf5`.
The reproduction above was re-run on it unchanged (same throwaway
`uvx --from git+...@94950eeee19e4219d938b81cf742065bd333d750`, same flags):

- Result: 557 nets, 550 pins; **no multi-pad pin split appears**. The only
  anonymous nets are 7 single-terminal nets, the `ZN` outputs of the floating
  clock-load cells (`inv`/`clkinv` leaves driving only a load) — a different,
  benign artifact, not a named net losing a branch.
- `col_sel[2]` extracts as one connected net: its register-side driver and
  address register, the decoder-side inverter and all decoder loads are on
  the single named net; no anonymous net carries a second terminal.

This route therefore does not reproduce the klayout-tools#6742 symptom; the
upstream gap itself is unchanged (abstract-cell extraction still drops the
intra-cell connection between multi-pad pin pads), the localization and old
GDS above remain the reproducer, and #176 stays open on the tool gap. No
claim is made that a future route cannot re-split a net the same way.
