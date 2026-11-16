"""sim/program-read-legs requests carry klt-side batch capacity patience.

Issue #300. Every ``klt sim`` request this driver emits goes through
``make_request`` (the Monte Carlo builder delegates to it), so the single
``"batch": dict(BATCH_OPTS)`` insertion covers the plain corner requests and
the four-concurrent Monte Carlo burst alike. The key is complementary to the
harness-side ``K.BACKOFF`` retry: ``capacity_wait_s`` makes klt wait *before*
refusing a launch; ``K.BACKOFF`` resubmits the same request *after* a refusal.
No simulator is driven here -- these are pure request-shape assertions.

Stdlib unittest (``tests/`` is discovered by ``npm run check:ci``).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))

from harness.modload import load_module  # noqa: E402

DRIVER = SIM / "program-read-legs" / "run_experiment.py"

NETLIST = "margin1.sp"
MEAS = [{"name": "i_read", "expr": "i(Vbl)"}]
PREAMBLE = "models/preamble.lib"
# Top-level keys make_request emitted before the batch key (issue #300 body).
PLAIN_KEYS = {"netlist", "models", "corners", "analysis", "measurements", "options"}
# Fleet job-ceiling sharding key added after the batch key (PR #326): a
# "remote": {"hosts": N} block keeps a request's conservative fully-serial
# bound under the fleet's whole-job ceiling. Its value is asserted in
# sim/program-read-legs/tests/test_requests.py, not here.
SHARD_KEYS = {"remote"}


class RequestBatchOptsTest(unittest.TestCase):
    """The batch block: present, minimal, and inherited by the MC path."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(DRIVER, "prl_run_request_test")

    def _plain(self) -> dict:
        return self.mod.make_request(NETLIST, MEAS, False, PREAMBLE)

    def test_plain_request_carries_capacity_wait(self):
        req = self._plain()
        self.assertEqual(req.get("batch"), {"capacity_wait_s": 1800})
        # The fleet rule's floor is 600 s; the value matches the sibling driver.
        self.assertGreaterEqual(req["batch"]["capacity_wait_s"], 600)

    def test_batch_key_is_purely_additive(self):
        req = self._plain()
        self.assertEqual(set(req), PLAIN_KEYS | SHARD_KEYS | {"batch"})

    def test_runner_version_check_is_not_copied_across(self):
        # runner_version_check solves cell-breakdown-model's runner image skew,
        # which this driver does not have; copying it risks downgrading a
        # version error (issue #300 acceptance criteria).
        self.assertNotIn("runner_version_check", self._plain()["batch"])

    def test_mc_request_inherits_the_batch_block(self):
        # make_mc_request builds on make_request by delegation; test that
        # explicitly so a future refactor that stops delegating fails loudly.
        req = self.mod.make_mc_request(NETLIST, MEAS, False, PREAMBLE, self.mod.MC_POINTS[0])
        self.assertEqual(req.get("batch"), {"capacity_wait_s": 1800})
        self.assertEqual(set(req), PLAIN_KEYS | SHARD_KEYS | {"monte_carlo", "batch"})

    def test_each_request_gets_its_own_batch_dict(self):
        # The "batch": dict(BATCH_OPTS) spelling must stay a per-request copy:
        # a shared mutable block would let one consumer corrupt every later
        # request's record.
        a, b = self._plain(), self._plain()
        self.assertIsNot(a["batch"], b["batch"])
        a["batch"]["capacity_wait_s"] = 0
        self.assertEqual(b["batch"]["capacity_wait_s"], 1800)


if __name__ == "__main__":
    unittest.main()
