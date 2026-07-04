"""
CORNERSTONE Phase 1 — Human Approval Runtime tests.

Proves the PENDING -> APPROVED -> EXECUTED and PENDING -> DENIED -> KILLED
lifecycles: approval resumes execution through the reused Executor exactly once,
denial never executes, credentials/timestamps are stored, and every lifecycle
event is recorded in chronological order. Deterministic; no Flask, no engine,
no threading, no persistence.
"""

from __future__ import annotations

import unittest

from cornerstone.controller import Controller
from cornerstone.executor import Executor
from cornerstone.ledger import WorkflowLedger
from cornerstone.models import (
    ApprovalStatus,
    ExecutorResult,
    ProposedAction,
    SessionContext,
)
from cornerstone.policy_gate import PolicyGate
from cornerstone.queue_manager import QueueManager

CRED = "demo-user:alice"


def make_context() -> SessionContext:
    return SessionContext(
        session_id="sess-approval",
        workflow_id="wf-approval",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def make_controller() -> Controller:
    return Controller(
        policy_gate=PolicyGate(),
        executor=Executor(),
        queue_manager=QueueManager(),
        ledger=WorkflowLedger(session_id="sess-approval"),
    )


def sensitive_action(action_id: str = "act-sensitive") -> ProposedAction:
    # send_email is a SENSITIVE action -> DELAY -> parked for human approval.
    return ProposedAction(action_id=action_id, action_type="send_email")


def queue_one(ctrl: Controller):
    """Route a sensitive action so it becomes a single PENDING item."""
    result = ctrl.receive_action(sensitive_action(), make_context())
    assert result is ExecutorResult.WAITING
    pending = ctrl.queue_manager.pending()
    assert len(pending) == 1
    return pending[0]


class TestPendingState(unittest.TestCase):
    def test_queued_item_remains_pending(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        self.assertEqual(item.status, ApprovalStatus.PENDING)
        # Nothing executed yet.
        self.assertEqual(ctrl.executor.execution_log, [])
        # A QUEUED lifecycle event was recorded.
        events = [e.event_type for e in ctrl.ledger.entries()]
        self.assertIn("QUEUED", events)


class TestApprovalResumesExecution(unittest.TestCase):
    def test_approval_resumes_and_executes_once(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)

        decision = ctrl.approve(item.approval_id, CRED)

        # Terminal state + fate.
        self.assertEqual(item.status, ApprovalStatus.APPROVED)
        self.assertEqual(decision.resulting_fate, ExecutorResult.EXECUTED)
        # Executor ran exactly once, for the original action.
        self.assertEqual(ctrl.executor.execution_log, [item.action.action_id])

    def test_executor_called_exactly_once_even_if_reapproved(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        ctrl.approve(item.approval_id, CRED)

        # A second approval must be rejected (item no longer PENDING) and must
        # NOT execute again.
        with self.assertRaises(ValueError):
            ctrl.approve(item.approval_id, CRED)
        self.assertEqual(ctrl.executor.execution_log, [item.action.action_id])


class TestDenialKillsExecution(unittest.TestCase):
    def test_denied_action_never_executes(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)

        decision = ctrl.deny(item.approval_id, CRED)

        self.assertEqual(item.status, ApprovalStatus.DENIED)
        self.assertEqual(decision.resulting_fate, ExecutorResult.KILLED)
        # Executor was never invoked.
        self.assertEqual(ctrl.executor.execution_log, [])

    def test_cannot_approve_after_denial(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        ctrl.deny(item.approval_id, CRED)
        with self.assertRaises(ValueError):
            ctrl.approve(item.approval_id, CRED)
        self.assertEqual(ctrl.executor.execution_log, [])


class TestDecisionRecording(unittest.TestCase):
    def test_credential_and_timestamp_and_fate_recorded(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        decision = ctrl.approve(item.approval_id, CRED)

        # Stored honestly on both the item and the audit record.
        self.assertEqual(item.user_credential, CRED)
        self.assertEqual(decision.user_credential, CRED)
        self.assertIsNotNone(decision.decision_timestamp)
        self.assertEqual(decision.approval_status, ApprovalStatus.APPROVED)
        self.assertEqual(decision.resulting_fate, ExecutorResult.EXECUTED)

        # Appended to the approval audit trail.
        self.assertEqual(len(ctrl.approval_audit), 1)
        self.assertIs(ctrl.approval_audit[0], decision)

    def test_denial_records_killed_fate(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        ctrl.deny(item.approval_id, CRED)
        self.assertEqual(ctrl.approval_audit[0].resulting_fate, ExecutorResult.KILLED)
        self.assertEqual(ctrl.approval_audit[0].user_credential, CRED)


class TestTraceEntries(unittest.TestCase):
    def _event_sequence(self, ctrl: Controller):
        return [e.event_type for e in ctrl.ledger.entries()]

    def test_approval_trace_sequence(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        ctrl.approve(item.approval_id, CRED)
        # Chronological order preserved.
        self.assertEqual(
            self._event_sequence(ctrl),
            ["QUEUED", "APPROVED", "EXECUTED_AFTER_APPROVAL"],
        )
        # Credential carried on the human-resolved entries.
        creds = [e.user_credential for e in ctrl.ledger.entries() if e.user_credential]
        self.assertEqual(creds, [CRED, CRED])

    def test_denial_trace_sequence(self) -> None:
        ctrl = make_controller()
        item = queue_one(ctrl)
        ctrl.deny(item.approval_id, CRED)
        self.assertEqual(
            self._event_sequence(ctrl),
            ["QUEUED", "DENIED", "KILLED_AFTER_DENIAL"],
        )


class TestDeterminism(unittest.TestCase):
    def _run(self, approve: bool):
        ctrl = make_controller()
        item = queue_one(ctrl)
        if approve:
            ctrl.approve(item.approval_id, CRED)
        else:
            ctrl.deny(item.approval_id, CRED)
        return (
            [e.event_type for e in ctrl.ledger.entries()],
            [e.executor_result.value if e.executor_result else None
             for e in ctrl.ledger.entries()],
            list(ctrl.executor.execution_log),
        )

    def test_repeatable_approval(self) -> None:
        self.assertEqual(self._run(approve=True), self._run(approve=True))

    def test_repeatable_denial(self) -> None:
        self.assertEqual(self._run(approve=False), self._run(approve=False))


if __name__ == "__main__":
    unittest.main()
