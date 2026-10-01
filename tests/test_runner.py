"""End-to-end test: the v1 demo agent passes the whole suite, v2 regresses."""
import tempfile
import unittest

from tracediff.differ import diff_runs
from tracediff.policies import POLICIES, PolicyAgent
from tracediff.runner import load_run, run_suite


class TestDemoSuite(unittest.TestCase):
    def test_v1_passes_everything_and_v2_regresses(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = run_suite("support", PolicyAgent(POLICIES["v1"]), f"{tmp}/base")
            cand = run_suite("support", PolicyAgent(POLICIES["v2"]), f"{tmp}/cand")

            base_scores = [t["score"] for t in base["tasks"].values()]
            self.assertTrue(all(s == 1.0 for s in base_scores),
                            f"v1 should pass every check, got {base_scores}")

            report = diff_runs(load_run(f"{tmp}/base"), load_run(f"{tmp}/cand"))
            self.assertTrue(report.has_regressions)
            self.assertGreaterEqual(len(report.regressions), 3)
            regressed_ids = {t.task_id for t in report.regressions}
            self.assertIn("t2", regressed_ids)  # refunds a non-refundable e-book
            self.assertIn("t3", regressed_ids)  # refunds a $899 order without approval

    def test_runs_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = run_suite("support", PolicyAgent(POLICIES["v1"]), f"{tmp}/a")
            second = run_suite("support", PolicyAgent(POLICIES["v1"]), f"{tmp}/b")
            for task_id in first["tasks"]:
                self.assertEqual(
                    first["tasks"][task_id]["final_answer"],
                    second["tasks"][task_id]["final_answer"],
                )
                self.assertEqual(
                    first["tasks"][task_id]["tools_called"],
                    second["tasks"][task_id]["tools_called"],
                )


if __name__ == "__main__":
    unittest.main()
