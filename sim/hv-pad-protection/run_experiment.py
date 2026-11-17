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
import re
import shutil
import sys
import time
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SIM_DIR = THIS_DIR.parent
REPO_ROOT = SIM_DIR.parent
CB_DIR = SIM_DIR / "cell-breakdown-model"
PAD_NETLIST = REPO_ROOT / "design" / "hv-pad" / "hv_pad_path.spice"

sys.path.insert(0, str(SIM_DIR))
sys.path.insert(0, str(THIS_DIR))
from harness import corners as C  # noqa: E402
from harness import evidence_store as ES  # noqa: E402
from harness.modload import load_module  # noqa: E402
from harness import pdk as P  # noqa: E402
from harness import report as R  # noqa: E402
import verdicts as V  # noqa: E402


CB = load_module(CB_DIR / "run_experiment.py", "sim_cb_lib")
CHAR = CB.CHAR

# --- placeholders (README "Limits") -------------------------------------------
V_PAD_MAX = 17.6          # 16 V (top of the ~8-16 V range of #203) + 10 % bench overshoot
FRACTIONS = (0.5, 0.95, 1.05, 1.10)   # x V_bd; 0.95 must NOT program, 1.05 must
R_SRC = 100.0             # bench source + cable resistance
R_EXT = 1e4               # OFF-die series resistor at the probe/socket (chosen path); value OPEN, set by the bench plan
C_CABLE = 100e-12         # bench cable at the pad
C_PAD = 1e-12             # die pad
C_PL = 100e-15            # plate-node shunt (as sim/program-bias-scheme: needed for the uic start)
R_ACC = 1e3               # access path to BL, on-state
R_FIL = 1e4               # programmed-filament resistance (assumed, as bd_rf_med)
C_COUPLE = 100e-15        # PL-to-PL route coupling between adjacent instances (estimate)
R_LEAK_HIZ = 1e9          # high-impedance PL pad leakage to substrate (estimate)
DVDD_STD = 5.5            # standard-pad rail, top of its range
VBW_C3 = 3.3              # Candidate 3 n-well tie during program (the #62 "on" bias)
TEMPS = C.TEMPS_C
PROCS = ("typical", "ff", "ss")

RAMPS = {"f": dict(tr=100e-9, tw=2e-6, tstep=2e-9, tail=1e-6),
         "s": dict(tr=100e-6, tw=50e-6, tstep=100e-9, tail=10e-6)}
T1 = 1e-6


def bench_defs(cand_n: int) -> dict[str, dict]:
    d = {"astd_f": dict(kind="astd", path="std", ramp="f"),
         "c1_f": dict(kind="c1", path="ballast", ramp="f"),
         "c0_f": dict(kind="c0", path="direct", ramp="f"),
         "cx_f": dict(kind="cx", path="direct", ramp="f", rext=True),
         "cx_s": dict(kind="cx", path="direct", ramp="s", rext=True),
         "nbh_f": dict(kind="nb", path="direct", ramp="f", rext=True, nb="hiz"),
         "nbh_s": dict(kind="nb", path="direct", ramp="s", rext=True, nb="hiz"),
         "nbd_f": dict(kind="nb", path="direct", ramp="f", rext=True, nb="drv")}
    models = ("pd2nw", "nw2ps") if cand_n == 3 else ("nd2ps", "nw2ps", "dw2ps")
    for m in models:
        d[f"jn_{m}_f"] = dict(kind="jn", path="direct", ramp="f", rext=True, jn=m)
    return d


def read_params() -> dict[str, float]:
    txt = (REPO_ROOT / "design" / "breakdown" / "breakdown_params.spice").read_text()
    return {k: float(v) for k, v in re.findall(r"^\.param\s+(\w+)\s*=\s*([0-9.eE+-]+)", txt, re.M)}


def vbd_of(cand_n: int, params: dict) -> float:
    return params["bd_ebd"] * params[f"c{cand_n}_bd_tox"]


def sign_of(cand) -> float:
    return 1.0 if cand.polarity == "n" else -1.0


def levels(cand, vbd: float) -> list[float]:
    s = sign_of(cand)
    return [round(s * x, 6) for x in [f * vbd for f in FRACTIONS] + [V_PAD_MAX]]


