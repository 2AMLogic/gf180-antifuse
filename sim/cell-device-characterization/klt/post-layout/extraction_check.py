"""Validate a retained `klt pex` report before its schematic/extracted pair is
generated, submitted or ingested (issue #447, review item 2).

`check_extraction(repo, n)` returns a list of findings (empty = usable).  It
checks that the report exists, pins the current GDS, reference netlist and
extracted netlist by sha256, and carries `body_bias.status == "biased"` with no
unbiased devices or nets.  A stale, missing, tied or unbiased extraction must
never reach a pair.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bare(h):
    return h.split(":", 1)[-1] if isinstance(h, str) else None


def signed_connectivity(reference: str, extracted: str) -> list[str]:
    """Check signed GF180 capacitor pins after collapsing extracted parasitic resistors."""
    def parse_cell(netlist):
        ports = set()
        caps, fets = [], []
        for line in netlist.lower().splitlines():
            words = line.split()
            if words[:1] == [".subckt"]:
                ports.update(words[2:])
            if not words or not words[0].startswith("x"):
                continue
            if len(words) >= 4 and words[3].startswith("cap_"):
                dimensions = dict(w.split("=", 1) for w in words[4:] if "=" in w)
                # klt may interchange width and length; both PDK capacitor
                # equations depend on their product. The fallback has two areas.
                size = sorted(float(dimensions[key].removesuffix("u"))
                              for key in ("c_width", "c_length"))
                caps.append((words[3], size, words[1:3]))
            elif len(words) >= 6 and words[5].startswith(("nfet_", "pfet_")):
                fets.append((words[5], words[1:5]))
        return ports, caps, fets

    graph = defaultdict(set)
    for line in extracted.lower().splitlines():
        words = line.split()
        if len(words) >= 4 and words[0].startswith("r"):
            a, b = words[1:3]
            graph[a].add(b)
            graph[b].add(a)

    def connected(node):
        seen, pending = {node}, [node]
        while pending:
            for adjacent in graph[pending.pop()] - seen:
                seen.add(adjacent)
                pending.append(adjacent)
        return seen

    ref_ports, ref_caps, ref_fets = parse_cell(reference)
    ports, caps, fets = parse_cell(extracted)
    if ports != ref_ports:
        return ["extracted cell ports differ from reference"]
    if not ref_caps or len(caps) != len(ref_caps):
        return ["signed MOS capacitor count differs from reference"]
    # The sole schematic C2 LDMOS represents the two outer access fingers.
    expected_fets = 2 if ref_fets and ref_fets[0][0] == "nfet_10v0_asym" else len(ref_fets)
    if len(fets) != expected_fets:
        return ["access finger count differs from reference"]
    for model, size, ref_pins in ref_caps:
        pairs = [pins for m, dims, pins in caps if (m, dims) == (model, size)]
        if len(pairs) != 1:
            return [f"expected one signed {model} with dimensions {size}"]
        gate, plate = map(connected, pairs[0])
        if gate & plate or plate & ports != {ref_pins[1]}:
            return [f"{model}: capacitor body plate does not exclusively reach {ref_pins[1]}"]
        if not ref_fets:  # Bare probe: two private gates and one shared BL.
            if gate & ports != {ref_pins[0]}:
                return [f"{model}: private gate does not exclusively reach {ref_pins[0]}"]
            continue
        if gate & ports:
            return [f"{model}: storage gate shorted to a cell port"]
        fet_model, ref_fet_pins = ref_fets[0]
        for extracted_model, pins in fets:
            if extracted_model != fet_model:
                return ["access model differs from reference"]
            for target, pin in zip(ref_fet_pins, pins):
                if target == ref_pins[0]:  # CN is private to the capacitor and access finger(s).
                    if pin not in gate:
                        return [f"{fet_model}: access pin does not reach {target}"]
                elif connected(pin) & ports != {target}:
                    return [f"{fet_model}: access pin does not exclusively reach {target}"]
    return []


def check_extraction(repo: Path, n: int | str) -> list[str]:
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
    try:
        out.extend(signed_connectivity(ref.read_text(), ext.read_text()))
    except (KeyError, ValueError) as error:
        out.append(f"unreadable signed device parameters: {error}")
    return out
