"""
CORNERSTONE Phase 1 — Controller + Executor integration tests (Milestone 3).

Proves the mandatory enforcement path Controller -> PolicyGate -> Executor/Queue
and the executor's own defense against unknown tools. No Flask, no engine, no
LLM. Runs with ``python -m unittest cornerstone.test_controller_executor`` or
``pytest``.
"""

from __future__ import annotations

import unittest

from cornerstone.controller import Controller
from cornerstone.executor import Executor
from cornerstone.ledger import WorkflowLedger
from cornerstone.models import (
    ExecutorResult,
    ProposedAction,
    SessionContext,
)
from cornerstone.policy_gate import PolicyGate
from cornerstone.queue_manager import QueueManager
from cornerstone.workflow import build_workflow


def make_action(action_type: str, action_id: str = "act-1") -> ProposedAction:
    return ProposedAction(action_id=action_id, action_type=action_type)


def make_context() -> SessionContext:
    return SessionContext(
        session_id="sess-1",
        workflow_id="wf-1",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def make_controller():
    return Controller(
        policy_gate=PolicyGate(),
        executor=Executor(),
        queue_manager=QueueManager(),
        ledger=WorkflowLedger(session_id="sess-1"),
    )


class TestDispatchRouting(unittest.TestCase):
    def test_executor_always_runs_for_allow(self) -> None:
        ctrl = make_controller()
        result = ctrl.receive_action(make_action("read_status"), make_context())
        self.assertEqual(result, ExecutorResult.EXECUTED)
        self.assertEqual(ctrl.executor.execution_log, ["act-1"])

    def test_executor_never_runs_for_block(self) -> None:
        ctrl = make_controller()
        result = ctrl.receive_action(make_action("delete_system_file"), make_context())
        self.assertEqual(result, ExecutorResult.BLOCKED)
        self.assertEqual(ctrl.executor.execution_log, [])

    def test_executor_never_runs_for_delay(self) -> None:
        ctrl = make_controller()
        result = ctrl.receive_action(make_action("send_email"), make_context())
        self.assertEqual(result, ExecutorResult.WAITING)
        self.assertEqual(ctrl.executor.execution_log, [])
        # Deferred action is parked in the queue for human approval.
        self.assertEqual(len(ctrl.queue_manager.pending()), 1)


class TestExecutorSafety(unittest.TestCase):
    def test_unknown_tool_never_executes(self) -> None:
        executor = Executor()
        result = executor.execute(make_action("totally_unknown_tool"))
        self.assertEqual(result, ExecutorResult.BLOCKED)
        self.assertEqual(executor.execution_log, [])
        self.assertIsNone(executor.last_output)

    def test_known_tools_execute(self) -> None:
        executor = Executor()
        for tool in ("read_file", "read_status", "get_metrics", "list_services"):
            self.assertEqual(
                executor.execute(make_action(tool, action_id=tool)),
                ExecutorResult.EXECUTED,
                tool,
            )

    def test_unknown_action_through_controller_is_delayed_not_executed(self) -> None:
        # An unrecognized action type is DELAY'd by the gate (fail-safe) and so
        # never reaches the executor at all.
        ctrl = make_controller()
        result = ctrl.receive_action(make_action("mystery_action"), make_context())
        self.assertEqual(result, ExecutorResult.WAITING)
        self.assertEqual(ctrl.executor.execution_log, [])


class TestLedger(unittest.TestCase):
    def test_trace_entry_written_for_every_action(self) -> None:
        ctrl = make_controller()
        actions = [
            make_action("read_status", "a1"),   # ALLOW
            make_action("delete_system_file", "a2"),  # BLOCK
            make_action("send_email", "a3"),     # DELAY
            make_action("get_metrics", "a4"),    # ALLOW
        ]
        for a in actions:
            ctrl.receive_action(a, make_context())

        entries = ctrl.ledger.entries()
        self.assertEqual(len(entries), 4)
        self.assertEqual([e.action_id for e in entries], ["a1", "a2", "a3", "a4"])

    def test_ledger_summary_and_intervention_count(self) -> None:
        ctrl = make_controller()
        for a in [
            make_action("read_status", "a1"),        # ALLOW  (not intervention)
            make_action("delete_system_file", "a2"), # BLOCK  (intervention)
            make_action("send_email", "a3"),         # DELAY  (intervention)
        ]:
            ctrl.receive_action(a, make_context())

        summary = ctrl.ledger.summary()
        self.assertEqual(summary["total_entries"], 3)
        self.assertEqual(summary["decisions"], {"ALLOW": 1, "BLOCK": 1, "DELAY": 1})
        self.assertEqual(summary["results"], {"EXECUTED": 1, "BLOCKED": 1, "WAITING": 1})
        # BLOCK + DELAY are interventions; ALLOW is not.
        self.assertEqual(summary["intervention_count"], 2)
        self.assertEqual(ctrl.ledger.count_interventions(), 2)


class TestNoBypassPath(unittest.TestCase):
    """The Executor must never be reached without a prior PolicyGate ruling."""

    def _instrumented_controller(self, call_order):
        gate = PolicyGate()
        executor = Executor()
        real_evaluate = gate.evaluate
        real_execute = executor.execute

        def spy_evaluate(action, ctx):
            call_order.append("gate")
            return real_evaluate(action, ctx)

        def spy_execute(action):
            call_order.append("executor")
            return real_execute(action)

        gate.evaluate = spy_evaluate          # type: ignore[assignment]
        executor.execute = spy_execute        # type: ignore[assignment]
        return Controller(gate, executor, QueueManager(), WorkflowLedger())

    def test_gate_precedes_executor_for_allow(self) -> None:
        order: list[str] = []
        ctrl = self._instrumented_controller(order)
        ctrl.receive_action(make_action("read_status"), make_context())
        self.assertEqual(order, ["gate", "executor"])

    def test_executor_untouched_for_block_and_delay(self) -> None:
        order: list[str] = []
        ctrl = self._instrumented_controller(order)
        ctrl.receive_action(make_action("delete_system_file"), make_context())
        ctrl.receive_action(make_action("send_email"), make_context())
        # Gate ran twice; executor never ran.
        self.assertEqual(order, ["gate", "gate"])

    def test_dispatch_requires_a_decision_record(self) -> None:
        # Structural guarantee: dispatch cannot be called without a DecisionRecord,
        # so there is no signature-level bypass to the executor.
        ctrl = make_controller()
        with self.assertRaises(TypeError):
            ctrl.dispatch(make_action("read_status"))  # type: ignore[call-arg]


class TestBuildWorkflow(unittest.TestCase):
    def test_build_workflow_wires_a_working_controller(self) -> None:
        ctrl = build_workflow(session_id="sess-9")
        self.assertIsInstance(ctrl, Controller)
        result = ctrl.receive_action(make_action("list_services"), make_context())
        self.assertEqual(result, ExecutorResult.EXECUTED)
        self.assertEqual(ctrl.ledger.summary()["total_entries"], 1)


if __name__ == "__main__":
    unittest.main()
