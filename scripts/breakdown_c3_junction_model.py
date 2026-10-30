#!/usr/bin/env python3
"""Candidate 3 well-junction avalanche model (issue #208, parent #204).

Reproduces every table in docs/breakdown-c3-junction-model.md. Pure stdlib, no
simulator. Two routes are computed side by side:

* PDK-anchored: the SPICE `bv` of the PDK diode / device model cards
  (p+/n-well 10.5 V, n-well/p-substrate 14 V, `pfet_06v0` bvd = bvs = 10.5 V),
  with an ASSUMED tolerance and an ASSUMED avalanche temperature coefficient.
* Doping profile: one-sided abrupt-junction avalanche (Sze), swept over an
  ASSUMED n-well / substrate doping range, to state the sensitivity to each
  profile parameter and to check what doping the PDK `bv` implies.

The junction stresses are the worst-corner terminal-pair extremes recorded by
the #90 / #129 / #130 program-bias benches; they are transcribed in STRESS and
tests/test_breakdown_c3_junction_model.py re-reads them from the committed
records. Nothing here is measured, and nothing changes a ratified spec.

Usage:
    python3 scripts/breakdown_c3_junction_model.py            # print all tables
    python3 scripts/breakdown_c3_junction_model.py --check    # compare the note to this script
    python3 scripts/breakdown_c3_junction_model.py --update   # rewrite the note's tables
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_blocks  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NOTE = ROOT / "docs" / "breakdown-c3-junction-model.md"

# ---------------------------------------------------------------------------
# Parameters. Provenance tags: pdk = read from the PDK model file, assumed = ours.
# ---------------------------------------------------------------------------

EG_300K = 1.12            # [eV] silicon band gap at 300 K (textbook)
BV_PN = 10.5              # [V] pdk: diode_pd2nw_06v0 `bv`, pfet_06v0 `bvd` = `bvs`
BV_NWPS = 14.0            # [V] pdk: diode_nw2ps_06v0 `bv`
BV_TOL = 0.20             # assumed: +-20 % on the model-card `bv` (no tolerance is published)
ALPHA = (0.0005, 0.0015)  # [1/K] assumed avalanche temperature coefficient range (positive)
T_NOM, T_COLD, T_HOT = 27.0, -40.0, 125.0   # [degC] corner temperatures of the benches
N_NW = (5e16, 2e17)       # [cm^-3] assumed n-well doping next to the p+ drain
N_SUB = (1e15, 1e16)      # [cm^-3] assumed p-substrate doping next to the n-well
CURV = (0.6, 1.0)         # assumed curvature / edge derating of the planar abrupt value
NOMINAL = {"n_nw": 1e17, "curv": 0.8, "alpha": 0.001, "t": T_NOM}

VBD_CASES = ("assumed", "typ", "floor")
VBD_V = {"assumed": 7.9, "typ": 8.8, "floor": 7.0}   # [V] gate-oxide V_bd(t_ref) per case (#130)
VB_ON = 3.3               # [V] #62 n-well "on" tie

# Worst-corner |V| at the 1x level, max of the median and low-quantile element benches.
# cj = CN-VB (p+ drain / n-well), bj = BL-VB (p+ source / n-well). Source records in RECORDS.
STRESS = {
    ("bl",  "assumed"): {"cj": 11.07, "bj": 3.57, "pairs_over": 3},
    ("bl",  "typ"):     {"cj": 11.95, "bj": 3.60, "pairs_over": 3},
    ("bl",  "floor"):   {"cj": 10.20, "bj": 3.54, "pairs_over": 3},
    ("plb", "assumed"): {"cj": 10.84, "bj": 3.30, "pairs_over": 3},
    ("plb", "typ"):     {"cj": 11.68, "bj": 3.30, "pairs_over": 3},
    ("plb", "floor"):   {"cj": 9.98,  "bj": 3.30, "pairs_over": 3},
    ("gwa", "assumed"): {"cj": 7.34,  "bj": 0.00, "pairs_over": 2},
    ("gwa", "typ"):     {"cj": 8.13,  "bj": 0.00, "pairs_over": 2},
    ("gwa", "floor"):   {"cj": 6.42,  "bj": 0.00, "pairs_over": 2},
    ("gwb", "assumed"): {"cj": 6.34,  "bj": 0.00, "pairs_over": 3},
    ("gwb", "typ"):     {"cj": 7.43,  "bj": 0.00, "pairs_over": 3},
    ("gwb", "floor"):   {"cj": 5.54,  "bj": 0.00, "pairs_over": 1},
}
SCHEMES = {
    "bl":  "BL-driven (VPP on BL, PL 0, WL and n-well ride VPP)",
    "plb": "PL-driven (PL -VPP, BL 0, WL -3.3 V, VB 3.3 V)",
    "gwa": "PL-driven, VB 0 V (WL -3.3 V)",
    "gwb": "PL-driven, VB 0 V (WL -6.0 V)",
}
# (bench prefix, record per V_bd case); the benches read are <prefix>_b1m and <prefix>_b1l.
RECORDS = {
    "bl":  ("progc", {"assumed": "20261015-081144-ece0130", "typ": "20261028-035857-84a7179", "floor": "20261028-035900-84a7179"}),
    "plb": ("plb",   {"assumed": "20261015-093632-ff07fee", "typ": "20261028-024145-84a7179", "floor": "20261028-024425-84a7179"}),
    "gwa": ("gwa",   {"assumed": "20261021-031756-9f8fa78", "typ": "20261028-024205-84a7179", "floor": "20261028-024445-84a7179"}),
    "gwb": ("gwb",   {"assumed": "20261021-031756-9f8fa78", "typ": "20261028-024205-84a7179", "floor": "20261028-024445-84a7179"}),
}


def well_substrate_v(scheme: str, case: str) -> float:
    """Reverse voltage across n-well / p-substrate while programming [V].

    Derived from the bench definition, not a recorded pair: the n-well is
    VB = 3.3 V + VPP(t) in the BL-driven bench, a static 3.3 V in `plb`, and 0 V
    in `gwa` / `gwb`; the substrate is at 0 V. VPP at the 1x level is V_bd.
    """
    if scheme == "bl":
        return VB_ON + VBD_V[case]
    return VB_ON if scheme == "plb" else 0.0


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

def abrupt_bv(n_cm3: float, eg: float = EG_300K) -> float:
    """Planar one-sided abrupt-junction avalanche voltage at 300 K [V] (Sze):
    V_B = 60 (Eg/1.1)^1.5 (N/1e16)^-0.75."""
    if n_cm3 <= 0:
        raise ValueError("doping must be positive")
    return 60.0 * (eg / 1.1) ** 1.5 * (n_cm3 / 1e16) ** -0.75


def equivalent_doping(bv: float, eg: float = EG_300K) -> float:
    """Doping [cm^-3] at which the planar abrupt model gives `bv` (inverse of abrupt_bv)."""
    return 1e16 * (60.0 * (eg / 1.1) ** 1.5 / bv) ** (4.0 / 3.0)


def temp_scale(t_c: float, alpha: float) -> float:
    """Avalanche voltage relative to 27 degC: 1 + alpha (T - 27)."""
    return 1.0 + alpha * (t_c - T_NOM)


def bv_profile(n_cm3: float, curv: float, t_c: float, alpha: float) -> float:
    """Doping-route V_B at temperature t_c [V]."""
    return abrupt_bv(n_cm3) * curv * temp_scale(t_c, alpha)


def bv_anchored_range(bv_nom: float, tol: float = BV_TOL) -> tuple:
    """(low, nominal, high) avalanche voltage over the corner temperatures [V].

    Low = (1 - tol) at -40 degC with the largest alpha; high = (1 + tol) at 125 degC
    with the largest alpha. The model-card `bv` carries no temperature information,
    so it is read as the 27 degC value.
    """
    lo = bv_nom * (1 - tol) * temp_scale(T_COLD, ALPHA[1])
    hi = bv_nom * (1 + tol) * temp_scale(T_HOT, ALPHA[1])
    return lo, bv_nom, hi


def verdict(stress: float, lo: float, hi: float) -> str:
    """IN-RATING if stress <= low bound, NOT IN-RATING if stress > high bound, else UNDETERMINED."""
    if stress <= lo:
        return "IN-RATING"
    if stress > hi:
        return "NOT IN-RATING"
    return "UNDETERMINED"


def critical_doping(stress: float, curv: float = 1.0, t_c: float = T_COLD, alpha: float = ALPHA[1]) -> float:
    """Largest n-well doping [cm^-3] for which the doping route stays above `stress`."""
    return equivalent_doping(stress / (curv * temp_scale(t_c, alpha)))


# ---------------------------------------------------------------------------
# Tables (markdown). Each returns a string; main() prints them, the note embeds them.
# ---------------------------------------------------------------------------

def table_pdk_anchor() -> str:
    rows = [
        ("p+ / n-well, drain and source (`diode_pd2nw_06v0`, `pfet_06v0` bvd = bvs)", BV_PN),
        ("n-well / p-substrate (`diode_nw2ps_06v0`)", BV_NWPS),
    ]
    out = ["| Junction (PDK model card) | `bv` [V] | Low [V] | High [V] | Equivalent planar-abrupt doping [cm^-3] |",
           "|---|---|---|---|---|"]
    for name, bv in rows:
        lo, nom, hi = bv_anchored_range(bv)
        out.append(f"| {name} | {nom:.1f} | {lo:.2f} | {hi:.2f} | {equivalent_doping(nom):.2e} |")
    return "\n".join(out)


def table_profile_range() -> str:
    out = ["| Junction | Doping range [cm^-3] (assumed) | Planar abrupt V_B at 27 degC [V] | With curvature 0.6-1.0, -40..125 degC [V] |",
           "|---|---|---|---|"]
    for name, (n_lo, n_hi) in (("p+ / n-well (n-well side)", N_NW), ("n-well / p-substrate (substrate side)", N_SUB)):
        lo = bv_profile(n_hi, CURV[0], T_COLD, ALPHA[1])
        hi = bv_profile(n_lo, CURV[1], T_HOT, ALPHA[1])
        out.append(f"| {name} | {n_lo:.0e} to {n_hi:.0e} | {abrupt_bv(n_hi):.1f} to {abrupt_bv(n_lo):.1f} | {lo:.1f} to {hi:.1f} |")
    return "\n".join(out)


def table_sensitivity() -> str:
    base = bv_profile(NOMINAL["n_nw"], NOMINAL["curv"], NOMINAL["t"], NOMINAL["alpha"])
    out = [f"Nominal point: N = {NOMINAL['n_nw']:.0e} cm^-3, curvature {NOMINAL['curv']}, 27 degC; V_B = {base:.2f} V.", "",
           "| Parameter (varied alone) | Low value | High value | V_B at low [V] | V_B at high [V] | Swing [V] |",
           "|---|---|---|---|---|---|"]

    def row(label, lo_v, hi_v, f):
        a, b = f(lo_v), f(hi_v)
        out.append(f"| {label} | {lo_v:g} | {hi_v:g} | {a:.2f} | {b:.2f} | {abs(a - b):.2f} |")

    row("n-well doping N [cm^-3]", N_NW[0], N_NW[1], lambda v: bv_profile(v, NOMINAL["curv"], T_NOM, NOMINAL["alpha"]))
    row("curvature derating", CURV[0], CURV[1], lambda v: bv_profile(NOMINAL["n_nw"], v, T_NOM, NOMINAL["alpha"]))
    out.append(f"| temperature (-40 / 125 degC, alpha {NOMINAL['alpha']:g}) | -40 | 125 | "
               f"{bv_profile(NOMINAL['n_nw'], NOMINAL['curv'], T_COLD, NOMINAL['alpha']):.2f} | "
               f"{bv_profile(NOMINAL['n_nw'], NOMINAL['curv'], T_HOT, NOMINAL['alpha']):.2f} | "
               f"{abs(bv_profile(NOMINAL['n_nw'], NOMINAL['curv'], T_HOT, NOMINAL['alpha']) - bv_profile(NOMINAL['n_nw'], NOMINAL['curv'], T_COLD, NOMINAL['alpha'])):.2f} |")
    row("alpha [1/K] at 125 degC", ALPHA[0], ALPHA[1], lambda v: bv_profile(NOMINAL["n_nw"], NOMINAL["curv"], T_HOT, v))
    out += ["", "Log-sensitivity of the planar abrupt model: d ln V_B / d ln N = -0.75 (a factor 2 in doping is a factor 1.68 in V_B)."]
    return "\n".join(out)


def table_stress() -> str:
    out = ["| Arrangement | Oxide V_bd case | V_bd [V] | p+ drain / n-well `cj` [V] | p+ source / n-well `bj` [V] | n-well / p-substrate [V] |",
           "|---|---|---|---|---|---|"]
    for s in SCHEMES:
        for c in VBD_CASES:
            st = STRESS[(s, c)]
            out.append(f"| `{s}` | {c} | {VBD_V[c]:.1f} | {st['cj']:.2f} | {st['bj']:.2f} | {well_substrate_v(s, c):.1f} |")
    return "\n".join(out)


def table_verdict() -> str:
    lo, nom, hi = bv_anchored_range(BV_PN)
    wlo, wnom, whi = bv_anchored_range(BV_NWPS)
    out = [f"p+/n-well bounds [{lo:.2f}, {hi:.2f}] V (nominal {nom:.1f} V); n-well/p-substrate bounds [{wlo:.2f}, {whi:.2f}] V (nominal {wnom:.1f} V).", "",
           "| Arrangement | V_bd case | p+/n-well stress [V] | Margin to nominal / to low bound [V] | p+/n-well verdict | n-well/substrate stress [V] | Margin to nominal / to low bound [V] | n-well/substrate verdict | Access pairs over 6 V (records) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for s in SCHEMES:
        for c in VBD_CASES:
            cj = max(STRESS[(s, c)]["cj"], STRESS[(s, c)]["bj"])
            ws = well_substrate_v(s, c)
            out.append(f"| `{s}` | {c} | {cj:.2f} | {nom - cj:+.2f} / {lo - cj:+.2f} | {verdict(cj, lo, hi)} | "
                       f"{ws:.1f} | {wnom - ws:+.1f} / {wlo - ws:+.1f} | {verdict(ws, wlo, whi)} | {STRESS[(s, c)]['pairs_over']} |")
    return "\n".join(out)


def table_critical() -> str:
    out = ["| Arrangement | V_bd case | Stress [V] | Largest n-well doping that keeps the junction below avalanche, planar abrupt, -40 degC [cm^-3] |",
           "|---|---|---|---|"]
    for s in SCHEMES:
        for c in VBD_CASES:
            cj = STRESS[(s, c)]["cj"]
            out.append(f"| `{s}` | {c} | {cj:.2f} | {critical_doping(cj):.2e} |")
    return "\n".join(out)


TABLES = {
    "pdk-anchor": table_pdk_anchor,
    "profile-range": table_profile_range,
    "sensitivity": table_sensitivity,
    "stress": table_stress,
    "verdict": table_verdict,
    "critical-doping": table_critical,
}


def render() -> dict[str, str]:
    return {name: fn() for name, fn in TABLES.items()}


def main(argv: list[str]) -> int:
    return gen_blocks.main(render(), NOTE, argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
