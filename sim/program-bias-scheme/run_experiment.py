#!/usr/bin/env python3
"""sim/program-bias-scheme -- program bias schemes against the ratified
access-device ratings, per candidate and per PVT corner (issue #90).

Two things, both reusing sim/cell-breakdown-model as a library (deck
helpers, breakdown wrapper, candidate definitions, corner grid, klt runner),
so the stimulus levels, the 45-corner grid and the assumed breakdown
parameters are identical by construction:

  --retabulate   Re-tabulate the EXISTING fleet evidence of the BL-driven
                 program leg (cell-breakdown-model `progc_*` benches, records
                 20261014-0017{17,20,23}-86afd07) as one row per PVT corner
                 with every access-device terminal-pair extreme. Runs no
                 simulation.
  (default)      Run the PL-driven scheme on the batch fleet:
                   plb_<v>   VPP pulse -> ballast -> PL; BL = 0 V through an
                             ammeter; WL, VB static at the #62 "on" bias.
                   plu_st    the same PL pulse on an UNSELECTED stock cell:
                             WL at its OFF level, BL = 0 V; CN floats.
                 with <v> = st (stock cell), b1m / b1l (element enabled,
                 median / low Weibull quantile). Each bench is one `klt sim`
                 request (3 moscap corners x 3 T x 5 levels = 45 corners),
                 submitted to the batch fleet; never run as a local grid.

    python3 sim/program-bias-scheme/run_experiment.py --retabulate
    python3 sim/program-bias-scheme/run_experiment.py --candidates 1,2,3
    python3 sim/program-bias-scheme/run_experiment.py --smoke 2:plb_b1m   # ONE local corner

All results are conditional on the ASSUMED breakdown parameters in
design/breakdown/breakdown_params.spice (V_bd 8.0 / 15.2 / 7.9 V). Nothing
here relaxes or edits a ratified spec.

The library itself lives in the siblings model.py (bench/drive constants,
deck-body and request builders, saved-report loaders) and render.py (the
record renderers); this file is the CLI driver and re-exports their
surface, so loading run_experiment.py as a library (as compare_vbd.py and
the tests do) keeps every attribute unchanged.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import evidence_store as ES  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402

# The library siblings are loaded once each under fixed unique names (never a
# bare `import`, which under python3 -I has no script dir on sys.path and
# would collide in sys.modules with other experiments' sibling modules, or
# with compare_vbd.py's own "sim_pbs_cmp" load of this file).
# model first: render.py reuses the already-loaded copy from sys.modules.
M = load_module(THIS_DIR / "model.py", "sim_pbs_model")
RENDER = load_module(THIS_DIR / "render.py", "sim_pbs_render")

# The library surface the CLI below calls directly (everything else is
# re-exported lazily through __getattr__).
CB = M.CB
CHAR = M.CHAR
BENCHES = M.BENCHES
LEGACY_BENCHES = M.LEGACY_BENCHES
GWD_BENCHES = M.GWD_BENCHES
body_pl = M.body_pl
make_request = M.make_request
collect = M.collect
load_saved = M.load_saved
render_retab = RENDER.render_retab
render_pl = RENDER.render_pl


def __getattr__(name: str):
    """Re-export model.py's and render.py's library surface under this module,
    so `load_module(.../run_experiment.py)` callers see the attribute set the
    pre-split single file had. Dynamic on purpose: module state that the
    library mutates in place (cell-breakdown-model's `VBD_EBD_OVERRIDE`,
    armed by apply_vbd_case) must be read through to the owning module, not
    frozen at load time."""
    for src in (M, RENDER):
        try:
            return getattr(src, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """dir() parity with the pre-split module: dir() does not consult
    __getattr__, so without this the facade would advertise only its own
    names instead of the library surface callers actually resolve -- losing
    tab completion and help() for interactive use."""
    return sorted(set(globals()) | {n for n in dir(M) + dir(RENDER) if not n.startswith("_")})


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def smoke(pdk, cand, bench: str, params: dict, idx: int = 3) -> int:
    """ONE corner of ONE bench, locally -- a debug probe, not evidence."""
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}-{bench}"
    work.mkdir(parents=True)
    body, ms = body_pl(pdk, cand, defaults, work, str(pdk.variant_dir), bench, params)
    (work / "body.spice").write_text(body)
    req = make_request(bench, cand, pdk, ms, params)
    corners = req["corners"]
    corners["process"] = corners["process"][:1]
    corners["temperature_c"] = [27.0]
    vals = corners["supply_v"]["vamp"]
    corners["supply_v"] = {"vamp": [vals[idx]]}        # default index 3 = 1.0 x V_bd
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    report, err = CB.run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke {bench}: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    print(f"smoke c{cand.n} {bench}: {c['corner_id']} status={c['status']}; work dir {work}")
    for m in c["measurements"]:
        print(f"   {m['name']} = {m['value']}")
    return 0 if c["status"] == "pass" else 1


def render_only(pdk, cand, rid: str, base_params: dict, note: str | None = None,
                vbd_case: str | None = None) -> int:
    """Re-render one record from saved reports; refuse to mint an empty one.

    Reads the run dir, or the artifact store once the run has been consumed
    (run_dir_for_reading fetches the stored copy back). An empty result means
    the reports could not be found anywhere: writing would commit a record
    with an empty convergence table and no per-bench sections, and write_once
    makes that permanent, so error out instead.
    """
    params = CB.apply_vbd_case(base_params, vbd_case, cand.n)
    res = load_saved(cand, rid, params,
                     base_dir=ES.run_dir_for_reading("program-bias-scheme", rid, REPO_ROOT,
                                                     THIS_DIR / "corners" / rid))
    if not res:
        print(f"ERROR: no saved reports for {rid} (disk or artifact store)", file=sys.stderr)
        return 2
    R.write_once(THIS_DIR / "records" / f"{rid}.md",
                 CB.tag_record(render_pl(pdk, cand, rid, params, res, note),
                               CB.sensitivity_block(vbd_case, cand.n, params)))
    print(f"record: records/{rid}.md (rendered from saved reports)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=",".join(LEGACY_BENCHES),
                    help="comma list; the Candidate 3 gate/well benches (" + ",".join(GWD_BENCHES) +
                         ") are opt-in: --candidates 3 --benches " + ",".join(GWD_BENCHES))
    ap.add_argument("--retabulate", action="store_true", help="re-tabulate existing BL-driven evidence (no sim)")
    ap.add_argument("--retab-src", default=None, metavar="RECORD_ID",
                    help="with --retabulate and ONE candidate: re-tabulate this cell-breakdown-model record's "
                         "progc_* reports (a #130 sensitivity run) instead of the #62/#74 original")
    ap.add_argument("--smoke", default=None, metavar="N:BENCH[:LEVEL_INDEX]", help="ONE local corner (debug probe, no record)")
    ap.add_argument("--resume", default=None, metavar="RECORD_ID",
                    help="finish an interrupted batch run of ONE candidate: benches with a saved report.json are "
                         "reloaded, the rest are submitted into the same corners/RECORD_ID/ (no new record id)")
    ap.add_argument("--render", default=None, metavar="RECORD_ID",
                    help="(re)write records/RECORD_ID.md from saved reports of ONE candidate; no simulation")
    ap.add_argument("--note", default=None)
    ap.add_argument("--vbd-case", choices=tuple(CB.SOURCED_VBD), default=None,
                    help="V_bd sensitivity point (#130): per-candidate override of bd_ebd to the sourced BVox "
                         "typ/floor value; the shared parameter file is not changed")
    ap.add_argument("--klt", default="klt")
    args = ap.parse_args(argv)
    CB.KLT_CMD[:] = args.klt.split()
    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if not shutil.which(CB.KLT_CMD[0]):
        print(f"ERROR: {CB.KLT_CMD[0]} not on PATH", file=sys.stderr)
        return 3
    base_params, perr = CB.CHECK.parse_params((CB.BD_DIR / "breakdown_params.spice").read_text())
    if perr:
        print("ERROR: breakdown_params.spice fails provenance checks", file=sys.stderr)
        return 3
    params = base_params
    by_n = {c.n: c for c in CHAR.CANDIDATES}
    wanted = [int(x) for x in args.candidates.split(",") if x.strip()]

    if args.smoke:
        n, bench, *ix = args.smoke.split(":")
        return smoke(pdk, by_n[int(n)], bench, CB.apply_vbd_case(base_params, args.vbd_case, int(n)),
                     int(ix[0]) if ix else 3)
    if args.render:
        return render_only(pdk, by_n[wanted[0]], args.render, base_params, args.note, args.vbd_case)
    if args.retabulate:
        if args.retab_src and len(wanted) != 1:
            print("ERROR: --retab-src applies to exactly one candidate", file=sys.stderr)
            return 2
        rc = 0
        for n in wanted:
            cand = by_n[n]
            params = CB.apply_vbd_case(base_params, args.vbd_case, n)
            if args.vbd_case and not args.retab_src:
                print("ERROR: --vbd-case with --retabulate needs --retab-src (the sensitivity run's record id)",
                      file=sys.stderr)
                return 2
            rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
            body = render_retab(pdk, cand, rid, params, args.note, args.retab_src)
            if body is None:
                rc = 2   # no progc_* reports anywhere: no empty append-only record
                continue
            R.write_once(THIS_DIR / "records" / f"{rid}.md",
                         CB.tag_record(body, CB.sensitivity_block(args.vbd_case, n, params)))
            print(f"Candidate {n}: records/{rid}.md (re-tabulation, no simulation)")
            time.sleep(1.1)
        return rc

    benches = [b for b in args.benches.split(",") if b.strip()]
    unknown = [b for b in benches if b not in BENCHES]
    if unknown:
        print(f"ERROR: unknown bench(es) {unknown}", file=sys.stderr)
        return 2
    if any(b in GWD_BENCHES for b in benches) and wanted != [3]:
        print("ERROR: the gate/well-drive benches are defined for Candidate 3 only (--candidates 3)", file=sys.stderr)
        return 2
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand = by_n[n]
        params = CB.apply_vbd_case(base_params, args.vbd_case, n)
        defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = args.resume or R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n} (Region {cand.region}) record {rid}" + (" (resumed)" if args.resume else ""))
        if not args.resume:
            R.write_once(THIS_DIR / "corners" / rid / "run-provenance.json",
                         json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty}) + "\n")
        # resume reads the run dir directly: resuming happens before a successful
        # publish, and publish is what removes the stored sources. base_dir is
        # passed explicitly so a monkey-patched THIS_DIR (tests) is honored.
        results = load_saved(cand, rid, params, base_dir=THIS_DIR / "corners" / rid) if args.resume else {}
        for bench in benches:
            if bench in results:
                continue
            bdir = THIS_DIR / "corners" / rid / bench
            if args.resume and bdir.exists():
                shutil.rmtree(bdir)   # interrupted submit: no report.json, nothing to preserve but the request
            bdir.mkdir(parents=True, exist_ok=False)
            body, ms = body_pl(pdk, cand, defaults, bdir, CB.fleet_lib_root(pdk), bench, params)
            R.write_once(bdir / "body.spice", body)
            req = make_request(bench, cand, pdk, ms, params)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = CB.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
            if report is not None:
                text, full_sha = R.klt_report_payload(report, indent=2)
                R.write_once(bdir / "report.json", text)
                R.write_once(bdir / "report.json.sha256", full_sha + "\n")
            res = collect(bench, report, err, bdir, cand, params)
            if res.error:
                R.write_once(bdir / "submit-error.txt", res.error + "\n")
            results[bench] = res
            job = (res.remote or {}).get("job_id") if res.remote else None
            print(f"   {bench}: {res.status} ({len(res.corner_status)} corners, {time.time()-t0:.0f}s, job {job})"
                  + (f" ERROR {res.error[:300]}" if res.error else ""), flush=True)
            if res.status not in ("pass", "pass_partial"):
                rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", CB.snapshot(cand))
        R.write_once(THIS_DIR / "records" / f"{rid}.md", CB.tag_record(render_pl(pdk, cand, rid, params, results, args.note),
                                   CB.sensitivity_block(args.vbd_case, n, params)))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("program-bias-scheme", rid, THIS_DIR / "corners" / rid, REPO_ROOT)
        time.sleep(1.1)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
