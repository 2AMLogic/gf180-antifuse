#!/usr/bin/env python3
"""Issue #481: C3 R_on schematic-vs-extracted diagnosis (single-corner, local).

Each variant is a self-contained ngspice deck: same PDK sections, bias and
10 MHz AC measurement as requests/c3_{schematic,extracted}/ron.json.
R_on = Re(-V(BL)/I(VBL)).  One ngspice -b per variant, run serially.
Usage: run_c3_diagnosis.py [--corner ss|ff|tt --temp C --vbl V] -o results.json
PDK models: $PDK_ROOT first (pinned open_pdks revision beneath it), else ~/.ciel.
"""
import argparse, json, os, pathlib, re, subprocess, sys, tempfile
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[4]
# open_pdks revision pin; twins: sim/harness/pdk.py PINNED_OPEN_PDKS and
# design/lib-pdk-root.sh PINNED_OPEN_PDKS.
PINNED_OPEN_PDKS = "f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7"
PDK_REL = f"ciel/gf180mcu/versions/{PINNED_OPEN_PDKS}/gf180mcuD/libs.tech/ngspice"


def pdk_dir():
    """Pinned-revision ngspice model dir: under $PDK_ROOT when it is set and
    holds the pinned path, else under the ~/.ciel default."""
    roots = []
    env = os.environ.get("PDK_ROOT")
    if env:
        roots.append(pathlib.Path(env).expanduser())
    home = pathlib.Path.home() / ".ciel"
    if not roots or roots[0] != home:
        roots.append(home)
    for root in roots:
        p = root / PDK_REL
        if p.is_dir():
            return p
    sys.exit("ERROR: pinned gf180mcu ngspice models not found. Looked under:\n  "
             + "\n  ".join(str(r / PDK_REL) for r in roots)
             + "\nSet PDK_ROOT to a ciel/open_pdks install root.")


PDK = pdk_dir()
EXTRACTED = (ROOT / "layout/cell_candidate3/pex/extracted.spice").read_text()
CAP = "XC1 CN PL cap_pmos_03v3 c_width=1.0u c_length=0.28u m=1"

def sch(order="CN WL BL VB", cap=CAP):
    return f".subckt cell_candidate3 BL WL PL VB\nXM1 {order} pfet_06v0 L=0.55u W=0.42u nf=1 m=1\n{cap}\n.ends\n"

def ext_variant(drop=(), transform=None):
    """Extracted netlist with element lines whose name is in `drop` removed."""
    out = []
    for ln in EXTRACTED.splitlines():
        tok = ln.split()
        if tok and tok[0] in drop:
            continue
        out.append(ln)
    t = "\n".join(out) + "\n"
    return transform(t) if transform else t

def short_resistors(t, names):
    """Replace each named R element with a 0 V source (keeps connectivity)."""
    lines = []
    for ln in t.splitlines():
        tok = ln.split()
        lines.append(f"V{tok[0]}s {tok[1]} {tok[2]} 0" if tok and tok[0] in names else ln)
    return "\n".join(lines) + "\n"

def sub(old, new):
    return lambda t: t.replace(old, new)

