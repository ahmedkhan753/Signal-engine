"""
CORNERSTONE Phase 1 — Section 7 contract tests.

Verifies each builder emits exactly the contracted keys (no missing, no extra),
is JSON-serializable, and is deterministic. No Flask, no engine, no persistence.
Runs with ``python -m unittest cornerstone.test_contracts`` or ``pytest``.
"""

from __future__ import annotations

import json
import unittest

from cornerstone.contracts import (
    build_approval_request,
    build_decision_record,
    build_pending_approval,
    build_run_summary,
    build_trace_entry,
)
from cornerstone.controller import Controller
from cornerstone.executor import Executor
from cornerstone.ledger import WorkflowLedger
from cornerstone.models import (
    Decision,
    DecisionRecord,
    ExecutorResult,
    ProposedAction,
    SessionContext,
    TraceEntry,
)
from cornerstone.policy_gate import PolicyGate
from cornerstone.queue_manager import QueueManager

CRED = "demo-user"


def make_context() -> SessionContext:
    return SessionContext(
        session_id="wf-1",
        workflow_id="wf-1",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def make_controller() -> Controller:
    return Controller(
        policy_gate=PolicyGate(),
        executor=Executor(),
        queue_manager=QueueManager(),
        ledger=WorkflowLedger(session_id="wf-1"),
    )


def sample_decision_record() -> DecisionRecord:
    return DecisionRecord(
        action_id="act-1",
        workflow_id="wf-1",
        decision=Decision.ALLOW,
        reason="Action is a safe read with no side effects and is allowed.",
        rule_id="SAFE_READ_ALLOW",
        live_state_snapshot={"runtime_state": "STABLE", "risk_level": "LOW"},
        timestamp="2026-07-04T00:00:00+00:00",
        sequence_index=1,
    )


def queued_item(ctrl: Controller):
    ctrl.receive_action(ProposedAction("act-2", "send_email"), make_context())
    return ctrl.queue_manager.pending()[0]


def assert_json(testcase, obj) -> None:
    # Round-trips cleanly => fully JSON-serializable (no enum/None leakage).
    testcase.assertEqual(json.loads(json.dumps(obj)), obj)


class TestDecisionRecordContract(unittest.TestCase):
    KEYS = {
        "action_id", "workflow_id", "decision", "reason",
        "rule_id", "live_state", "timestamp", "sequence_index",
    }

    def test_serialization_and_exact_keys(self) -> None:
        out = build_decision_record(sample_decision_record())
        self.assertEqual(set(out), self.KEYS)          # no missing / no extra
        self.assertEqual(out["decision"], "ALLOW")     # enum -> string
        self.assertEqual(out["live_state"], {"runtime_state": "STABLE", "risk_level": "LOW"})
        assert_json(self, out)

    def test_deterministic(self) -> None:
        rec = sample_decision_record()
        self.assertEqual(build_decision_record(rec), build_decision_record(rec))


class TestPendingApprovalContract(unittest.TestCase):
    KEYS = {
        "id", "workflow_id", "proposed_action",
        "reason_held", "timestamp", "status", "resolution",
    }
    RES_KEYS = {"verdict", "user_credential", "decision_timestamp", "resulting_fate"}

    def test_pending_serialization_all_null_resolution(self) -> None:
        ctrl = make_controller()
        item = queued_item(ctrl)
        out = build_pending_approval(item, workflow_id="wf-1", reason_held="held: sensitive")
        self.assertEqual(set(out), self.KEYS)
        self.assertEqual(set(out["resolution"]), self.RES_KEYS)
        self.assertEqual(out["status"], "PENDING")
        self.assertEqual(
            out["resolution"],
            {"verdict": None, "user_credential": None,
             "decision_timestamp": None, "resulting_fate": None},
        )
        assert_json(self, out)

    def test_approved_serialization(self) -> None:
        ctrl = make_controller()
        item = queued_item(ctrl)
        ctrl.approve(item.approval_id, CRED)
        out = build_pending_approval(item, workflow_id="wf-1")
        self.assertEqual(out["status"], "APPROVED")
        self.assertEqual(out["resolution"], {
            "verdict": "APPROVED",
            "user_credential": CRED,
            "decision_timestamp": item.resolved_at,
            "resulting_fate": "EXECUTED",
        })
        assert_json(self, out)

    def test_denied_serialization(self) -> None:
        ctrl = make_controller()
        item = queued_item(ctrl)
        ctrl.deny(item.approval_id, CRED)
        out = build_pending_approval(item, workflow_id="wf-1")
        self.assertEqual(out["status"], "DENIED")
        self.assertEqual(out["resolution"]["verdict"], "DENIED")
        self.assertEqual(out["resolution"]["resulting_fate"], "KILLED")
        self.assertEqual(out["resolution"]["user_credential"], CRED)
        assert_json(self, out)

    def test_deterministic(self) -> None:
        ctrl = make_controller()
        item = queued_item(ctrl)
        self.assertEqual(
            build_pending_approval(item, workflow_id="wf-1"),
            build_pending_approval(item, workflow_id="wf-1"),
        )


class TestTraceEntryContract(unittest.TestCase):
    KEYS = {
        "event_type", "workflow_id", "action_id", "decision",
        "executor_result", "message", "timestamp", "sequence_index",
    }

    def test_serialization_and_exact_keys(self) -> None:
        entry = TraceEntry(
            entry_id="e1",
            timestamp="2026-07-04T00:00:00+00:00",
            session_id="wf-1",
            actor="controller",
            message="send_email -> DELAY (SENSITIVE_DELAY) -> WAITING",
            action_id="act-2",
            decision=Decision.DELAY,
            executor_result=ExecutorResult.WAITING,
            event_type="QUEUED",
        )
        out = build_trace_entry(entry, workflow_id="wf-1", sequence_index=0)
        self.assertEqual(set(out), self.KEYS)
        self.assertEqual(out["decision"], "DELAY")
        self.assertEqual(out["executor_result"], "WAITING")
        self.assertEqual(out["event_type"], "QUEUED")
        assert_json(self, out)

    def test_from_real_ledger(self) -> None:
        ctrl = make_controller()
        queued_item(ctrl)
        entry = ctrl.ledger.entries()[0]
        out = build_trace_entry(entry, workflow_id="wf-1", sequence_index=0)
        self.assertEqual(set(out), self.KEYS)
        assert_json(self, out)


class TestRunSummaryContract(unittest.TestCase):
    KEYS = {"total_allow", "total_delay", "total_block", "workflow_counts"}

    def test_summary_consumes_ledger(self) -> None:
        ctrl = make_controller()
        ctrl.receive_action(ProposedAction("a1", "read_status"), make_context())        # ALLOW
        ctrl.receive_action(ProposedAction("a2", "send_email"), make_context())         # DELAY
        ctrl.receive_action(ProposedAction("a3", "delete_system_file"), make_context())  # BLOCK

        out = build_run_summary(ctrl.ledger)
        self.assertEqual(set(out), self.KEYS)
        self.assertEqual(out["total_allow"], 1)
        self.assertEqual(out["total_delay"], 1)
        self.assertEqual(out["total_block"], 1)
        self.assertEqual(out["workflow_counts"], [{"workflow_id": "wf-1", "human_interventions": 2}])
        assert_json(self, out)

    def test_summary_accepts_multiple_ledgers(self) -> None:
        ctrl_a = make_controller()
        ctrl_b = Controller(PolicyGate(), Executor(), QueueManager(), WorkflowLedger("wf-2"))
        ctrl_a.receive_action(ProposedAction("a1", "read_status"), make_context())
        ctrl_b.receive_action(ProposedAction("b1", "send_email"), make_context())

        out = build_run_summary([ctrl_a.ledger, ctrl_b.ledger])
        self.assertEqual(out["total_allow"], 1)
        self.assertEqual(out["total_delay"], 1)
        self.assertEqual({w["workflow_id"] for w in out["workflow_counts"]}, {"wf-1", "wf-2"})
        assert_json(self, out)

    def test_deterministic(self) -> None:
        ctrl = make_controller()
        ctrl.receive_action(ProposedAction("a1", "read_status"), make_context())
        self.assertEqual(build_run_summary(ctrl.ledger), build_run_summary(ctrl.ledger))


class TestApprovalRequestContract(unittest.TestCase):
    KEYS = {"queue_item_id", "verdict", "user_credential"}

    def test_serialization_and_defaults(self) -> None:
        out = build_approval_request("apr-1", "APPROVE")
        self.assertEqual(set(out), self.KEYS)
        self.assertEqual(out, {
            "queue_item_id": "apr-1",
            "verdict": "APPROVE",
            "user_credential": "demo-user",
        })
        assert_json(self, out)

    def test_deny_verdict(self) -> None:
        out = build_approval_request("apr-9", "DENY", user_credential="demo-user:bob")
        self.assertEqual(out["verdict"], "DENY")
        self.assertEqual(out["user_credential"], "demo-user:bob")


if __name__ == "__main__":
    unittest.main()
