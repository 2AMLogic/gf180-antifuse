#!/usr/bin/env python3
"""Compliance-limited post-breakdown filament model (issue #209, parent #204).

Reproduces every table in docs/breakdown-filament-model.md. Stdlib only, no
simulator. Nothing here edits design/breakdown/breakdown_params.spice.

Model (all numeric parameters are `assumed`, see PARAMS):

  R_f(I_c) = (V_f / I_a) * (I_a / I_c)**alpha          chord resistance at V_f
  ln R_f ~ Normal(ln R_med(I_c), sig_tot**2)
  sig_tot**2 = sig_int**2 + (alpha * sig_Ic)**2         intrinsic + compliance spread
  filament read I-V:  I = I_c' * (V / V_f)**p           (p = 1 is ohmic)

Programmed read = rail across (access resistance R_acc in series with the
filament). R_acc is not a PDK number: it is the effective series resistance
implied by the existing sim/cell-breakdown-model worst-corner I_prog_min
(which used the assumed 81.7 kOhm worst-case filament), so the model
reproduces that baseline exactly at the matching compliance.

Usage:
    scripts/breakdown_filament_model.py            # print all tables
    scripts/breakdown_filament_model.py --check docs/breakdown-filament-model.md
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- existing (read-only) inputs, from design/breakdown/breakdown_params.spice
# and sim/cell-breakdown-model/README.md; tests/ re-derive them from the files.
RF_MED_ASSUMED = 1.0e4        # bd_rf_med [ohm]
RF_SIG_ASSUMED = 0.7          # bd_rf_sig [ln-units]
Z_WC = 3.0                    # bd_zrf_wc
TOX = {"thin": 8.0e-9, "thick": 1.52e-8}   # c1_bd_tox, c2_bd_tox [m]
V_RAIL_LOW = 0.9              # V, low read rail of the worst corner
# worst-corner I_prog_min [A] with the assumed 81.7 kOhm filament, and I_sneak_max [A]
CAND = {
    "C1": {"oxide": "thin", "i_prog_min": 8.35e-6, "i_sneak_max": 9.8192e-12,
           "corner": "ss_125c_bl0p90v"},
    "C2": {"oxide": "thick", "i_prog_min": 10.98e-6, "i_sneak_max": 7.2888e-9,
           "corner": "ss_125c_bl0p90v"},
}
# Candidate 3 (spec/candidate3-read-bias-decision.md, s3_vb_track): access-limited.
C3_I_PROG_MIN = 1.25e-9       # A at ss_-40c_bl0p90v
C3_I_SNEAK_MAX = 3.2e-11     # A, max I_zero,f of s3_vb_track (the decision record's window of 39)

# --- model parameters: (value, unit, provenance, uncertainty)
V_F_THIN = 1.0                # V
SIG_INT = RF_SIG_ASSUMED
SIG_IC = 0.3                  # ln-units
ALPHA = 1.0
I_ANCHOR = 1.0e-4             # A
P_NL = 1.0
PARAMS = [
    ("V_f,thin", V_F_THIN, "V", "assumed", "x/÷ 2.5"),
    ("V_f,thick = V_f,thin * tox_thick/tox_thin", V_F_THIN * TOX["thick"] / TOX["thin"], "V",
     "assumed", "x/÷ 2.5 (scaling itself unverified)"),
    ("I_a (anchor current)", I_ANCHOR, "A", "assumed",
     "chosen so thin R_med(I_a) = 10 kOhm = bd_rf_med"),
    ("alpha (R_f ~ I_c^-alpha)", ALPHA, "1", "assumed", "0.5 to 1.0 (sensitivity table)"),
    ("sig_int", SIG_INT, "ln", "assumed", "= bd_rf_sig; 0.4 to 1.0 plausible, unsourced"),
    ("sig_Ic", SIG_IC, "ln", "assumed", "0 to 0.6 (ballast + VPP + access-device spread)"),
    ("p (filament I-V exponent)", P_NL, "1", "assumed", "1 to 2 (nonlinear table)"),
    ("Z_wc", Z_WC, "1", "assumed", "= bd_zrf_wc"),
]
I_C_GRID = [10e-6, 30e-6, 100e-6, 300e-6, 500e-6, 1e-3]


def v_f(oxide: str) -> float:
    return V_F_THIN * TOX[oxide] / TOX["thin"]


def r_med(i_c: float, oxide: str, alpha: float = ALPHA) -> float:
    return v_f(oxide) / I_ANCHOR * (I_ANCHOR / i_c) ** alpha


def sig_tot(sig_int: float = SIG_INT, sig_ic: float = SIG_IC, alpha: float = ALPHA) -> float:
    return math.hypot(sig_int, alpha * sig_ic)


def r_quantile(i_c: float, oxide: str, z: float, alpha: float = ALPHA,
               sig_ic: float = SIG_IC) -> float:
    return r_med(i_c, oxide, alpha) * math.exp(z * sig_tot(SIG_INT, sig_ic, alpha))


RF_WC_ASSUMED = RF_MED_ASSUMED * math.exp(Z_WC * RF_SIG_ASSUMED)   # 81.7 kOhm


def r_acc(cand: str) -> float:
    c = CAND[cand]
    return V_RAIL_LOW / c["i_prog_min"] - RF_WC_ASSUMED


def i_read(r_f: float, cand: str, p: float = P_NL, oxide: str | None = None) -> float:
    """Series read current: rail across R_acc + filament (chord R_f at V_f, exponent p)."""
    ox = oxide or CAND[cand]["oxide"]
    ra, vf = r_acc(cand), v_f(ox)
    if p == 1.0:
        return V_RAIL_LOW / (ra + r_f)
    i_c = vf / r_f
    lo, hi = 0.0, V_RAIL_LOW / ra if ra > 0 else V_RAIL_LOW / 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mid * ra + vf * (mid / i_c) ** (1.0 / p) > V_RAIL_LOW:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def i_prog_min(i_c: float, cand: str, **kw) -> float:
    ox = CAND[cand]["oxide"]
    return i_read(r_quantile(i_c, ox, Z_WC, kw.get("alpha", ALPHA), kw.get("sig_ic", SIG_IC)),
                  cand, kw.get("p", P_NL))


def i_c_equal_baseline(oxide: str, sig_ic: float = SIG_IC) -> float:
    """Compliance at which the +3 sigma filament equals the assumed 81.7 kOhm."""
    return I_ANCHOR * (r_quantile(I_ANCHOR, oxide, Z_WC, ALPHA, sig_ic) / RF_WC_ASSUMED) ** (1 / ALPHA)


# --- formatting -------------------------------------------------------------
def e(x: float, n: int = 3) -> str:
    return f"{x:.{n}e}"


def si_r(x: float) -> str:
    return f"{x/1e3:.3g} kΩ" if x < 1e6 else f"{x/1e6:.3g} MΩ"


def si_i(x: float) -> str:
    return f"{x*1e6:.4g} µA" if x >= 1e-6 else f"{x*1e9:.4g} nA" if x >= 1e-9 else f"{x*1e12:.4g} pA"


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def t_params() -> str:
    return table(["Parameter", "Value", "Unit", "Source", "Uncertainty"],
                 [[n, f"{v:.4g}", u, s, unc] for n, v, u, s, unc in PARAMS])


def t_rf() -> str:
    rows = []
    for ic in I_C_GRID:
        row = [si_i(ic)]
        for ox in ("thin", "thick"):
            row += [si_r(r_med(ic, ox)), si_r(r_quantile(ic, ox, Z_WC))]
        rows.append(row)
    return (f"sig_tot = {sig_tot():.3f} ln-units (x{math.exp(sig_tot()):.2f} per sigma).\n\n"
            + table(["I_c", "thin R_med", "thin R(+3σ)", "thick R_med", "thick R(+3σ)"], rows))


def t_margin() -> str:
    rows = [["assumed (existing)", "81.7 kΩ", si_i(CAND["C1"]["i_prog_min"]), "1.00",
             e(CAND["C1"]["i_prog_min"] / CAND["C1"]["i_sneak_max"], 2),
             si_i(CAND["C2"]["i_prog_min"]), "1.00",
             e(CAND["C2"]["i_prog_min"] / CAND["C2"]["i_sneak_max"], 2)]]
    for ic in I_C_GRID:
        r = [si_i(ic), f"{si_r(r_quantile(ic, 'thin', Z_WC))} / {si_r(r_quantile(ic, 'thick', Z_WC))}"]
        for c in ("C1", "C2"):
            i = i_prog_min(ic, c)
            r += [si_i(i), f"{i / CAND[c]['i_prog_min']:.2f}", e(i / CAND[c]["i_sneak_max"], 2)]
        rows.append(r)
    ra = {c: r_acc(c) for c in CAND}
    head = ["I_c", "R(+3σ) thin / thick", "C1 I_prog_min", "C1 ratio", "C1 / I_sneak_max",
            "C2 I_prog_min", "C2 ratio", "C2 / I_sneak_max"]
    return (f"Worst corner `ss_125c_bl0p90v` (rail 0.9 V). Derived R_acc: C1 {si_r(ra['C1'])}, "
            f"C2 {si_r(ra['C2'])}. 'ratio' = I_prog_min / existing assumed-model value.\n\n"
            + table(head, rows)
            + f"\n\nCompliance at which the +3σ filament equals the assumed 81.7 kΩ: "
              f"thin {si_i(i_c_equal_baseline('thin'))}, thick {si_i(i_c_equal_baseline('thick'))}.\n"
              f"Candidate 3 (`s3_vb_track`): I_prog_min {si_i(C3_I_PROG_MIN)} at `ss_-40c_bl0p90v` implies "
              f"an effective access resistance of {si_r(V_RAIL_LOW / C3_I_PROG_MIN)}, "
              f"{V_RAIL_LOW / C3_I_PROG_MIN / RF_WC_ASSUMED:.0f}x the assumed filament: a filament "
              f"change moves I_prog_min by under 1 % until R_f(+3σ) exceeds "
              f"{si_r(0.01 * V_RAIL_LOW / C3_I_PROG_MIN)}, so Candidate 3 is access-limited and "
              f"this model does not change its margin (window "
              f"{e(C3_I_PROG_MIN / C3_I_SNEAK_MAX, 2)} unchanged).")


def t_sens() -> str:
    rows = []
    for alpha in (0.5, 1.0):
        for sic in (0.0, 0.3, 0.6):
            r = [f"{alpha}", f"{sic}", f"{sig_tot(SIG_INT, sic, alpha):.3f}"]
            for ic in (30e-6, 500e-6):
                r.append(si_r(r_quantile(ic, "thin", Z_WC, alpha, sic)))
                r.append(si_i(i_prog_min(ic, "C1", alpha=alpha, sig_ic=sic)))
            rows.append(r)
    return table(["alpha", "sig_Ic", "sig_tot", "thin R(+3σ) @30 µA", "C1 I_prog_min @30 µA",
                  "thin R(+3σ) @500 µA", "C1 I_prog_min @500 µA"], rows)


def t_nl() -> str:
    rows = []
    for c in ("C1", "C2"):
        for ic in (30e-6, 100e-6, 500e-6):
            rf = r_quantile(ic, CAND[c]["oxide"], Z_WC)
            base = i_read(rf, c, 1.0)
            vfil = V_RAIL_LOW * rf / (rf + r_acc(c))
            r = [c, si_i(ic), si_r(rf), f"{vfil:.3f} V"]
            r += [f"{i_read(rf, c, p) / base:.3f}" for p in (1.5, 2.0)]
            rows.append(r)
    return table(["Cand.", "I_c", "R(+3σ)", "V across filament (ohmic)", "I(p=1.5)/I(ohmic)",
                  "I(p=2)/I(ohmic)"], rows)


def t_pred() -> str:
    rows = []
    for c in ("C1", "C2"):
        ox = CAND[c]["oxide"]
        for ic in (30e-6, 100e-6, 500e-6):
            rows.append([c, si_i(ic), si_r(r_med(ic, ox)),
                         f"{si_r(r_quantile(ic, ox, -Z_WC))} to {si_r(r_quantile(ic, ox, Z_WC))}",
                         si_i(i_read(r_med(ic, ox), c, 1.0)), si_i(i_prog_min(ic, c, p=1.0))])
    return table(["Cand.", "I_c", "R_f median", "R_f ±3σ band", "median I_read (0.9 V, worst-corner access)",
                  "+3σ I_read"], rows)


SECTIONS = {"params": t_params, "rf": t_rf, "margin": t_margin, "sens": t_sens,
            "nonlinear": t_nl, "predictions": t_pred}


def render() -> dict[str, str]:
    return {k: f() for k, f in SECTIONS.items()}


def extract(note: str) -> dict[str, str]:
    pat = re.compile(r"<!-- BEGIN GENERATED: (\w+) -->\n(.*?)\n<!-- END GENERATED: \1 -->", re.S)
    return {m.group(1): m.group(2) for m in pat.finditer(note)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", metavar="NOTE", help="fail if NOTE's generated tables differ")
    a = ap.parse_args(argv)
    gen = render()
    if not a.check:
        for k, v in gen.items():
            print(f"<!-- BEGIN GENERATED: {k} -->\n{v}\n<!-- END GENERATED: {k} -->\n")
        return 0
    have = extract(Path(a.check).read_text())
    bad = [k for k in gen if have.get(k) != gen[k]]
    if bad:
        print(f"stale or missing generated tables in {a.check}: {', '.join(bad)}", file=sys.stderr)
        return 1
    print("note and script agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
