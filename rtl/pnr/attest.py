#!/usr/bin/env python3
"""Write the T1 item 2 (digital) attestation for the routed GDS.

An artifact-anchored `generic` envelope (`klt signoff` "t1_item": 2) derived
from the committed `klt place-and-route` report. `status` is "pass" only when
that report shows a completed route with a built PDN and placed tapcells;
anything else writes "fail" so a degraded re-run cannot be cited as passing.
Usage: rtl/pnr/attest.py   (run from the repo root; run_pnr.sh does this)
"""
import hashlib
import json
from pathlib import Path

D = Path("rtl/pnr")
report = json.loads((D / "antifuse_digital_top.pnr.report.json").read_text())
gds = D / "antifuse_digital_top.gds"
digest = "sha256:" + hashlib.sha256(gds.read_bytes()).hexdigest()
power = report["power"]
placed = power.get("placed") or {}
ok = (
    report["status"] == "ok"
    and report["stage_reached"] == "route"
    and power["pdn"] is True
    and power.get("tapcell_master")
    and placed.get("status") == "complete"
    and placed.get("tapcells", 0) > 0
)
envelope = {
    "schema_version": 1,
    "kind": "generic",
    "t1_item": 2,
    "status": "pass" if ok else "fail",
    "source": "rtl/pnr/antifuse_digital_top.pnr.report.json",
    "summary": (
        "antifuse_digital_top routed GDS (N=32) from klt place-and-route: "
        f"stage_reached={report['stage_reached']}, power.pdn={power['pdn']}, "
        f"tapcell_master={power.get('tapcell_master')}, "
        f"tapcells={placed.get('tapcells')}, "
        f"route_drc_violation_count={report['route_drc_violation_count']}. "
        "Evidence of reproducible P&R only; not DRC, LVS or timing sign-off."
    ),
    "provenance": {
        "klt_version": report["provenance"]["klt_version"],
        "input": {
            "path": {"path": str(gds), "scope": "repo"},
            "content_hash": digest,
            "role": "layout",
        },
    },
}
(D / "antifuse_digital_top.attest.json").write_text(json.dumps(envelope, indent=2) + "\n")
