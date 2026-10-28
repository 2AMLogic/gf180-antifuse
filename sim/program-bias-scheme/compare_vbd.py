#!/usr/bin/env python3
"""Side-by-side program and read evidence at the assumed V_bd and the two sourced-V_bd sensitivity
points (issue #130). Reads saved fleet reports only; runs no simulation and writes one markdown
document (default: stdout).

Cases: `assumed` (the committed #90/#129/#75 records, bd_ebd from the parameter file), `typ` and
`floor` (per-candidate V_bd override, sourced BVox typ / spec floor, docs/breakdown-vbd-sources.md).
Everything is per candidate and per stress level (rated, 0.9x ... 1.1x V_bd); levels are never merged,
and a level's absolute voltage differs between cases because it is a fraction of that case's V_bd.
The run manifest `vbd-sensitivity-runs.json` names the record ids of the typ / floor runs.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PBS = _load(THIS_DIR / "run_experiment.py", "sim_pbs_cmp")
CB = PBS.CB
CASES = ("assumed", "typ", "floor")
LEVELS = ["rated"] + [f"{f:g}x" for f in CB.TRIG_FRACTIONS]
ASSUMED_RUNS = {
    "progc": dict(PBS.EXISTING_PROGC),
    "pbs": {1: "20261015-100043-ff07fee", 2: "20261015-091611-ff07fee", 3: "20261015-093632-ff07fee"},
    "gwd": "20261021-031756-9f8fa78",
    "bias": "20261014-104105-9220086",
}


def load_manifest() -> dict:
    m = json.loads((THIS_DIR / "vbd-sensitivity-runs.json").read_text())
    m["assumed"] = {k: ({str(n): r for n, r in v.items()} if isinstance(v, dict) else v) for k, v in ASSUMED_RUNS.items()}
    return m


def params_for(base: dict, case: str, n: int) -> dict:
    return CB.apply_vbd_case(base, None if case == "assumed" else case, n)


def level_stats(cand, params, res, stim: str) -> dict[str, dict]:
    """Per level: converged/attempted, programmed (st=1) corners, and the largest |V| of each
    access-device pair over the level's converged corners (worst corner, within one level only)."""
    rating = CB.ACCESS_RATING_V[cand.n]
    out = {}
    for h in LEVELS:
        cids = [c for c in res.values if CB.level_label(cand, params, stim, CB.corner_level(c)) == h]
        ok = [c for c in cids if res.outcome[c]["kind"] == "pass"]
        sts = [res.values[c].get("st") for c in ok]
        prog = sum(1 for s in sts if s is not None and s > 0.5) if any(s is not None for s in sts) else None
        mx = {}
        for k in CB.ACCESS_PAIRS:
            xs = [CB.abs_extreme(res.values[c], k) for c in ok]
            xs = [x for x in xs if x is not None]
            mx[k] = max(xs) if xs else None
        out[h] = {"att": len(cids), "ok": len(ok), "prog": prog, "mx": mx,
                  "over": [k for k, v in mx.items() if v is not None and v > rating],
                  "vlevel": abs(CB.corner_level(cids[0])) if cids else None}
    return out


def cell(s: dict | None) -> str:
    if s is None or not s["att"]:
        return "n/a"
    prog = "" if s["prog"] is None else f"prog {s['prog']}/{s['ok']}; "
    over = ", ".join(s["over"]) if s["over"] else "none"
    return f"{s['vlevel']:.2f} V: {prog}{s['ok']}/{s['att']} conv; over rating: {over}"


def program_tables(a, base, man) -> None:
    by_n = {c.n: c for c in PBS.CHAR.CANDIDATES}
    for n in (1, 2, 3):
        cand = by_n[n]
        rating = CB.ACCESS_RATING_V[n]
        a(f"### Candidate {n} (Region {cand.region}), access-device rating {rating:g} V")
        a("")
        # (label, stim, bench, loader key)
        sets = [("BL-driven `progc_b1m`", "progc", "progc_b1m", "progc"), ("BL-driven `progc_b1l`", "progc", "progc_b1l", "progc"),
                ("BL-driven `progc_st` (intact cell)", "progc", "progc_st", "progc"),
                ("PL-driven `plb_b1m`", "trigc", "plb_b1m", "pbs"), ("PL-driven `plb_b1l`", "trigc", "plb_b1l", "pbs"),
                ("PL-driven `plb_st` (intact cell)", "trigc", "plb_st", "pbs"),
                ("unselected cell `plu_st`", "trigc", "plu_st", "pbs")]
        loaded = {}
        for case in CASES:
            p = params_for(base, case, n)
            rid = man[case]["progc"][str(n)]
            loaded[(case, "progc")] = (p, CB.results_from_reports(cand, rid, p, benches=("progc_st", "progc_b1m", "progc_b1l")))
            rid = man[case]["pbs"][str(n)]
            loaded[(case, "pbs")] = (p, PBS.load_saved(cand, rid, p))
        for label, stim, bench, key in sets:
            a(f"**{label}** -- one row per stress level; each cell: level voltage, programmed corners / converged, "
              "converged / attempted, access-device pairs whose largest |V| exceeds the rating (worst corner within the level).")
            a("")
            a("| Level | " + " | ".join(CASES) + " | what changed vs assumed |")
            a("|---|---|---|---|---|")
            st = {}
            for case in CASES:
                p, res = loaded[(case, key)]
                st[case] = level_stats(cand, p, res[bench], stim) if bench in res else None
            for h in LEVELS:
                cells = [cell(st[c][h]) if st[c] else "not run" for c in CASES]
                chg = []
                for c in ("typ", "floor"):
                    if st[c] and st["assumed"]:
                        x, y = st[c][h], st["assumed"][h]
                        if x["prog"] != y["prog"] or x["over"] != y["over"] or x["ok"] != y["ok"]:
                            chg.append(f"{c}: " + ("programmed " + f"{y['prog']}->{x['prog']}; " if x["prog"] != y["prog"] else "")
                                       + (f"over {y['over']}->{x['over']}" if x["over"] != y["over"] else "")
                                       + (f"conv {y['ok']}->{x['ok']}" if x["ok"] != y["ok"] else ""))
                a(f"| {h} | " + " | ".join(cells) + " | " + ("; ".join(chg) if chg else "no change") + " |")
            a("")


