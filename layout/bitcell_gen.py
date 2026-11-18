"""Shared plumbing for the per-candidate bitcell generators.

Each `cell_candidateN/generate.py` declares its own geometry (flavor, device
widths and lengths, block offset, strap/marker rectangles, placement origins,
pin map) and calls `main(...)` here. This module only runs the flow:

  klt gen mos_array (cap, acc)  ->  klt draw (straps)  ->  klt gen-compose

and implements the write / `--check` (byte-compare against the committed GDS)
behaviour. It holds no geometry decisions. Requires `klt` on PATH; pin it with
`uvx --from klayout-tools==X.Y.Z python3 .../generate.py`.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

PDK = "gf180mcuA"
W_MIN = 0.42       # um, generator floor for mos_array w_um (a contact-fit
                   # floor above the PDK minimum widths). NOT a spec level:
                   # the capacitor-geometry Minimum is W = 1.0 um
                   # (spec/capacitor-geometry-decision.md) and every caller
                   # passes w_cap_um explicitly. Kept only as w_acc_um's
                   # default -- the access axis (spec/split-axis-plan.md
                   # section 3) is not under a MOSCAP rule and its Minimum is
                   # unchanged.
L_CAP = 0.28       # um, thin-oxide minimum drawn length
GAP = {"ring_gap_um": 1.0, "ring_gap_offset_um": -0.7}
METAL1 = [34, 0]
MOS_CAP_MK = [166, 5]


def run(args, **kw):
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if r.returncode not in (0,):
        sys.exit(f"command failed ({r.returncode}): {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


def build(workdir, *, gds_name, cell, flavor, l_acc, cap_gap_side, acc_gap_side,
          straps, origins_um, pins,
          w_cap_um, l_cap_um=L_CAP, w_acc_um=W_MIN, ring_padding_acc_um=0.5):
    """Run the klt flow in `workdir`; return the path of the composed GDS.

    `origins_um` maps block id (cap, acc, straps) -> {"x", "y"}.

    `w_cap_um` / `l_cap_um` / `w_acc_um` are the per-cell device dimensions of
    the split-axis grid (`spec/split-axis-plan.md` sections 2-3). `w_cap_um`
    is required and has no default: the capacitor level is ratified
    (`spec/capacitor-geometry-decision.md`, Minimum W = 1.0 um), not the
    generator floor this module once defaulted it to. `l_cap_um` defaults to
    the thin-oxide minimum drawn length and `w_acc_um` to the generator floor
    (the access axis is unchanged), so a caller that omits those two generates
    the same bytes as before these keywords existed. Access length stays
    `l_acc`, which was already per-cell.

    `ring_padding_acc_um` is the acc block's generator `ring_padding_um`
    (padding between the finger array and the tap ring's inner edge), applied
    to the acc block only and defaulting to the generator's own 0.5: a caller
    that omits it generates the same bytes as before this keyword existed.
    Candidate 3 raises it because the generator's default draws a pfet/MV
    block whose N-well misses the native deck's Nwell-overlap rule (DF.4d_MV)
    and whose Dualgate marker misses the enclosure rule (DV.6); the cap block
    draws neither marker and stays at the default.
    """
    def gen(name, w_um, l_um, flavor_extra, gap_side, ring_padding_um=None):
        params = {"w_um": w_um, "l_um": l_um, "rows": 1, "cols": 1, "dummy": 0,
                  "flavor": flavor, "gate_contact": True, "add_guard_ring": True,
                  "ring_gap_side": gap_side, **GAP, **flavor_extra}
        if ring_padding_um is not None:
            params["ring_padding_um"] = ring_padding_um
        out = run(["klt", "gen", "mos_array", "--pdk", PDK, "--params",
                   json.dumps(params), "--cell-name", name,
                   "-o", os.path.join(workdir, name + ".gds"), "--format", "json"])
        with open(os.path.join(workdir, name + ".json"), "w") as fh:
            fh.write(out)

    gen("cap", w_cap_um, l_cap_um, {}, cap_gap_side)
    gen("acc", w_acc_um, l_acc, {"voltage_flavor": "medium_voltage"}, acc_gap_side,
        ring_padding_um=ring_padding_acc_um)
    with open(os.path.join(workdir, "straps_params.json"), "w") as fh:
        json.dump(straps, fh)
    out = run(["klt", "draw", "--params", os.path.join(workdir, "straps_params.json"),
               "--cell-name", "straps", "-o", os.path.join(workdir, "straps.gds"),
               "--format", "json"])
    with open(os.path.join(workdir, "straps.json"), "w") as fh:
        fh.write(out)
    req = {
        "schema": "klt.gen_compose.request/1", "pdk": {"variant": PDK},
        "blocks": [{"id": b, "generator_report": b + ".json"} for b in ("cap", "acc", "straps")],
        "placement": {"strategy": "explicit", "order": ["cap", "acc", "straps"],
                      "origins_um": origins_um},
        "pins": pins,
        "options": {"cell_name": cell, "output": os.path.join(workdir, gds_name)},
    }
    rq = os.path.join(workdir, "compose.json")
    with open(rq, "w") as fh:
        json.dump(req, fh)
    run(["klt", "gen-compose", rq, "--format", "json"])
    return os.path.join(workdir, gds_name)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(here, **spec):
    """CLI entry: write the GDS next to `here`, or `--check` against it."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    gds_name = spec["gds_name"]
    committed = os.path.join(here, gds_name)
    with tempfile.TemporaryDirectory() as tmp:
        new = build(tmp, **spec)
        if args.check:
            if not os.path.isfile(committed):
                sys.exit(f"missing {committed}")
            a, b = sha(new), sha(committed)
            if a != b:
                sys.exit(f"DRIFT: regenerated sha256 {a} != committed {b}")
            print(f"OK: {gds_name} sha256 {b}")
        else:
            shutil.copyfile(new, committed)
            print(f"wrote {committed} sha256 {sha(committed)}")
