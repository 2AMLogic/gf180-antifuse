#!/usr/bin/env python3
"""Expected sampling-interval width of the Weibull slope and voltage
acceleration for the PROPOSED constant-voltage time-to-breakdown plan
(spec/tddb-weibull-plan-proposed.md).

No measured data are used. Every input is a design choice or an `assumed`
model value (docs/breakdown-oxide-model.md); the output says how precisely a
given cell budget could pin the slope and acceleration IF the oxide behaved as
assumed, not what the slope is.

Model (log-time location-scale form of the Weibull / E-model):
    ln t_ij = mu_s - g * k_i + (1/beta) * w,   w ~ smallest-extreme-value
    (CDF 1 - exp(-exp(w))), k_i = voltage level index (+1 high ... -1 low),
    one location mu_s per stratum s (sub-combination).
Observation window: [-W/2, +W/2] decades about the centre of the design;
cells broken before the first pulse are left-censored at the lower edge,
cells surviving the last pulse are right-censored at the upper edge.
Pulse-count quantisation is ignored (negligible above ~10 pulses).

Two quantities per scenario, both by Monte Carlo (finite-sample):
  * the central 95 % range of beta_hat/beta and g_hat/g over REPS simulated
    experiments (a sampling interval, not an asymptotic formula);
  * for the base scenario only, the ASYMPTOTIC (expected-information)
    95 % half-width, labelled as such, as a cross-check.

Usage:  python3 scripts/tddb_ci_width.py [--reps N] [--seed S]
Stdlib + numpy + scipy; single process.
"""
from __future__ import annotations

import argparse
import math

import numpy as np
from scipy.optimize import minimize

LN10 = math.log(10.0)


