"""
CORNERSTONE Phase 1 — non-blocking / multi-workflow tests (Track 6).

Proves two workflows are isolated: a DELAY in one does not block another, their
queues/executors/ledgers are independent, and multiple pending items resolve
independently and out of order. No threads/async — isolation is structural.
"""

from __future__ import annotations

import unittest

from cornerstone.concurrency import build_concurrency_report, run_concurrency
from cornerstone.models import ExecutorResult, ProposedAction, SessionContext
from cornerstone.workflow import build_workflow


def ctx(name: str) -> SessionContext:
    return SessionContext(session_id=name, workflow_id=name,
                          scenario_id="stable_deployment", runtime_state="STABLE", risk_level="LOW")


class TestWorkflowIsolation(unittest.TestCase):
    def test_delay_in_a_does_not_block_b(self) -> None:
        a = build_workflow("A")
        b = build_workflow("B")
        a_res = a.receive_action(ProposedAction("A1", "send_email"), ctx("A"))     # DELAY
        b_res = b.receive_action(ProposedAction("B1", "read_status"), ctx("B"))    # ALLOW
        self.assertEqual(a_res, ExecutorResult.WAITING)
        self.assertEqual(b_res, ExecutorResult.EXECUTED)
        # A is still parked; B ran regardless.
        self.assertEqual(len(a.queue_manager.pending()), 1)
        self.assertEqual(b.executor.execution_log, ["B1"])

    def test_queues_and_ledgers_are_independent(self) -> None:
        a = build_workflow("A")
        b = build_workflow("B")
        self.assertIsNot(a.queue_manager, b.queue_manager)
        self.assertIsNot(a.executor, b.executor)
        self.assertIsNot(a.ledger, b.ledger)

    def test_block_in_b_does_not_affect_a_pending(self) -> None:
        a = build_workflow("A")
        b = build_workflow("B")
        a.receive_action(ProposedAction("A1", "send_email"), ctx("A"))
        b.receive_action(ProposedAction("B1", "delete_system_file"), ctx("B"))  # BLOCK
        self.assertEqual(len(a.queue_manager.pending()), 1)   # untouched
        self.assertEqual(b.executor.execution_log, [])        # nothing executed in B

    def test_approval_of_a_does_not_touch_b(self) -> None:
        a = build_workflow("A")
        b = build_workflow("B")
        a.receive_action(ProposedAction("A1", "send_email"), ctx("A"))
        b.receive_action(ProposedAction("B1", "read_status"), ctx("B"))
        a.approve(a.queue_manager.pending()[0].approval_id, "demo-user")
        self.assertEqual(a.executor.execution_log, ["A1"])
        self.assertEqual(b.executor.execution_log, ["B1"])  # unchanged


class TestOutOfOrderResolution(unittest.TestCase):
    def test_multiple_pending_resolve_out_of_order(self) -> None:
        c = build_workflow("C")
        c.receive_action(ProposedAction("C1", "send_email"), ctx("C"))       # apr-1
        c.receive_action(ProposedAction("C2", "approve_payment"), ctx("C"))  # apr-2
        self.assertEqual(len(c.queue_manager.pending()), 2)

        # Resolve the second before the first.
        d2 = c.approve("apr-2", "demo-user")
        self.assertEqual(d2.resulting_fate, ExecutorResult.EXECUTED)
        self.assertEqual(len(c.queue_manager.pending()), 1)

        d1 = c.deny("apr-1", "demo-user")
        self.assertEqual(d1.resulting_fate, ExecutorResult.KILLED)
        self.assertEqual(len(c.queue_manager.pending()), 0)

        # Only the approved one executed.
        self.assertEqual(c.executor.execution_log, ["C2"])


class TestConcurrencyDemo(unittest.TestCase):
    def test_demo_passes(self) -> None:
        report, passed = build_concurrency_report()
        self.assertTrue(passed)
        self.assertTrue(report.strip().endswith("PASS"))

    def test_demo_deterministic(self) -> None:
        first, _ = build_concurrency_report()
        second, _ = build_concurrency_report()
        self.assertEqual(first, second)

    def test_run_prints_and_passes(self) -> None:
        captured = []
        passed = run_concurrency(printer=captured.append)
        self.assertTrue(passed)
        self.assertIn("PASS", captured[0])


if __name__ == "__main__":
    unittest.main()
