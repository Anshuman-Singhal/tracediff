"""Tests for run diffing."""
import unittest

from tracediff.differ import diff_runs


def fake_run(agent, checks_by_task):
    tasks = {}
    for task_id, (passed_names, failed_names, tools) in checks_by_task.items():
        checks = [{"name": n, "passed": True, "detail": "ok"} for n in passed_names]
        checks += [{"name": n, "passed": False, "detail": "bad"} for n in failed_names]
        tasks[task_id] = {
            "title": task_id,
            "checks": checks,
            "score": len(passed_names) / (len(passed_names) + len(failed_names)),
            "tools_called": tools,
            "tokens_in": 10,
            "tokens_out": 10,
            "latency_ms": 100.0,
        }
    return {"agent": agent, "suite": "s", "tasks": tasks}


class TestDiffer(unittest.TestCase):
    def test_regression_detected_on_newly_failed_check(self):
        base = fake_run("v1", {"t1": (["a", "b"], [], ["search_kb"])})
        cand = fake_run("v2", {"t1": (["a"], ["b"], ["lookup_order"])})
        report = diff_runs(base, cand)
        self.assertTrue(report.has_regressions)
        (task,) = report.tasks
        self.assertEqual(task.status, "regression")
        self.assertEqual(task.newly_failed, ["b"])
        self.assertEqual(task.added_tools, ["lookup_order"])
        self.assertEqual(task.removed_tools, ["search_kb"])

    def test_improvement_detected_on_newly_passed_check(self):
        base = fake_run("v1", {"t1": (["a"], ["b"], ["search_kb"])})
        cand = fake_run("v2", {"t1": (["a", "b"], [], ["search_kb"])})
        report = diff_runs(base, cand)
        self.assertFalse(report.has_regressions)
        self.assertEqual(report.tasks[0].status, "improvement")
        self.assertEqual(report.tasks[0].newly_passed, ["b"])

    def test_unchanged_when_nothing_differs(self):
        run = fake_run("v1", {"t1": (["a"], [], ["search_kb"])})
        report = diff_runs(run, fake_run("v2", {"t1": (["a"], [], ["search_kb"])}))
        self.assertFalse(report.has_regressions)
        self.assertEqual(report.tasks[0].status, "unchanged")

    def test_new_and_missing_tasks(self):
        base = fake_run("v1", {"t1": (["a"], [], [])})
        cand = fake_run("v2", {"t2": (["a"], [], [])})
        report = diff_runs(base, cand)
        statuses = {t.task_id: t.status for t in report.tasks}
        self.assertEqual(statuses, {"t1": "missing", "t2": "new"})
        self.assertFalse(report.has_regressions)

    def test_mixed_regression_and_improvement_is_regression(self):
        base = fake_run("v1", {"t1": (["a"], ["b"], [])})
        cand = fake_run("v2", {"t1": (["b"], ["a"], [])})
        report = diff_runs(base, cand)
        self.assertEqual(report.tasks[0].status, "regression")
        self.assertTrue(report.has_regressions)


if __name__ == "__main__":
    unittest.main()
