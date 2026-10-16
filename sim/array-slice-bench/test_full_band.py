"""Unit tests for the full-band leakage mode (no ngspice, no network).

    python3 -m unittest discover -s sim/array-slice-bench -p 'test_full_band.py'
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fullband as F  # noqa: E402
import gen_array as G  # noqa: E402
import make_bench as B  # noqa: E402

COLS = {"I": 11, "II": 11, "III": 10}


def pg_terms(band, v=1e-10):
    return {c: v for lab, lo, hi, _ in G.BANDS if lab == band for c in range(lo, hi + 1)}


class Cardinality(unittest.TestCase):
    def test_band_widths_11_11_10(self):
        got = {B.leak_band_label(n): len(B.leak_window(n)[1]) for n in G.BAND_SLICES}
        self.assertEqual(got, COLS)

    def test_band_slices_tile_the_array_without_overlap(self):
        cols = [c for n in G.BAND_SLICES for c in B.leak_window(n)[1]]
        self.assertEqual(cols, list(range(G.N)))

    def test_netlist_has_one_pass_gate_per_column(self):
        for n in G.BAND_SLICES:
            text = (B.TB_DIR.parents[2] / "design" / "netlists" / f"{n}.spice").read_text()
            self.assertEqual(text.count("\nXPC_"), len(B.leak_window(n)[1]), n)


class Requests(unittest.TestCase):
    def test_every_key_has_one_value_per_point_and_matches_points(self):
        for n in G.BAND_SLICES:
            for v in B.LEAK_VARIANTS:
                r = B.leak_request(n, "typical", v)
                lens = {len(x) for x in r["corners"]["supply_v"].values()}
                self.assertEqual(lens, {len(B.leak_points(n, v))}, (n, v))

    def test_levels_stay_per_region(self):
        for n in G.BAND_SLICES:
            lab = B.leak_band_label(n)
            vb = set(B.leak_request(n, "ff", "pgoff")["corners"]["supply_v"][f"vbl_{lab.lower()}"])
            want = {round(lv * s, 6) for _n, lv in B.READ_LEVELS[lab] for s in B.LEVEL_SCALES}
            self.assertEqual(vb, want, n)

    def test_pgoff_measures_one_clamp_per_column_and_sel_has_one_selected_cell(self):
        for n in G.BAND_SLICES:
            names = [m["name"] for m in B.leak_measurements(n, "pgoff")]
            self.assertEqual(sorted(x for x in names if x.startswith("icl_")),
                             sorted(f"icl_{c}" for c in B.leak_window(n)[1]))
            sv = B.leak_request(n, "typical", "sel")["corners"]["supply_v"]
            npts = len(B.leak_points(n, "sel"))
            for i in range(npts):
                on_r = sum(1 for k, v in sv.items() if k.startswith("vrsel") and v[i] > 0)
                on_c = sum(1 for k, v in sv.items() if k.startswith("vcsel") and v[i] > 0)
                self.assertEqual((on_r, on_c), (1, 1))

    def test_sel_selections_cover_every_sub_combination(self):
        for n in G.BAND_SLICES:
            self.assertEqual(len(B.leak_selections(n)), 4, n)


class SignAndBudget(unittest.TestCase):
    def test_source_current_sign_is_normalised(self):
        # a supplying source reads negative; leakage out of the node is positive
        self.assertEqual(F.out_of_node(-2.5e-9), 2.5e-9)
        self.assertEqual(F.out_of_node(0.0), 0.0)

    def test_cell_term_counted_exactly_once(self):
        pg = pg_terms("I", 1e-10)
        b = F.budget("I", pg, 1.2e-9, 8e-12, 1e-6, 3.98)
        self.assertAlmostEqual(b["total"], 1.2e-9 + 8e-12, 20)
        self.assertAlmostEqual(b["pg_channel"] + b["pg_other"], b["pg_node"], 20)
        self.assertAlmostEqual(b["headroom"], 1e-6 - b["total"], 20)
        self.assertEqual(b["n_cols"], 11)

    def test_missing_or_extra_columns_rejected(self):
        pg = pg_terms("III")
        short = dict(pg); short.pop(22)
        with self.assertRaises(F.AnalysisError):
            F.budget("III", short, 1e-9, 0.0, 1e-6, 3.0)
        extra = dict(pg); extra[21] = 1e-10     # a Region II column leaking into a Region III sum
        with self.assertRaises(F.AnalysisError):
            F.budget("III", extra, 1e-9, 0.0, 1e-6, 3.0)

    def test_node_below_channel_sum_rejected(self):
        with self.assertRaises(F.AnalysisError):
            F.budget("II", pg_terms("II", 1e-9), 1e-10, 0.0, 1e-6, 1.6)

    def test_missing_value_rejected(self):
        pg = pg_terms("I"); pg[3] = None
        with self.assertRaises(F.AnalysisError):
            F.budget("I", pg, 1e-9, 0.0, 1e-6, 1.0)

    def test_floor_flag(self):
        b = F.budget("I", pg_terms("I", 1e-14), 1.1e-13, 0.0, 1e-6, 1.0)
        self.assertTrue(b["floor_dominated"])
        b = F.budget("I", pg_terms("I", 1e-9), 1.1e-8, 0.0, 1e-6, 1.0)
        self.assertFalse(b["floor_dominated"])


def fake_report(name, variant, proc, fn):
    """Build a klt-shaped report from the generator's own points."""
    lab = B.leak_band_label(name)
    rows, cols = B.leak_window(name)
    corners = []
    for t in B.TEMPS:
        for i, p in enumerate(B.leak_points(name, variant)):
            sv = {"vddl": B.VDDL * p["scale"], f"vbl_{lab.lower()}": p["vbl"]}
            if variant == "sel":
                for r in rows:
                    sv[f"vrsel{r}"] = 3.3 if p["sel"][0] == r else 0.0
                for c in cols:
                    sv[f"vcsel{c}"] = 3.3 if p["sel"][1] == c else 0.0
            corners.append({"corner_id": f"{proc}/{t}/{i}", "process": proc, "temperature_c": t, "status": "pass",
                            "supply_v": sv, "measurements": [{"name": m["name"], "value": fn(m["name"], p)}
                                                             for m in B.leak_measurements(name, variant)]})
    return {"corners": corners}


