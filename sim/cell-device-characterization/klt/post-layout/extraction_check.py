"""Validate a retained `klt pex` report before its schematic/extracted pair is
generated, submitted or ingested (issue #447, review item 2).

`check_extraction(repo, n)` returns a list of findings (empty = usable).  It
checks that the report exists, pins the current GDS, reference netlist and
extracted netlist by sha256, and carries `body_bias.status == "biased"` with no
unbiased devices or nets.  A stale, missing, tied or unbiased extraction must
never reach a pair.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bare(h):
    return h.split(":", 1)[-1] if isinstance(h, str) else None


def check_extraction(repo: Path, n: int) -> list[str]:
    d = repo / "layout" / f"cell_candidate{n}"
    gds, ref, ext = d / f"cell_candidate{n}.gds", d / "lvs_reference.spice", d / "pex" / "extracted.spice"
    rpt = d / "pex" / "pex_report.json"
    for p in (gds, ref, ext):
        if not p.is_file():
            return [f"missing input {p.relative_to(repo)}"]
    if not rpt.is_file():
        return [f"missing PEX report {rpt.relative_to(repo)}"]
    try:
        r = json.loads(rpt.read_text())
    except json.JSONDecodeError as e:
        return [f"unreadable PEX report: {e}"]
    out = []
    got = _bare(((r.get("provenance") or {}).get("input") or {}).get("content_hash"))
    if got != _sha(gds):
        out.append(f"stale GDS: report pins {got}, current GDS is {_sha(gds)}")
    if _bare(r.get("reference_netlist_sha256")) != _sha(ref):
        out.append("reference netlist hash differs from the report's reference_netlist_sha256")
    if _bare((r.get("extraction") or {}).get("netlist_sha256")) != _sha(ext):
        out.append("extracted.spice hash differs from the report's extraction.netlist_sha256")
    bb = r.get("body_bias") or {}
    if bb.get("status") != "biased":
        out.append(f"body_bias.status is {bb.get('status')!r}, not 'biased'")
    if bb.get("unbiased_device_count") or bb.get("unbiased_nets") or bb.get("unbiased_pmos_body_nets"):
        out.append("body_bias lists unbiased devices or nets")
    return out