def fnum(x: float) -> str:
    return f"{x:.6e}"


# --- deck ----------------------------------------------------------------------

def cell_lines(sfx: str, cand, defaults: dict, vbd: float, pl: str) -> list[str]:
    """One cell: moscap (CN gate-side, PL plate-side, as design/netlists), access
    path to BL, and the threshold filament. Control polarity follows the drive sign."""
    ctl = (pl, f"CN{sfx}") if sign_of(cand) > 0 else (f"CN{sfx}", pl)
    return [f"XC{sfx} CN{sfx} {pl} {cand.cap_model} c_width={fnum(defaults['wcap'])} c_length={fnum(defaults['lcap'])}",
            f"RACC{sfx} CN{sfx} BL {fnum(R_ACC)}",
            f"S{sfx} {pl} NF{sfx} {ctl[0]} {ctl[1]} SBD",
            f"RF{sfx} NF{sfx} CN{sfx} {fnum(R_FIL)}",
            f"BIF{sfx} IFIL{sfx} 0 V = 'abs(v(nf{sfx})-v(cn{sfx}))/{fnum(R_FIL)}'",
            f"BOX{sfx} DOX{sfx} 0 V = 'abs(v({pl})-v(cn{sfx}))'"]


def body(bench: str, bd: dict, cand, pdk, defaults: dict, vbd: float) -> tuple[str, list[dict]]:
    rp = RAMPS[bd["ramp"]]
    o = [f"* gf180-antifuse sim/hv-pad-protection -- Candidate {cand.n} bench {bench} (tran, #210)",
         "* Generated by run_experiment.py; frozen here as evidence. See README.",
         CB.design_param_block(pdk).rstrip(),
         ".options gmin=1.000000e-13",
         f".param t1={fnum(T1)} tr={fnum(rp['tr'])} tw={fnum(rp['tw'])}",
         ".func af_fe(u) {exp(-1/max(u,1e-6))}",
         ".func af_edge(x) {af_fe(min(max(x,0),1))/(af_fe(min(max(x,0),1))+af_fe(1-min(max(x,0),1)))}",
         "BSH SH 0 V = 'af_edge((time-t1)/tr) - af_edge((time-t1-tr-tw)/tr)'",
         f"* --- inlined from design/hv-pad/hv_pad_path.spice (sha256 {CB.sha256(PAD_NETLIST)}) ---",
         PAD_NETLIST.read_text().rstrip(),
         "* --- end inline ---",
         f".model SBD SW(vt={fnum(0.55 * vbd)} vh={fnum(0.45 * vbd)} ron=1.0e-3 roff=1.0e9)",
         "VAMP AMP 0 DC 0",
         "BVPP VPP 0 V = 'v(amp)*v(sh)'",
         f"CPD PAD 0 {fnum(C_PAD)}", "VBL BL 0 DC 0", f"CPL PL 0 {fnum(C_PL)}"]
    if bd.get("rext"):    # cable capacitance stays on the source side of the off-die resistor
        o += [f"RSRC VPP VCAB {fnum(R_SRC)}", f"CCAB VCAB 0 {fnum(C_CABLE)}", f"REXT VCAB PAD {fnum(R_EXT)}",
              f"BIP IPD 0 V = '(v(vpp)-v(vcab))/{fnum(R_SRC)}'"]
    else:
        o += [f"RSRC VPP PAD {fnum(R_SRC)}", f"CCAB PAD 0 {fnum(C_CABLE)}",
              f"BIP IPD 0 V = '(v(vpp)-v(pad))/{fnum(R_SRC)}'"]
    if bd["path"] == "std":
        o += [f"VDV DVDDX 0 DC {DVDD_STD}", "RDV DVDDX DVDD 0.5", "CDV DVDD 0 1.0e-9",
              "VSSS DVSSX 0 DC 0", "XPAD PAD DVDD DVSSX std_pad_asig5v", "VPLM PAD PL DC 0",
              "BDV IDVDD 0 V = '(v(dvdd)-v(dvddx))/0.5'", "BSV IDVSS 0 V = 'abs(i(vsss))'"]
    elif bd["path"] == "direct":
        o += ["XPD PAD PL hv_pad_direct"]
    else:
        o += ["XPD PAD PL 0 hv_pad_ballast", "BDR DRP 0 V = 'abs(v(pad)-v(pl))'"]
    o += cell_lines("", cand, defaults, vbd, "PL")
    o += ["BAP APAD 0 V = 'abs(v(pad))'", "BAL APL 0 V = 'abs(v(pl))'"]
    if "jn" in bd:
        m, area, pj = bd["jn"], defaults["wcap"] * defaults["lcap"], 2 * (defaults["wcap"] + defaults["lcap"])
        if m == "pd2nw":     # p+ plate over a separate n-well tied to VBW_C3
            o += [f"VJNS NWT 0 DC {VBW_C3}", f"DJN PL NWT diode_pd2nw_06v0 area={fnum(area)} pj={fnum(pj)}"]
        else:                # n-type plate region over the p substrate
            o += ["VJNS VSSJ 0 DC 0", f"DJN VSSJ PL diode_{m}{'_06v0' if m != 'dw2ps' else ''} "
                  f"area={fnum(area)} pj={fnum(pj)}"]
        o += ["BIJ IJN 0 V = 'abs(i(vjns))'"]
    if "nb" in bd:
        o += ["XPDJ PADJ PLJ hv_pad_direct", f"CPDJ PADJ 0 {fnum(C_PAD)}", f"CPLJ PLJ 0 {fnum(C_PL)}",
              f"CCPL PL PLJ {fnum(C_COUPLE)}"]
        if bd["nb"] == "drv":
            o += ["VNJ NJ 0 DC 0", f"RSRCJ NJ VCABJ {fnum(R_SRC)}", f"CCABJ VCABJ 0 {fnum(C_CABLE)}",
                  f"REXTJ VCABJ PADJ {fnum(R_EXT)}"]
        else:
            o += [f"RLKJ PADJ 0 {fnum(R_LEAK_HIZ)}"]
        o += cell_lines("J", cand, defaults, vbd, "PLJ")
    ms = [("vpad_max", "APAD"), ("vpl_max", "APL"), ("vox_max", "DOX"), ("ifil_max", "IFIL"), ("ipad_max", "IPD")]
    if bd["path"] == "ballast":
        ms.append(("vr_max", "DRP"))
    if bd["path"] == "std":
        ms += [("idvdd_hold", "IDVDD"), ("idvss_hold", "IDVSS")]
    if "jn" in bd:
        ms += [("ijn_max", "IJN"), ("ijn_hold", "IJN")]
    if "nb" in bd:
        ms += [("voxj_max", "DOXJ"), ("ifilj_max", "IFILJ")]
    t_hold = T1 + rp["tr"] + 0.9 * rp["tw"]     # late in the hold, edge currents settled
    meas = [{"name": n, "spice": (f".meas tran {n} FIND v({node.lower()}) AT={fnum(t_hold)}" if n.endswith("_hold")
                                  else f".meas tran {n} MAX v({node.lower()})"),
             "unit": "A" if n.startswith("i") else "V"} for n, node in ms]
    return "\n".join(o) + "\n", meas


