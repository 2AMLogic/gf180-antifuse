#!/usr/bin/env python3
"""sim/program-read-legs -- program-leg / read-leg benches and margin tables.

Run directly:

    python3 sim/program-read-legs/run_experiment.py [--benches ...] [--probe]

Every grid in this experiment is expressed as a ``klt sim`` request (corners
axes), so a multi-corner sweep goes to whichever backend ``KLT_SIM_BACKEND`` /
``--backend`` selects -- export ``KLT_SIM_BACKEND=batch`` for the Spot batch
fleet (the dispatch-host default); when unset, ``klt`` defaults to ``local``.
This script never loops over ngspice itself. ``--probe`` runs ONE typical
corner on the ``local`` backend, as a debug aid only; its output is not
evidence and is not recorded.

Benches (see README.md):
    exclusion        PROG_EN/READ_EN states x VPP x bit-line level, both legs
                     on one bit line
    ballast          program leg alone, BL held at an assumed compliance voltage
    margin1/2/3      read decision per candidate/region, unprogrammed and
                     programmed sides, access sizing min/2x

Stdlib only (klt is the only external tool; set KLT to override its path).

The library itself lives in the siblings model.py (constants, request/bench
builders, analysis and statistics) and render.py (the record renderers);
this file is the CLI driver and re-exports their surface, so loading
run_experiment.py as a library (as the tests do)
keeps every attribute unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
sys.path.insert(0, str(SIM_DIR))

from harness import evidence_store as ES  # noqa: E402
from harness import klt as K  # noqa: E402
from harness.modload import facade_hooks, load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402

# The library siblings are loaded once each under fixed unique names (never a
# bare `import`, which under python3 -I has no script dir on sys.path and
# would collide in sys.modules with other experiments' sibling modules).
# model first: render.py reuses the already-loaded copy from sys.modules.
M = load_module(THIS_DIR / "model.py", "sim_prl_model")
RENDER = load_module(THIS_DIR / "render.py", "sim_prl_render")

# The library surface the CLI below calls directly (everything else is
# re-exported lazily through __getattr__).
B = M.B
KLT_TIMEOUT_S = M.KLT_TIMEOUT_S
MC_N = M.MC_N
MC_POINTS = M.MC_POINTS
bench_defs = M.bench_defs
mc_bench_defs = M.mc_bench_defs
bench_iref = M.bench_iref
make_request = M.make_request
make_mc_request = M.make_mc_request
meas_table = M.meas_table
mc_table = M.mc_table
analyze_exclusion = M.analyze_exclusion
analyze_ballast = M.analyze_ballast
analyze_margin = M.analyze_margin
analyze_mc_offset = M.analyze_mc_offset
analyze_mc_margin = M.analyze_mc_margin
env_summary = RENDER.env_summary
render_exclusion = RENDER.render_exclusion
render_ballast = RENDER.render_ballast
render_margin = RENDER.render_margin
render_mc_offset = RENDER.render_mc_offset
render_mc_margin = RENDER.render_mc_margin
render_mc_record = RENDER.render_mc_record
render_record = RENDER.render_record

WORK = THIS_DIR / ".work"          # git-ignored scratch (host-specific paths)


# Library surface of model.py/render.py, read through live (see modload.facade_hooks).
__getattr__, __dir__ = facade_hooks(globals(), M, RENDER)


# ---------------------------------------------------------------------------
# klt invocation
# ---------------------------------------------------------------------------

def run_klt(request_path: Path, outdir: Path, backend: str | None) -> tuple[dict | None, str]:
    env = dict(os.environ)
    env.setdefault("PDK_ROOT", str(Path.home() / ".ciel"))
    return K.run_klt(request_path, outdir, backend, klt_cmd=[os.environ.get("KLT", "klt")],
                     timeout_s=KLT_TIMEOUT_S, env=env, retry=K.BACKOFF)


def run_mc(args, pdk, preamble: Path) -> int:
    from concurrent.futures import ThreadPoolExecutor
    wanted = [b.strip() for b in args.benches.split(",") if b.strip()]
    defs = mc_bench_defs()
    unknown = [b for b in wanted if b not in defs]
    if unknown:
        print(f"ERROR: unknown MC benches {unknown}; known: {sorted(defs)}", file=sys.stderr)
        return 2
    backend = "local" if args.probe else args.backend
    n_samples = 1 if args.probe else args.mc_n
    points = MC_POINTS[:1] if args.probe else MC_POINTS
    dirty = R.git_is_dirty(REPO_ROOT)
    record_id = R.allocate_record_id(THIS_DIR, REPO_ROOT)
    snap_dir = THIS_DIR / "netlist-snapshots" / record_id
    corner_dir = THIS_DIR / "corners" / record_id

    jobs = []
    for name in wanted:
        text, meas, smbb, _cand = defs[name]
        netlist_path = WORK / f"{name}.sp"
        netlist_path.write_text(text.replace(f".include {B.PDK_DESIGN}\n", ""))
        for pt in points:
            req = make_mc_request(f"{name}.sp", meas, smbb, str(preamble), pt, n=n_samples)
            req_path = WORK / f"{name}.{pt[0]}.mc.request.json"
            req_path.write_text(json.dumps(req, indent=1))
            out = (WORK / "probe" / f"mc_{name}_{pt[0]}") if args.probe else (corner_dir / f"{name}.{pt[0]}")
            out.mkdir(parents=True, exist_ok=True)
            jobs.append((name, pt, req_path, out))

    def submit(job):
        name, pt, req_path, out = job
        t0 = time.time()
        # Fleet-refusal retry is the harness's (K.BACKOFF, passed by run_klt above);
        # nothing else is retried, and a batch submit is never replayed locally.
        resp, err = run_klt(req_path, out, backend)
        print(f"== {name}/{pt[0]}: {time.time() - t0:.0f}s status="
              f"{(resp or {}).get('status')} units={(resp or {}).get('corner_count')} "
              f"pass={(resp or {}).get('passed')} err={(resp or {}).get('errored')}", flush=True)
        return job, resp, err

    # Submissions only go through klt (batch fleet via KLT_SIM_BACKEND); the thread pool just
    # overlaps the waits. No local ngspice grid is ever started here (--probe is one unit).
    with ThreadPoolExecutor(max_workers=1 if args.probe else 4) as ex:
        results = list(ex.map(submit, jobs))

    responses: dict[tuple, dict] = {}
    failures: dict[tuple, str] = {}
    for (name, pt, req_path, out), resp, err in results:
        key = (name, pt[0])
        if resp is None or "corners" not in resp:
            failures[key] = (err or "no response").strip()[-1500:]
        elif not resp.get("passed"):
            remote = resp.get("environment", {}).get("remote") or {}
            failures[key] = (f"no sample resolved; diagnostics={resp.get('diagnostic_counts', {}).get('by_code', {})}; "
                             f"job={remote.get('job_id')}")
        else:
            responses[key] = resp
    for key, msg in failures.items():
        print(f"   FAILED {key}: {msg[:300]}", file=sys.stderr)
    if args.probe:
        for key, resp in responses.items():
            print(key, json.dumps(list(mc_table(resp).items())[:1])[:800])
        return 1 if failures else 0
    if not responses:
        shutil.rmtree(corner_dir, ignore_errors=True)
        print("ERROR: no MC request resolved; no record written. Failures:\n  "
              + "\n  ".join(f"{k}: {v}" for k, v in failures.items()), file=sys.stderr)
        return 1

    snap_dir.mkdir(parents=True, exist_ok=True)
    for (name, pt, req_path, out) in jobs:
        key = (name, pt[0])
        if key not in responses:
            continue
        if not (snap_dir / f"{name}.sp").exists():
            R.write_once(snap_dir / f"{name}.sp", (WORK / f"{name}.sp").read_text())
        req_norm = json.loads(req_path.read_text())
        for b in req_norm["corners"]["process"]:
            for sec in b["sections"]:
                if isinstance(sec, dict) and sec["lib"].endswith("preamble.lib"):
                    sec["lib"] = "sim/program-read-legs/models/preamble.lib"
        R.write_once(snap_dir / f"{name}.{pt[0]}.mc.request.json", json.dumps(req_norm, indent=1) + "\n")
        text, full_sha = R.klt_report_payload(responses[key], indent=1)
        R.write_once(corner_dir / f"{name}.{pt[0]}.report.json", text)
        R.write_once(corner_dir / f"{name}.{pt[0]}.report.json.sha256", full_sha + "\n")
        for stale in [*out.rglob("corner.cir"), *out.rglob("ngspice.log")]:
            stale.unlink()      # per-sample decks/logs: the report keeps values, seeds and diagnostics

    sections, unevidenced, remotes = [], [], {}
    for name in wanted:
        per_point = {}
        for pt in points:
            key = (name, pt[0])
            label = f"{pt[0]} ({pt[1]}, {pt[2]} C, VDD {pt[3]:.2f} V)"
            resp = responses.get(key)
            if resp is None:
                per_point[label] = None
                unevidenced.append(f"{name}/{pt[0]}: klt sim did not return a report ({failures.get(key, 'not run')[:200]})")
                continue
            remotes[f"{name}/{pt[0]}"] = (resp.get("environment", {}).get("remote") or {}).get("job_id")
            tab = mc_table(resp)
            short = [lab for lab, v in tab.items() if any(x is None for x in v.values())]
            if short or len(tab) != args.mc_n:
                unevidenced.append(f"{name}/{pt[0]}: {len(tab)} of {args.mc_n} samples returned, "
                                   f"{len(short)} with a missing measurement")
            tab = {k: v for k, v in tab.items() if k not in short}
            if name == "offset":
                per_point[label] = analyze_mc_offset(tab) if tab else None
            else:
                per_point[label] = analyze_mc_margin(tab, bench_iref(name)) if tab else None
        if name == "offset":
            sections.append(("Sense-mirror current offset vs I_ref", render_mc_offset(per_point)))
        else:
            k = defs[name][3]
            c = B.CANDIDATES[k]
            sections.append((f"Read decision under mismatch, Candidate {k} (Region {c['region']}), "
                             f"I_ref = {bench_iref(name):.0e} A", render_mc_margin(k, per_point)))
    rec = render_mc_record(record_id, pdk, dirty, args.mc_n, sections, unevidenced, failures, remotes)
    R.write_once(THIS_DIR / "records" / f"{record_id}.md", rec)
    print(f"record: sim/program-read-legs/records/{record_id}.md")
    rc = 1 if (failures or unevidenced) else 0
    rc |= ES.publish_for_runner("program-read-legs", record_id, THIS_DIR / "corners" / record_id, REPO_ROOT)
    return rc


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--benches", default="exclusion,ballast,margin1,margin2,margin3,margin3_lowiref")
    ap.add_argument("--backend", default=None, help="klt sim backend (default: $KLT_SIM_BACKEND, then request/local)")
    ap.add_argument("--pdk-root", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="ONE typical corner on the local backend; debug only, nothing recorded")
    ap.add_argument("--check-env", action="store_true")
    ap.add_argument("--mc", action="store_true",
                    help="mismatch Monte Carlo variant (klt `monte_carlo`, vary=mismatch) of the margin "
                         "benches + the mirror-offset bench; default benches then become "
                         "offset,margin1,margin2,margin3,margin3_lowiref")
    ap.add_argument("--mc-n", type=int, default=MC_N, help="samples per corner point (default %(default)s)")
    args = ap.parse_args(argv)
    if args.mc and args.benches == ap.get_default("benches"):
        args.benches = "offset,margin1,margin2,margin3,margin3_lowiref"

    try:
        pdk = P.resolve_pdk(args.pdk_root)
    except P.PDKNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if shutil.which(os.environ.get("KLT", "klt")) is None:
        print("ERROR: klt not found on PATH (set KLT to override).", file=sys.stderr)
        return 3
    print(f"PDK: {pdk.variant} at {pdk.variant_dir} (open_pdks {pdk.revision})")
    if args.check_env:
        print("klt + PDK OK.")
        return 0

    WORK.mkdir(exist_ok=True)
    # Host-specific preamble: design.ngspice include with the resolved absolute path.
    preamble = WORK / "preamble.lib"
    preamble.write_text(
        (THIS_DIR / "models" / "preamble.lib").read_text().replace(
            "$PDK_ROOT/gf180mcuD", str(pdk.variant_dir)))

    if args.mc:
        return run_mc(args, pdk, preamble)

    wanted = [b.strip() for b in args.benches.split(",") if b.strip()]
    defs = bench_defs()
    unknown = [b for b in wanted if b not in defs]
    if unknown:
        print(f"ERROR: unknown benches {unknown}; known: {sorted(defs)}", file=sys.stderr)
        return 2

    backend = "local" if args.probe else args.backend
    dirty = R.git_is_dirty(REPO_ROOT)
    record_id = R.allocate_record_id(THIS_DIR, REPO_ROOT)
    responses: dict[str, dict] = {}
    failures: dict[str, str] = {}
    snap_dir = THIS_DIR / "netlist-snapshots" / record_id
    corner_dir = THIS_DIR / "corners" / record_id

    for name in wanted:
        text, meas, smbb, _cand = defs[name]
        netlist_path = WORK / f"{name}.sp"
        netlist_path.write_text(text.replace(f".include {B.PDK_DESIGN}\n", ""))
        if args.probe:
            req = make_request(f"{name}.sp", meas, smbb, str(preamble), temps=(27,),
                               processes=("typical",), vdd_points=(B.VDD_NOM,))
        else:
            req = make_request(f"{name}.sp", meas, smbb, str(preamble))
        req_path = WORK / f"{name}.request.json"
        req_path.write_text(json.dumps(req, indent=1))
        out = (WORK / "probe" / name) if args.probe else (corner_dir / name)
        out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        print(f"== {name}: klt sim ({len(req['corners']['process']) * len(req['corners']['temperature_c']) * len(req['corners']['supply_v']['VDD'])} corners, backend={backend or 'env/default'}) ==", flush=True)
        resp, err = run_klt(req_path, out, backend)
        print(f"   {time.time() - t0:.0f}s", flush=True)
        if resp is None or "corners" not in resp:
            failures[name] = err.strip()[-1500:] if err else "no response"
            print(f"   FAILED: {failures[name][:300]}", file=sys.stderr)
            continue
        print(f"   status={resp.get('status')} corners={resp.get('corner_count')} "
              f"pass={resp.get('passed')} err={resp.get('errored')}")
        if not resp.get("passed"):
            # Nothing resolved (e.g. the batch submit was rejected): that is a
            # failed submit to report, not evidence to commit. Do NOT fall back
            # to a local grid (host rule): fix the backend and re-run.
            codes = resp.get("diagnostic_counts", {}).get("by_code", {})
            remote = resp.get("environment", {}).get("remote") or {}
            failures[name] = (f"no corner resolved; diagnostics={codes}; "
                              f"job={remote.get('job_id')} runner_compat={remote.get('runner_compatibility')} "
                              f"runner_klt={remote.get('runner_klt_version')} client_klt={remote.get('client_klt_version')}")
            print(f"   FAILED: {failures[name]}", file=sys.stderr)
            shutil.rmtree(out, ignore_errors=True)
            continue
        responses[name] = resp
        if args.probe:
            tab = meas_table(resp)
            for lab, v in tab.items():
                print(lab, json.dumps(v, indent=0)[:1500])
            continue
        # Evidence: frozen netlist + normalised request + full klt response; drop
        # the generated per-corner decks (host paths) and raw vectors.
        snap_dir.mkdir(parents=True, exist_ok=True)
        R.write_once(snap_dir / f"{name}.sp", netlist_path.read_text())
        req_norm = json.loads(req_path.read_text())
        for b in req_norm["corners"]["process"]:
            for s in b["sections"]:
                if isinstance(s, dict) and s["lib"].endswith("preamble.lib"):
                    s["lib"] = "sim/program-read-legs/models/preamble.lib"
        R.write_once(snap_dir / f"{name}.request.json", json.dumps(req_norm, indent=1) + "\n")
        text, full_sha = R.klt_report_payload(resp, indent=1)
        R.write_once(corner_dir / f"{name}.report.json", text)
        R.write_once(corner_dir / f"{name}.report.json.sha256", full_sha + "\n")
        for deck in out.rglob("corner.cir"):
            deck.unlink()

    if args.probe:
        return 1 if failures else 0

    if not responses:
        shutil.rmtree(corner_dir, ignore_errors=True)
        print("ERROR: no bench produced a resolved report; no record written. "
              "Failures:\n  " + "\n  ".join(f"{k}: {v}" for k, v in failures.items()), file=sys.stderr)
        return 1

    # --- tables -----------------------------------------------------------
    sections = []
    unevidenced = []
    for name in wanted:
        if name not in responses:
            unevidenced.append(f"{name}: klt sim did not return a report ({failures.get(name, 'not run')[:200]})")
            continue
        resp = responses[name]
        tab = meas_table(resp)
        unresolved = [lab for lab, v in tab.items() if any(x is None for x in v.values())]
        note = (f"corners requested {resp.get('corner_count')}, passed {resp.get('passed')}, "
                f"errored {resp.get('errored')}, unresolved (some measurement missing): {len(unresolved)}; "
                f"{env_summary(resp)}")
        if name == "exclusion":
            sections.append(("Mutual exclusion", note, render_exclusion(analyze_exclusion(tab))))
        elif name == "ballast":
            sections.append(("Program leg ballast / compliance", note, render_ballast(analyze_ballast(tab))))
        else:
            k = defs[name][3]
            c = B.CANDIDATES[k]
            ir = bench_iref(name)
            sections.append((f"Read margin, Candidate {k} (Region {c['region']}), I_ref = {ir:.0e} A", note,
                             render_margin(k, analyze_margin(tab, ir))))
        if unresolved:
            unevidenced.append(f"{name}: {len(unresolved)} corner(s) with unresolved measurements: "
                               + ", ".join(unresolved[:6]))
    rec = render_record(record_id, pdk, dirty, wanted, sections, unevidenced, failures)
    R.write_once(THIS_DIR / "records" / f"{record_id}.md", rec)
    print(f"record: sim/program-read-legs/records/{record_id}.md")
    rc = 1 if (failures or unevidenced) else 0
    rc |= ES.publish_for_runner("program-read-legs", record_id, THIS_DIR / "corners" / record_id, REPO_ROOT)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
