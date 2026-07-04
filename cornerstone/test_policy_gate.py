"""
CORNERSTONE Phase 1 — PolicyGate unit tests (Milestone 2).

Deterministic-only tests: no network, no Flask, no engine. Runs with either
``python -m unittest cornerstone.test_policy_gate`` or ``pytest``.
"""

from __future__ import annotations

import unittest

from cornerstone.models import Decision, ProposedAction, SessionContext
from cornerstone.policy_gate import PolicyGate


def make_action(action_type: str, action_id: str = "act-1") -> ProposedAction:
    return ProposedAction(action_id=action_id, action_type=action_type)


def make_context(**overrides) -> SessionContext:
    base = dict(
        session_id="sess-1",
        workflow_id="wf-1",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        recommended_action="MONITOR_FOR_DRIFT",
        risk_level="LOW",
        operator_id="op-42",
    )
    base.update(overrides)
    return SessionContext(**base)


class TestPolicyGateOutcomes(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = PolicyGate()
        self.ctx = make_context()

    def test_safe_read_allows(self) -> None:
        record = self.gate.evaluate(make_action("read_status"), self.ctx)
        self.assertEqual(record.decision, Decision.ALLOW)
        self.assertEqual(record.rule_id, "SAFE_READ_ALLOW")
        self.assertEqual(record.action_id, "act-1")
        self.assertEqual(record.workflow_id, "wf-1")

    def test_dangerous_action_blocks(self) -> None:
        record = self.gate.evaluate(make_action("delete_system_file"), self.ctx)
        self.assertEqual(record.decision, Decision.BLOCK)
        self.assertEqual(record.rule_id, "DANGEROUS_BLOCK")

    def test_sensitive_action_delays(self) -> None:
        for action_type in ("send_email", "approve_payment"):
            record = self.gate.evaluate(make_action(action_type), self.ctx)
            self.assertEqual(record.decision, Decision.DELAY, action_type)
            self.assertEqual(record.rule_id, "SENSITIVE_DELAY", action_type)

    def test_unknown_action_defaults_to_delay(self) -> None:
        record = self.gate.evaluate(make_action("totally_unknown_action"), self.ctx)
        self.assertEqual(record.decision, Decision.DELAY)
        self.assertEqual(record.rule_id, "DEFAULT_DELAY")

    def test_record_is_complete(self) -> None:
        record = self.gate.evaluate(make_action("read_file"), self.ctx)
        self.assertIsNotNone(record.reason)
        self.assertIsNotNone(record.timestamp)
        self.assertIsInstance(record.sequence_index, int)
        self.assertIsInstance(record.live_state_snapshot, dict)


class TestPolicyGateDeterminism(unittest.TestCase):
    def test_repeated_evaluation_is_deterministic(self) -> None:
        gate = PolicyGate()
        ctx = make_context()
        action = make_action("approve_payment")

        rulings = [gate.evaluate(action, ctx) for _ in range(25)]
        decisions = {r.decision for r in rulings}
        rule_ids = {r.rule_id for r in rulings}
        reasons = {r.reason for r in rulings}

        # Decision surface is identical across every repeat.
        self.assertEqual(decisions, {Decision.DELAY})
        self.assertEqual(rule_ids, {"SENSITIVE_DELAY"})
        self.assertEqual(len(reasons), 1)

        # Sequence index still advances monotonically per call.
        self.assertEqual([r.sequence_index for r in rulings], list(range(1, 26)))

    def test_determinism_independent_of_gate_instance(self) -> None:
        ctx = make_context()
        action = make_action("delete_system_file")
        r1 = PolicyGate().evaluate(action, ctx)
        r2 = PolicyGate().evaluate(action, ctx)
        self.assertEqual(r1.decision, r2.decision)
        self.assertEqual(r1.rule_id, r2.rule_id)


class TestPolicyGateLiveState(unittest.TestCase):
    def test_live_state_read_occurs_on_every_evaluation(self) -> None:
        gate = PolicyGate()
        ctx = make_context()
        action = make_action("read_status")

        self.assertEqual(gate.live_state_read_count, 0)
        gate.evaluate(action, ctx)
        gate.evaluate(action, ctx)
        gate.evaluate(action, ctx)
        self.assertEqual(gate.live_state_read_count, 3)

    def test_snapshot_reflects_current_session_state(self) -> None:
        gate = PolicyGate()
        action = make_action("read_status")

        ctx = make_context(runtime_state="STABLE", risk_level="LOW")
        first = gate.evaluate(action, ctx).live_state_snapshot
        self.assertEqual(first["runtime_state"], "STABLE")
        self.assertEqual(first["risk_level"], "LOW")

        # Mutating the live context between calls must be picked up by a fresh read.
        ctx.runtime_state = "DEGRADED"
        ctx.risk_level = "HIGH"
        second = gate.evaluate(action, ctx).live_state_snapshot
        self.assertEqual(second["runtime_state"], "DEGRADED")
        self.assertEqual(second["risk_level"], "HIGH")

    def test_snapshot_carries_workflow_and_session_identity(self) -> None:
        gate = PolicyGate()
        record = gate.evaluate(make_action("read_status"), make_context())
        snap = record.live_state_snapshot
        self.assertEqual(snap["session_id"], "sess-1")
        self.assertEqual(snap["workflow_id"], "wf-1")
        self.assertIn("read_at", snap)


if __name__ == "__main__":
    unittest.main()
