#!/usr/bin/env python3
"""sim/cell-breakdown-model -- single-cell bench for the behavioral
breakdown-augmented cell model (issue #62).

For each ratified cell candidate (spec/cell-candidates.md) this runs, as
`klt sim` corner requests (one request per bench -- see README for why):

  access_op   operating point, 5 MOS x 3 T x 3 read-rail corners (45):
              - regression: access-device OFF current through the stock cell,
                the wrapper with the element disabled (bden=0), and the
                wrapper enabled but unprogrammed (bden=1) -- same stimulus as
                sim/cell-device-characterization's tb_access_device.spice
              - programmed-cell read current at the median and worst-case
                filament resistance -> I_prog_min
  access_ac   AC at 10 MHz, same 45 corners: R_on regression (3 variants)
  cap_op      operating point, 3 moscap x 3 T (9): capacitor leakage regression
  cap_ac      AC at 1 kHz, same 9 corners: C-V regression
  trigger     .tran, 3 moscap x 3 T x 10 stress points (90): the breakdown
              trigger + latch check, one stressed instance per corner

and writes one append-only record per candidate under records/. Requests
use only features the fleet runner's klt has (README "Fleet klt version").

Issue #74 adds the transient-convergence campaign (`--campaign conv74`):
the trigger bench above re-run unchanged as a control, plus ONE-cell-per-deck
benches, each 3 moscap x 3 T x 5 levels (45):

  trig1_<v>   the trigger stimulus (PL driven, BL = 0)
  prog_<v>    a BL-driven program leg: VPP pulse -> ballast -> BL, PL = 0

with <v> = st (stock cell), b0 (element disabled), b1m / b1l (element
enabled, median / low Weibull quantile) -- decks identical but for the cell
line, so a non-converged corner can be attributed (README "Transient
convergence (#74)").

    python3 sim/cell-breakdown-model/run_experiment.py
    python3 sim/cell-breakdown-model/run_experiment.py --candidates 1
    python3 sim/cell-breakdown-model/run_experiment.py --campaign conv74 --candidates 1

The corner grids go to whatever backend the requests name -- `batch` (the
Spot fleet) by default. They are never run as a local ngspice grid. A
one-corner local pre-flight of a single bench is available for debugging:

    python3 sim/cell-breakdown-model/run_experiment.py --smoke 1:access_op

stdlib only; needs `klt` on PATH and a gf180mcuD install the PDK resolver
finds (sim/harness/pdk.py).

The library itself lives in the siblings model.py (constants, deck/request
builders, collection and analysis) and render.py (record renderers); this
file is the CLI driver and re-exports their surface, so loading
run_experiment.py as a library (as downstream drivers and tests do) keeps
every attribute unchanged.
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
BD_DIR = REPO_ROOT / "design" / "breakdown"

sys.path.insert(0, str(SIM_DIR))
from harness import evidence_store as ES  # noqa: E402
from harness import klt as K  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402

# The library siblings are loaded once each under fixed unique names (never a
# bare `import`, which under python3 -I has no script dir on sys.path and
# would collide in sys.modules with other experiments' sibling modules).
# model first: render.py reuses the already-loaded copy from sys.modules.
M = load_module(THIS_DIR / "model.py", "sim_cb_model")
RENDER = load_module(THIS_DIR / "render.py", "sim_cb_render")


def __getattr__(name: str):
    """Re-export model.py's and render.py's library surface under this module,
    so `load_module(.../run_experiment.py)` callers see the attribute set the
    pre-split single file had. Dynamic on purpose: module state that the
    library mutates in place (`VBD_EBD_OVERRIDE`, armed by apply_vbd_case)
    must be read through to the owning module, not frozen at load time."""
    for src in (M, RENDER):
        try:
            return getattr(src, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """dir() parity with the pre-split module: dir() does not consult
    __getattr__, so without this the facade would advertise only its own
    names (28 of them) instead of the library surface callers actually
    resolve -- losing tab completion and help() for interactive use."""
    return sorted(set(globals()) | {n for n in dir(M) + dir(RENDER) if not n.startswith("_")})


# ---------------------------------------------------------------------------
# klt invocation
# ---------------------------------------------------------------------------


KLT_CMD = ["klt"]


def run_klt(req_path: Path, outdir: Path, backend: str | None) -> tuple[dict | None, str]:
    return K.run_klt(req_path, outdir, backend, klt_cmd=KLT_CMD, retry=K.BACKOFF)


def smoke(pdk, cand, bench: str, params: dict, pick: list[str] | None = None) -> int:
    """ONE corner of ONE bench, locally -- a debug probe, not evidence.
    `pick` = [process, temperature, supply-index] selects the corner
    (default: the first process, 27 degC, a bench-specific level)."""
    defaults = M.CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    work = THIS_DIR / ".work" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}-c{cand.n}-{bench}"
    work.mkdir(parents=True)
    body, ms = M.build_body(bench, pdk, cand, defaults, work, str(pdk.variant_dir), params)
    (work / "body.spice").write_text(body)
    req = M.make_request(bench, cand, pdk, ms, params)
    corners = req["corners"]
    proc = [p for p in corners["process"] if pick and p["name"] == pick[0]]
    corners["process"] = proc or corners["process"][:1]
    corners["temperature_c"] = [float(pick[1]) if pick else 27.0]
    if "supply_v" in corners:
        k = len(next(iter(corners["supply_v"].values())))
        idx = k - 2 if bench == "trigger" else k // 2   # trigger: inst b at 1.0 x V_bd; else nominal
        if pick:
            idx = int(pick[2])
        corners["supply_v"] = {key: [vals[idx]] for key, vals in corners["supply_v"].items()}
    req["backend"] = "local"
    (work / "request.json").write_text(json.dumps(req, indent=2))
    report, err = run_klt(work / "request.json", work / "klt", "local")
    if report is None or "corners" not in report:
        print(f"smoke {bench}: klt failed: {err or report}")
        return 1
    c = report["corners"][0]
    bad = [m for m in c["measurements"] if m["value"] is None]
    print(f"smoke c{cand.n} {bench}: {c['corner_id']} status={c['status']} "
          f"{len(c['measurements']) - len(bad)}/{len(c['measurements'])} measurements; work dir {work}")
    derived = M.derive(bench, {m["name"].lower(): m["value"] for m in c["measurements"]})
    for k in list(derived)[:40]:
        print(f"   {k} = {derived[k]}")
    for d in c["diagnostics"][:3]:
        print(f"   diag: {d}")
    return 0 if c["status"] == "pass" else 1


def set_supersedes(text: str, prior: str | None) -> str:
    """Replace the record's `- **Supersedes**` line when --supersedes names the earlier-PDK record it re-qualifies."""
    if not prior:
        return text
    new = (f"- **Supersedes**: `{prior}` (PDK re-pin, open_pdks `c6d73a3...` -> `{P.PINNED_OPEN_PDKS[:8]}...`; "
           "that record is unchanged and stays as evidence)")
    return "\n".join(new if ln.startswith("- **Supersedes**") else ln for ln in text.split("\n"))


