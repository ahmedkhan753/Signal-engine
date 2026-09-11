"""
CORNERSTONE Phase 1 — autonomous agent tests (Track 4).

Proves the autonomous agent is genuinely autonomous (it derives its own action
from goal + tool descriptions, not a scripted target), that it has no executor
or rulebook access, that its violating action reaches the gate and is BLOCK'd,
and that the executor never runs it. Deterministic; reuses the enforcement core.
"""

from __future__ import annotations

import inspect
import unittest

import cornerstone.autonomous as autonomous_module
from cornerstone.autonomous import (
    AUTONOMOUS_GOAL,
    AutonomousAgent,
    build_autonomous_report,
    build_scenario_autonomous_report,
    run_autonomous,
    run_scenario_autonomous,
)
from cornerstone.controller import Controller
from cornerstone.models import ExecutorResult, ProposedAction, SessionContext
from cornerstone.tool_catalog import DEFAULT_TOOL_CATALOG
from cornerstone.workflow import build_workflow

# Each vertical must autonomously derive a DISTINCT, domain-appropriate action
# that the gate independently BLOCKs.
VERTICAL_EXPECTED = {
    "financial_tech": "disable_security_controls",
    "medical_tech": "drop_database",
    "insurance_tech": "delete_system_file",
}


def make_context() -> SessionContext:
    return SessionContext(
        session_id="auto-test",
        workflow_id="auto-test",
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


class TestAutonomousIsolation(unittest.TestCase):
    def test_no_executor_or_rulebook_import(self) -> None:
        src = inspect.getsource(autonomous_module)
        self.assertNotIn("from .executor", src)
        self.assertNotIn("from .policy_gate", src)
        self.assertNotIn("from .policy_rules", src)
        # Neither the Executor class nor the rulebook is bound in the module.
        self.assertFalse(hasattr(autonomous_module, "Executor"))
        self.assertFalse(hasattr(autonomous_module, "PolicyGate"))
        self.assertFalse(hasattr(autonomous_module, "RULEBOOK"))
        self.assertFalse(hasattr(autonomous_module, "match_rule"))

    def test_agent_has_no_executor_or_gate_attributes(self) -> None:
        agent = AutonomousAgent(build_workflow("iso"), DEFAULT_TOOL_CATALOG)
        self.assertFalse(hasattr(agent, "executor"))
        self.assertFalse(hasattr(agent, "policy_gate"))
        self.assertFalse(hasattr(agent, "execute"))
        # Only collaborator is the Controller.
        self.assertIsInstance(agent.controller, Controller)

    def test_agent_not_given_the_target_action(self) -> None:
        # The agent is only handed a goal + tool descriptions; the catalog does
        # not tag anything as blocked/allowed. The agent derives the action.
        agent = AutonomousAgent(build_workflow("derive"), DEFAULT_TOOL_CATALOG)
        action = agent.select_action(AUTONOMOUS_GOAL, make_context())
        # It genuinely selected the dangerous tool by matching the goal,
        # evidenced by the recorded reasoning and match tokens.
        self.assertEqual(action.action_type, "delete_system_file")
        self.assertTrue(action.payload["selected_because"])
        self.assertEqual(action.source, "autonomous-agent")


class TestAutonomousReasoning(unittest.TestCase):
    def test_ranking_picks_best_fit_deterministically(self) -> None:
        agent = AutonomousAgent(build_workflow("rank"), DEFAULT_TOOL_CATALOG)
        ranking = agent.plan(AUTONOMOUS_GOAL, make_context())
        self.assertEqual(ranking[0].tool.name, "delete_system_file")
        self.assertGreater(ranking[0].score, 0)
        # Every other tool scored strictly lower (the choice is unambiguous).
        self.assertTrue(all(s.score < ranking[0].score for s in ranking[1:]))

    def test_different_goal_selects_different_action(self) -> None:
        # Autonomy check: a benign goal derives a safe action, proving the
        # selection is driven by the goal, not hardwired to delete_system_file.
        agent = AutonomousAgent(build_workflow("benign"), DEFAULT_TOOL_CATALOG)
        action = agent.select_action("check the health status of the system", make_context())
        self.assertEqual(action.action_type, "read_status")

    def test_deterministic_selection(self) -> None:
        a1 = AutonomousAgent(build_workflow("d1"), DEFAULT_TOOL_CATALOG)
        a2 = AutonomousAgent(build_workflow("d2"), DEFAULT_TOOL_CATALOG)
        self.assertEqual(
            a1.select_action(AUTONOMOUS_GOAL, make_context()).action_type,
            a2.select_action(AUTONOMOUS_GOAL, make_context()).action_type,
        )


class TestAutonomousEnforcement(unittest.TestCase):
    def test_violating_action_reaches_gate_and_is_blocked(self) -> None:
        controller = build_workflow("enf")
        agent = AutonomousAgent(controller, DEFAULT_TOOL_CATALOG)
        outcome = agent.pursue(AUTONOMOUS_GOAL, make_context())

        self.assertEqual(outcome.result, ExecutorResult.BLOCKED)
        record = controller.get_decision_record(outcome.selected_action.action_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.decision.value, "BLOCK")

    def test_executor_never_runs_the_violating_action(self) -> None:
        controller = build_workflow("noexec")
        agent = AutonomousAgent(controller, DEFAULT_TOOL_CATALOG)
        outcome = agent.pursue(AUTONOMOUS_GOAL, make_context())
        self.assertEqual(controller.executor.execution_log, [])
        self.assertNotIn(
            outcome.selected_action.action_id, controller.executor.execution_log
        )

    def test_live_state_still_evaluated(self) -> None:
        controller = build_workflow("live")
        agent = AutonomousAgent(controller, DEFAULT_TOOL_CATALOG)
        outcome = agent.pursue(AUTONOMOUS_GOAL, make_context())
        record = controller.get_decision_record(outcome.selected_action.action_id)
        self.assertEqual(record.live_state_snapshot.get("runtime_state"), "STABLE")
        self.assertIsNotNone(record.live_state_snapshot.get("read_at"))

    def test_proposals_go_through_controller_only(self) -> None:
        controller = build_workflow("route")
        calls = []
        real_receive = controller.receive_action

        def spy(action, ctx):
            calls.append(action)
            return real_receive(action, ctx)

        controller.receive_action = spy  # type: ignore[assignment]
        AutonomousAgent(controller, DEFAULT_TOOL_CATALOG).pursue(AUTONOMOUS_GOAL, make_context())
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(calls[0], ProposedAction)


class TestAutonomousDemo(unittest.TestCase):
    def test_demo_completes_and_passes(self) -> None:
        report, passed = build_autonomous_report()
        self.assertTrue(passed)
        self.assertTrue(report.strip().endswith("PASS"))

    def test_demo_identifies_action_and_block(self) -> None:
        report, _ = build_autonomous_report()
        self.assertIn("delete_system_file", report)
        self.assertIn("BLOCK", report)
        self.assertIn("NOT EXECUTED", report)
        self.assertIn("Live-state evaluated: YES", report)

    def test_demo_is_deterministic(self) -> None:
        first, _ = build_autonomous_report()
        second, _ = build_autonomous_report()
        self.assertEqual(first, second)

    def test_run_autonomous_prints_and_passes(self) -> None:
        captured = []
        passed = run_autonomous(printer=captured.append)
        self.assertTrue(passed)
        self.assertIn("PASS", captured[0])


class TestVerticalAutonomous(unittest.TestCase):
    def test_each_vertical_derives_domain_action_and_is_blocked(self) -> None:
        for scenario_id, expected in VERTICAL_EXPECTED.items():
            controller, outcome, scenario, goal, labels = run_scenario_autonomous(scenario_id)
            action = outcome.selected_action
            record = controller.get_decision_record(action.action_id)
            with self.subTest(scenario=scenario_id):
                # Agent derived the domain-appropriate action itself.
                self.assertEqual(action.action_type, expected)
                self.assertGreater(outcome.ranking[0].score, 0)
                self.assertTrue(all(s.score < outcome.ranking[0].score
                                    for s in outcome.ranking[1:]))
                # Gate independently BLOCK'd it; executor never ran it.
                self.assertEqual(record.decision.value, "BLOCK")
                self.assertEqual(controller.executor.execution_log, [])
                # Live-state still evaluated.
                self.assertIsNotNone(record.live_state_snapshot.get("read_at"))
                # A domain label is present for the attempted action.
                self.assertTrue(labels.get(action.action_type))

    def test_verticals_derive_distinct_actions(self) -> None:
        chosen = {
            sid: run_scenario_autonomous(sid)[1].selected_action.action_type
            for sid in VERTICAL_EXPECTED
        }
        self.assertEqual(len(set(chosen.values())), 3)  # all different

    def test_scenario_uses_configured_goal_not_generic(self) -> None:
        _, _, scenario, goal, _ = run_scenario_autonomous("financial_tech")
        self.assertNotEqual(goal, AUTONOMOUS_GOAL)
        self.assertIn("settlement", goal)  # domain-specific financial goal

    def test_unknown_scenario_falls_back_to_generic(self) -> None:
        # Safe fallback: no autonomous config -> generic catalog/goal.
        controller, outcome, scenario, goal, labels = run_scenario_autonomous("nope")
        self.assertEqual(goal, AUTONOMOUS_GOAL)
        self.assertEqual(labels, {})
        self.assertEqual(outcome.selected_action.action_type, "delete_system_file")

    def test_vertical_report_passes_and_names_action(self) -> None:
        report, passed = build_scenario_autonomous_report("medical_tech")
        self.assertTrue(passed)
        self.assertIn("drop_database", report)
        self.assertIn("BLOCK", report)
        self.assertIn("NOT EXECUTED", report)
        self.assertIn("not an LLM", report)

    def test_vertical_report_deterministic(self) -> None:
        first, _ = build_scenario_autonomous_report("insurance_tech")
        second, _ = build_scenario_autonomous_report("insurance_tech")
        self.assertEqual(first, second)

    def test_agent_still_no_executor_in_vertical_run(self) -> None:
        controller, outcome, *_ = run_scenario_autonomous("financial_tech")
        # The agent object is not retained on the controller; verify the module
        # boundary still holds (no executor/gate import in autonomous.py).
        src = inspect.getsource(autonomous_module)
        self.assertNotIn("from .executor", src)
        self.assertNotIn("from .policy_gate", src)
        self.assertNotIn("from .policy_rules", src)


class TestScriptedAgentUnchanged(unittest.TestCase):
    def test_scripted_acceptance_agent_still_deterministic(self) -> None:
        # The autonomous track must not alter the scripted acceptance agent.
        from cornerstone.agent import Agent, DEMO_GOAL

        c1 = build_workflow("s1")
        c2 = build_workflow("s2")
        r1 = [s.result.value for s in Agent(c1).run(DEMO_GOAL, make_context())]
        r2 = [s.result.value for s in Agent(c2).run(DEMO_GOAL, make_context())]
        self.assertEqual(r1, r2)
        self.assertEqual(r1, ["EXECUTED", "WAITING", "BLOCKED"])


if __name__ == "__main__":
    unittest.main()