def make_request(bench: str, bd: dict, cand, pdk, meas: list[dict], lvls: list[float]) -> dict:
    rp = RAMPS[bd["ramp"]]
    tstop = T1 + 2 * rp["tr"] + rp["tw"] + rp["tail"]
    return {"netlist": "body.spice", "engine": "ngspice", "backend": CB.KLT_BACKEND, "batch": dict(CB.BATCH_OPTS),
            "models": {"pdk": pdk.variant, "lib": "libs.tech/ngspice/sm141064.ngspice"},
            "corners": {"process": [{"name": p, "sections": [p, f"moscap_{p}", f"res_{p}", f"diode_{p}"]} for p in PROCS],
                        "supply_v": {"vamp": lvls}, "temperature_c": [float(t) for t in TEMPS]},
            "analysis": {"kind": "tran", "args": f"{fnum(rp['tstep'])} {fnum(tstop)} uic"},
            "measurements": meas, "options": {"timeout_s": 300, "keep_artifacts": True}}


# --- results -------------------------------------------------------------------

def corner_id(c: dict) -> str:
    return C.corner_id(c["process"], int(round(c["temperature_c"])),
                       C.fmt_node_supply("pl", c["supply_v"]["vamp"]))


def collect(report: dict, bd: dict, cand, vbd: float) -> list[dict]:
    rows = []
    for c in report["corners"]:
        vals = {m["name"].lower(): m["value"] for m in c["measurements"]}
        lv = c["supply_v"]["vamp"]
        codes = V.check_corner(bd["kind"], lv, vbd, cand.n, vals, ballast=bd["path"] == "ballast") if c["status"] == "pass" else [f"error:{c['status']}"]
        rows.append({"cid": corner_id(c), "level": lv, "status": c["status"], "vals": vals, "codes": codes})
    return rows


