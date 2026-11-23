#!/usr/bin/env python3
"""sim/programming-yield -- programming-yield Monte Carlo campaign (issue #66).

Per ratified candidate (== per grid region), per access-sizing sub-
configuration, per program-pulse condition (spec/split-axis-plan.md section
4) and per PVT corner, it draws `n` Monte Carlo samples of the breakdown-
threshold quantile (`ubd`) and the filament-resistance draw (`zrf`) of the
behavioral breakdown element in design/breakdown/, applies the program pulse
in a transient, and counts successes. Everything is a `klt sim` request with
a `monte_carlo` block submitted to the batch fleet; a failed submit is
recorded and NEVER falls back to a local grid.

    python3 sim/programming-yield/run_experiment.py --check-env
    python3 sim/programming-yield/run_experiment.py --candidates 1 --n 24
    python3 sim/programming-yield/run_experiment.py --smoke 1      # ONE sample, locally (probe)
    python3 sim/programming-yield/run_experiment.py --render RID --candidates 1

Stdlib only. The bench library of sim/cell-breakdown-model is imported, not
copied, so the candidates, bias placeholders, geometry levels and fleet
workarounds are identical by construction.

The library itself lives in the siblings model.py (campaign constants, deck
and request builders, statistical analysis, saved-report loaders) and
render.py (the record renderer); this file is the CLI driver and re-exports
their surface, so loading run_experiment.py as a library
keeps every attribute unchanged.
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))
from harness import corners as C  # noqa: E402
from harness import evidence_store as ES  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402

# The library siblings are loaded once each under fixed unique names (never a
# bare `import`, which under python3 -I has no script dir on sys.path and
# would collide in sys.modules with other experiments' sibling modules).
# model first: render.py reuses the already-loaded copy from sys.modules.
M = load_module(THIS_DIR / "model.py", "sim_py_model")
RENDER = load_module(THIS_DIR / "render.py", "sim_py_render")

BM = M.BM
CHAR = M.CHAR
CHECK = M.CHECK
BD_DIR = M.BD_DIR


def __getattr__(name: str):
    """Re-export model.py's and render.py's library surface under this module,
    so `load_module(.../run_experiment.py)` callers see the attribute set the
    pre-split single file had. Dynamic on purpose: module state that the CLI
    mutates in place (`PARAMS`, updated by main) must be read through to the
    owning module, not frozen at load time."""
    for src in (M, RENDER):
        try:
            return getattr(src, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


KLT_CMD = BM.KLT_CMD


def run_group(bdir: Path, req: dict) -> tuple[dict | None, str | None]:
    R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
    report, err = BM.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
    if report is not None and "corners" in report:
        # gzip: the plain reports are ~1 MB per 300 samples; the content is byte-identical once gunzipped
        gz = bdir / "report.json.gz"
        if gz.exists():
            raise FileExistsError(f"refusing to overwrite existing evidence file: {gz}")
        with gzip.GzipFile(gz, "wb", mtime=0) as fh:
            fh.write((json.dumps(report, indent=2) + "\n").encode())
        return report, None
    R.write_once(bdir / "submit-error.txt", (err or json.dumps(report)[:4000]) + "\n")
    return None, err or "no corners in report"


def snapshot(cand) -> str:
    return BM.snapshot(cand)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def smoke(pdk, cand, params: dict) -> int:
    """ONE sample, ONE corner, locally -- a debug probe, not evidence."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}"
    work.mkdir(parents=True)
    tw = M.NOMINAL_TW
    body, ms = M.body_yield(pdk, cand, defaults, work, str(pdk.variant_dir), "min", tw)
    (work / "body.spice").write_text(body)
    req = M.make_request(cand, pdk, ms, tw, [M.NOMINAL_FRAC], 1, ["moscap_typical"], [27.0], M.MC_SEED)
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    t0 = time.time()
    report, err = BM.run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    print(f"smoke c{cand.n}: {c['corner_id']} status={c['status']} {time.time() - t0:.1f}s wall; work dir {work}")
    for m in c["measurements"]:
        print(f"   {m['name']} = {m['value']}")
    return 0 if c["status"] == "pass" else 1


