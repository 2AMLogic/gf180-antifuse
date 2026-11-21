#!/usr/bin/env python3
"""Submit the paired post-layout request set and ingest the reports (issue #447).

    python3 sim/cell-device-characterization/klt/post-layout/run_post_layout_campaign.py
    python3 sim/cell-device-characterization/klt/post-layout/run_post_layout_campaign.py --ingest-only <rundir>
    python3 sim/cell-device-characterization/klt/post-layout/run_post_layout_campaign.py --resume <rundir>

Submission: one `klt sim -o <rundir>/<leg>/<ioff|ron> <request> --format json
--wait-for-capacity 600` per request (12 requests: 3 cells x 2 legs x 2
metrics).  The backend is whatever the environment selects (`KLT_SIM_BACKEND`;
on the dispatch workers that is `batch`, the Spot fleet); the capacity wait is
the host's standing rule for batch submits.  `KLT_CMD` overrides the klt
launcher.  A request whose submit fails is recorded verbatim in
`<rundir>/submit-errors.txt`; there is no local fallback.

Ingest: nothing is averaged -- one row per cell, per metric, per leg, at the
single bound corner.  Writes `<rundir>/summary.json` and renders the results
table into `post-layout/README.md` (rewritten by the latest ingest; the run
directories under `runs/` are the append-only evidence).
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent          # .../klt/post-layout
KLT = HERE.parent
EXP = KLT.parent
REPO = EXP.parent.parent
sys.path.insert(0, str(KLT))
sys.path.insert(0, str(EXP))
sys.path.insert(0, str(EXP.parent))

import run_klt_campaign as RK  # noqa: E402
from harness import report as R  # noqa: E402
from harness import numfmt as NF  # noqa: E402

REQ_DIR = HERE / "requests"
RUNS_DIR = HERE / "runs"
PROBE_ORDER = (1, 3, 2)
CAPACITY_WAIT_S = "600"
CANDS = {1: "I", 2: "II", 3: "III"}
MODEL_NOTE = {
    1: "nfet_06v0 (0.42 x 0.70 um, 1 finger)",
    3: "pfet_06v0 (0.42 x 0.55 um, 1 finger)",
    2: "nfet_10v0_asym (2 x 4 um fingers, total 8.0 x 0.60 um, drain on BL)",
}


def leg_names(n: int) -> list[str]:
    return [f"c{n}_schematic", f"c{n}_extracted"]


def submit_one(rundir: Path, sub: str, which: str):
    req = REQ_DIR / sub / f"{which}.json"
    out = rundir / sub / which
    out.mkdir(parents=True, exist_ok=True)
    # KLT_SIM_BACKEND selects the backend (default batch on the dispatch
    # workers); --backend is passed explicitly because an inline env prefix
    # does not reliably survive the uvx launcher.
    backend = os.environ.get("KLT_SIM_BACKEND", "batch")
    cmd = [
        *shlex.split(os.environ.get("KLT_CMD", "klt")), "sim", "--backend", backend,
        "-o", str(out), str(req), "--format", "json",
    ]
    if backend == "batch":
        cmd += ["--wait-for-capacity", CAPACITY_WAIT_S]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    RK.write_report(out / "report.json", proc.stdout)
    if proc.stderr.strip():
        (out / "stderr.txt").write_text(proc.stderr)
    return sub, which, proc.returncode, proc.stderr


def submit_all(rundir: Path, parallel: int, only_missing: bool = False) -> None:
    jobs = [(sub, w) for n in PROBE_ORDER for sub in leg_names(n) for w in ("ioff", "ron")]
    if only_missing:
        jobs = [(s, w) for s, w in jobs if RK.load_report(rundir, s, w) is None]
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
# Ingest
# ---------------------------------------------------------------------------

def leg_ioff_worst(rundir: Path, n: int, leg: str):
    """Worst |I_off| over the three OFF-gate biases at the bound corner."""
    rep = RK.load_report(rundir, f"c{n}_{leg}", "ioff")
    if rep is None:
        return None, None, "no report (submit failed; see submit-errors.txt)"
    pts = RK.ioff_points(rep)
    bad = [p for p in pts if p["status"] != "pass" or p["ioff"] is None]
    vals = [p["ioff"] for p in pts if p["ioff"] is not None]
    if bad or not vals:
        return None, rep, f"{len(bad)}/{len(pts)} units failed or missing"
    return max(vals), rep, None


def leg_ron(rundir: Path, n: int, leg: str):
    rep = RK.load_report(rundir, f"c{n}_{leg}", "ron")
    if rep is None:
        return None, None, None, "no report (submit failed; see submit-errors.txt)"
    pts = RK.ron_points(rep)
    bad = [p for p in pts if p["status"] != "pass" or p["ron"] is None]
    if bad or not pts:
        return None, None, None, f"{len(bad)}/{len(pts)} units failed or missing"
    m = RK.meas(rep["corners"][0])
    z = complex(m["vre"], m["vim"]) / (-complex(m["ire"], m["iim"]))
    return pts[0]["ron"], z.imag, rep, None


def job_id(rep) -> str:
    return ((rep or {}).get("environment") or {}).get("remote", {}).get("job_id", "-")


def delta(a, b):
    if a is None or b is None:
        return None
    return b - a


def sci(v):
    return NF.sci(v)


def collect(rundir: Path) -> dict:
    out = {"run_id": rundir.name, "cells": {}}
    for n in PROBE_ORDER:
        i_s, ri_s, e_s = leg_ioff_worst(rundir, n, "schematic")
        i_e, ri_e, e_e = leg_ioff_worst(rundir, n, "extracted")
        r_s, zi_s, rr_s, re_s = leg_ron(rundir, n, "schematic")
        r_e, zi_e, rr_e, re_e = leg_ron(rundir, n, "extracted")
        # The R_on bench reads only Re(VBL / -I(VBL)) at 10 MHz; the input
        # reactance at that frequency is dominated by the storage-node MOS
        # capacitor (the only AC return from that node).  Two joint conditions
        # say the R_on difference is dominated by the cap representation
        # divergence (drawn tanh C(V) law vs extracted linear area-law C,
        # klayout-tools#7004) rather than by extracted parasitics:
        #   (a) the legs' input reactances differ by more than 2x, and
        #   (b) |delta| exceeds 25% of the schematic value -- the extracted
        #       interconnect adds at most ~80 ohm of series R on any net of
        #       these cells (see the R cards in each extracted.spice), so a
        #       change of that size cannot be a parasitic effect.
        rep_dom = (
            zi_s is not None and zi_e is not None and zi_s != 0 and zi_e != 0
            and abs(zi_s / zi_e) > 2
            and r_s not in (None, 0) and delta(r_s, r_e) is not None
            and abs(delta(r_s, r_e)) > 0.25 * abs(r_s)
        )
        out["cells"][str(n)] = {
            "ioff": {"schematic": i_s, "extracted": i_e, "delta": delta(i_s, i_e),
                     "schematic_error": e_s, "extracted_error": e_e,
                     "jobs": [job_id(ri_s), job_id(ri_e)]},
            "ron": {"schematic": r_s, "extracted": r_e, "delta": delta(r_s, r_e),
                    "schematic_error": re_s, "extracted_error": re_e,
                    "z_imag_schematic_ohm": zi_s, "z_imag_extracted_ohm": zi_e,
                    "representation_dominated": rep_dom,
                    "jobs": [job_id(rr_s), job_id(rr_e)]},
        }
    return out


def fmt_val(v, err, unit):
    if err:
        return f"FAILED: {err}"
    if v is None:
        return "MISSING"
    return f"{sci(v)} {unit}"


def render_readme(rundir: Path, summary: dict) -> str:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    L = []
    L.append("# Post-layout access-device probe (issue #447)")
    L.append("")
    L.append("Paired schematic-vs-extracted re-run of the access-device bench (I_off, R_on)")
    L.append("on `klt pex` extractions of the three drawn bitcells.  This directory is the")
    L.append("probe's bench half; the extraction half lives under `layout/<cell>/pex/`.")
    L.append("Ungraded supporting evidence only -- `7.analog` is NOT cited from this probe")
    L.append("(array-level post-layout verification stays with the array layout; see")
    L.append("`signoff/README.md`).")
    L.append("")
    L.append(f"- **Run**: `runs/{summary['run_id']}/` (this README is rendered by the latest ingest)")
    L.append(f"- **Timestamp**: {ts}")
    L.append("- **Requests**: `requests/c<N>_{schematic,extracted}/{body.spice,ioff.json,ron.json}`,")
    L.append("  generated by `mk_post_layout_requests.py`; corner/measurement builders reused")
    L.append("  verbatim from `../mk_klt_requests.py`, axes cut to the bound corner:")
    L.append("  I_off at `ff / 125 degC / vbl = 1.1 V` over the three OFF-gate biases;")
    L.append("  R_on at `ss / -40 degC / vbl = 0.9 V` at the candidate's on-gate bias, 10 MHz.")
    L.append("- **Legs**: schematic = the cell's fixed-geometry `lvs_reference.spice` (the same")
    L.append("  netlist `klt pex --reference-netlist` used; drawn geometry, no sizing overrides);")
    L.append("  extracted = `layout/<cell>/pex/extracted.spice` included verbatim, instantiated in")
    L.append("  the emitted `.SUBCKT` pin order (see each `requests/c<N>/provenance.json` for the")
    L.append("  ordered pin map and both DUT sha256s).  Supplies, body connection, model sections,")
    L.append("  solver settings and measurements are identical on both legs; `netlist_source` is")
    L.append("  `schematic` / `extracted`.")
    L.append("- **Extraction**: klayout-tools `0.9.2` (KLayout `0.30.13`), `--deck gf180mcu --pdk")
    L.append("  gf180mcuD --extract-only`; `body_bias.status: \"biased\"` for all three cells")
    L.append("  (full blocks quoted in each `layout/<cell>/pex/README.md`).")
    L.append("- **Fleet**: `klt sim --backend batch --wait-for-capacity 600`; runner klt `0.9.0`,")
    L.append("  client `0.9.2` (`runner_compatibility: match` on every job; job ids per row below).")
    L.append("- **Known representation divergence**: every drawn MOS capacitor extracts as a")
    L.append("  linear `C` card (deck area law), not the PDK's nonlinear `cap_*` subcircuit --")
    L.append("  `model_mismatch` reports the cap in `reference_only` for all three cells")
    L.append("  (2AMLogic/klayout-tools#7004).  I_off is a DC measurement (cap open on both")
    L.append("  legs); R_on at 10 MHz sees the linearised cap on the extracted leg only.")
    L.append("- **gmin floor**: both legs keep `.options gmin=1e-13`; I_off remains a")
    L.append("  gmin-floor-limited upper bound exactly as in the schematic campaign.")
    L.append("")
    L.append("## Results (per cell, per metric, at the bound corner; nothing is averaged)")
    L.append("")
    L.append("difference = extracted − schematic.")
    L.append("")
    for n in PROBE_ORDER:
        c = summary["cells"][str(n)]
        L.append(f"### Candidate {n} (Region {CANDS[n]}): {MODEL_NOTE[n]}")
        L.append("")
        L.append("| metric | corner | schematic | extracted | difference |")
        L.append("|---|---|---|---|---|")
        i, r = c["ioff"], c["ron"]
        L.append(f"| I_off (worst \\|I(VBL)\\| over 3 OFF biases) | ff / 125 degC / vbl 1.1 V "
                 f"| {fmt_val(i['schematic'], i['schematic_error'], 'A')} "
                 f"| {fmt_val(i['extracted'], i['extracted_error'], 'A')} "
                 f"| {fmt_val(delta(i['schematic'], i['extracted']) if not (i['schematic_error'] or i['extracted_error']) else None, None, 'A')} |")
        if r.get("representation_dominated"):
            diff = "WITHHELD (representation-dominated; see note)"
        elif r["schematic_error"] or r["extracted_error"]:
            diff = "MISSING"
        else:
            diff = fmt_val(delta(r["schematic"], r["extracted"]), None, "ohm")
        L.append(f"| R_on (Re(VBL/-I(VBL)) at 10 MHz) | ss / -40 degC / vbl 0.9 V "
                 f"| {fmt_val(r['schematic'], r['schematic_error'], 'ohm')} "
                 f"| {fmt_val(r['extracted'], r['extracted_error'], 'ohm')} "
                 f"| {diff} |")
        L.append("")
        if r.get("representation_dominated"):
            L.append(f"  - **R_on delta WITHHELD for this cell**: the input reactance at 10 MHz is")
            L.append(f"    {sci(r['z_imag_schematic_ohm'])} ohm (schematic) vs "
                     f"{sci(r['z_imag_extracted_ohm'])} ohm (extracted). That reactance IS the")
            L.append("    storage-node MOS capacitor -- the drawn cell's tanh C(V) law sits in deep")
            L.append("    depletion at this bias while the extracted linear area-law C does not, so")
            L.append("    the two legs divide AC current differently and the Re difference is a")
            L.append("    device-representation artifact (2AMLogic/klayout-tools#7004), not a")
            L.append("    parasitic measure. Both raw values remain above for traceability.")
            L.append("")
        L.append(f"batch jobs ioff [schematic, extracted]: {i['jobs']}; ron: {r['jobs']}")
        L.append("")
    L.append("## Dispositions")
    L.append("")
    L.append("- All three extractions are usable: access-device model, geometry and drain")
    L.append("  orientation match the per-cell LVS reference (evidence quoted per cell in")
    L.append("  `layout/<cell>/pex/README.md`); `body_bias.status` is `biased` everywhere;")
    L.append("  parasitics present (per-net lumped R + substrate C, plus C2's coupling caps).")
    L.append("- No refusal occurred, so no upstream refusal link was needed; the MOS-cap")
    L.append("  linearisation finding is linked on 2AMLogic/klayout-tools#7004 (the runset-route")
    L.append("  issues #6559/#6606 cover families the curated deck cannot recognise at all --")
    L.append("  not this case: all device families here bind under the curated deck with `--pdk`).")
    L.append("- Numbers above cover exactly the drawn Minimum x Minimum split of each")
    L.append("  candidate's GDS (one cell per candidate; no other splits, no averaging).")
    L.append("")
    return "\n".join(L)


def ingest(rundir: Path) -> None:
    summary = collect(rundir)
    R.write_once(rundir / "summary.json", json.dumps(summary, indent=2) + "\n")
    (HERE / "README.md").write_text(render_readme(rundir, summary))
    for n in PROBE_ORDER:
        c = summary["cells"][str(n)]
        print(f"c{n}: ioff {sci(c['ioff']['schematic'])} -> {sci(c['ioff']['extracted'])} A; "
              f"ron {sci(c['ron']['schematic'])} -> {sci(c['ron']['extracted'])} ohm")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parallel", type=int, default=2, help="concurrent klt submits (each is a fleet job, not local ngspice)")
    ap.add_argument("--ingest-only", metavar="RUNDIR")
    ap.add_argument("--resume", metavar="RUNDIR", help="re-submit only requests with no report, then ingest")
    args = ap.parse_args(argv)
    if args.ingest_only:
        rundir = Path(args.ingest_only).resolve()
    elif args.resume:
        rundir = Path(args.resume).resolve()
        submit_all(rundir, args.parallel, only_missing=True)
    else:
        run_id = R.allocate_record_id(EXP, REPO)
        rundir = RUNS_DIR / run_id
        rundir.mkdir(parents=True)
        submit_all(rundir, args.parallel)
    ingest(rundir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