class Analysis(unittest.TestCase):
    def test_pgoff_end_to_end_per_region(self):
        for n in G.BAND_SLICES:
            lab = B.leak_band_label(n)
            ncols = COLS[lab]

            def val(name, p):
                if name == "ibus":
                    return -(ncols * 1e-10 + 5e-11)       # supplying source reads negative
                return 1e-10
            reps = {proc: fake_report(n, "pgoff", proc, val) for proc in B.PROCESS}
            rows = F.analyze_pgoff(n, reps)
            self.assertTrue(all(r["band"] == lab and r["n_cols"] == ncols for r in rows))
            self.assertAlmostEqual(rows[0]["pg_channel"], ncols * 1e-10, 20)
            self.assertAlmostEqual(rows[0]["pg_other"], 5e-11, 20)
            self.assertEqual(len(rows), len(B.PROCESS) * len(B.TEMPS) * len(B.leak_points(n, "pgoff")) * len(F.I_REF[lab]))

    def test_duplicate_operating_point_rejected(self):
        n = "band_i"
        rep = fake_report(n, "pgoff", "typical", lambda name, p: -1e-9 if name == "ibus" else 1e-10)
        rep["corners"] += rep["corners"][:1]
        with self.assertRaises(F.AnalysisError):
            F.analyze_pgoff(n, {"typical": rep})

    def test_failed_unit_rejected(self):
        n = "band_ii"
        rep = fake_report(n, "pgoff", "ss", lambda name, p: -1e-9 if name == "ibus" else 1e-10)
        rep["corners"][0]["status"] = "error"
        with self.assertRaises(F.AnalysisError):
            F.analyze_pgoff(n, {"ss": rep})

    def test_incomplete_set_of_processes_rejected(self):
        n = "band_iii"
        rep = fake_report(n, "pgoff", "ff", lambda name, p: -1e-9 if name == "ibus" else 1e-10)
        with self.assertRaises(F.AnalysisError):
            F.analyze_pgoff(n, {"ff": rep})

    def test_rejects_corner_matching_no_generated_point(self):
        n = "band_i"
        rep = fake_report(n, "nat", "typical", lambda name, p: -1e-10 if name == "ibus" else 0.1)
        rep["corners"][0]["supply_v"]["vbl_i"] = 9.99
        with self.assertRaises(F.AnalysisError):
            F.analyze_nat(n, {"typical": rep})

    def test_sel_grading(self):
        n = "band_i"

        def val(name, p):
            if name == "ibus":
                return -p["vbl"] / 1e6
            if name == "iret":
                return p["vbl"] / 1e6
            if name.startswith("ifil_"):
                r, c = map(int, name.split("_")[1:])
                return p["vbl"] / 1e6 if (r, c) == p["sel"] else 0.0
            if name.startswith("nv_bl_"):
                return p["vbl"] if int(name.split("_")[2]) == p["sel"][1] else 0.0
            return 0.0
        rep = fake_report(n, "sel", "typical", val)
        res = F.analyze_sel(n, {"typical": rep})
        self.assertTrue(all(r["ok"] for r in res))
        self.assertEqual({(r["cap"], r["acc"]) for r in res}, {("min", "min"), ("min", "2x"), ("2x", "min"), ("2x", "2x")})


if __name__ == "__main__":
    unittest.main()
