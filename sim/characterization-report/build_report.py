#!/usr/bin/env python3
"""Deterministic per-split characterization report (T1 item 8 groundwork).

Pure post-processing: reads the committed, append-only records, netlist
snapshots and raw ngspice logs named in ``inputs.json``, verifies them against
the hashes pinned there, and emits a content-addressed bundle
(``bundles/<bundle-id>/report.json`` + ``report.md``). No simulation is run.

Rules this generator enforces (see README.md in this directory):

* Input selection is explicit: only records listed in ``inputs.json`` are
  read, and each is pinned by sha256 (record file, netlist snapshot, and a
  digest over every raw log it covers).
* Split populations are never pooled: every value is keyed by region
  (candidate), access-sizing x capacitor-geometry sub-configuration and corner,
  and carries a source locator (log path + measurement name).
* Missing, hash-mismatched, superseded, incompatible and failed inputs are
  disclosed, and any disclosure forces ``status`` != ``complete``.
* Programming yield, full sense margin and retention are always emitted as
  ``unmeasured`` until a supported input type exists.
* The item-8 generic envelope is only emitted for a ``complete`` report.

Stdlib only. Usage::

    python3 sim/characterization-report/build_report.py            # write bundle
    python3 sim/characterization-report/build_report.py --check    # verify committed bundle
    python3 sim/characterization-report/build_report.py --print-pins  # hashes for inputs.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

GENERATOR_VERSION = 1
HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from harness import numfmt  # noqa: E402

SCOPE_STATEMENT = (
    "This report covers antifuse cell DEVICE characterization only (access-device "
    "OFF-state leakage, ON-state series resistance, pre-breakdown capacitance and "
    "the stock-model leakage floor) for the selected candidate/region records. It "
    "does not cover the whole block: no array, addressing, program-path, sense-path "
    "or SPI evidence is summarized here."
)

UNMEASURED = [
    {
        "quantity": "programming_yield",
        "status": "unmeasured",
        "reason": "needs a breakdown-augmented cell model and a yield-vs-condition "
                  "Monte Carlo/corner campaign; no supported input record exists",
    },
    {
        "quantity": "full_sense_margin",
        "status": "unmeasured",
        "reason": "needs programmed and unprogrammed resistance distributions through "
                  "the sense path at its worst-case corner; only the access-device "
                  "R_on and I_off inputs to that margin are measured here",
    },
    {
        "quantity": "retention",
        "status": "unmeasured",
        "reason": "no retention/stress measurement input exists",
    },
]

SELECTION_POLICY = (
    "Only records listed in inputs.json are consumed (no directory globbing). Each is "
    "pinned by sha256 of its record file, its netlist snapshot, and a digest over all "
    "raw logs under its corners/ directory. A pin mismatch means the committed evidence "
    "moved after selection: the record is excluded and disclosed as hash_mismatch."
)
SUPERSESSION_POLICY = (
    "A selected record is stale if any committed record in the experiment's records/ "
    "directory names it in its 'Supersedes' field, or if its netlist snapshot no longer "
    "matches the current design netlist. Stale records are excluded and disclosed; the "
    "replacement must be selected explicitly by a new inputs.json (new bundle id). "
    "Newer same-region records that do not name the selected record are listed as "
    "informational 'unselected_same_region' notes, never silently preferred."
)

_SCALAR = r"^\s*{name}\s*=\s*([0-9eE.+-]+)\s*$"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def logs_tree_digest(root: Path, logs_dir: Path) -> str | None:
    """Digest over (relative path, sha256) of every regular file under logs_dir."""
    if not logs_dir.is_dir():
        return None
    lines = []
    for p in sorted(q for q in logs_dir.rglob("*") if q.is_file() and ".work" not in q.parts):
        lines.append(f"{p.relative_to(root).as_posix()} {sha256_file(p)}\n")
    return sha256_bytes("".join(lines).encode())


def parse_scalar(text: str, name: str):
    m = re.search(_SCALAR.format(name=re.escape(name)), text, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def supply_volts(token: str) -> float:
    m = re.fullmatch(r"bl(\d)p(\d\d)v", token)
    if not m:
        raise ValueError(f"unrecognized supply token {token!r}")
    return float(f"{m.group(1)}.{m.group(2)}")


def read_field(record_text: str, label: str):
    m = re.search(rf"^- \*\*{re.escape(label)}\*\*:\s*(.*)$", record_text, re.MULTILINE)
    return m.group(1).strip() if m else None


def canonical(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


# ---------------------------------------------------------------------------
# Record loading
# ---------------------------------------------------------------------------


def superseders(root: Path, records_dir: str) -> dict[str, list[str]]:
    """Map record-id -> committed records whose Supersedes field names it."""
    out: dict[str, list[str]] = {}
    d = root / records_dir
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.md")):
        text = p.read_text()
        sup = read_field(text, "Supersedes") or ""
        for rid in re.findall(r"\d{8}-\d{6}-[0-9a-f]+", sup):
            out.setdefault(rid, []).append(p.stem)
    return out


def expected_corners(grid: dict):
    access = [
        (p, t, s)
        for p in grid["access_process"]
        for t in grid["temps_c"]
        for s in grid["access_supply"]
    ]
    cap = [(p, t) for p in grid["moscap_process"] for t in grid["temps_c"]]
    return access, cap


def load_record(root: Path, manifest: dict, sel: dict, sup_map: dict):
    """Return (region_report, disclosures)."""
    grid = manifest["grid"]
    rid = sel["record_id"]
    exp_dir = manifest["experiment_dir"]
    rec_path = f"{exp_dir}/records/{rid}.md"
    snap_path = f"{exp_dir}/netlist-snapshots/{rid}.spice"
    logs_path = f"{exp_dir}/corners/{rid}"
    region = {
        "region": sel["region"],
        "candidate": sel["candidate"],
        "record_id": rid,
        "record_status": "ok",
        "inputs": {"record": rec_path, "netlist_snapshot": snap_path, "logs": logs_path},
        "provenance": {},
        "sub_configs": {},
    }
    disc: list[dict] = []

    def reject(status: str, detail: str):
        region["record_status"] = status
        disc.append({"kind": status, "region": sel["region"], "record_id": rid, "detail": detail})
        return region, disc

    # --- presence and pins
    for label, rel in (("record", rec_path), ("netlist_snapshot", snap_path)):
        if not (root / rel).is_file():
            return reject("missing", f"{label} file {rel} not found")
    digest = logs_tree_digest(root, root / logs_path)
    if digest is None:
        return reject("missing", f"raw log directory {logs_path} not found")
    got = {
        "record_sha256": sha256_file(root / rec_path),
        "snapshot_sha256": sha256_file(root / snap_path),
        "logs_tree_sha256": digest,
    }
    bad = [k for k in got if got[k] != sel.get(k)]
    if bad:
        return reject("hash_mismatch", f"pinned hash differs for {', '.join(bad)} "
                      "(committed evidence changed after selection; values excluded)")
    region["provenance"]["pins"] = got

    # --- supersession / staleness
    newer = sup_map.get(rid, [])
    if newer:
        return reject("superseded", f"superseded by committed record(s) {', '.join(newer)}")
    design = sel.get("design_netlist")
    if design:
        dp = root / design
        if not dp.is_file():
            return reject("stale", f"current design netlist {design} not found")
        if sha256_file(dp) != got["snapshot_sha256"]:
            return reject("stale", f"netlist snapshot no longer matches current {design}")
        region["provenance"]["design_netlist"] = design

    # --- compatibility
    text = (root / rec_path).read_text()
    pdk = re.search(r"open_pdks `([0-9a-f]+)`", text)
    pdk_rev = pdk.group(1) if pdk else None
    if pdk_rev != manifest["pdk_revision"]:
        return reject("incompatible", f"PDK revision {pdk_rev} != pinned {manifest['pdk_revision']}")
    if read_field(text, "Record ID") != rid:
        return reject("incompatible", "record file's Record ID field does not match its filename")
    claim = read_field(text, "Claim") or ""
    if f"Region {sel['region']} / Candidate {sel['candidate']}" not in claim:
        return reject("incompatible", "record's Claim does not name the selected region/candidate")
    region["provenance"].update({
        "pdk_revision": pdk_rev,
        "netlist_provenance": read_field(text, "Netlist provenance"),
        "timestamp_author": read_field(text, "Timestamp / author"),
        "supersedes": read_field(text, "Supersedes"),
    })
    if "dirty tree" in (region["provenance"]["netlist_provenance"] or ""):
        disc.append({"kind": "provenance_caveat", "region": sel["region"], "record_id": rid,
                     "detail": "record states the working tree was dirty at run time; the "
                               "netlist snapshot is the frozen DUT actually simulated"})
    for other in sel.get("unselected_same_region", []):
        disc.append({"kind": "unselected_same_region", "region": sel["region"],
                     "record_id": rid, "detail": f"committed record {other} covers the same "
                     "region and was not selected"})

    # --- geometry from the frozen snapshot
    snap = (root / snap_path).read_text()
    keys = ("wcap", "lcap", "wacc", "lacc")
    d = numfmt.parse_defaults(snap, raw=True)
    geom_defaults = {k: d[k] for k in keys} if set(keys) <= d.keys() else None
    region["geometry_note"] = (
        "Levels 'min' and '2x' are the committed netlist's subcircuit-parameter defaults "
        "and a x2 width; they are placeholders, NOT the ratified split-axis levels."
    )
    region["netlist_defaults"] = geom_defaults

    stim = manifest["stimulus"][str(sel["candidate"])]
    access_expected, cap_expected = expected_corners(grid)
    failed_total = 0
    for sizing in grid["sizing_levels"]:
        for geometry in grid["geometry_levels"]:
            sub_id = f"access-{sizing}_cap-{geometry}"
            sub = {
                "access_sizing": sizing,
                "cap_geometry": geometry,
                "width_multipliers": {"access_wacc_x": 1 if sizing == "min" else 2,
                                      "cap_wcap_x": 1 if geometry == "min" else 2},
                "access_corners": {},
                "cap_corners": {},
            }
            for proc, temp, sup in access_expected:
                cid = f"{proc}_{temp}c_{sup}"
                rel = f"{logs_path}/{sub_id}/{cid}.log"
                entry = _parse_access(root, rel, stim)
                if entry["status"] != "ok":
                    failed_total += 1
                    disc.append({"kind": "failed_corner" if entry["status"] == "failed" else "missing_corner",
                                 "region": sel["region"], "record_id": rid,
                                 "detail": f"{sub_id}/{cid}: {entry['status']}", "locator": rel})
                entry.update({"process": proc, "temp_c": temp, "supply": sup, "vread_v": supply_volts(sup)})
                sub["access_corners"][cid] = entry
            for proc, temp in cap_expected:
                cid = f"{proc}_{temp}c_nosupply"
                rel = f"{logs_path}/{sub_id}/{cid}.log"
                entry = _parse_cap(root, rel, stim)
                if entry["status"] != "ok":
                    failed_total += 1
                    disc.append({"kind": "failed_corner" if entry["status"] == "failed" else "missing_corner",
                                 "region": sel["region"], "record_id": rid,
                                 "detail": f"{sub_id}/{cid}: {entry['status']}", "locator": rel})
                entry.update({"process": proc, "temp_c": temp})
                sub["cap_corners"][cid] = entry
            sub["worst_case"] = _worst_case(sub, grid)
            region["sub_configs"][sub_id] = sub
    if failed_total:
        region["record_status"] = "failed"

    _cross_check(region, text, grid, disc, sel)
    return region, disc


def _parse_access(root: Path, rel: str, stim: dict) -> dict:
    p = root / rel
    if not p.is_file():
        return {"status": "missing", "locator": rel}
    text = p.read_text()
    vals = {}
    for key in ("ioff_lo", "ioff_mid", "ioff_hi", "ron"):
        vals[key] = parse_scalar(text, key)
    if any(v is None for v in vals.values()):
        return {"status": "failed", "locator": rel,
                "unparsed": sorted(k for k, v in vals.items() if v is None)}
    return {
        "status": "ok", "locator": rel,
        "ioff_a": {f"{stim['off_gate_bias_v'][i]:+g}V": {"value": vals[k], "source": f"{rel}#{k}"}
                   for i, k in enumerate(("ioff_lo", "ioff_mid", "ioff_hi"))},
        "ron_ohm": {"value": vals["ron"], "source": f"{rel}#ron", "on_gate_bias_v": stim["on_gate_bias_v"]},
    }


def _parse_cap(root: Path, rel: str, stim: dict) -> dict:
    p = root / rel
    if not p.is_file():
        return {"status": "missing", "locator": rel}
    text = p.read_text()
    ilk = [parse_scalar(text, f"ilk_{i}") for i in range(1, 6)]
    cval = [parse_scalar(text, f"cval_{i}") for i in range(1, 6)]
    if any(v is None for v in ilk + cval):
        return {"status": "failed", "locator": rel}
    return {
        "status": "ok", "locator": rel,
        "capacitance_f": {f"{b:+g}V": {"value": cval[i], "source": f"{rel}#cval_{i+1}"}
                          for i, b in enumerate(stim["cv_bias_v"])},
        "leakage_a": {f"{b:+g}V": {"value": ilk[i], "source": f"{rel}#ilk_{i+1}"}
                      for i, b in enumerate(stim["cv_bias_v"])},
    }


def _worst_case(sub: dict, grid: dict) -> dict:
    """Worst case WITHIN one sub-configuration, with locator. Never across sub-configs."""
    best_i = best_r = None
    for cid, e in sub["access_corners"].items():
        if e["status"] != "ok":
            continue
        for bias, v in e["ioff_a"].items():
            if best_i is None or v["value"] > best_i["value"]:
                best_i = {"value": v["value"], "corner": cid, "gate_bias": bias, "source": v["source"]}
        r = e["ron_ohm"]
        if best_r is None or r["value"] > best_r["value"]:
            best_r = {"value": r["value"], "corner": cid, "source": r["source"]}
    return {"max_ioff_a_any_corner": best_i, "max_ron_ohm_any_corner": best_r}


def _cross_check(region, text, grid, disc, sel):
    """Recompute the record's headline I_off / R_on for the named corners from the logs
    and compare with the record's own text. Mismatch is an inconsistency disclosure."""
    fh = grid["fast_hot_corner"]
    sc = grid["slow_cold_corner"]
    ioffs = [max(v["value"] for v in sub["access_corners"][fh]["ioff_a"].values())
             for sub in region["sub_configs"].values()
             if sub["access_corners"].get(fh, {}).get("status") == "ok"]
    rons = [sub["access_corners"][sc]["ron_ohm"]["value"]
            for sub in region["sub_configs"].values()
            if sub["access_corners"].get(sc, {}).get("status") == "ok"]
    mi = re.search(r"worst-case I_off = ([0-9.e+-]+) A", text)
    mr = re.search(r"R_on = ([0-9.e+-]+) ohm", text)
    checks = {}
    for name, got, m in (("fast_hot_worst_ioff_a", max(ioffs) if ioffs else None, mi),
                         ("slow_cold_worst_ron_ohm", max(rons) if rons else None, mr)):
        if m is None or got is None:
            checks[name] = "not_checkable"
            continue
        want = float(m.group(1))
        ok = abs(got - want) <= 5e-5 * abs(want)  # record prints 5 significant digits
        checks[name] = "consistent" if ok else "inconsistent"
        if not ok:
            disc.append({"kind": "inconsistent_record_headline", "region": sel["region"],
                         "record_id": region["record_id"],
                         "detail": f"{name}: recomputed {got:.4e} vs record text {want:.4e}"})
    region["record_headline_cross_check"] = {
        "corners": {"fast_hot": fh, "slow_cold": sc},
        "note": "record headlines take a worst case across the four sub-configurations; "
                "this is only a consistency check on the raw logs, not a reported pooled value",
        "result": checks,
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build(root: Path, manifest_path: Path) -> tuple[dict, str, str]:
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get("generator_version") != GENERATOR_VERSION:
        raise SystemExit(f"inputs.json generator_version {manifest.get('generator_version')} "
                         f"!= generator {GENERATOR_VERSION}")
    manifest_sha = sha256_bytes(raw)
    bundle_id = manifest_sha[:12]
    sup_map = superseders(root, f"{manifest['experiment_dir']}/records")
    regions, disclosures = [], []
    for sel in manifest["records"]:
        r, d = load_record(root, manifest, sel, sup_map)
        regions.append(r)
        disclosures.extend(d)
    blocking = [d for d in disclosures if d["kind"] not in ("provenance_caveat", "unselected_same_region")]
    required = set(manifest["required_regions"])
    present_ok = {r["region"] for r in regions if r["record_status"] == "ok"}
    for missing in sorted(required - {r["region"] for r in regions}):
        blocking.append({"kind": "missing_region", "region": missing, "detail": "no input selected"})
        disclosures.append(blocking[-1])
    if required - present_ok:
        pass  # already covered by per-record disclosures
    status = "complete" if not blocking and not UNMEASURED and required <= present_ok else "incomplete"
    report = {
        "schema_version": 1,
        "generator_version": GENERATOR_VERSION,
        "bundle_id": bundle_id,
        "inputs_manifest": {"path": manifest_path.relative_to(root).as_posix(), "sha256": manifest_sha},
        "scope": SCOPE_STATEMENT,
        "status": status,
        "status_reason": (
            "unmeasured quantities remain" if UNMEASURED else "") + (
            "; " if UNMEASURED and blocking else "") + (
            f"{len(blocking)} blocking input disclosure(s)" if blocking else ""),
        "unmeasured": UNMEASURED,
        "item_8_contract": {
            "met": False,
            "reason": "T1 item 8 asks for one aggregated artifact of per-spec-row performance "
                      "across conditions; this report covers device characterization only and "
                      "lists programming yield, full sense margin and retention as unmeasured, "
                      "and has no digital-partition (Fmax/area/power) content",
        },
        "policies": {"input_selection": SELECTION_POLICY, "supersession": SUPERSESSION_POLICY},
        "grid": manifest["grid"],
        "stimulus": manifest["stimulus"],
        "stimulus_note": manifest.get("stimulus_note"),
        "measurement_notes": manifest["measurement_notes"],
        "disclosures": disclosures,
        "regions": regions,
    }
    return report, render_md(report), bundle_id


def _e(x: float) -> str:
    return f"{x:.4e}"


def render_md(rep: dict) -> str:
    L = []
    a = L.append
    a(f"# Device characterization report (bundle {rep['bundle_id']})\n")
    a(f"**Status: {rep['status'].upper()}** ({rep['status_reason']})\n")
    a(f"**Scope.** {rep['scope']}\n")
    a("**Item 8 contract: NOT met.** " + rep["item_8_contract"]["reason"] + ".\n")
    a("Generated by `sim/characterization-report/build_report.py` from "
      f"`{rep['inputs_manifest']['path']}` (sha256 `{rep['inputs_manifest']['sha256']}`). "
      "No simulation was run; every value below is read from a committed raw log and "
      "carries its locator in `report.json`. Populations are never pooled: each row is one "
      "region x sub-configuration x corner.\n")
    a("## Unmeasured\n")
    a("| Quantity | Status | Reason |\n|---|---|---|")
    for u in rep["unmeasured"]:
        a(f"| {u['quantity']} | {u['status']} | {u['reason']} |")
    a("")
    a("## Measurement notes\n")
    for n in rep["measurement_notes"]:
        a(f"- {n}")
    a("")
    a("## Input policies\n")
    a(f"- **Selection.** {rep['policies']['input_selection']}")
    a(f"- **Supersession.** {rep['policies']['supersession']}\n")
    a("## Disclosures\n")
    if not rep["disclosures"]:
        a("(none)\n")
    else:
        a("| Kind | Region | Record | Detail |\n|---|---|---|---|")
        for d in rep["disclosures"]:
            a(f"| {d['kind']} | {d.get('region', '')} | {d.get('record_id', '')} | {d['detail']} |")
        a("")
    for r in rep["regions"]:
        a(f"## Region {r['region']} / Candidate {r['candidate']} (record {r['record_id']}, "
          f"record status: {r['record_status']})\n")
        if not r["sub_configs"]:
            a("No values reported: input excluded (see Disclosures).\n")
            continue
        p = r["provenance"]
        a(f"Provenance: PDK open_pdks `{p.get('pdk_revision')}`; netlist: {p.get('netlist_provenance')}; "
          f"run: {p.get('timestamp_author')}; supersedes: {p.get('supersedes')}.  ")
        a(f"Record `{r['inputs']['record']}`, snapshot `{r['inputs']['netlist_snapshot']}`, "
          f"logs `{r['inputs']['logs']}/`.\n")
        d = r["netlist_defaults"] or {}
        a(f"### Geometry and access sizing (netlist defaults: {d})\n")
        a(r["geometry_note"] + "\n")
        a("| Sub-configuration | Access W x | Cap W x | Worst I_off any corner (A) | at corner / gate bias | Worst R_on any corner (ohm) | at corner |")
        a("|---|---|---|---|---|---|---|")
        for sid, s in r["sub_configs"].items():
            w = s["worst_case"]
            wi, wr = w["max_ioff_a_any_corner"], w["max_ron_ohm_any_corner"]
            a(f"| {sid} | {s['width_multipliers']['access_wacc_x']} | {s['width_multipliers']['cap_wcap_x']} | "
              f"{_e(wi['value']) if wi else 'n/a'} | {wi['corner'] + ' / ' + wi['gate_bias'] if wi else ''} | "
              f"{_e(wr['value']) if wr else 'n/a'} | {wr['corner'] if wr else ''} |")
        a("")
        a("### PVT: access device (worst over the supply axis within each process/temperature row)\n")
        a("Source locators for every value are in `report.json`; the row's extreme is at the named supply.\n")
        a("| Sub-configuration | Process | Temp (C) | max I_off (A) | at supply | max R_on (ohm) | at supply | Status |")
        a("|---|---|---|---|---|---|---|---|")
        for sid, s in r["sub_configs"].items():
            groups: dict = {}
            for cid, e in s["access_corners"].items():
                groups.setdefault((e["process"], e["temp_c"]), []).append((cid, e))
            for (proc, temp), items in groups.items():
                oks = [(c, e) for c, e in items if e["status"] == "ok"]
                bad = [c for c, e in items if e["status"] != "ok"]
                if oks:
                    ci, ei = max(oks, key=lambda t: max(v["value"] for v in t[1]["ioff_a"].values()))
                    cr, er = max(oks, key=lambda t: t[1]["ron_ohm"]["value"])
                    ivals = max(v["value"] for v in ei["ioff_a"].values())
                    a(f"| {sid} | {proc} | {temp} | {_e(ivals)} | {ei['supply']} | "
                      f"{_e(er['ron_ohm']['value'])} | {er['supply']} | "
                      f"{'ok' if not bad else 'INCOMPLETE: ' + ', '.join(bad)} |")
                else:
                    a(f"| {sid} | {proc} | {temp} | n/a | | n/a | | MISSING/FAILED: {', '.join(bad)} |")
        a("")
        a("### PVT: pre-breakdown capacitor (per moscap corner)\n")
        a("Leakage is the stock-model result (no DC branch exists in the stock cap model); "
          "it is not a measurement of oxide leakage.\n")
        a("| Sub-configuration | Corner | C at -V_rated (F) | C at 0 V (F) | C at +V_rated (F) | max abs leakage (A) | Status |")
        a("|---|---|---|---|---|---|---|")
        for sid, s in r["sub_configs"].items():
            for cid, e in s["cap_corners"].items():
                if e["status"] != "ok":
                    a(f"| {sid} | {cid} | n/a | n/a | n/a | n/a | {e['status'].upper()} |")
                    continue
                keys = list(e["capacitance_f"])
                a(f"| {sid} | {cid} | {_e(e['capacitance_f'][keys[0]]['value'])} | "
                  f"{_e(e['capacitance_f'][keys[2]]['value'])} | {_e(e['capacitance_f'][keys[4]]['value'])} | "
                  f"{_e(max(abs(v['value']) for v in e['leakage_a'].values()))} | ok |")
        a("")
    return "\n".join(L) + "\n"


def envelope_for(report: dict) -> dict:
    """Generic item-8 envelope. Refuses unless the report is complete."""
    if report["status"] != "complete" or not report["item_8_contract"]["met"]:
        raise SystemExit("refusing to emit an item-8 envelope: report status is "
                         f"{report['status']!r} and its item-8 contract is not met")
    return {"schema_version": 1, "kind": "generic", "status": "pass",
            "summary": f"characterization bundle {report['bundle_id']}",
            "source": f"sim/characterization-report/bundles/{report['bundle_id']}/report.json"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root")
    ap.add_argument("--inputs", type=Path, default=None, help="inputs manifest (default: <this dir>/inputs.json)")
    ap.add_argument("--check", action="store_true", help="verify the committed bundle reproduces byte-for-byte")
    ap.add_argument("--print-pins", action="store_true", help="print current hashes for each selected record")
    ap.add_argument("--emit-envelope", action="store_true", help="print the generic item-8 envelope (refused unless complete)")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    inputs = (args.inputs or (root / "sim/characterization-report/inputs.json")).resolve()

    if args.print_pins:
        manifest = json.loads(inputs.read_text())
        ed = manifest["experiment_dir"]
        for sel in manifest["records"]:
            rid = sel["record_id"]
            print(json.dumps({
                "record_id": rid,
                "record_sha256": sha256_file(root / ed / "records" / f"{rid}.md"),
                "snapshot_sha256": sha256_file(root / ed / "netlist-snapshots" / f"{rid}.spice"),
                "logs_tree_sha256": logs_tree_digest(root, root / ed / "corners" / rid),
            }, indent=2))
        return 0

    report, md, bundle_id = build(root, inputs)
    rj = canonical(report)
    out = inputs.parent / "bundles" / bundle_id
    if args.emit_envelope:
        print(canonical(envelope_for(report)), end="")
        return 0
    if args.check:
        for name, want in (("report.json", rj), ("report.md", md)):
            f = out / name
            if not f.is_file():
                print(f"check: {f} missing", file=sys.stderr)
                return 1
            if f.read_text() != want:
                print(f"check: {f} differs from regenerated output", file=sys.stderr)
                return 1
        print(f"check: bundle {bundle_id} reproduces byte-for-byte (status {report['status']})")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for name, want in (("report.json", rj), ("report.md", md)):
        f = out / name
        if f.exists() and f.read_text() != want:
            print(f"refusing to overwrite {f}: bundles are append-only; change inputs.json "
                  "(new bundle id) to mint a new bundle", file=sys.stderr)
            return 2
        f.write_text(want)
    print(f"bundle {bundle_id}: status {report['status']} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
