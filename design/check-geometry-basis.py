#!/usr/bin/env python3
"""Fail if drawn bitcell geometry drifts from the geometry the committed SPICE
evidence was run at, beyond the divergences recorded in
design/geometry-basis.json.

    design/check-geometry-basis.py [--root DIR] [--emit-record]

The simulated basis and the drawn geometry live on opposite sides of the
design/ <-> layout/ boundary, and no other check crosses that boundary on
geometry:

  * design/check-array.py validates the array's wcap/lcap/wacc/lacc levels
    against the cell subcircuit's own defaults - the simulated world's
    internal consistency. It never reads layout/.
  * layout/cell_*/lvs_reference.spice resolves the subcircuit's parameters
    to the drawn geometry by design (`klt lvs --reference-form subckt-call`
    cannot carry parameter expressions), so `klt lvs` compares the layout
    against the layout's own dimensions and reports match - correctly, for
    what it checks.

This script reads, and trusts neither to agree with the other:

  * design/netlists/cell_candidateN.spice - the .subckt parameter defaults:
    the geometry every committed sim/ campaign instantiates at its minimum
    level. The 2x level is derived the same way design/check-array.py
    derives it: 2x wcap at fixed lcap, 2x wacc at fixed lacc.
  * layout/cell_candidate*/lvs_reference.spice - the XM1/XC1 instance-line
    W/L/c_width/c_length literals: the geometry the die will contain. A
    multi-finger access device (nf > 1) is compared at its total drawn
    width; the W literal in these files is already the total across fingers.

and reports, per drawn cell and per parameter (capacitor width/length,
access width/length), each divergence with both numbers and the
drawn/simulated ratio.

Every divergence must be recorded in design/geometry-basis.json to be
acceptable, and a recorded entry whose numbers no longer match the tree is a
failure too - a stale record is a failure, not a pass. The record also lists
the simulated split levels with no drawn cell at all (coverage gaps), checked
the same way. When a geometry change deliberately lands (e.g. a redraw), the
gate fails until the record is re-stated; `--emit-record` prints the measured
set as a fresh record to restate it from.

Green does NOT mean the geometry agrees. A within-axis relative claim is
unaffected: both worlds step exactly 2x per axis (the PDK moscap model's
C ~ c_length*c_width form makes the 2x/Min C ratio exactly 2.000 at fixed
bias), so relative comparisons recorded per region hold. An absolute claim -
yield at a given VPP for a given C, I_sneak_max at N=32 - does not: until the
recorded divergences are resolved (design/README.md PROVISIONAL open item
1(a)), no absolute number taken from one world describes the other.

Each capacitor-side entry also records where its resolution lives, derived
per entry by comparing both its simulated and drawn values against the
ratified level for that cell's moscap device (spec/capacitor-geometry-
decision.md, #294): drawn side stale -> #296's redraw; simulated side stale
-> the netlist regeneration tracked by design/README.md open item 1(a); both
-> both. Status says the same thing: the capacitor level is decided in spec
and the entry names which side does not yet conform. The access half is
genuinely undecided and stays status "unresolved" /
design/README.md open item 1(a). A recorded owner/status that no longer
matches this derivation is a stale-record failure, so neither the tree nor
the ratified table can drift past the gate silently.

Exit status: 0 = the measured divergence set equals the recorded set;
1 = any divergence not recorded, any recorded entry (or coverage gap) whose
facts no longer match the tree, or any unreportable drawn cell (missing
lvs_reference.spice, missing XM1/XC1 instance, unparseable literal or cell
name); 2 = could not run (missing simulated basis, missing or malformed
record). stdlib only; run with `python3 -I`. Issue #292.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DESIGN = Path(__file__).resolve().parent
ROOT = DESIGN.parent

sys.path.insert(0, str(ROOT / "sim"))
from harness import numfmt  # noqa: E402

RECORD_NAME = "geometry-basis.json"
PARAMS = ("cap_w", "cap_l", "acc_w", "acc_l")
PARAM_LABEL = {
    "cap_w": "capacitor width (wcap / c_width)",
    "cap_l": "capacitor length (lcap / c_length)",
    "acc_w": "access total width (wacc / W)",
    "acc_l": "access length (lacc / L)",
}
LEVELS = ("min", "2x")
CELL_PARAMS = ("wcap", "lcap", "wacc", "lacc")

# Ratified capacitor Minimum levels (W_um x L_um) per moscap device, from
# spec/capacitor-geometry-decision.md ("Ratified levels" table; ratified in
# #294, 2026-11-15): Region I/III cap_nmos_03v3 / cap_pmos_03v3 = 1.0 x 0.28,
# Region II cap_nmos_06v0 = 1.0 x 0.70; "2x-area" doubles W at fixed L (the
# same convention sim_geometry applies). This table is pinned to the spec by
# the suite (tests/test_check_geometry_basis.py::RatifiedLevelsMatchSpecTests)
# and the derived owner/status below is compared against the committed record,
# so a level that disagrees with the spec is a gate failure (stale record, or
# a red spec-drift test), never a silent relaxation of it.
RATIFIED_CAP_MIN_UM = {
    "cap_nmos_03v3": (1.0, 0.28),
    "cap_pmos_03v3": (1.0, 0.28),
    "cap_nmos_06v0": (1.0, 0.70),
}

ACC_OWNER = "design/README.md open item 1(a)"
# Live loci only: the netlist regeneration is tracked by the standing
# PROVISIONAL item, the redraw by open #296; closed #292/#294 appear in this
# module only as phrased provenance.
REGEN_OWNER = "design/README.md open item 1(a) (netlist regeneration)"
REDRAW_OWNER = "#296 (drawn capacitor redraw)"
BOTH_OWNERS = f"{REDRAW_OWNER}; {REGEN_OWNER}"
GAP_OWNER = ("Run 3 bitcell layout drop (WORK_PLAN.md Run 3: #207/#211); "
             "capacitor levels per spec/capacitor-geometry-decision.md (#294)")
STATUS_UNRESOLVED = "unresolved"
STATUS_DRAWN_STALE = "decided in spec; drawn geometry not conformed"
STATUS_SIM_STALE = "decided in spec; simulated basis not conformed"
STATUS_BOTH_STALE = "decided in spec; drawn geometry and simulated basis not conformed"
STATUS_GAP = "decided in spec (capacitor half); no drawn cell"


def cap_owner_status(sim_v: float, drawn_v: float, ratified_v: float) -> tuple[str, str]:
    """(status, owner) for one capacitor divergence, derived per entry.

    Compares both sides against the ratified level for that device, parameter
    and split level: drawn != ratified -> the redraw owns it; simulated !=
    ratified -> the netlist regeneration owns it; both -> both. A divergence
    exists only when the sides differ, so at least one side is always stale.
    """
    sim_ok = numfmt.close(sim_v, ratified_v)
    drawn_ok = numfmt.close(drawn_v, ratified_v)
    if not drawn_ok and sim_ok:
        return STATUS_DRAWN_STALE, REDRAW_OWNER
    if drawn_ok and not sim_ok:
        return STATUS_SIM_STALE, REGEN_OWNER
    return STATUS_BOTH_STALE, BOTH_OWNERS


def ratified_cap_value_um(rat_min_wl: tuple[float, float], cap_lvl: str, param: str) -> float:
    """Ratified capacitor value (SI metres) for one parameter at a split level.

    2x doubles W at fixed L (spec/capacitor-geometry-decision.md), matching
    sim_geometry's derivation of the 2x level; length never doubles.
    """
    w = rat_min_wl[0] * (2 if cap_lvl == "2x" else 1)
    return (w if param == "cap_w" else rat_min_wl[1]) * 1e-6

NOTES = [
    "A within-axis relative claim is unaffected: both worlds step exactly 2x "
    "per axis (the PDK moscap model's C ~ c_length*c_width form makes the "
    "2x/Min C ratio exactly 2.000 at fixed bias), so relative comparisons "
    "recorded per region hold.",
    "An absolute claim does not: yield at a given VPP for a given C, or "
    "I_sneak_max at N=32, taken from one world does not describe the other "
    "until these entries are resolved (design/README.md PROVISIONAL open "
    "item 1(a)).",
    "The gate being green means the divergences below are acknowledged and "
    "owned - NOT that the drawn geometry and the simulated geometry agree.",
]

_CELL_RE = re.compile(r"^cell_candidate(\d+)(?:_A(2x|min))?(?:_G(2x|min))?$")

# Drawn cells that are not split-axis grid points and are skipped here on
# purpose: the Run 3 C2-fallback variant (#372, spec/run3-c2-fallback-
# proposed.md) has no access device and no simulated basis -- there is no
# design/netlists fallback subckt to diverge from. Its capacitor levels are
# the ratified record's (spec/capacitor-geometry-decision.md Region II), and
# its binding evidence is the cell's own generator `--check` hash and LVS.
FALLBACK_CELLS = {"cell_candidate2_fallback"}


def parse_cell_name(name: str) -> tuple[int, str, str] | None:
    """cell_candidateN[_A<lvl>][_G<lvl>] -> (candidate, access_lvl, cap_lvl).

    Tolerates the committed forms (base `cell_candidate1`, both-axes
    `cell_candidate1_A2x_G2x`) and a single-axis form
    (`cell_candidate1_A2x` / `cell_candidate1_G2x`): an absent axis token
    means the Minimum level. Returns None for anything else.
    """
    m = _CELL_RE.match(name)
    if not m:
        return None
    cand, acc, cap = m.groups()
    return int(cand), acc or "min", cap or "min"


def ratio_close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(abs(a), abs(b), 1e-30)


def round6(x: float) -> float:
    return float(f"{x:.6g}")


def round12(x: float) -> float:
    return float(f"{x:.12g}")


def um(x: float) -> str:
    return f"{x * 1e6:.6g}um"


def instance_params(lines: list[str], inst: str) -> dict[str, str] | None:
    for ln in lines:
        if ln.split()[0].upper() == inst.upper():
            return dict(tok.split("=", 1) for tok in ln.split()[1:] if "=" in tok)
    return None


def cell_device(path: Path) -> str | None:
    """The moscap device name off the XC1 instance line (4th token), or None."""
    for ln in numfmt.logical_lines(path.read_text()):
        toks = ln.split()
        if toks[0].upper() == "XC1":
            return toks[3] if len(toks) > 3 else None
    return None


def parse_drawn_cell(path: Path) -> dict:
    """{cap_w, cap_l, acc_w, acc_l, acc_fingers} off the XM1/XC1 instance lines.

    Raises LookupError when XM1 or XC1 is absent and ValueError when a
    needed literal is missing or unparseable.
    """
    lines = numfmt.logical_lines(path.read_text())
    xm1 = instance_params(lines, "XM1")
    xc1 = instance_params(lines, "XC1")
    missing = [n for n, p in (("XM1", xm1), ("XC1", xc1)) if p is None]
    if missing:
        raise LookupError(f"{path.name}: no {missing[0]} instance line")
    try:
        out = {
            "acc_w": numfmt.spice_num(xm1["W"]),
            "acc_l": numfmt.spice_num(xm1["L"]),
            "cap_w": numfmt.spice_num(xc1["c_width"]),
            "cap_l": numfmt.spice_num(xc1["c_length"]),
        }
    except KeyError as e:
        raise ValueError(f"{path.name}: instance line lacks {e.args[0]}") from None
    except ValueError as e:
        raise ValueError(f"{path.name}: {e}") from None
    try:
        out["acc_fingers"] = int(xm1.get("nf", "1"))
    except ValueError:
        raise ValueError(f"{path.name}: unparseable nf {xm1.get('nf')!r}") from None
    return out


def sim_geometry(d: dict[str, float], acc_lvl: str, cap_lvl: str) -> dict[str, float]:
    return {
        "cap_w": d["wcap"] * (2 if cap_lvl == "2x" else 1),
        "cap_l": d["lcap"],
        "acc_w": d["wacc"] * (2 if acc_lvl == "2x" else 1),
        "acc_l": d["lacc"],
    }


def measure(root: Path):
    """Read both worlds. Returns (divergences, coverage_gaps, multi_finger,
    findings, fatal): divergences keyed by (cell, parameter), coverage gaps
    by (candidate, access_lvl, cap_lvl), findings are exit-1 strings, fatal
    are exit-2 strings."""
    findings: list[str] = []
    fatal: list[str] = []
    netlists = root / "design" / "netlists"
    layout = root / "layout"

    sim_defaults: dict[int, dict[str, float]] = {}
    devices: dict[int, str] = {}
    for p in sorted(netlists.glob("cell_candidate*.spice")):
        m = re.fullmatch(r"cell_candidate(\d+)\.spice", p.name)
        if not m:
            continue
        dev = cell_device(p)
        if dev not in RATIFIED_CAP_MIN_UM:
            fatal.append(f"{p}: XC1 device {dev!r} has no ratified capacitor level in "
                         "spec/capacitor-geometry-decision.md - cannot derive capacitor owner/status")
            continue
        d = numfmt.cell_defaults(p)
        missing = [k for k in CELL_PARAMS if k not in d]
        if missing:
            fatal.append(f"{p}: .subckt line lacks {', '.join(missing)} - cannot establish the simulated basis")
            continue
        sim_defaults[int(m.group(1))] = d
        devices[int(m.group(1))] = dev

    divergences: dict[tuple[str, str], dict] = {}
    multi_finger: dict[str, int] = {}
    drawn_points: set[tuple[int, str, str]] = set()
    for cdir in sorted(layout.glob("cell_candidate*")):
        if not cdir.is_dir():
            continue
        name = cdir.name
        if name in FALLBACK_CELLS:
            continue  # not a grid point: bare-capacitor fallback, #372
        parsed = parse_cell_name(name)
        if parsed is None:
            findings.append(f"{name}: unparseable bitcell cell name (expected cell_candidateN[_A<min|2x>][_G<min|2x>])")
            continue
        cand, acc_lvl, cap_lvl = parsed
        ref = cdir / "lvs_reference.spice"
        if not ref.exists():
            findings.append(f"{name}: {ref.relative_to(root)} missing - drawn cell with no LVS reference (reported, not silently skipped)")
            continue
        if cand not in sim_defaults:
            fatal.append(f"{name}: no simulated basis at design/netlists/cell_candidate{cand}.spice")
            continue
        try:
            drawn = parse_drawn_cell(ref)
        except (LookupError, ValueError) as e:
            findings.append(f"{name}: {e}")
            continue
        drawn_points.add((cand, acc_lvl, cap_lvl))
        if drawn["acc_fingers"] > 1:
            multi_finger[name] = drawn["acc_fingers"]
        sim = sim_geometry(sim_defaults[cand], acc_lvl, cap_lvl)
        for p in PARAMS:
            if numfmt.close(sim[p], drawn[p]):
                continue
            if p.startswith("cap"):
                rat = ratified_cap_value_um(RATIFIED_CAP_MIN_UM[devices[cand]], cap_lvl, p)
                status, owner = cap_owner_status(sim[p], drawn[p], rat)
            else:
                status, owner = STATUS_UNRESOLVED, ACC_OWNER
            divergences[(name, p)] = {
                "cell": name,
                "levels": {"access": acc_lvl, "capacitor": cap_lvl},
                "parameter": p,
                "simulated": sim[p],
                "drawn": drawn[p],
                "ratio": round6(drawn[p] / sim[p]) if sim[p] else None,
                "status": status,
                "owner": owner,
            }

    coverage_gaps: dict[tuple[int, str, str], dict] = {}
    for cand in sorted(sim_defaults):
        for acc_lvl in LEVELS:
            for cap_lvl in LEVELS:
                if (cand, acc_lvl, cap_lvl) in drawn_points:
                    continue
                sim = sim_geometry(sim_defaults[cand], acc_lvl, cap_lvl)
                coverage_gaps[(cand, acc_lvl, cap_lvl)] = {
                    "candidate": cand,
                    "levels": {"access": acc_lvl, "capacitor": cap_lvl},
                    "simulated": {p: sim[p] for p in PARAMS},
                    "status": STATUS_GAP,
                    "owner": GAP_OWNER,
                }
    return divergences, coverage_gaps, multi_finger, findings, fatal


def _req(e, keys, where) -> list[str]:
    if not isinstance(e, dict):
        return [f"{where}: entry must be a JSON object"]
    return [f"{where}: entry lacks '{k}'" for k in keys if k not in e]


def _levels_errors(levels, where) -> list[str]:
    if not isinstance(levels, dict) or set(levels) != {"access", "capacitor"}:
        return [f"{where}: 'levels' must carry 'access' and 'capacitor'"]
    bad = [f"{where}: unknown level {levels[a]!r}" for a in ("access", "capacitor") if levels.get(a) not in LEVELS]
    return bad


def load_record(path: Path) -> tuple[dict | None, list[str]]:
    """Parse + schema-check the record. Returns (record, fatal)."""
    if not path.exists():
        return None, [f"{path} missing - no recorded divergence set to compare against"]
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return None, [f"{path} is not valid JSON: {e}"]
    if not isinstance(raw, dict):
        return None, [f"{path}: top level must be a JSON object"]
    fatal: list[str] = []
    for key in ("divergences", "coverage_gaps"):
        if not isinstance(raw.get(key), list):
            fatal.append(f"{path}: '{key}' must be a list")
    if fatal:
        return None, fatal
    for i, e in enumerate(raw["divergences"]):
        where = f"{path}: divergences[{i}]"
        errs = _req(e, {"cell", "levels", "parameter", "simulated", "drawn", "ratio", "status", "owner"}, where)
        fatal += errs
        if errs:
            continue
        if e["parameter"] not in PARAMS:
            fatal.append(f"{where}: unknown parameter {e['parameter']!r}")
        fatal += _levels_errors(e["levels"], where)
        for k in ("simulated", "drawn"):
            if not isinstance(e[k], (int, float)) or isinstance(e[k], bool):
                fatal.append(f"{where}: '{k}' must be a number")
        if e["ratio"] is not None and (not isinstance(e["ratio"], (int, float)) or isinstance(e["ratio"], bool)):
            fatal.append(f"{where}: 'ratio' must be a number or null")
    for i, e in enumerate(raw["coverage_gaps"]):
        where = f"{path}: coverage_gaps[{i}]"
        errs = _req(e, {"candidate", "levels", "simulated", "status", "owner"}, where)
        fatal += errs
        if errs:
            continue
        if not isinstance(e["candidate"], int) or isinstance(e["candidate"], bool):
            fatal.append(f"{where}: 'candidate' must be an integer")
        fatal += _levels_errors(e["levels"], where)
        s = e["simulated"]
        if not isinstance(s, dict) or any(not isinstance(s.get(p), (int, float)) or isinstance(s.get(p), bool) for p in PARAMS):
            fatal.append(f"{where}: 'simulated' must carry numeric {', '.join(PARAMS)}")
    if fatal:
        return None, fatal
    return raw, []


def compare(record: dict, divergences, coverage_gaps, findings: list[str]) -> None:
    rec_divs = {(e["cell"], e["parameter"]): e for e in record["divergences"]}
    rec_gaps = {(e["candidate"], e["levels"]["access"], e["levels"]["capacitor"]): e for e in record["coverage_gaps"]}

    for key, e in divergences.items():
        r = rec_divs.get(key)
        if r is None:
            findings.append(
                f"unrecorded divergence: {key[0]} {key[1]} ({PARAM_LABEL[key[1]]}): "
                f"simulated {um(e['simulated'])}, drawn {um(e['drawn'])}, "
                f"drawn/sim {e['ratio']} - not in {RECORD_NAME}"
            )
            continue
        stale = []
        if r["levels"] != e["levels"]:
            stale.append(f"levels now access={e['levels']['access']} capacitor={e['levels']['capacitor']}, "
                         f"recorded access={r['levels']['access']} capacitor={r['levels']['capacitor']}")
        for k in ("simulated", "drawn"):
            if not numfmt.close(float(r[k]), float(e[k])):
                stale.append(f"{k} now {um(e[k])}, recorded {um(float(r[k]))}")
        for k in ("status", "owner"):
            if r[k] != e[k]:
                stale.append(f"{k} now {e[k]!r}, recorded {r[k]!r}")
        if (e["ratio"] is None) != (r["ratio"] is None):
            stale.append(f"ratio now {e['ratio']}, recorded {r['ratio']}")
        elif e["ratio"] is not None and not ratio_close(float(r["ratio"]), float(e["ratio"])):
            stale.append(f"ratio now {e['ratio']}, recorded {r['ratio']}")
        if stale:
            findings.append(f"stale record entry: {key[0]} {key[1]}: " + "; ".join(stale))
    for key in rec_divs:
        if key not in divergences:
            findings.append(f"stale record entry: {key[0]} {key[1]} - no longer diverges in the tree "
                            "(equal now, or the cell or its lvs_reference.spice is gone)")

    for key, e in coverage_gaps.items():
        r = rec_gaps.get(key)
        if r is None:
            findings.append(f"unrecorded coverage gap: candidate {key[0]} access={key[1]} capacitor={key[2]} "
                            f"has no drawn cell - not in {RECORD_NAME}")
            continue
        stale = [f"{p} now {um(e['simulated'][p])}, recorded {um(float(r['simulated'][p]))}"
                 for p in PARAMS if not numfmt.close(float(r["simulated"][p]), float(e["simulated"][p]))]
        for k in ("status", "owner"):
            if r[k] != e[k]:
                stale.append(f"{k} now {e[k]!r}, recorded {r[k]!r}")
        if stale:
            findings.append(f"stale record gap: candidate {key[0]} access={key[1]} capacitor={key[2]}: "
                            + "; ".join(stale))
    for key in rec_gaps:
        if key not in coverage_gaps:
            findings.append(f"stale record gap: candidate {key[0]} access={key[1]} capacitor={key[2]} - "
                            "a drawn cell now covers this level")


def build_record(divergences, coverage_gaps, multi_finger) -> dict:
    divs = []
    for key in sorted(divergences, key=lambda k: (k[0], PARAMS.index(k[1]))):
        e = dict(divergences[key])
        e["simulated"] = round12(e["simulated"])
        e["drawn"] = round12(e["drawn"])
        if e["ratio"] is not None:
            e["ratio"] = round12(e["ratio"])
        if key[1] == "acc_w" and key[0] in multi_finger:
            e["drawn_note"] = f"W literal is the drawn total across nf={multi_finger[key[0]]} fingers"
        divs.append(e)
    gaps = []
    for k in sorted(coverage_gaps):
        e = dict(coverage_gaps[k])
        e["simulated"] = {p: round12(v) for p, v in e["simulated"].items()}
        gaps.append(e)
    return {
        "schema": "geometry-basis/1",
        "issue": "#292",
        "status": "unresolved",
        "owner": ("design/README.md PROVISIONAL open item 1(a) (simulated capacitor basis "
                  "regeneration); #296 moves the drawn capacitor geometry; capacitor "
                  "Minimum/2x levels ratified per spec/capacitor-geometry-decision.md (#294)"),
        "conventions": {
            "units": "SI metres (0.42 = 0.42 um)",
            "min_level": "the cell subcircuit's own .subckt parameter default",
            "capacitor_2x": "2x wcap at fixed lcap",
            "access_2x": "2x wacc at fixed lacc",
            "ratio": "drawn / simulated",
            "divergence": "one entry per drawn cell and parameter whose drawn literal differs numerically "
                          "from the simulated basis at that cell's split level",
            "coverage_gap": "a simulated split level (candidate x access level x capacitor level) with no "
                            "drawn cell at all",
            "owner_status": "capacitor entries: owner/status derived per entry from the ratified levels "
                            "(spec/capacitor-geometry-decision.md, #294) - 'decided in spec; ...' names "
                            "which side (drawn / simulated / both) does not yet conform; access entries "
                            "stay 'unresolved' (level undecided). A recorded owner/status that no longer "
                            "matches the derivation is a stale-record failure.",
        },
        "notes": NOTES,
        "divergences": divs,
        "coverage_gaps": gaps,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="drawn-vs-simulated bitcell geometry basis check (issue #292)")
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="repo root to check (default: this script's repo; tests point it at a fixture tree)")
    ap.add_argument("--emit-record", action="store_true",
                    help="print the measured divergence set as a fresh geometry-basis.json instead of "
                         "checking - the restatement tool for when a geometry change deliberately lands")
    args = ap.parse_args(argv)
    root = args.root.resolve()

    divergences, coverage_gaps, multi_finger, findings, fatal = measure(root)
    for f in fatal:
        print(f"ERROR: {f}", file=sys.stderr)
    if fatal:
        return 2

    if args.emit_record:
        print(json.dumps(build_record(divergences, coverage_gaps, multi_finger), indent=2))
        return 0

    record, rec_fatal = load_record(root / "design" / RECORD_NAME)
    for f in rec_fatal:
        print(f"ERROR: {f}", file=sys.stderr)
    if rec_fatal:
        return 2

    compare(record, divergences, coverage_gaps, findings)

    print(f"== drawn vs simulated geometry basis (issue #292) ==")
    print(f"recorded divergences ({len(record['divergences'])}):")
    for e in record["divergences"]:
        lv = e["levels"]
        note = f" ({e['drawn_note']})" if "drawn_note" in e else ""
        print(f"  {e['cell']} [access={lv['access']} capacitor={lv['capacitor']}] {e['parameter']} "
              f"({PARAM_LABEL[e['parameter']]}): simulated {um(float(e['simulated']))}, "
              f"drawn {um(float(e['drawn']))}{note}, drawn/sim {e['ratio']} "
              f"[{e['status']} -> {e['owner']}]")
    print(f"recorded coverage gaps ({len(record['coverage_gaps'])}):")
    for e in record["coverage_gaps"]:
        lv = e["levels"]
        s = e["simulated"]
        print(f"  candidate {e['candidate']} [access={lv['access']} capacitor={lv['capacitor']}]: "
              f"no drawn cell; simulated cap {um(float(s['cap_w']))} x {um(float(s['cap_l']))}, "
              f"access {um(float(s['acc_w']))} x {um(float(s['acc_l']))} "
              f"[{e['status']} -> {e['owner']}]")
    if findings:
        print(f"FAIL: {len(findings)} finding(s):")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"ok: the measured divergence set equals the recorded set "
          f"({len(record['divergences'])} divergences, {len(record['coverage_gaps'])} coverage gaps)")
    print("NOTE: green means the divergences above are acknowledged and owned, NOT that the drawn and "
          "simulated geometry agree.")
    print("NOTE: a within-axis relative claim (exactly 2x per axis in both worlds) is unaffected; an "
          "absolute claim is not (design/README.md PROVISIONAL open item 1(a)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
