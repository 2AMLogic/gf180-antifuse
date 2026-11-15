#!/usr/bin/env python3
"""Gate-oxide breakdown model: V_bd versus pulse width and its spread (issue #205).

Reproduces every generated table in docs/breakdown-oxide-model.md. Stdlib only, no
simulator, no randomness.

Usage:
    scripts/breakdown_oxide_model.py            print all generated blocks
    scripts/breakdown_oxide_model.py --check    fail if the note's blocks differ
    scripts/breakdown_oxide_model.py --update   rewrite the note's blocks in place

The note embeds each table between `<!-- gen:NAME -->` and `<!-- /gen:NAME -->`.
Nothing here edits design/breakdown/breakdown_params.spice; it only reads it.
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_blocks  # noqa: E402
from gen_blocks import table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARAMS_FILE = ROOT / "design" / "breakdown" / "breakdown_params.spice"
NOTE = ROOT / "docs" / "breakdown-oxide-model.md"

MVCM = 1e8  # V/m per MV/cm
LN2 = math.log(2.0)
YEAR = 3.156e7  # s
TEN_YEARS = 10 * YEAR
EPS0 = 8.854e-12  # F/m
EPS_R = 3.9  # SiO2, as the S2 cross-check in docs/breakdown-vbd-sources.md

# --- parameters read from the params file (tox is PDK-sourced; the rest are the existing assumed values)
def read_params(path: Path = PARAMS_FILE) -> dict[str, float]:
    out = {}
    for m in re.finditer(r"^\.param\s+(\w+)\s*=\s*([-+0-9.eE]+)\s*$", path.read_text(), re.M):
        out[m.group(1)] = float(m.group(2))
    return out


P = read_params()

# --- assumed model inputs (every one is listed with source and uncertainty in the note)
E0 = P["bd_ebd"]  # V/m, median field of a reference device at TREF
TREF = P["bd_tref"]  # s
GAMMA = P["bd_gam"]  # m/V, E-model field acceleration
BETA_EXT = P["bd_beta"]  # extrinsic / defect-limited Weibull shape (existing assumed value)
PERC_A = 0.4  # 1/nm, intrinsic Weibull shape per nm of oxide (percolation scaling), assumed
A0 = 1e-12  # m^2 reference area (1 um^2 = committed cell cap default, wcap = lcap = 1u)
V_OFF = 0.0  # V, flat-band + surface-potential offset, assumed zero
Q_FLOOR = 1e-3  # quantile at which the S1 spec floor is read, assumed
RAMP_S1 = 1.0  # V/s, assumed ramp rate behind S1 (variant B)
RAMP_WINDOW = (1e-2, 1e2)  # V/s, assumed range of laboratory ramp rates
S3_Q, S3_AREA, S3_LIFE = 1e-4, 1e-5, TEN_YEARS  # 100 ppm, 0.1 cm^2 of oxide, 10 yr (assumed)

# S1 BVox |V|: (typ, floor); S3 DC operating limit, V
CANDS = {
    1: dict(name="C1 thin NMOS cap", tox=P["c1_bd_tox"], s1=(9.0, 7.0), s3=3.63),
    2: dict(name="C2 thick NMOS cap", tox=P["c2_bd_tox"], s1=(16.0, 12.0), s3=6.0),
    3: dict(name="C3 thin PMOS cap", tox=P["c3_bd_tox"], s1=(8.8, 7.0), s3=3.63),
}
COX = {  # S2, fF/um^2 (min, typ, max) -> F/m^2 = 1e-3 * value
    "thin 3.3 V": (3.4, 4.4, 5.4),
    "thick 6 V": (1.8, 2.3, 2.8),
}

PULSES = [(1e-7, "100 ns"), (1e-6, "1 us"), (1e-5, "10 us"), (1e-4, "100 us"), (1e-3, "1 ms"),
          (1e-2, "10 ms"), (1.0, "1 s"), (1e3, "1000 s"), (TEN_YEARS, "10 yr (DC proxy)")]


@dataclass(frozen=True)
class Model:
    tox: float  # m
    beta: float
    e0: float = E0  # V/m
    gamma: float = GAMMA  # m/V
    voff: float = V_OFF  # V
    law: str = "E"  # "E" or "1/E"

    def t50(self, e: float) -> float:
        """Median lifetime of an A0 device at field e (V/m)."""
        if self.law == "E":
            return TREF * math.exp(-self.gamma * (e - self.e0))
        g = self.gamma * self.e0 ** 2  # 1/E branch: same value and slope at e0
        return TREF * math.exp(g * (1.0 / e - 1.0 / self.e0))

    def quantile_factor(self, q: float, area: float) -> float:
        """t_q / t50 for a device of the given area: Weibull weakest link."""
        return ((-math.log(1.0 - q) / LN2) * (A0 / area)) ** (1.0 / self.beta)

    def field(self, t: float, q: float = 0.5, area: float = A0) -> float:
        """Field (V/m) at which fraction q of devices of this area break within a pulse of width t."""
        t_med = t / self.quantile_factor(q, area)
        if self.law == "E":
            return self.e0 + math.log(TREF / t_med) / self.gamma
        inv = 1.0 / self.e0 + math.log(t_med / TREF) / (self.gamma * self.e0 ** 2)
        return 1.0 / inv if inv > 0 else math.inf

    def vbd(self, t: float, q: float = 0.5, area: float = A0) -> float:
        return self.voff + self.tox * self.field(t, q, area)

    def t_eff_ramp(self, rate_v: float) -> float:
        """A field ramp k = rate/tox breaks like a pulse of width 1/(gamma*k) (E-model, Miner sum)."""
        return self.tox / (self.gamma * rate_v)

    def vbd_ramp(self, rate_v: float, q: float = 0.5, area: float = A0) -> float:
        return self.vbd(self.t_eff_ramp(rate_v), q, area)

    def lifetime(self, v: float, q: float, area: float) -> float:
        return self.t50((v - self.voff) / self.tox) * self.quantile_factor(q, area)

    def sigma_v(self, q_lo: float = 1e-3, q_hi: float = 0.999, area: float = A0) -> float:
        """V_bd(q_hi) - V_bd(q_lo) at fixed t (E-model: independent of t)."""
        return self.vbd(1e-6, q_hi, area) - self.vbd(1e-6, q_lo, area)


def beta_perc(tox: float) -> float:
    return PERC_A * tox * 1e9


def model(n: int, beta: str = "perc", **kw) -> Model:
    c = CANDS[n]
    b = beta_perc(c["tox"]) if beta == "perc" else BETA_EXT
    return Model(tox=c["tox"], beta=b, **kw)


def g(x: float) -> str:
    return f"{x:.3g}"


def dec(gamma: float) -> float:
    return gamma * MVCM / math.log(10)


# --------------------------------------------------------------------------------- generated blocks
def blk_params() -> str:
    rows = []
    for n, c in CANDS.items():
        lo, hi = (EPS_R * EPS0 / (COX["thick 6 V" if n == 2 else "thin 3.3 V"][i] * 1e-3) for i in (2, 0))
        rows.append([f"tox, {c['name']}", "tox", g(c["tox"] * 1e9), "nm", "PDK model file via breakdown_params.spice (`c%d_bd_tox`)" % n,
                     f"electrical tox from S2 Cox min..max: {g(lo*1e9)}..{g(hi*1e9)} nm"])
    rows += [
        ["median field, A0 device, at TREF", "E0", g(E0 / MVCM), "MV/cm", "`assumed` (= `bd_ebd`; not a gf180 number)", "+-2 MV/cm (assumed range)"],
        ["reference time", "TREF", g(TREF), "s", "definition (`bd_tref`)", "none, it is a coordinate"],
        ["E-model field acceleration", "gamma", g(dec(GAMMA)), "decades/(MV/cm)", "`assumed` (= `bd_gam`)", "2..4 decades/(MV/cm) (assumed range); lower bound from S3 in section 7"],
        ["Weibull shape, intrinsic", "beta_i", f"{PERC_A} * tox[nm] = " + " / ".join(g(beta_perc(CANDS[n]['tox'])) for n in CANDS), "1", "`assumed`: percolation-type scaling with oxide thickness, coefficient not read from a primary source here", "coefficient 0.2..0.6 /nm (assumed)"],
        ["Weibull shape, extrinsic bound", "beta_x", g(BETA_EXT), "1", "`assumed` (= `bd_beta`)", "1..2 (assumed)"],
        ["reference / cell area", "A0, A", "1", "um^2", "committed cell cap default (`wcap = lcap = 1u`, `design/breakdown/cell_candidates_bd.spice`)", "none for the cell; S1 test-structure area unknown"],
        ["oxide-voltage offset (flat-band + surface potential)", "V_off", g(V_OFF), "V", "`assumed` zero (the existing element ignores it)", "+-1 V (assumed)"],
        ["relative permittivity of SiO2", "eps_r", g(EPS_R), "1", "textbook value, as used in S2 cross-check of the sources note", "none claimed"],
        ["quantile read as the S1 spec floor", "q_fl", g(Q_FLOOR), "1", "`assumed`: S1 states no quantile", "1e-4..1e-2 (assumed)"],
        ["ramp rate behind S1 (variant B only)", "R_S1", g(RAMP_S1), "V/s", "`assumed`: S1 states none", "+-2 decades (assumed)"],
        ["S3 lifetime criterion", "-", f"{g(S3_Q)} fraction, {g(S3_AREA*1e12)} um^2, 10 yr", "-", "`assumed`: S3 states none", "see section 7"],
        ["temperature", "T", "not modelled", "-", "`assumed`: E0 and gamma are implicitly at one unstated temperature", "unquantified"],
    ]
    return table(["Parameter", "Symbol", "Value", "Unit", "Source", "Uncertainty"], rows)


def blk_cox() -> str:
    rows = []
    for label, vals in COX.items():
        tox = [EPS_R * EPS0 / (v * 1e-3) for v in vals]
        n = 2 if label.startswith("thick") else 1
        v1 = [V_OFF + t * E0 for t in tox]  # median field at TREF is E0 by definition
        rows.append([label, "/".join(g(v) for v in vals), "/".join(g(t * 1e9) for t in tox), "/".join(g(v) for v in v1)])
    return table(["Oxide", "Cox min/typ/max (fF/um^2)", "tox = eps_r*eps0/Cox (nm)", "median V_bd(1 us) = V_off + E0*tox, E0 held fixed (V)"], rows)


def blk_vbd() -> str:
    rows = []
    for t, lab in PULSES:
        r = [lab]
        for n in CANDS:
            m = model(n)
            r.append(f"{g(m.vbd(t, 0.001))} / **{g(m.vbd(t))}** / {g(m.vbd(t, 0.999))}")
        rows.append(r)
    return table(["Pulse width"] + [f"{c['name']}: 0.1% / median / 99.9% (V)" for c in CANDS.values()], rows)


def blk_spread() -> str:
    rows = []
    for n, c in CANDS.items():
        for lab, b in (("intrinsic beta_i", "perc"), ("extrinsic bound beta_x", "ext")):
            m = model(n, b)
            s_lnt = math.pi / (math.sqrt(6) * m.beta)
            rows.append([c["name"], lab, g(m.beta), g(m.sigma_v()), g(m.tox / (m.beta * m.gamma) * math.log(10)),
                         g(s_lnt), g(m.vbd(1e-6, 0.001) - m.vbd(1e-6, 0.001, 100e-12))])
    return table(["Candidate", "Shape", "beta", "V_bd(99.9%) - V_bd(0.1%), 1 um^2 (V)", "V per decade of area (V)",
                  "sd of ln t_bd", "0.1% V_bd lost going 1 -> 100 um^2 (V)"], rows)


def s1_condition(n: int) -> dict:
    c = CANDS[n]
    m = model(n)
    typ, floor = c["s1"]
    out = {}
    for key, v, q in (("typ", typ, 0.5), ("floor", floor, Q_FLOOR)):
        e = (v - m.voff) / m.tox
        t = TREF * math.exp(-m.gamma * (e - m.e0)) * m.quantile_factor(q, A0)
        out[key] = dict(v=v, e=e, t=t, ramp=m.tox / (m.gamma * t))
    return out


def blk_s1() -> str:
    rows = []
    for n, c in CANDS.items():
        m = model(n)
        k = s1_condition(n)
        typ, fl = k["typ"], k["floor"]

        def ok(r):
            return "inside" if RAMP_WINDOW[0] <= r <= RAMP_WINDOW[1] else "OUTSIDE"
        both = abs(math.log10(typ["t"] / fl["t"])) <= 1
        rows.append([c["name"], g(typ["v"]), g(typ["e"] / MVCM), g(typ["t"]), g(typ["ramp"]) + f" ({ok(typ['ramp'])})",
                     g(fl["v"]), g(fl["t"]), g(fl["ramp"]) + f" ({ok(fl['ramp'])})",
                     g(m.vbd(typ["t"], Q_FLOOR)), "yes" if both else "NO"])
    return table(["Candidate", "S1 typ (V)", "typ field (MV/cm)", "t_eff matching typ as median (s)", "equivalent ramp (V/s)",
                  "S1 floor (V)", "t_eff matching floor as 0.1% (s)", "equivalent ramp (V/s)",
                  "model 0.1% V_bd at the typ condition (V)", "typ and floor within 1 decade of t_eff?"], rows)


def blk_s1_at() -> str:
    rows = []
    for ramp in (1e-2, 1.0, 1e2):
        r = [g(ramp)]
        for n in CANDS:
            m = model(n)
            typ, fl = CANDS[n]["s1"]
            r.append(f"{g(m.vbd_ramp(ramp, Q_FLOOR))} / {g(m.vbd_ramp(ramp))}  (S1 {g(fl)} / {g(typ)})")
        rows.append(r)
    return table(["Ramp rate (V/s)"] + [f"{c['name']}: model 0.1% / median (S1 floor / typ) (V)" for c in CANDS.values()], rows)


def variant_b(n: int) -> Model:
    """E0 re-anchored so the model median at ramp R_S1 on an A0 device equals S1 typ."""
    c = CANDS[n]
    m = model(n)
    e_typ = (c["s1"][0] - m.voff) / m.tox
    k = RAMP_S1 / m.tox
    e0b = e_typ - math.log(m.gamma * k * TREF) / m.gamma
    return replace(m, e0=e0b)


def blk_varb() -> str:
    rows = []
    for n, c in CANDS.items():
        mb = variant_b(n)
        floor_v = mb.vbd_ramp(RAMP_S1, Q_FLOOR)
        life = mb.lifetime(c["s3"], S3_Q, S3_AREA)
        rows.append([c["name"], g(mb.e0 / MVCM), g(mb.vbd(1e-6)), g(mb.vbd(1e-6, 0.001)), g(mb.vbd(TEN_YEARS)),
                     f"{g(floor_v)} vs S1 floor {g(c['s1'][1])}", f"{g(life)} s ({'meets' if life >= S3_LIFE else 'FAILS'} 10 yr)"])
    return table(["Candidate", "E0 re-anchored (MV/cm)", "median V_bd(1 us) (V)", "0.1% V_bd(1 us) (V)", "median V_bd(10 yr) (V)",
                  "model 0.1% at R_S1 vs S1 floor", f"S3 limit lifetime at {g(S3_Q)} fraction, {g(S3_AREA*1e12)} um^2"], rows)


def blk_s3() -> str:
    rows = []
    for gd in (2.0, 2.5, 3.0, 3.5, 4.0):
        r = [g(gd)]
        for n, c in CANDS.items():
            m = model(n, gamma=gd * math.log(10) / MVCM)
            life = m.lifetime(c["s3"], S3_Q, S3_AREA)
            r.append(f"{g(life)} s" + (" ok" if life >= S3_LIFE else " FAIL"))
        rows.append(r)
    # smallest gamma that meets the criterion, per candidate (bisection on the monotone lifetime)
    mins = []
    for n, c in CANDS.items():
        lo, hi = 0.1, 20.0
        for _ in range(60):
            mid = (lo + hi) / 2
            m = model(n, gamma=mid * math.log(10) / MVCM)
            lo, hi = (mid, hi) if m.lifetime(c["s3"], S3_Q, S3_AREA) < S3_LIFE else (lo, mid)
        mins.append(hi)
    rows.append(["smallest meeting 10 yr"] + [g(x) + " decades/(MV/cm)" for x in mins])
    return table(["gamma (decades/(MV/cm))"] + [f"{c['name']}, S3 limit {g(c['s3'])} V" for c in CANDS.values()], rows)


def blk_regime() -> str:
    rows = []
    for t, lab in ((1e-6, "1 us"), (1e-3, "1 ms"), (1.0, "1 s"), (TEN_YEARS, "10 yr")):
        r = [lab]
        for n in CANDS:
            ve, v1 = model(n).vbd(t), model(n, law="1/E").vbd(t)
            r.append(f"{g(ve)} / {g(v1)} (+{g(max(v1 - ve, 0.0) if v1 - ve > 1e-9 else 0.0)})")
        rows.append(r)
    return table(["Pulse width"] + [f"{c['name']}: E-model / 1/E-model (V)" for c in CANDS.values()], rows)


def blk_sens() -> str:
    rows = []
    cases = [("baseline", {}), ("E0 - 2 MV/cm", dict(e0=E0 - 2 * MVCM)), ("E0 + 2 MV/cm", dict(e0=E0 + 2 * MVCM)),
             ("gamma 2 dec/(MV/cm)", dict(gamma=2 * math.log(10) / MVCM)), ("gamma 4 dec/(MV/cm)", dict(gamma=4 * math.log(10) / MVCM)),
             ("V_off -1 V", dict(voff=-1.0)), ("V_off +1 V", dict(voff=1.0))]
    for lab, kw in cases:
        r = [lab]
        for n in CANDS:
            m = model(n, **kw)
            r.append(f"{g(m.vbd(1e-6))} / {g(m.vbd(1e-3))} / {g(m.vbd(TEN_YEARS))}")
        rows.append(r)
    for lab, a in (("beta coefficient 0.2 /nm", 0.2), ("beta coefficient 0.6 /nm", 0.6)):
        r = [lab]
        for n in CANDS:
            m = replace(model(n), beta=a * CANDS[n]["tox"] * 1e9)
            r.append(f"{g(m.vbd(1e-6, 0.001))} / {g(m.vbd(1e-3, 0.001))} / {g(m.vbd(TEN_YEARS, 0.001))} (0.1% quantile)")
        rows.append(r)
    return table(["Case"] + [f"{c['name']}: V_bd at 1 us / 1 ms / 10 yr, median (V)" for c in CANDS.values()], rows)


def blk_pred() -> str:
    rows = []
    for n, c in CANDS.items():
        m = model(n)
        mx = model(n, "ext")
        d_t = (m.vbd(1e-6) - m.vbd(1e-5))
        d_a = m.vbd(1e-6, 0.5, A0) - m.vbd(1e-6, 0.5, 10 * A0)
        rows.append([c["name"], g(m.vbd(1e-6)), g(d_t), g(d_a), g(m.beta), g(mx.beta), g(m.sigma_v()), g(mx.sigma_v()),
                     g(m.sigma_v(0.1, 0.9)), g(mx.sigma_v(0.1, 0.9)), g(model(n, e0=E0 - 2 * MVCM).vbd(1e-6) - 1.0), g(variant_b(n).vbd(1e-6) + 1.0)])
    return table(["Candidate", "P1: median V_bd(1 us), 1 um^2 (V)", "P2: V lost per decade of pulse width (V)",
                  "P3: median V_bd lost per decade of area (V)", "P4: beta_i", "beta_x", "P5: 0.1..99.9% V_bd width, beta_i (V)", "same, beta_x (V)",
                  "10..90% width, beta_i (V)", "10..90% width, beta_x (V)", "P1 band lower edge: variant A, E0 -2 MV/cm, V_off -1 V (V)", "P1 band upper edge: variant B, V_off +1 V (V)"], rows)


BLOCKS = {"params": blk_params, "cox": blk_cox, "vbd": blk_vbd, "spread": blk_spread, "s1": blk_s1,
          "s1_at": blk_s1_at, "s3": blk_s3, "varb": blk_varb, "regime": blk_regime, "sens": blk_sens, "pred": blk_pred}


def render() -> dict[str, str]:
    return {k: f() for k, f in BLOCKS.items()}


def check(note: Path = NOTE) -> list[str]:
    return gen_blocks.check(render(), note)


def main(argv: list[str]) -> int:
    return gen_blocks.main(render(), NOTE, argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