def sci(x) -> str:
    return "n/a" if x is None else f"{x:.3g}"


def render_bench(a, bench: str, bd: dict, rows: list[dict], vbd: float) -> None:
    keys = [k for k in ("vpad_max", "vpl_max", "vox_max", "vr_max", "ipad_max", "ifil_max", "ijn_max", "ijn_hold", "idvdd_hold", "idvss_hold",
                        "voxj_max", "ifilj_max") if any(k in r["vals"] for r in rows)]
    a(f"#### `{bench}` ({sum(r['status'] == 'pass' for r in rows)}/{len(rows)} corners converged)")
    a("")
    a("| Level [V] | corners ok | programmed | " + " | ".join(f"max {k}" for k in keys) + " | violations (corners) |")
    a("|---|---|---|" + "---|" * (len(keys) + 1))
    for lv in sorted({r["level"] for r in rows}, key=abs):
        rs = [r for r in rows if r["level"] == lv]
        ok = [r for r in rs if r["status"] == "pass"]
        prog = sum((r["vals"].get("ifil_max") or 0) > V.TRIP_I for r in ok)
        cnt: dict[str, int] = {}
        for r in rs:
            for c in r["codes"]:
                cnt[c] = cnt.get(c, 0) + 1
        mx = {k: max((abs(r["vals"][k]) for r in ok if r["vals"].get(k) is not None), default=None) for k in keys}
        a(f"| {lv:+.2f} | {len(ok)}/{len(rs)} | {prog}/{len(ok)} | " + " | ".join(sci(mx[k]) for k in keys)
          + " | " + ("; ".join(f"`{c}` x{n}" for c, n in sorted(cnt.items())) or "none") + " |")
    a("")


def render(rid: str, cand, vbd: float, lvls: list[float], results: dict, dirty: bool, defs: dict) -> str:
    out: list[str] = []
    a = out.append
    a(f"# sim/hv-pad-protection record {rid} -- Candidate {cand.n} (Region {cand.region})")
    a("")
    a("- **Issue**: #210 (part of #203). Evidence for `spec/hv-pad-protection-decision.md`.")
    a(f"- **V_bd (ASSUMED, design/breakdown/breakdown_params.spice)**: {vbd:g} V. Pad levels (signed): "
      + ", ".join(f"{x:+g}" for x in lvls) + f" V = {', '.join(f'{f:g}x' for f in FRACTIONS)} V_bd and "
      f"{V_PAD_MAX:g} V (16 V + 10 % bench overshoot).")
    a(f"- **Grid per bench**: {len(PROCS)} process ({', '.join(PROCS)} with moscap/res/diode sections) x "
      f"{len(TEMPS)} temperatures ({', '.join(map(str, TEMPS))} C) x {len(lvls)} levels = "
      f"{len(PROCS) * len(TEMPS) * len(lvls)} corners, `klt sim` on the batch fleet. Non-converged corners stay in the denominator.")
    a("- **Placeholders**: " + f"R_src {R_SRC:g} ohm, C_cable {C_CABLE:g} F, C_pad {C_PAD:g} F, C_PL {C_PL:g} F, R_acc {R_ACC:g} ohm, "
      f"R_fil {R_FIL:g} ohm, C_couple {C_COUPLE:g} F, R_leak(hi-Z) {R_LEAK_HIZ:g} ohm, DVDD {DVDD_STD} V, "
      "filament = threshold switch (on at V_bd, off below 0.1 V_bd). Not measured values.")
    a(f"- **Git**: `{R.git_short_sha(REPO_ROOT)}`" + (" (working tree dirty at run time)" if dirty else ""))
    a("- **Pass/fail rules**: `sim/hv-pad-protection/verdicts.py`. `rating:` = a device past its cited limit; "
      "`function:` = the path did not deliver the intended voltage or the expected programmed state.")
    a("")
    for bench, rows in results.items():
        if isinstance(rows, str):
            a(f"#### `{bench}`\n\nNO RESULT: {rows}\n")
        else:
            render_bench(a, bench, defs[bench], rows, vbd)
    return "\n".join(out) + "\n"