def gwd_table(a, base, man) -> None:
    cand = {c.n: c for c in PBS.CHAR.CANDIDATES}[3]
    rating = CB.ACCESS_RATING_V[3]
    a(f"### Candidate 3 gate/well-drive benches (`gwa`: WL -3.3 V, VB 0 V; `gwb`: WL -6.0 V, VB 0 V), rating {rating:g} V")
    a("")
    a("Cells are corners with ALL six access-device pairs within the rating / attempted corners (a non-converged corner is "
      "never in rating). Per stress level; the `_b1m` / `_b1l` rows are the program-event rows.")
    a("")
    res_by = {}
    for case in CASES:
        p = params_for(base, case, 3)
        res_by[case] = (p, PBS.load_saved(cand, man[case]["gwd"], p))
    for b in PBS.GWD_BENCHES:
        a(f"**`{b}`**")
        a("")
        a("| Level | " + " | ".join(CASES) + " |")
        a("|---|---|---|---|")
        for h in LEVELS:
            cells = []
            for case in CASES:
                p, res = res_by[case]
                r = res.get(b)
                if r is None:
                    cells.append("not run")
                    continue
                cids = [c for c in r.values if CB.level_label(cand, p, "trigc", CB.corner_level(c)) == h]
                good = sum(1 for c in cids if r.outcome[c]["kind"] == "pass" and all(
                    (x := CB.abs_extreme(r.values[c], k)) is not None and x <= rating for k in CB.ACCESS_PAIRS))
                cells.append(f"{good}/{len(cids)}")
            a(f"| {h} | " + " | ".join(cells) + " |")
        a("")


def read_table(a, base, man) -> None:
    cand = {c.n: c for c in PBS.CHAR.CANDIDATES}[3]
    a("### Candidate 3 read bias (`bias_op`, 45 PVT corners, 4 sizing x geometry sub-configs)")
    a("")
    a("Programmed (worst filament rf_wc, `I_prog`, minimum over corners) and unprogrammed (`I_zero,f`, maximum over corners, "
      "solver-floor-limited) read currents at the sense path's worst-case corner, per read-bias scenario. The read bench has "
      "no stress level; V_bd enters only through the breakdown element's field at the read bias.")
    a("")
    a("| Scenario | case | min I_prog [A] (corner) | max I_zero,f [A] (corner) | window | corners I_prog > I_zero,f | failed corners | feasible |")
    a("|---|---|---|---|---|---|---|---|")
    stats = {}
    for case in CASES:
        p = params_for(base, case, 3)
        res = CB.results_from_reports(cand, man[case]["bias"], p, benches=(CB.BIAS_BENCH,))[CB.BIAS_BENCH]
        stats[case] = {s.name: CB.bias_stats(res.values, res.corner_status, s) for s in CB.BIAS_SCENARIOS}
    def key(t):
        return (t.get("prog_min"), t.get("prog_min_at"), t.get("zero_f_max"), t.get("zero_f_max_at"),
                t.get("per_corner_ok"), len(t["failed"]), t["common_iref"])

    for s in CB.BIAS_SCENARIOS:
        same = key(stats["typ"][s.name]) == key(stats["floor"][s.name]) == key(stats["assumed"][s.name])
        for case in (("assumed = typ = floor",) if same else CASES):
            t = stats["assumed" if same else case][s.name]
            if not t["rows"]:
                a(f"| `{s.name}` | {case} | n/a | n/a | n/a | 0 | {len(t['failed'])} | **NO** |")
                continue
            a(f"| `{s.name}` | {case} | {t['prog_min']:.4e} (`{t['prog_min_at']}`) | {t['zero_f_max']:.4e} (`{t['zero_f_max_at']}`) | "
              f"{t['window']:.3g} | {t['per_corner_ok']}/{len(t['rows'])} | {len(t['failed'])} | "
              f"{'**yes**' if t['common_iref'] else '**NO**'} |")
    a("")
    ch = [s.name for s in CB.BIAS_SCENARIOS for c in ("typ", "floor")
          if stats[c][s.name].get("prog_min") != stats["assumed"][s.name].get("prog_min")
          or stats[c][s.name].get("zero_f_max") != stats["assumed"][s.name].get("zero_f_max")]
    a("Scenarios whose `min I_prog` or `max I_zero,f` differs from the assumed-V_bd record: " + (", ".join(sorted(set(ch))) if ch else "**none** (read evidence is unchanged by V_bd at the digits recorded)") + ".")
    a("")


def main() -> int:
    base, err = CB.CHECK.parse_params((CB.BD_DIR / "breakdown_params.spice").read_text())
    if err:
        print("params fail provenance checks", file=sys.stderr)
        return 3
    man = load_manifest()
    L: list[str] = []
    a = L.append
    program_tables(a, base, man)
    gwd_table(a, base, man)
    read_table(a, base, man)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
