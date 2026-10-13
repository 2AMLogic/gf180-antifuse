#!/usr/bin/env python3
"""Submit the checked-in `klt sim` request set and ingest the reports.

    python3 sim/cell-device-characterization/klt/run_klt_campaign.py            # submit + ingest
    python3 sim/cell-device-characterization/klt/run_klt_campaign.py --ingest-only klt/runs/<run-id>

Submission: one `klt sim -o <rundir>/<sub>/<ioff|ron> <request> --format json`
per request. The backend is whatever the environment selects
(`KLT_SIM_BACKEND`; on the dispatch workers that is `batch`, i.e. the Spot
fleet). `KLT_CMD` overrides the klt launcher, e.g.
`KLT_CMD='uvx --from klayout-tools==0.7.0 klt'` to match the fleet runner's
klt version (the runner refuses a newer client). This script never falls back to a local grid: a request whose submit
fails is recorded verbatim in `<rundir>/submit-errors.txt` and its sub-
configuration is left out of the record (the record then says so).

Ingest: builds one append-only per-region (= per-candidate) Markdown record
`records/<run-id>-c<N>.md`. Per-region, per-sub-configuration results are
listed separately -- nothing is averaged across sub-configurations or
regions. A reproduction check compares every klt corner value against the
legacy harness's committed raw logs and the legacy record's headline numbers.

stdlib only. The run directory is new and timestamped; existing sim/
evidence is read, never written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent.parent
sys.path.insert(0, str(EXP.parent))

from harness import report as R  # noqa: E402

REQ_DIR = HERE / "requests"
RUNS_DIR = HERE / "runs"
SIZING = ("min", "2x")
GEOM = ("min", "2x")
CANDS = {1: "I", 2: "II", 3: "III"}
MOS = ("typical", "ff", "ss", "fs", "sf")
TEMPS = (-40, 27, 125)
N_GRID = 32
TOL_REL = 1e-2   # stated reproduction tolerance (relative), see README
FAST_HOT = ("ff", 125, 1.1)
SLOW_COLD = ("ss", -40, 0.9)


def sub_names(n):
    return [f"c{n}_access-{s}_cap-{g}" for s in SIZING for g in GEOM]


def submit_one(rundir: Path, sub: str, which: str, workers_note: str = "") -> tuple[str, str, int, str]:
    req = REQ_DIR / sub / f"{which}.json"
    out = rundir / sub / which
    out.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [*shlex.split(os.environ.get("KLT_CMD", "klt")), "sim", "-o", str(out), str(req), "--format", "json"],
        capture_output=True, text=True,
    )
    (out / "report.json").write_text(proc.stdout)
    if proc.stderr.strip():
        (out / "stderr.txt").write_text(proc.stderr)
    return sub, which, proc.returncode, proc.stderr


def submit_all(rundir: Path, cands: list[int], parallel: int, only_missing: bool = False) -> None:
    jobs = [(sub, w) for n in cands for sub in sub_names(n) for w in ("ioff", "ron")]
    if only_missing:
        # Re-submit (to the batch backend again -- never locally) only requests
        # that produced no report at all, e.g. a fleet capacity refusal.
        jobs = [(s, w) for s, w in jobs if load_report(rundir, s, w) is None]
    errs = []
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        for sub, w, rc, err in pool.map(lambda j: submit_one(rundir, *j), jobs):
            print(f"{sub}/{w}: klt sim rc={rc}", flush=True)
            if rc != 0:
                errs.append(f"== {sub}/{w}: rc={rc}\n{err}\n")
    if errs:
        with open(rundir / "submit-errors.txt", "a") as fh:
            fh.write("".join(errs))


# ---------------------------------------------------------------------------
# Report decoding
# ---------------------------------------------------------------------------


def load_report(rundir: Path, sub: str, which: str):
    p = rundir / sub / which / "report.json"
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text())
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) and "corners" in d else None


def meas(c: dict) -> dict:
    return {m["name"]: m["value"] for m in c["measurements"]}


def ioff_points(rep) -> list[dict]:
    """-> [{process,temp,vread,voff,ioff,status}]"""
    out = []
    for c in rep["corners"]:
        v = meas(c).get("ibl")
        out.append({
            "process": c["process"], "temp": c["temperature_c"],
            "vread": c["supply_v"]["vbl"], "voff": c["supply_v"]["vwl"],
            "ioff": None if v is None else abs(v), "status": c["status"],
        })
    return out


def ron_points(rep) -> list[dict]:
    out = []
    for c in rep["corners"]:
        m = meas(c)
        ron = None
        if None not in (m.get("ire"), m.get("iim"), m.get("vre"), m.get("vim")):
            v = complex(m["vre"], m["vim"])
            i = complex(m["ire"], m["iim"])
            ron = (v / (-i)).real
        out.append({"process": c["process"], "temp": c["temperature_c"],
                    "vread": c["supply_v"]["vbl"], "ron": ron, "status": c["status"]})
    return out


def close(a, b):
    return abs(a - b) < 1e-9


def worst_ioff(points, proc, temp, vread):
    vals = [p["ioff"] for p in points
            if p["process"] == proc and p["temp"] == temp and close(p["vread"], vread) and p["ioff"] is not None]
    return max(vals) if vals else None


def grid_ioff(points):
    """(process,temp,vread) -> worst |I_off| over the three OFF-gate biases"""
    g = {}
    for p in points:
        if p["ioff"] is None:
            continue
        k = (p["process"], p["temp"], round(p["vread"], 2))
        g[k] = max(g.get(k, 0.0), p["ioff"])
    return g


def grid_ron(points):
    return {(p["process"], p["temp"], round(p["vread"], 2)): p["ron"] for p in points if p["ron"] is not None}


# ---------------------------------------------------------------------------
# Legacy harness values (read-only)
# ---------------------------------------------------------------------------


def legacy_record_for(n: int):
    """-> (record_id, record_text) of the legacy first-run record for candidate n."""
    for rec in sorted((EXP / "records").glob("2*.md")):
        if rec.stem.count("-") != 2:
            continue
        t = rec.read_text()
        if re.search(rf"Region \w+ / Candidate {n}\b", t):
            return rec.stem, t
    return None, None


def legacy_scalar(log: Path, name: str):
    m = re.search(rf"^\s*{name}\s*=\s*([0-9eE.+-]+)\s*$", log.read_text(), re.MULTILINE)
    return float(m.group(1)) if m else None


def fmt_v(v: float) -> str:
    return f"bl{v:.2f}".replace(".", "p") + "v"


def legacy_grid(rec_id: str, sub: str):
    """sub like c1_access-min_cap-min -> ({(proc,temp,vread): max ioff}, {..: ron})"""
    s = sub.split("_", 1)[1]
    d = EXP / "corners" / rec_id / s
    ig, rg = {}, {}
    for proc in MOS:
        for t in TEMPS:
            for v in (0.9, 1.0, 1.1):
                log = d / f"{proc}_{t}c_{fmt_v(v)}.log"
                vals = [legacy_scalar(log, k) for k in ("ioff_lo", "ioff_mid", "ioff_hi")]
                if None in vals:
                    continue
                ig[(proc, t, v)] = max(vals)
                r = legacy_scalar(log, "ron")
                if r is not None:
                    rg[(proc, t, v)] = r
    return ig, rg


def sci(x):
    return "n/a" if x is None else f"{x:.4e}"


# ---------------------------------------------------------------------------
# Record rendering
# ---------------------------------------------------------------------------


def render_record(rundir: Path, run_id: str, n: int, summary: dict) -> str:
    region = CANDS[n]
    leg_id, leg_text = legacy_record_for(n)
    L = []
    rid = f"{run_id}-c{n}"
    L.append(f"# Record {rid}")
    L.append("")
    L.append(f"- **Record ID**: {rid}")
    L.append(
        "- **Claim**: `spec/architecture.md#3-sneak-path-analysis-partially-programmed-array` "
        "(`I_sneak_max ~= (N-1) x I_off`) and `spec/architecture.md#4-sense-scheme` (the slow/cold "
        f"access-device series-resistance term). Region {region} / Candidate {n} "
        "(`spec/split-axis-plan.md`, `spec/cell-candidates.md`). Re-expression of the access-device "
        "bench as a `klt sim` request set; the capacitor C-V bench is NOT part of this record."
    )
    L.append(f"- **Netlist provenance**: schematic (`design/netlists/cell_candidate{n}.spice`, included unchanged)")
    L.append("- **Corner matrix run** (every axis below is a `klt sim` request axis except geometry/sizing):")
    L.append("  - Access-device MOS process: typical, ff, ss, fs, sf (bundled with `moscap_typical`"
             + ("; Candidate 2 also binds `smbb000149` at the same section" if n == 2 else "") + ")")
    L.append("  - Temperature: -40, 27, 125 degC")
    L.append("  - Read voltage on BL: 0.90 / 1.00 / 1.10 V; I_off additionally at the three OFF-gate biases "
             "of the legacy bench, enumerated in `corners.supply_v` alongside BL")
    L.append("  - Access-device sizing x capacitor geometry: min/2x x min/2x -- one request pair per "
             "sub-configuration (not a klt corner axis; see README). **Values used are the committed "
             "netlist-default geometry and its doublings, NOT the ratified split-axis levels** "
             "(unchanged caveat from the legacy record).")
    L.append("  - Requests: `sim/cell-device-characterization/klt/requests/c%d_access-*/{ioff,ron}.json`" % n)
    L.append("- **Result** (one block per sub-configuration; nothing is averaged across sub-configurations):")
    for sub in sub_names(n):
        ri, rr = load_report(rundir, sub, "ioff"), load_report(rundir, sub, "ron")
        s = sub.split("_", 1)[1]
        L.append(f"  - **{s}**")
        if ri is None or rr is None or ri["errored"] or rr["errored"]:
            L.append("    - NOT RESOLVED: the klt submit for this sub-configuration produced no usable report "
                     "(see `submit-errors*.txt` and the per-request `report.json` in the run directory). No local fallback was run.")
            for w, rep_ in (("ioff", ri), ("ron", rr)):
                if rep_ is not None:
                    msgs = sorted({d["message"] for c in rep_["corners"] for d in c["diagnostics"]})
                    for m in msgs[:2]:
                        L.append(f"      - `{w}` report diagnostic (verbatim): {m}")
            continue
        pi, pr = ioff_points(ri), ron_points(rr)
        bad = sum(1 for p in pi + pr if p["status"] != "pass" or (p.get("ioff", p.get("ron")) is None))
        rem_i = (ri.get("environment") or {}).get("remote") or {}
        rem_r = (rr.get("environment") or {}).get("remote") or {}
        L.append(f"    - klt corners: ioff {ri['corner_count']} (pass {ri['passed']}), ron {rr['corner_count']} "
                 f"(pass {rr['passed']}); unresolved: {bad}; batch jobs `{rem_i.get('job_id')}` / `{rem_r.get('job_id')}`")
        fi = worst_ioff(pi, FAST_HOT[0], FAST_HOT[1], FAST_HOT[2])
        L.append(f"    - fast/hot/high-read corner `ff_125c_bl1p10v`: worst |I_off| over OFF-gate biases = {sci(fi)} A "
                 f"-> 31 x = {sci(None if fi is None else (N_GRID - 1) * fi)} A")
        gr = grid_ron(pr)
        L.append(f"    - slow/cold/low-read corner `ss_-40c_bl0p90v`: R_on = {sci(gr.get((SLOW_COLD[0], SLOW_COLD[1], SLOW_COLD[2])))} ohm")
        gi = grid_ioff(pi)
        L.append("    - full grid (worst |I_off| over the three OFF-gate biases, A / R_on, ohm):")
        L.append("")
        L.append("      | process | temp | bl 0.90 V I_off | bl 1.00 V I_off | bl 1.10 V I_off | bl 0.90 V R_on | bl 1.00 V R_on | bl 1.10 V R_on |")
        L.append("      |---|---|---|---|---|---|---|---|")
        for proc in MOS:
            for t in TEMPS:
                row = [sci(gi.get((proc, t, v))) for v in (0.9, 1.0, 1.1)] + [sci(gr.get((proc, t, v))) for v in (0.9, 1.0, 1.1)]
                L.append(f"      | {proc} | {t} | " + " | ".join(row) + " |")
        L.append("")
    # headline per region
    sc = summary["regions"].get(str(n), {})
    L.append("  - **Region headline (worst case across this region's four sub-configurations; the per-sub-configuration "
             "values above are the primary record):**")
    L.append(f"    - `I_sneak_max = {N_GRID-1} x I_off` at `ff_125c_bl1p10v`: **{sci(sc.get('i_sneak_max'))} A** "
             f"(klt) vs legacy {sci(sc.get('legacy_i_sneak_max'))} A")
    L.append(f"    - `R_on` at `ss_-40c_bl0p90v`: **{sci(sc.get('r_on_worst'))} ohm** (klt) vs legacy {sci(sc.get('legacy_r_on'))} ohm")
    L.append(f"  - **Reproduction check against the legacy harness** (`{leg_id}`): stated tolerance {TOL_REL*100:.0f}% relative; "
             f"max relative deviation over {sc.get('n_compared', 0)} compared grid values: I_off "
             f"{sc.get('max_dev_ioff', 'n/a')}, R_on {sc.get('max_dev_ron', 'n/a')}; headline within tolerance: "
             f"**{sc.get('headline_ok')}**; all grid values within tolerance: **{sc.get('grid_ok')}**.")
    L.append("  - I_off remains a gmin-floor-limited upper bound exactly as in the legacy record (`.options gmin=1e-13`, "
             "same bench); stated as the `I_ref > I_sneak_max` lower bound only.")
    L.append("- **Links**:")
    L.append("  - Request set + generator: `sim/cell-device-characterization/klt/`")
    L.append(f"  - klt reports (cited from `signoff/manifest.json` where applicable): `sim/cell-device-characterization/klt/runs/{run_id}/`")
    L.append(f"- **Timestamp / author**: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, agent-builder")
    L.append(f"- **Supersedes**: (none -- supplements legacy record `{leg_id}`, which stays authoritative until a human retires the old harness)")
    L.append("")
    return "\n".join(L)


def compute_summary(rundir: Path, cands: list[int]) -> dict:
    summary = {"regions": {}}
    for n in cands:
        leg_id, leg_text = legacy_record_for(n)
        m_sn = re.search(r"\*\*I_sneak_max = ([0-9.e+-]+) A\*\*", leg_text or "")
        m_ro = re.search(r"\*\*R_on = ([0-9.e+-]+) ohm\*\*", leg_text or "")
        leg_sn = float(m_sn.group(1)) if m_sn else None
        leg_ro = float(m_ro.group(1)) if m_ro else None
        fh, sc = [], []
        devi, devr, ncmp, complete = [], [], 0, True
        for sub in sub_names(n):
            ri, rr = load_report(rundir, sub, "ioff"), load_report(rundir, sub, "ron")
            if ri is None or rr is None:
                complete = False
                continue
            pi, pr = ioff_points(ri), ron_points(rr)
            if any(p["status"] != "pass" for p in pi + pr):
                complete = False
            v = worst_ioff(pi, *FAST_HOT)
            if v is not None:
                fh.append(v)
            r = grid_ron(pr).get((SLOW_COLD[0], SLOW_COLD[1], SLOW_COLD[2]))
            if r is not None:
                sc.append(r)
            lig, lrg = legacy_grid(leg_id, sub)
            gi, gr = grid_ioff(pi), grid_ron(pr)
            for k, lv in lig.items():
                if k in gi:
                    ncmp += 1
                    devi.append(abs(gi[k] - lv) / lv)
            for k, lv in lrg.items():
                if k in gr:
                    devr.append(abs(gr[k] - lv) / lv)
        i_sn = (N_GRID - 1) * max(fh) if fh else None
        r_on = max(sc) if sc else None
        head_ok = (
            complete and len(fh) == 4 and len(sc) == 4 and leg_sn is not None and leg_ro is not None
            and abs(i_sn - leg_sn) / leg_sn <= TOL_REL and abs(r_on - leg_ro) / leg_ro <= TOL_REL
        )
        grid_ok = complete and bool(devi) and max(devi) <= TOL_REL and max(devr) <= TOL_REL
        summary["regions"][str(n)] = {
            "complete": complete, "i_sneak_max": i_sn, "r_on_worst": r_on,
            "legacy_record": leg_id, "legacy_i_sneak_max": leg_sn, "legacy_r_on": leg_ro,
            "n_compared": ncmp,
            "max_dev_ioff": f"{max(devi):.2e}" if devi else "n/a",
            "max_dev_ron": f"{max(devr):.2e}" if devr else "n/a",
            "headline_ok": bool(head_ok), "grid_ok": bool(grid_ok), "tolerance_rel": TOL_REL,
        }
    return summary


def ingest(rundir: Path, cands: list[int]) -> None:
    run_id = rundir.name
    summary = compute_summary(rundir, cands)
    R.write_once(rundir / "summary.json", json.dumps(summary, indent=2) + "\n")
    for n in cands:
        R.write_once(EXP / "records" / f"{run_id}-c{n}.md", render_record(rundir, run_id, n, summary))
        print(f"record: records/{run_id}-c{n}.md  headline_ok={summary['regions'][str(n)]['headline_ok']} "
              f"grid_ok={summary['regions'][str(n)]['grid_ok']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--parallel", type=int, default=2, help="concurrent klt submits (each is a fleet job, not local ngspice)")
    ap.add_argument("--ingest-only", metavar="RUNDIR", help="skip submission; ingest an existing run directory")
    ap.add_argument("--resume", metavar="RUNDIR", help="re-submit only requests with no report in RUNDIR, then ingest")
    args = ap.parse_args(argv)
    cands = [int(x) for x in args.candidates.split(",") if x.strip()]
    if args.ingest_only:
        rundir = Path(args.ingest_only).resolve()
    elif args.resume:
        rundir = Path(args.resume).resolve()
        submit_all(rundir, cands, args.parallel, only_missing=True)
    else:
        run_id = R.allocate_record_id(EXP, REPO)
        rundir = RUNS_DIR / run_id
        rundir.mkdir(parents=True)
        submit_all(rundir, cands, args.parallel)
    ingest(rundir, cands)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
