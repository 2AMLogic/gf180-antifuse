"""Rules and deck generation of sim/hv-pad-protection (issue #210). No simulator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))
sys.path.insert(0, str(SIM / "hv-pad-protection"))

import verdicts as V  # noqa: E402


def _runner():
    spec = importlib.util.spec_from_file_location("hv_pad_run", SIM / "hv-pad-protection" / "run_experiment.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hv_pad_run"] = mod
    spec.loader.exec_module(mod)
    return mod


GOOD = {"vox_max": 15.1, "ifil_max": 1.2e-3}


def test_programs_at_105_percent_and_passes():
    assert V.check_corner("cx", 15.96, 15.2, 2, GOOD) == []


def test_below_vbd_must_not_program():
    codes = V.check_corner("cx", 14.44, 15.2, 2, {"vox_max": 14.4, "ifil_max": 1.4e-8})
    assert codes == []
    assert "function:program-state" in V.check_corner("cx", 14.44, 15.2, 2, GOOD)


def test_clamped_plate_is_a_function_failure():
    codes = V.check_corner("jn", 15.96, 15.2, 2, {"vox_max": 12.0, "ifil_max": 1e-8, "ijn_max": 5e-4, "ijn_hold": 4e-4})
    assert "function:cell-voltage-short" in codes
    assert "function:program-state" in codes
    assert "rating:junction-conducts" in codes


def test_standard_pad_rail_injection_and_pad_rating():
    vals = {"vox_max": 6.5, "ifil_max": 6e-9, "vpad_max": 6.5, "idvdd_max": 0.1}
    codes = V.check_corner("astd", 15.96, 15.2, 2, vals)
    assert {"rating:pad-over-5.5V", "rating:rail-injection", "function:cell-voltage-short"} <= set(codes)


def test_ballast_area_flag_only_with_ballast():
    vals = {**GOOD, "vr_max": 6.9}
    assert "rating:ballast-over-6V-area(open)" in V.check_corner("c1", 16.72, 15.2, 2, vals)
    assert "rating:ballast-over-6V-area(open)" in V.check_corner("nb", 16.72, 15.2, 2, vals, ballast=True)
    assert V.check_corner("cx", 16.72, 15.2, 2, vals) == []


@pytest.mark.parametrize("cand,limit", [(1, 3.3), (2, 6.0), (3, 3.3)])
def test_neighbour_limit_is_the_candidate_cap_rating(cand, limit):
    ok = {**GOOD, "voxj_max": limit - 0.1, "ifilj_max": 1e-9}
    bad = {**GOOD, "voxj_max": limit + 0.1, "ifilj_max": 1e-9}
    lv = 16.72 if cand == 2 else 8.8
    vbd = 15.2 if cand == 2 else (8.0 if cand == 1 else 7.9)
    assert V.check_corner("nb", lv, vbd, cand, ok) == []
    assert "rating:neighbour-over-cap-rating" in V.check_corner("nb", lv, vbd, cand, bad)


def test_negative_level_uses_magnitude():
    assert V.check_corner("cx", -8.69, 7.9, 3, {"vox_max": 8.6, "ifil_max": 5e-4}) == []


def test_junction_edge_current_is_not_conduction():
    vals = {**GOOD, "ijn_max": 1.7e-6, "ijn_hold": 2e-11}
    assert V.check_corner("jn", 15.96, 15.2, 2, vals) == []


def test_missing_measurement_is_never_a_pass():
    assert V.check_corner("cx", 8.4, 8.0, 1, {"vox_max": None, "ifil_max": 1e-3}) == ["no-measurement"]


def test_summarise_counts_per_level():
    s = V.summarise([(8.4, "a", ["x"]), (8.4, "b", []), (4.0, "c", [])])
    assert s["corners"] == {8.4: 2, 4.0: 1}
    assert s["per_level"][8.4] == {"x": 1}


def test_levels_and_vbd_follow_the_assumed_params():
    r = _runner()
    p = r.read_params()
    assert r.vbd_of(1, p) == pytest.approx(8.0)
    assert r.vbd_of(2, p) == pytest.approx(15.2)
    assert r.vbd_of(3, p) == pytest.approx(7.9)
    cands = {c.n: c for c in r.CHAR.CANDIDATES}
    lv3 = r.levels(cands[3], 7.9)
    assert all(x < 0 for x in lv3) and lv3[-1] == -r.V_PAD_MAX
    assert r.levels(cands[2], 15.2)[-1] == r.V_PAD_MAX


def test_every_bench_deck_builds_and_names_each_measured_node():
    r = _runner()
    pdk = r.P.resolve_pdk()
    for n in (1, 2, 3):
        cand, pdk, defaults, vbd = r.setup(n)
        for name, bd in r.bench_defs(n).items():
            text, meas = r.body(name, bd, cand, pdk, defaults, vbd)
            assert "VAMP AMP 0 DC 0" in text
            for m in meas:
                node = m["spice"].split("v(")[1].split(")")[0]
                assert f"B" in text and f" {node.upper()} 0 V" in text.upper(), (n, name, node)
            assert ("XPD PAD PL 0 hv_pad_ballast" in text) == (bd["path"] == "ballast")
    assert pdk is not None