def parse_supersedes(spec: str | None) -> dict[int, str]:
    """`1=RID,2=RID,3=RID` -> {1: RID, ...}."""
    out: dict[int, str] = {}
    for part in (spec or "").split(","):
        if part.strip():
            n, rid = part.split("=")
            out[int(n)] = rid.strip()
    return out


def render_only(pdk, cand, rid: str, params: dict, note: str | None = None, vbd_case: str | None = None,
                prior: str | None = None) -> int:
    base = ES.run_dir_for_reading("cell-breakdown-model", rid, REPO_ROOT, THIS_DIR / "corners" / rid)
    results = M.results_from_reports(cand, rid, params, base_dir=base)
    if not results:
        print(f"ERROR: no saved reports for {rid} (disk or artifact store)", file=sys.stderr)
        return 2
    prov_file = base / "run-provenance.json"
    dirty = json.loads(prov_file.read_text())["dirty"] if prov_file.is_file() else None
    R.write_once(THIS_DIR / "records" / f"{rid}.md",
                 M.tag_record(set_supersedes(RENDER.render_any(pdk, cand, rid, results, params, dirty, note), prior),
                              M.sensitivity_block(vbd_case, cand.n, params)))
    print(f"record: records/{rid}.md (rendered from saved reports)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=",".join(M.BENCHES),
                    help=f"comma-separated; #62 benches {', '.join(M.BENCHES)} (default); #74 benches "
                         f"{', '.join(M.CONV_BENCHES)}; `{M.BIAS_BENCH}` (Candidate 3 only, issue #75) must be run "
                         "on its own and writes its own record")
    ap.add_argument("--campaign", choices=tuple(M.CAMPAIGNS), default=None,
                    help="conv74: the #62 trigger bench (control) + the single-instance trig1/prog benches "
                         "(raised-cosine edges); conv74c: the trigc/progc benches (C-infinity edges). "
                         "Overrides --benches")
    ap.add_argument("--smoke", default=None, metavar="N:BENCH[:PROCESS:TEMP:LEVEL_INDEX]",
                    help="run ONE corner of ONE bench locally (debug probe; writes no record)")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--note", default=None, help="free-text run note carried into the record(s)")
    ap.add_argument("--vbd-case", choices=tuple(M.SOURCED_VBD), default=None,
                    help="V_bd sensitivity point (#130): per-candidate override of bd_ebd to the sourced BVox "
                         "typ/floor value; the shared parameter file is not changed")
    ap.add_argument("--render", default=None, metavar="RECORD_ID",
                    help="(re)write records/RECORD_ID.md from the saved reports of ONE candidate "
                         "(--candidates N; committed bytes where they exist, else fetched from the "
                         "artifact store); runs no simulation. Refuses to overwrite.")
    ap.add_argument("--supersedes", default=None, metavar="N=RID[,N=RID...]",
                    help="per candidate, the earlier-PDK record this run re-qualifies; written into the new "
                         "record's Supersedes field (the old record is not touched)")
    ap.add_argument("--klt", default="klt",
                    help="klt command (space-separated), e.g. a version-pinned `uvx --from ... klt` to "
                         "pre-flight a request against the fleet runner's klt with --smoke")
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
    base_params, perr = M.CHECK.parse_params((BD_DIR / "breakdown_params.spice").read_text())
    if perr:
        print("ERROR: breakdown_params.spice fails provenance checks; run design/breakdown/check_params.py",
              file=sys.stderr)
        return 3
    params = base_params
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK + parameter file OK.")
        return 0

    by_n = {c.n: c for c in M.CHAR.CANDIDATES}
    if args.render:
        n = int(args.candidates)
        return render_only(pdk, by_n[n], args.render, M.apply_vbd_case(base_params, args.vbd_case, n), args.note,
                           args.vbd_case, parse_supersedes(args.supersedes).get(n))
    if args.smoke:
        n, bench, *pick = args.smoke.split(":")
        return smoke(pdk, by_n[int(n)], bench, M.apply_vbd_case(base_params, args.vbd_case, int(n)), pick or None)

    wanted = [int(x) for x in args.candidates.split(",") if x.strip()]
    supersedes = parse_supersedes(args.supersedes)
    benches = [b for b in args.benches.split(",") if b.strip()]
    if args.campaign:
        benches = list(M.CAMPAIGNS[args.campaign])
    unknown = [b for b in benches if b not in M.ALL_BENCHES]
    if unknown:
        print(f"ERROR: unknown bench(es) {unknown}", file=sys.stderr)
        return 2
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand = by_n[n]
        params = M.apply_vbd_case(base_params, args.vbd_case, n)
        if M.BIAS_BENCH in benches and (benches != [M.BIAS_BENCH] or n != 3):
            print(f"ERROR: {M.BIAS_BENCH} runs alone and for Candidate 3 only (--candidates 3 --benches {M.BIAS_BENCH})",
                  file=sys.stderr)
            return 3
        defaults = M.CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        print(f"== Candidate {n} (Region {cand.region}) record {rid}")
        R.write_once(THIS_DIR / "corners" / rid / "run-provenance.json",
                     json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty}) + "\n")
        results: dict[str, M.BenchResult] = {}
        for bench in benches:
            bdir = THIS_DIR / "corners" / rid / bench
            bdir.mkdir(parents=True, exist_ok=False)  # corners/<rid>/ itself exists (run-provenance.json)
            body, ms = M.build_body(bench, pdk, cand, defaults, bdir, M.fleet_lib_root(pdk), params)
            R.write_once(bdir / "body.spice", body)
            req = M.make_request(bench, cand, pdk, ms, params)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
            if report is not None:
                text, full_sha = R.klt_report_payload(report, indent=2)
                R.write_once(bdir / "report.json", text)
                R.write_once(bdir / "report.json.sha256", full_sha + "\n")
            res = M.collect(bench, report, err, bdir, cand, params)
            if res.error:
                R.write_once(bdir / "submit-error.txt", res.error + "\n")
            results[bench] = res
            job = (res.remote or {}).get("job_id") if res.remote else None
            print(f"   {bench}: {res.status} ({len(res.corner_status)} corners, {time.time()-t0:.0f}s, job {job})"
                  + (f" ERROR {res.error[:300]}" if res.error else ""))
            if res.status not in ("pass", "pass_partial"):
                rc = 1
        R.write_once(THIS_DIR / "netlist-snapshots" / f"{rid}.spice", M.snapshot(cand))
        R.write_once(THIS_DIR / "records" / f"{rid}.md",
                     M.tag_record(set_supersedes(RENDER.render_any(pdk, cand, rid, results, params, dirty, args.note),
                                                 supersedes.get(n)),
                                  M.sensitivity_block(args.vbd_case, n, params)))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("cell-breakdown-model", rid, THIS_DIR / "corners" / rid, REPO_ROOT)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
