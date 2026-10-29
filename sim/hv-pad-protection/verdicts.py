"""Pass/fail rules for the program-voltage pad-path benches (issue #210).

Pure functions of one corner's measurements, so the rules are unit-tested
without a simulator (tests/test_hv_pad_protection.py) and re-applied to saved
reports by ``run_experiment.py --check``. Every limit below is cited to the
file it comes from; none is chosen to make a result pass.

A violation is a short code. ``rating`` codes mean a device in the path was
stressed past a limit; ``function`` codes mean the path did not do its job
(the cell did not see the intended voltage, or its state is wrong).
"""

from __future__ import annotations

# --- limits, with provenance -------------------------------------------------

# Highest supply corner of the standard I/O cell library
# (libs.ref/gf180mcu_fd_io/lib/gf180mcu_fd_io__*_5v50.lib). The library states
# timing/power corners, not an absolute-maximum; this is the top of the
# characterised range, used as the pad cell's limit.
STD_PAD_MAX_V = 5.5

# ppolyf_u_2k_6p0: "(6.0V area)" is a gate-oxide-area designation, not a
# voltage rating (spec/leg-design-record.md section 3, rating question OPEN).
# Exceeding it is reported as a rating-unverified flag, not a proven failure.
BALLAST_AREA_V = 6.0

# Junction breakdown knees `bv` of the PDK diode models
# (libs.tech/ngspice/sm141064.ngspice, `.model` lines).
JUNCTION_BV = {"nd2ps": 11.0, "nw2ps": 14.0, "dw2ps": 30.48, "pd2nw": 10.5}

# Rated oxide voltage of the cell capacitor per candidate
# (spec/cell-candidates.md), the no-disturb limit for an unprogrammed neighbour.
CAP_RATED_V = {1: 3.3, 2: 6.0, 3: 3.3}

TRIP_I = 1e-6          # A; filament current above this means the cell programmed
INJECT_I = 1e-6        # A; current into a shared rail above this is injection
JUNCTION_I = 1e-6      # A; late-hold junction current above this means it conducts
INTENDED_FRAC = 0.98   # cell must reach this fraction of min(level, V_bd)


def _v(vals: dict, name: str) -> float | None:
    x = vals.get(name)
    return None if x is None else float(x)


def check_corner(kind: str, level: float, vbd: float, cand: int, vals: dict, ballast: bool = False) -> list[str]:
    """Violation codes for one corner.

    kind: ``astd`` (standard pad cell), ``c0`` (bare pad, direct), ``c1``
    (bare pad + on-die ballast), ``cx`` (bare pad + off-die series resistor),
    ``jn`` (cx plus a plate-node junction), ``nb`` (cx with an unprogrammed
    neighbour).  ``ballast``: an on-die ballast is in the path.  level: signed
    pad level [V].
    """
    out: list[str] = []
    lv = abs(level)
    vox = _v(vals, "vox_max")
    ifil = _v(vals, "ifil_max")
    if vox is None or ifil is None:
        return ["no-measurement"]
    tripped = ifil > TRIP_I
    want_trip = lv >= vbd
    if vox < INTENDED_FRAC * min(lv, vbd):
        out.append("function:cell-voltage-short")
    if tripped != want_trip:
        out.append("function:program-state")
    if kind == "astd":
        if (_v(vals, "vpad_max") or 0.0) > STD_PAD_MAX_V:
            out.append("rating:pad-over-5.5V")
        if (_v(vals, "idvdd_max") or 0.0) > INJECT_I:
            out.append("rating:rail-injection")
    if (kind == "c1" or ballast) and (_v(vals, "vr_max") or 0.0) > BALLAST_AREA_V:
        out.append("rating:ballast-over-6V-area(open)")
    # Steady-state (late-hold) current: the peak includes C dV/dt of the junction
    # capacitance on the 100 ns edge, which is not conduction.
    ij = _v(vals, "ijn_hold")
    if kind == "jn" and ij is not None and ij > JUNCTION_I:
        out.append("rating:junction-conducts")
    if kind == "nb":
        if (_v(vals, "voxj_max") or 0.0) > CAP_RATED_V[cand]:
            out.append("rating:neighbour-over-cap-rating")
        if (_v(vals, "ifilj_max") or 0.0) > TRIP_I:
            out.append("rating:neighbour-programmed")
    return out


def summarise(rows: list[tuple[float, str, list[str]]]) -> dict:
    """rows: (level, corner-id, codes) -> {level: {code: n corners}} + totals."""
    per: dict[float, dict[str, int]] = {}
    n: dict[float, int] = {}
    for lv, _cid, codes in rows:
        n[lv] = n.get(lv, 0) + 1
        d = per.setdefault(lv, {})
        for c in codes:
            d[c] = d.get(c, 0) + 1
    return {"per_level": per, "corners": n}