def variants():
    v = {}
    v["sch_baseline"] = ("sch", sch(), "BL WL PL VB")
    v["ext_baseline"] = ("ext", ext_variant(), "BL PL VB WL")
    # H1: terminal orientation on the schematic reference (D/S swap, body perms).
    # sch_gate_BL is a sanity permutation (unphysical, negative R), not a hypothesis.
    for name, order in [("sch_swapDS", "BL WL CN VB"), ("sch_body_to_D", "CN WL BL CN"),
                        ("sch_gate_BL", "CN BL WL VB")]:
        v[name] = ("sch", sch(order), "BL WL PL VB")
    # H1 on the extracted card: swap D/S
    v["ext_swapDS"] = ("ext", ext_variant(transform=sub(
        "X$2 \\$3__t1 WL__t0 BL__t0 VB__t0", "X$2 BL__t0 WL__t0 \\$3__t1 VB__t0")), "BL PL VB WL")
    # H2: drop parasitic groups one at a time
    groups = {
        "no_C_3_storage": ("C_3",), "no_CBL": ("CBL",), "no_CPL": ("CPL",),
        "no_CVB": ("CVB",), "no_CWL": ("CWL",),
        "no_R_storage": ("R_3_t0", "R_3_t1"), "no_RBL": ("RBL_t0",),
        "no_RPL": ("RPL_t0",), "no_RVB": ("RVB_t0",), "no_RWL": ("RWL_t0",),
    }
    for k, d in groups.items():
        # shorted resistors: reconnect nets so dropping an R keeps connectivity
        t = ext_variant(drop=d) if not k.startswith("no_R") else short_resistors(ext_variant(), d)
        v["ext_" + k] = ("ext", t, "BL PL VB WL")
    # NOTE: all_sub_caps = the five substrate CAPACITORS only; every lumped R stays.
    all_sub_caps = ("C_3", "CBL", "CPL", "CVB", "CWL")
    all_R = ("R_3_t0", "R_3_t1", "RBL_t0", "RPL_t0", "RVB_t0", "RWL_t0")
    nojg = lambda t: t.replace(" AS=0.21P AD=0.21P\n+ PS=1.84U PD=1.84U", "")
    # H3: explicit AS/AD/PS/PD junction geometry on the extracted pfet card
    v["ext_noJunctionGeom"] = ("ext", ext_variant(transform=lambda t: re.sub(r"\n\+ AS=\S+ AD=\S+\n\+ PS=\S+ PD=\S+", "", nojg(t))), "BL PL VB WL")
    v["ext_cap_only_noJunctionGeom"] = ("ext", ext_variant(drop=all_sub_caps, transform=nojg), "BL PL VB WL")
    # ALL parasitics removed: five substrate C dropped AND six lumped R shorted
    v["ext_all_parasitics_removed"] = ("ext", short_resistors(ext_variant(drop=all_sub_caps), all_R), "BL PL VB WL")
    v["ext_all_parasitics_removed_noJunctionGeom"] = ("ext", short_resistors(ext_variant(drop=all_sub_caps, transform=nojg), all_R), "BL PL VB WL")
    v["ext_all_R_shorted_C_kept"] = ("ext", short_resistors(ext_variant(), all_R), "BL PL VB WL")
    v["sch_withJunctionGeom"] = ("sch", sch().replace("m=1\nXC1", "m=1 AS=0.21P AD=0.21P PS=1.84U PD=1.84U\nXC1"), "BL WL PL VB")
    v["sch_linearcap"] = ("sch", sch(cap="CC1 CN PL 1.232f"), "BL WL PL VB")
    v["sch_linearcap_withJunctionGeom"] = ("sch", sch(cap="CC1 CN PL 1.232f").replace("m=1\nCC1", "m=1 AS=0.21P AD=0.21P PS=1.84U PD=1.84U\nCC1"), "BL WL PL VB")
    v["ext_cap_only"] = ("ext", ext_variant(drop=all_sub_caps), "BL PL VB WL")
    return v

def _git_sha():
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def provenance():
    v = subprocess.run(["ngspice", "--version"], capture_output=True, text=True)
    m = re.search(r"ngspice-(\S+)", v.stdout)
    return {
        "ngspice_version": m.group(1) if m else "unknown",
        "pdk_revision": PINNED_OPEN_PDKS,
        "git_sha": _git_sha(),
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def deck(body, pins, corner, temp, vbl, vwl, vvb=3.3):
    return f"""* issue #481 diagnosis deck
.include "{PDK}/design.ngspice"
.lib "{PDK}/sm141064.ngspice" {corner}
.lib "{PDK}/sm141064.ngspice" moscap_typical
.temp {temp}
.options gmin=1e-13
{body}
X1 {pins} cell_candidate3
VVB VB 0 DC {vvb}
VBL BL 0 DC {vbl} AC 1
VWL WL 0 DC {vwl}
VPL PL 0 DC 0
.control
set nobreak
ac lin 1 1e7 1e7
let z = -v(bl)/i(vbl)
print real(z) imag(z)
.endc
.end
"""

def run(body, pins, args):
    d = deck(body, pins, args.corner, args.temp, args.vbl, args.vwl)
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "d.cir"; p.write_text(d)
        r = subprocess.run(["ngspice", "-b", str(p)], capture_output=True, text=True, timeout=300, cwd=td)
    m = re.search(r"real\(z\)\s*=\s*([-+0-9.eE]+)", r.stdout)
    i = re.search(r"imag\(z\)\s*=\s*([-+0-9.eE]+)", r.stdout)
    if not m:
        return {"error": (r.stdout + r.stderr)[-400:]}
    return {"re_ohm": float(m.group(1)), "im_ohm": float(i.group(1))}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corner", default="ss"); ap.add_argument("--temp", type=float, default=-40)
    ap.add_argument("--vbl", type=float, default=0.9); ap.add_argument("--vwl", type=float, default=0.0)
    ap.add_argument("-o", default="-")
    a = ap.parse_args()
    res = {"corner": a.corner, "temp_c": a.temp, "vbl": a.vbl, "vwl": a.vwl, "freq_hz": 1e7,
           **provenance(), "variants": {}}
    for k, (_kind, body, pins) in variants().items():
        res["variants"][k] = run(body, pins, a)
        print(k, res["variants"][k], file=sys.stderr)
    s = json.dumps(res, indent=2)
    (sys.stdout if a.o == "-" else open(a.o, "w")).write(s)