def render_only(pdk, cand, rid: str, params: dict, ibound: float, n: int, note: str | None,
                supersedes: str | None = None) -> int:
    base = ES.run_dir_for_reading("programming-yield", rid, REPO_ROOT, THIS_DIR / "corners" / rid)
    groups, readtab, rerr = M.load_run(cand, rid, base_dir=base)
    if not groups:
        print(f"ERROR: no saved reports for {rid} (disk or artifact store)", file=sys.stderr)
        return 2
    pf = base / "run-provenance.json"
    dirty = json.loads(pf.read_text())["dirty"] if pf.is_file() else None
    snap = THIS_DIR / "netlist-snapshots" / f"{rid}.spice"
    if not snap.exists():
        R.write_once(snap, snapshot(cand))
    R.write_once(THIS_DIR / "records" / f"{rid}.md",
                 RENDER.render_record(pdk, cand, rid, groups, readtab, rerr, params, dirty, ibound, n, note,
                                      supersedes))
    print(f"record: records/{rid}.md (rendered from saved reports)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--n", type=int, default=100, help="Monte Carlo samples per cell")
    ap.add_argument("--processes", default=",".join(C.MOSCAP_CORNERS))
    ap.add_argument("--temps", default=",".join(str(t) for t in C.TEMPS_C))
    ap.add_argument("--ibound", type=float, default=M.I_BOUND_DEFAULT)
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--smoke", default=None, metavar="N")
    ap.add_argument("--render", default=None, metavar="RECORD_ID")
    ap.add_argument("--note", default=None)
    ap.add_argument("--conds", default="", help="comma list of condition tags to run (default: all 5)")
    ap.add_argument("--sizings", default=",".join(M.SIZINGS))
    ap.add_argument("--supersedes", default=None, help="record id this run supersedes (stated in the record)")
    ap.add_argument("--no-readtab", action="store_true", help="skip the programmed-read table request")
    ap.add_argument("--klt", default="klt")
    args = ap.parse_args(argv)
    KLT_CMD[:] = args.klt.split()
    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if not shutil.which(KLT_CMD[0]):
        print(f"ERROR: {KLT_CMD[0]} not on PATH", file=sys.stderr)
        return 3
    params, perr = CHECK.parse_params((BD_DIR / "breakdown_params.spice").read_text())
    if perr:
        print("ERROR: breakdown_params.spice fails provenance checks", file=sys.stderr)
        return 3
    M.PARAMS.update(params)
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK + parameter file OK.")
        return 0
    by_n = {c.n: c for c in CHAR.CANDIDATES}
    if args.render:
        return render_only(pdk, by_n[int(args.candidates)], args.render, params, args.ibound, args.n, args.note,
                           args.supersedes)
    if args.smoke:
        return smoke(pdk, by_n[int(args.smoke)], params)

    conds = {x for x in args.conds.split(",") if x}
    sizings = [x for x in args.sizings.split(",") if x]
    procs = [x for x in args.processes.split(",") if x]
    temps = [float(x) for x in args.temps.split(",") if x]
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n_c in [int(x) for x in args.candidates.split(",") if x.strip()]:
        cand = by_n[n_c]
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n_c} (Region {cand.region}) record {rid}")
        base = THIS_DIR / "corners" / rid
        R.write_once(base / "run-provenance.json",
                     json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty, "n": args.n,
                                 "processes": procs, "temps": temps, "ibound": args.ibound}) + "\n")
        jobs: list[tuple[str, Path, dict]] = []
        for sz in sizings:
            for cnd in M.conditions():
                if conds and cnd["tag"] not in conds:
                    continue
                for proc in procs:
                    gdir = base / M.gtag(sz, cnd, proc)
                    gdir.mkdir(parents=True)
                    body, ms = M.body_yield(pdk, cand, defaults, gdir, BM.FLEET_PDK_VARIANT_DIR, sz, cnd["tw"])
                    R.write_once(gdir / "body.spice", body)
                    jobs.append((f"{sz}/{cnd['tag']}/{proc}", gdir,
                                 M.make_request(cand, pdk, ms, cnd["tw"], [cnd["frac"]], args.n, [proc], temps, M.proc_seed(proc))))
        if cand.n != 3 and not args.no_readtab:
            gdir = base / "readtab"
            gdir.mkdir(parents=True)
            body, ms = M.body_readtab(pdk, cand, defaults, gdir, BM.FLEET_PDK_VARIANT_DIR)
            R.write_once(gdir / "body.spice", body)
            jobs.append(("readtab", gdir, M.make_readtab_request(cand, pdk, ms)))
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.time()

        def go(j):
            return j[0], run_group(j[1], j[2])
        with ThreadPoolExecutor(max_workers=2) as ex:      # fleet submits, not local simulation
            for label, (report, err) in ex.map(go, jobs):
                job = ((report or {}).get("environment", {}).get("remote") or {}).get("job_id")
                print(f"   {label}: {'ok ' + str(report.get('status')) if report else 'SUBMIT ERROR'} "
                      f"({time.time() - t0:.0f}s, job {job})" + (f" {err[:200]}" if err else ""), flush=True)
                if not report:
                    rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", snapshot(cand))
        groups, readtab, rerr = M.load_run(cand, rid)
        R.write_once(THIS_DIR / "records" / f"{rid}.md",
                     RENDER.render_record(pdk, cand, rid, groups, readtab, rerr, params, dirty, args.ibound, args.n,
                                          args.note, args.supersedes))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("programming-yield", rid, base, REPO_ROOT)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