def simulate(rng, per_level, strata, beta, r, off, W, levels=(1, 0, -1)):
    """Return arrays y (clipped to window), cens (0 exact, -1 left, +1 right),
    level index k, stratum s. per_level cells at each level, split evenly over
    `strata` strata."""
    k = np.repeat(levels, per_level)
    s = np.tile(np.arange(strata), len(k) // strata + 1)[: len(k)]
    # strata assigned so each level is balanced over strata
    s = np.concatenate([np.arange(per_level) % strata for _ in levels])
    w = np.log(-np.log(rng.random(len(k))))
    mu = off * LN10 - r * k * LN10
    y = mu + w / beta
    lo, hi = -W / 2 * LN10, W / 2 * LN10
    cens = np.where(y < lo, -1, np.where(y > hi, 1, 0))
    y = np.clip(y, lo, hi)
    return y, cens, k, s


def nll(theta, y, cens, k, s, strata):
    a = theta[:strata]
    lns, g = theta[strata], theta[strata + 1]
    sig = math.exp(lns)
    w = (y - (a[s] - g * k)) / sig
    ew = np.exp(np.clip(w, -50, 50))
    ll = np.where(
        cens == 0,
        -lns + w - ew,
        np.where(cens == 1, -ew, np.log(-np.expm1(-ew) + 1e-300)),
    )
    return -ll.sum()


def fit(y, cens, k, s, strata):
    x0 = np.concatenate([np.zeros(strata), [math.log(0.7), LN10]])
    res = minimize(nll, x0, args=(y, cens, k, s, strata), method="BFGS")
    if not res.success and res.fun != res.fun:
        return None
    return res.x


def scenario(rng, reps, per_level, strata, beta, r, off, W):
    b_ratio, g_ratio, dmu, cens_frac, bad = [], [], [], [], 0
    for _ in range(reps):
        y, c, k, s = simulate(rng, per_level, strata, beta, r, off, W)
        th = fit(y, c, k, s, strata)
        if th is None:
            bad += 1
            continue
        b_ratio.append(1.0 / math.exp(th[strata]) / beta)
        g_ratio.append(th[strata + 1] / (r * LN10))
        if strata >= 3:
            dmu.append(th[2] - th[0])
        cens_frac.append(np.mean(c != 0))
    q = lambda v: np.percentile(v, [2.5, 50, 97.5])
    out = dict(
        beta=q(b_ratio), g=q(g_ratio), cens=float(np.mean(cens_frac)), bad=bad
    )
    if dmu:
        out["dmu_sd"] = float(np.std(dmu))
    return out


def asymptotic(beta, r, off, W, per_level=60, strata=1):
    """Expected-information 95 % half-width (relative) for beta and g, one
    stratum, via a large simulated sample and a finite-difference Hessian.
    ASYMPTOTIC: valid only for large n; shown as a cross-check."""
    rng = np.random.default_rng(7)
    big = 40000
    y, c, k, s = simulate(rng, big, 1, beta, r, off, W)
    th0 = np.array([0.0, math.log(1 / beta), r * LN10])
    f = lambda t: nll(t, y, c, k, s, 1) / len(y)
    h = 1e-3
    H = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            ei, ej = np.eye(3)[i] * h, np.eye(3)[j] * h
            H[i, j] = (f(th0 + ei + ej) - f(th0 + ei - ej)
                       - f(th0 - ei + ej) + f(th0 - ei - ej)) / (4 * h * h)
    cov = np.linalg.inv(H) / (3 * per_level)
    sd_lns, sd_g = math.sqrt(cov[1, 1]), math.sqrt(cov[2, 2])
    return 1.96 * sd_lns, 1.96 * sd_g / (r * LN10)  # beta=1/sigma: rel sd = sd(ln sigma)


def fmt(q):
    return f"{q[0]:.2f}..{q[2]:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--seed", type=int, default=255)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    W = 4.0  # window width in decades (assumed bench limit; open item)

    print(f"# window {W} decades, levels spaced r decades apart (r=1 is the design"
          f" point), reps={a.reps}, seed={a.seed}")
    print("# columns: design | beta | r | offset | cens frac | beta_hat/beta"
          " 2.5..97.5% | g_hat/g 2.5..97.5% | sd(mu_S3-mu_S1) [ln t]")
    designs = [
        ("S: 3 x 28, 1 stratum", 28, 1),
        ("M: 3 x 40, 2 strata", 40, 2),
        ("L: 3 x 60, 1 stratum", 60, 1),
        ("L: 3 x 66, 3 strata", 66, 3),
        ("X: 3 x 200, 1 stratum", 200, 1),
    ]
    for name, n, st in designs:
        o = scenario(rng, a.reps, n, st, 1.5, 1.0, 0.0, W)
        print(f"{name:24s} | 1.5 | 1.0 | 0 | {o['cens']:.2f} | {fmt(o['beta'])}"
              f" | {fmt(o['g'])} | {o.get('dmu_sd', float('nan')):.2f}")
    print("# sensitivity of design L (3 x 66, 3 strata) to wrong assumptions")
    for beta, r, off in [(1.5, 1, 0), (3.2, 1, 0), (6.08, 1, 0),
                         (1.5, 0.5, 0), (1.5, 2, 0),
                         (1.5, 1, 1), (1.5, 1, 2), (1.5, 1, -2)]:
        o = scenario(rng, a.reps, 66, 3, beta, r, off, W)
        print(f"L3 sens | {beta} | {r} | {off:+d} | {o['cens']:.2f} | "
              f"{fmt(o['beta'])} | {fmt(o['g'])} | {o.get('dmu_sd', float('nan')):.2f}")
    print("# asymptotic (expected information) 95% relative half-width,"
          " 1 stratum, beta=1.5, r=1, no offset")
    for n in (28, 60, 200):
        hb, hg = asymptotic(1.5, 1.0, 0.0, W, per_level=n)
        print(f"n/level={n}: beta +-{hb:.2f}, g +-{hg:.2f} (asymptotic)")
    print("# zero-failure upper bound, exact two-sided 95% (k=0 of n)")
    for n in (14, 15, 16, 22, 30, 60, 100):
        print(f"n={n}: <= {1 - 0.025 ** (1.0 / n):.3f}")


if __name__ == "__main__":
    main()
