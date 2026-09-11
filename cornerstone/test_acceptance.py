"""
CORNERSTONE Phase 1 — acceptance validator + demo runner tests.

Verifies the validator reports every criterion as passing, the demo runner
completes with a deterministic report, and the individual acceptance paths hold.
Deterministic; reuses existing components only.
"""

from __future__ import annotations

import unittest

from cornerstone.acceptance import validate_phase1
from cornerstone.demo_runner import build_report, run

EXPECTED_CHECK_IDS = {
    "blocked_tool_never_executes",
    "delayed_item_queued",
    "approval_resumes",
    "denial_kills",
    "queue_supports_multiple_pending",
    "non_blocking_behavior",
    "workflow_intervention_count",
    "live_state_evaluated",
    "executor_inaccessible_to_agent",
    "controller_mandatory",
    "deterministic_output",
}


def check(result, check_id):
    return next(c for c in result["checks"] if c["id"] == check_id)


class TestValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.result = validate_phase1()

    def test_validator_passes(self) -> None:
        self.assertTrue(self.result["passed"])

    def test_result_shape(self) -> None:
        self.assertEqual(set(self.result), {"passed", "checks"})
        for c in self.result["checks"]:
            self.assertEqual(set(c), {"id", "description", "passed", "detail"})

    def test_every_acceptance_check_exists(self) -> None:
        ids = {c["id"] for c in self.result["checks"]}
        self.assertEqual(ids, EXPECTED_CHECK_IDS)

    def test_all_checks_pass(self) -> None:
        failing = [c["id"] for c in self.result["checks"] if not c["passed"]]
        self.assertEqual(failing, [])

    def test_validator_deterministic(self) -> None:
        again = validate_phase1()
        self.assertEqual(
            [(c["id"], c["passed"]) for c in self.result["checks"]],
            [(c["id"], c["passed"]) for c in again["checks"]],
        )


class TestIndividualCriteria(unittest.TestCase):
    def setUp(self) -> None:
        self.result = validate_phase1()

    def test_no_blocked_execution(self) -> None:
        self.assertTrue(check(self.result, "blocked_tool_never_executes")["passed"])

    def test_approval_path(self) -> None:
        self.assertTrue(check(self.result, "approval_resumes")["passed"])

    def test_denial_path(self) -> None:
        self.assertTrue(check(self.result, "denial_kills")["passed"])

    def test_intervention_count(self) -> None:
        c = check(self.result, "workflow_intervention_count")
        self.assertTrue(c["passed"])
        # DELAY -> 1 human intervention; BLOCK -> 1 autonomous denial.
        self.assertIn("human_interventions=1", c["detail"])
        self.assertIn("autonomous_denials=1", c["detail"])

    def test_queue_behavior(self) -> None:
        self.assertTrue(check(self.result, "queue_supports_multiple_pending")["passed"])
        self.assertTrue(check(self.result, "non_blocking_behavior")["passed"])

    def test_controller_mandatory(self) -> None:
        self.assertTrue(check(self.result, "controller_mandatory")["passed"])

    def test_live_state_and_agent_isolation(self) -> None:
        self.assertTrue(check(self.result, "live_state_evaluated")["passed"])
        self.assertTrue(check(self.result, "executor_inaccessible_to_agent")["passed"])


class TestDemoRunner(unittest.TestCase):
    def test_demo_runner_completes_and_passes(self) -> None:
        report, passed = build_report()
        self.assertTrue(passed)
        self.assertTrue(report.strip().endswith("PASS"))

    def test_report_contains_key_sections(self) -> None:
        report, _ = build_report()
        for token in (
            "CORNERSTONE PHASE 1 DEMO",
            "Goal:\ntriage_incident",
            "ALLOW",
            "DELAY",
            "BLOCK",
            "NOT EXECUTED",
            "Workflow Summary",
            "Human interventions (DELAY): 1",
            "Autonomous denials (BLOCK): 1",
        ):
            self.assertIn(token, report)

    def test_deterministic_demo_output(self) -> None:
        first, _ = build_report()
        second, _ = build_report()
        self.assertEqual(first, second)

    def test_run_returns_true_and_prints(self) -> None:
        captured = []
        passed = run(printer=captured.append)
        self.assertTrue(passed)
        self.assertEqual(len(captured), 1)
        self.assertIn("PASS", captured[0])


if __name__ == "__main__":
    unittest.main()