# --- driver --------------------------------------------------------------------

def setup(cand_n: int):
    cands = {c.n: c for c in CHAR.CANDIDATES}
    cand = cands[cand_n]
    pdk = P.resolve_pdk()
    defaults = CHAR.parse_defaults(REPO_ROOT / "design" / "netlists" / cand.netlist)
    vbd = vbd_of(cand_n, read_params())
    return cand, pdk, defaults, vbd


def smoke(spec: str) -> int:
    n, bench = spec.split(":")[:2]
    cand, pdk, defaults, vbd = setup(int(n))
    CB.fleet_lib_root(pdk)
    defs = bench_defs(cand.n)
    lv = levels(cand, vbd)
    work = REPO_ROOT / "sim" / ".artifact-scratch" / "hv-pad-smoke"
    work.mkdir(parents=True, exist_ok=True)
    text, meas = body(bench, defs[bench], cand, pdk, defaults, vbd)
    (work / "body.spice").write_text(text)
    req = make_request(bench, defs[bench], cand, pdk, meas, lv)
    cr = req["corners"]
    cr["process"], cr["temperature_c"], cr["supply_v"] = cr["process"][:1], [27.0], {"vamp": [lv[3]]}
    req["backend"] = "local"
    req.pop("batch", None)
    (work / "request.json").write_text(json.dumps(req))
    report, err = CB.K.run_klt(work / "request.json", work / "out", "local", klt_cmd=CB.KLT_CMD)
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
        cand, pdk, defaults, vbd = setup(n)
        for bench, bd in bench_defs(n).items():
            rp = base / f"c{n}" / bench / "report.json"
            if not rp.is_file():
                continue
            rows = collect(json.loads(rp.read_text()), bd, cand, vbd)
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
    pdk = P.resolve_pdk()
    CB.fleet_lib_root(pdk)
    dirty = R.git_is_dirty(REPO_ROOT)
    rc = 0
    for n in wanted:
        cand, pdk, defaults, vbd = setup(n)
        defs = bench_defs(n)
        names = args.benches.split(",") if args.benches else list(defs)
        lv = levels(cand, vbd)
        rid = R.allocate_record_id(THIS_DIR, REPO_ROOT)
        base = THIS_DIR / "corners" / rid
        print(f"== Candidate {n} (Region {cand.region}) record {rid}")
        R.write_once(base / "run-provenance.json", json.dumps({"git_sha": R.git_short_sha(REPO_ROOT), "dirty": dirty}) + "\n")
        results: dict = {}
        for bench in names:
            bdir = base / f"c{n}" / bench
            bdir.mkdir(parents=True, exist_ok=False)
            text, meas = body(bench, defs[bench], cand, pdk, defaults, vbd)
            R.write_once(bdir / "body.spice", text)
            req = make_request(bench, defs[bench], cand, pdk, meas, lv)
            R.write_once(bdir / "request.json", json.dumps(req, indent=2) + "\n")
            t0 = time.time()
            report, err = CB.run_klt(bdir / "request.json", bdir / ".work" / "klt", None)
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
            results[bench] = collect(report, defs[bench], cand, vbd)
            env = report.get("environment", {})
            print(f"   {bench}: {report.get('status')} ({len(report['corners'])} corners, {time.time() - t0:.0f}s, "
                  f"job {(env.get('remote') or {}).get('job_id')})", flush=True)
        R.write_once(THIS_DIR / "records" / f"{rid}.md", render(rid, cand, vbd, lv, results, dirty, defs))
        print(f"   record: records/{rid}.md")
        rc |= ES.publish_for_runner("hv-pad-protection", rid, base, REPO_ROOT)
        time.sleep(1.1)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
