"""Offline tests for sim/program-read-legs request building (no simulator, no
klt, no PDK): the units-per-shard invariant that keeps every request's declared
job bound under the fleet's whole-job ceiling. Run:

    python3 -m unittest discover -s sim/program-read-legs/tests
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_experiment as RE  # noqa: E402

MEAS = [{"name": "m", "spice": "measure tran m param='1'"}]


def corner_units(req: dict) -> int:
    """The unit count klt derives from a corners request (same arithmetic the
    runner prints at submit time)."""
    return (len(req["corners"]["process"]) * len(req["corners"]["temperature_c"])
            * len(req["corners"]["supply_v"]["VDD"]))


def mc_units(req: dict) -> int:
    return req["monte_carlo"]["n"]


class Requests(unittest.TestCase):
    def requests(self):
        """Every full-size request shape the driver builds: one 45-unit corner
        request and one 200-unit Monte Carlo request per MC point."""
        yield "corner", RE.make_request("bench.sp", MEAS, False, "preamble.lib")
        for pt in RE.MC_POINTS:
            yield f"mc_{pt[0]}", RE.make_mc_request("bench.sp", MEAS, False, "preamble.lib", pt)

    def test_shard_size_is_derived_from_the_ceiling(self):
        self.assertEqual(RE.MAX_UNITS_PER_SHARD,
                         (RE.JOB_CEILING_S - RE.JOB_OVERHEAD_S) // RE.PER_UNIT_TIMEOUT_S)
        self.assertEqual(RE.MAX_UNITS_PER_SHARD, 11)
        self.assertEqual(RE.JOB_CEILING_S, 3600)
        self.assertLessEqual(RE.MAX_UNITS_PER_SHARD * RE.PER_UNIT_TIMEOUT_S + RE.JOB_OVERHEAD_S,
                             RE.JOB_CEILING_S)

    def test_options_timeout_is_the_per_unit_budget_the_shard_is_derived_from(self):
        for kind, req in self.requests():
            self.assertEqual(req["options"]["timeout_s"], RE.PER_UNIT_TIMEOUT_S, kind)

    def test_units_per_shard_stay_under_the_job_ceiling(self):
        for kind, req in self.requests():
            units = mc_units(req) if "monte_carlo" in req else corner_units(req)
            hosts = req["remote"]["hosts"]
            self.assertGreaterEqual(hosts, 1, (kind, units))
            per_shard = -(-units // hosts)
            self.assertLessEqual(per_shard, RE.MAX_UNITS_PER_SHARD, (kind, units, hosts))
            bound = per_shard * req["options"]["timeout_s"] + RE.JOB_OVERHEAD_S
            self.assertLessEqual(bound, RE.JOB_CEILING_S, (kind, units, hosts))

    def test_full_size_requests_shard_as_klt_recommends(self):
        # klt's committed job_ceiling evidence for these shapes: unit_count 45 ->
        # recommended_hosts 5, unit_count 200 -> recommended_hosts 19.
        _, corner = next(iter(self.requests()))
        self.assertEqual(corner_units(corner), 45)
        self.assertEqual(corner["remote"]["hosts"], 5)
        mc = RE.make_mc_request("bench.sp", MEAS, False, "preamble.lib", RE.MC_POINTS[0])
        self.assertEqual(mc_units(mc), 200)
        self.assertEqual(mc["remote"]["hosts"], 19)

    def test_single_unit_requests_get_one_host(self):
        # probe-style requests: fewer units than one shard must yield hosts 1, never 0
        req = RE.make_request("bench.sp", MEAS, False, "preamble.lib", temps=(27,),
                              processes=("typical",), vdd_points=(RE.B.VDD_NOM,))
        self.assertEqual(corner_units(req), 1)
        self.assertEqual(req["remote"]["hosts"], 1)
        mc = RE.make_mc_request("bench.sp", MEAS, False, "preamble.lib", RE.MC_POINTS[0], n=1)
        self.assertEqual(mc_units(mc), 1)
        self.assertEqual(mc["remote"]["hosts"], 1)


if __name__ == "__main__":
    unittest.main()
