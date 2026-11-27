#!/usr/bin/env python3
"""sim/hv-pad-protection -- program-voltage (PL) pad and protection paths at
PVT corners (issue #210, part of #203).

One bench = one `klt sim` request = 3 process x 3 temperature x 5 pad levels =
45 corners, submitted to the batch fleet (KLT_SIM_BACKEND=batch); never run as a
local grid. Benches, per candidate (levels are signed: Candidate 3 is driven
negative, as in sim/cell-breakdown-model):

  astd_f   standard analog pad cell gf180mcu_fd_io__asig_5p0 (its ESD diodes to
           DVDD / DVSS) wired to the plate.                       [rejected]
  c0_f     bare pad wired straight to the plate.                  [rejected]
  c1_f/s   bare pad + series ppolyf_u_2k_6p0 ballast; fast / slow ramp. [chosen]
  jn_<m>_f c1_f plus a PDK junction diode `m` on the plate node (the plate's
           diffusion type is a layout question; one bench per possibility).
  nbh_f/s  c1 on the selected cell AND a second, unprogrammed cell on the same
           BL/WL whose own PL pad is left high-impedance (policy a).
  nbd_f    the same, neighbour PL pad driven to 0 V (policy b).

Stimulus, source impedance, cable and coupling capacitances, filament and
access resistances are PLACEHOLDERS (see README); the V_bd are the ASSUMED
values of design/breakdown/breakdown_params.spice. The filament is a threshold
switch, not the stochastic model: this is a pad-path rating bench, not a yield
claim (that is sim/programming-yield).

    python3 sim/hv-pad-protection/run_experiment.py --candidates 1,2,3   # fleet
    python3 sim/hv-pad-protection/run_experiment.py --smoke 2:c1_f       # ONE local corner
    python3 sim/hv-pad-protection/run_experiment.py --check RECORD_ID    # re-apply the rules
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent

sys.path.insert(0, str(SIM_DIR))
from harness import evidence_store as ES  # noqa: E402
from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402

M = load_module(THIS_DIR / "model.py", "sim_hv_model")
RENDER = load_module(THIS_DIR / "render.py", "sim_hv_render")


def __getattr__(name: str):
    for module in (M, RENDER):
        try:
            return getattr(module, name)
        except AttributeError:
            continue
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | {n for n in dir(M) + dir(RENDER) if not n.startswith("_")})


def smoke(spec: str) -> int:
    n, bench = spec.split(":")[:2]
    cand, pdk, defaults, vbd = M.setup(int(n))
    M.CB.fleet_lib_root(pdk)
    defs = M.bench_defs(cand.n)
    lv = M.levels(cand, vbd)
    work = REPO_ROOT / "sim" / ".artifact-scratch" / "hv-pad-smoke"
    work.mkdir(parents=True, exist_ok=True)
    text, meas = M.body(bench, defs[bench], cand, pdk, defaults, vbd)
    (work / "body.spice").write_text(text)
    req = M.make_request(bench, defs[bench], cand, pdk, meas, lv)
    cr = req["corners"]
    cr["process"], cr["temperature_c"], cr["supply_v"] = cr["process"][:1], [27.0], {"vamp": [lv[3]]}
    req["backend"] = "local"
    req.pop("batch", None)
    (work / "request.json").write_text(json.dumps(req))
    report, err = M.CB.K.run_klt(work / "request.json", work / "out", "local", klt_cmd=M.CB.KLT_CMD)
    if report is None or "corners" not in report:
        print("smoke FAILED:", err or report)
        return 1
    c = report["corners"][0]
    print(c["status"], {m["name"]: m["value"] for m in c["measurements"]}, c.get("diagnostics"))
    return 0


def check(rid: str, cand_ns: list[int]) -> int:
    bad = 0
    base = ES.run_dir_for_reading("hv-pad-protection", rid, REPO_ROOT, THIS_DIR / "corners" / rid)
    for n in cand_ns:
        cand, pdk, defaults, vbd = M.setup(n)
        for bench, bd in M.bench_defs(n).items():
            rp = base / f"c{n}" / bench / "report.json"
            if not rp.is_file():
                continue
            rows = M.collect(json.loads(rp.read_text()), bd, cand, vbd)
            codes = {c for r in rows for c in r["codes"]}
            print(f"C{n} {bench}: {len(rows)} corners, violations: {sorted(codes) or 'none'}")
            bad += any(c.startswith("error") or c == "no-measurement" for c in codes)
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidates", default="1,2,3")
    ap.add_argument("--benches", default=None, help="comma list; default all")
    ap.add_argument("--smoke", metavar="N:BENCH", help="ONE local corner, debug only, records nothing")
    ap.add_argument("--check", metavar="RECORD_ID",
                    help="re-apply verdicts.py to a record's saved reports (committed bytes where they "
                         "exist, else fetched from the artifact store)")
    args = ap.parse_args(argv)
    wanted = [int(x) for x in args.candidates.split(",")]
    if args.smoke:
        return smoke(args.smoke)
    if args.check:
        return check(args.check, wanted)
    pdk = M.P.resolve_pdk()
    M.CB.fleet_lib_root(pdk)
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand, pdk, defaults, vbd = M.setup(n)
        defs = M.bench_defs(n)
        names = args.benches.split(",") if args.benches else list(defs)
        lv = M.levels(cand, vbd)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        git_sha = rid.rsplit("-", 1)[-1]  # allocate_record_id already captured HEAD
        base = THIS_DIR / "corners" / rid
        print(f"== Candidate {n} (Region {cand.region}) record {rid}")
        R.write_once(base / "run-provenance.json", json.dumps({"git_sha": git_sha, "dirty": dirty}) + "\n")
        results: dict = {}
        for bench in names:
            bdir = base / f"c{n}" / bench
            bdir.mkdir(parents=True, exist_ok=False)
            text, meas = M.body(bench, defs[bench], cand, pdk, defaults, vbd)
            R.write_once(bdir / "body.spice", text)
            req = M.make_request(bench, defs[bench], cand, pdk, meas, lv)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = M.CB.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
            if report is None or "corners" not in report:
                msg = err if report is None else json.dumps(report.get("error"))
                R.write_once(bdir / "submit-error.txt", str(msg) + "\n")
                results[bench] = f"submit failed: {str(msg)[:300]}"
                rc = 1
                print(f"   {bench}: SUBMIT ERROR {str(msg)[:200]}", flush=True)
                continue
            text, full_sha = R.klt_report_payload(report, indent=2)
            R.write_once(bdir / "report.json", text)
            R.write_once(bdir / "report.json.sha256", full_sha + "\n")
            results[bench] = M.collect(report, defs[bench], cand, vbd)
            env = report.get("environment", {})
            print(f"   {bench}: {report.get('status')} ({len(report['corners'])} corners, {time.time() - t0:.0f}s, "
                  f"job {(env.get('remote') or {}).get('job_id')})", flush=True)
        R.write_once(THIS_DIR / "records" / f"{rid}.md", RENDER.render(rid, cand, vbd, lv, results, dirty, git_sha=git_sha))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("hv-pad-protection", rid, base, REPO_ROOT)
        time.sleep(1.1)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
