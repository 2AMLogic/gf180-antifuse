"""Render HV pad protection corner results as Markdown evidence records."""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR.parent))
from harness.modload import load_module  # noqa: E402

M = sys.modules.get("sim_hv_model") or load_module(THIS_DIR / "model.py", "sim_hv_model")


def sci(x) -> str:
    return "n/a" if x is None else f"{x:.3g}"


def render_bench(a, bench: str, rows: list[dict]) -> None:
    keys = [k for k in ("vpad_max", "vpl_max", "vox_max", "vr_max", "ipad_max", "ifil_max", "ijn_max", "ijn_hold", "idvdd_hold", "idvss_hold",
                        "voxj_max", "ifilj_max") if any(k in r["vals"] for r in rows)]
    a(f"#### `{bench}` ({sum(r['status'] == 'pass' for r in rows)}/{len(rows)} corners converged)")
    a("")
    a("| Level [V] | corners ok | programmed | " + " | ".join(f"max {k}" for k in keys) + " | violations (corners) |")
    a("|---|---|---|" + "---|" * (len(keys) + 1))
    for lv in sorted({r["level"] for r in rows}, key=abs):
        rs = [r for r in rows if r["level"] == lv]
        ok = [r for r in rs if r["status"] == "pass"]
        prog = sum((r["vals"].get("ifil_max") or 0) > M.V.TRIP_I for r in ok)
        cnt: dict[str, int] = {}
        for r in rs:
            for c in r["codes"]:
                cnt[c] = cnt.get(c, 0) + 1
        mx = {k: max((abs(r["vals"][k]) for r in ok if r["vals"].get(k) is not None), default=None) for k in keys}
        a(f"| {lv:+.2f} | {len(ok)}/{len(rs)} | {prog}/{len(ok)} | " + " | ".join(sci(mx[k]) for k in keys)
          + " | " + ("; ".join(f"`{c}` x{n}" for c, n in sorted(cnt.items())) or "none") + " |")
    a("")


def render(rid: str, cand, vbd: float, lvls: list[float], results: dict, dirty: bool,
           git_sha: str | None = None) -> str:
    """Use the SHA in the record ID when rendering saved results without explicit provenance."""
    if git_sha is None:
        git_sha = rid.rsplit("-", 1)[-1]
    out: list[str] = []
    a = out.append
    a(f"# sim/hv-pad-protection record {rid} -- Candidate {cand.n} (Region {cand.region})")
    a("")
    a("- **Issue**: #210 (part of #203). Evidence for `spec/hv-pad-protection-decision.md`.")
    a(f"- **V_bd (ASSUMED, design/breakdown/breakdown_params.spice)**: {vbd:g} V. Pad levels (signed): "
      + ", ".join(f"{x:+g}" for x in lvls) + f" V = {', '.join(f'{f:g}x' for f in M.FRACTIONS)} V_bd and "
      f"{M.V_PAD_MAX:g} V (16 V + 10 % bench overshoot).")
    a(f"- **Grid per bench**: {len(M.PROCS)} process ({', '.join(M.PROCS)} with moscap/res/diode sections) x "
      f"{len(M.TEMPS)} temperatures ({', '.join(map(str, M.TEMPS))} C) x {len(lvls)} levels = "
      f"{len(M.PROCS) * len(M.TEMPS) * len(lvls)} corners, `klt sim` on the batch fleet. Non-converged corners stay in the denominator.")
    a(f"- **Placeholders**: R_src {M.R_SRC:g} ohm, C_cable {M.C_CABLE:g} F, C_pad {M.C_PAD:g} F, "
      f"C_PL {M.C_PL:g} F, R_acc {M.R_ACC:g} ohm, "
      f"R_fil {M.R_FIL:g} ohm, C_couple {M.C_COUPLE:g} F, R_leak(hi-Z) {M.R_LEAK_HIZ:g} ohm, DVDD {M.DVDD_STD} V, "
      "filament = threshold switch (on at V_bd, off below 0.1 V_bd). Not measured values.")
    a(f"- **Git**: `{git_sha}`" + (" (working tree dirty at run time)" if dirty else ""))
    a("- **Pass/fail rules**: `sim/hv-pad-protection/verdicts.py`. `rating:` = a device past its cited limit; "
      "`function:` = the path did not deliver the intended voltage or the expected programmed state.")
    a("")
    for bench, rows in results.items():
        if isinstance(rows, str):
            a(f"#### `{bench}`\n\nNO RESULT: {rows}\n")
        else:
            render_bench(a, bench, rows)
    return "\n".join(out) + "\n"
