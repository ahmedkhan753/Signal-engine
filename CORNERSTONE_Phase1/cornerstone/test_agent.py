"""
CORNERSTONE Phase 1 — Live Agent Loop tests.

Proves the agent can only propose (never execute), that every proposal is
forced through the Controller -> PolicyGate enforcement point, and that the
demo workflow yields ALLOW/DELAY/BLOCK from the rulebook (not from the agent).
Deterministic; no Flask, no engine, no external LLM.
"""

from __future__ import annotations

import inspect
import unittest

import cornerstone.agent as agent_module
from cornerstone.agent import DEMO_GOAL, Agent, run_demo
from cornerstone.controller import Controller
from cornerstone.executor import Executor
from cornerstone.ledger import WorkflowLedger
from cornerstone.models import ExecutorResult, ProposedAction, SessionContext
from cornerstone.policy_gate import PolicyGate
from cornerstone.queue_manager import QueueManager


def make_context() -> SessionContext:
    return SessionContext(
        session_id="sess-agent",
        workflow_id="wf-agent",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def make_controller() -> Controller:
    return Controller(
        policy_gate=PolicyGate(),
        executor=Executor(),
        queue_manager=QueueManager(),
        ledger=WorkflowLedger(session_id="sess-agent"),
    )


class TestAgentCannotExecute(unittest.TestCase):
    def test_agent_module_does_not_import_executor(self) -> None:
        src = inspect.getsource(agent_module)
        # No import of the executor module or tool implementations.
        self.assertNotIn("from .executor", src)
        self.assertNotIn("import executor", src)
        # The Executor class name is not bound in the agent module namespace.
        self.assertFalse(hasattr(agent_module, "Executor"))

    def test_agent_has_no_execute_capability(self) -> None:
        agent = Agent(make_controller())
        self.assertFalse(hasattr(agent, "executor"))
        self.assertFalse(hasattr(agent, "execute"))
        # Its only collaborator is the Controller.
        self.assertIsInstance(agent.controller, Controller)

    def test_agent_only_emits_proposals(self) -> None:
        agent = Agent(make_controller())
        action = agent.propose_next_action(DEMO_GOAL, make_context())
        self.assertIsInstance(action, ProposedAction)
        self.assertEqual(action.source, "agent")


class TestEveryProposalGoesThroughController(unittest.TestCase):
    def test_all_proposals_routed_via_receive_action(self) -> None:
        ctrl = make_controller()
        calls: list[ProposedAction] = []
        real_receive = ctrl.receive_action

        def spy_receive(action, ctx):
            calls.append(action)
            return real_receive(action, ctx)

        ctrl.receive_action = spy_receive  # type: ignore[assignment]

        agent = Agent(ctrl)
        steps = agent.run(DEMO_GOAL, make_context())

        # One receive_action call per step, each with a ProposedAction.
        self.assertEqual(len(calls), len(steps))
        self.assertTrue(all(isinstance(a, ProposedAction) for a in calls))
        self.assertEqual(len(steps), 3)


class TestDemoWorkflowOutcomes(unittest.TestCase):
    def test_demo_yields_one_allow_one_delay_one_block(self) -> None:
        steps, summary = run_demo()
        results = [s.result for s in steps]

        self.assertEqual(results.count(ExecutorResult.EXECUTED), 1)  # ALLOW
        self.assertEqual(results.count(ExecutorResult.WAITING), 1)   # DELAY
        self.assertEqual(results.count(ExecutorResult.BLOCKED), 1)   # BLOCK

        # Decisions in the ledger arose from the rulebook, not the agent.
        self.assertEqual(summary["decisions"], {"ALLOW": 1, "DELAY": 1, "BLOCK": 1})

    def test_allow_executes(self) -> None:
        ctrl = make_controller()
        Agent(ctrl).run(DEMO_GOAL, make_context())
        # Only the ALLOW'd read_status action reached the executor.
        self.assertEqual(ctrl.executor.execution_log, [f"{DEMO_GOAL}-0"])

    def test_block_prevents_execution(self) -> None:
        ctrl = make_controller()
        Agent(ctrl).run(DEMO_GOAL, make_context())
        # delete_system_file (step 2) is BLOCK and must never appear as executed.
        self.assertNotIn(f"{DEMO_GOAL}-2", ctrl.executor.execution_log)

    def test_delay_enters_the_queue(self) -> None:
        ctrl = make_controller()
        Agent(ctrl).run(DEMO_GOAL, make_context())
        pending = ctrl.queue_manager.pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].action.action_type, "send_email")

    def test_ledger_records_all_actions(self) -> None:
        ctrl = make_controller()
        steps = Agent(ctrl).run(DEMO_GOAL, make_context())
        entries = ctrl.ledger.entries()
        self.assertEqual(len(entries), len(steps))
        self.assertEqual(
            [e.action_id for e in entries],
            [f"{DEMO_GOAL}-{i}" for i in range(3)],
        )


class TestDeterminism(unittest.TestCase):
    def _signature(self, ctrl: Controller):
        return [
            (e.action_id, e.decision.value, e.executor_result.value)
            for e in ctrl.ledger.entries()
        ]

    def test_repeated_runs_are_deterministic(self) -> None:
        ctrl_a = make_controller()
        ctrl_b = make_controller()
        Agent(ctrl_a).run(DEMO_GOAL, make_context())
        Agent(ctrl_b).run(DEMO_GOAL, make_context())
        self.assertEqual(self._signature(ctrl_a), self._signature(ctrl_b))

    def test_same_agent_rerun_is_deterministic(self) -> None:
        ctrl = make_controller()
        agent = Agent(ctrl)
        first = [s.result for s in agent.run(DEMO_GOAL, make_context())]
        # Re-running resets the cursor and reproduces the same result sequence.
        second_ctrl = make_controller()
        agent2 = Agent(second_ctrl)
        second = [s.result for s in agent2.run(DEMO_GOAL, make_context())]
        self.assertEqual(first, second)


class TestNoBypassRemains(unittest.TestCase):
    def test_executor_only_runs_after_gate_for_allow(self) -> None:
        order: list[str] = []
        gate = PolicyGate()
        executor = Executor()
        real_eval = gate.evaluate
        real_exec = executor.execute

        def spy_eval(action, ctx):
            order.append(f"gate:{action.action_type}")
            return real_eval(action, ctx)

        def spy_exec(action):
            order.append(f"exec:{action.action_type}")
            return real_exec(action)

        gate.evaluate = spy_eval    # type: ignore[assignment]
        executor.execute = spy_exec  # type: ignore[assignment]
        ctrl = Controller(gate, executor, QueueManager(), WorkflowLedger())

        Agent(ctrl).run(DEMO_GOAL, make_context())

        # Gate ran for every one of the three proposals...
        self.assertEqual(
            [e for e in order if e.startswith("gate:")],
            ["gate:read_status", "gate:send_email", "gate:delete_system_file"],
        )
        # ...but the executor ran only for the ALLOW'd read_status, and only
        # after its gate evaluation.
        self.assertEqual([e for e in order if e.startswith("exec:")], ["exec:read_status"])
        self.assertLess(order.index("gate:read_status"), order.index("exec:read_status"))


if __name__ == "__main__":
    unittest.main()
