"""
CORNERSTONE Phase 1 — sandboxed agent simulator (Live Agent Loop).

A deterministic, scripted stand-in for an LLM planner. It exists to *propose*
actions toward a goal — it never carries anything out. Every proposal is handed
to the Controller, which is the only component the agent is allowed to depend
on:

    Agent
      -> Controller.receive_action()
           -> PolicyGate  (ALLOW / BLOCK / DELAY)
                -> Executor OR Queue
                     -> Ledger

Hard boundaries (enforced by construction and by tests):
  * The agent imports neither the Executor nor any tool implementation.
  * The agent has no method that executes anything; it only builds
    ProposedAction objects and passes them to the Controller.
  * Planning is deterministic scripted lookup — no external LLM, no randomness.

Outcomes (ALLOW/BLOCK/DELAY) are never chosen by the agent; they arise solely
from the existing PolicyGate rulebook once a proposal reaches the Controller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .controller import Controller
from .models import ExecutorResult, ProposedAction, SessionContext


# --------------------------------------------------------------------------
# Deterministic scripted plans (goal -> ordered action types)
# --------------------------------------------------------------------------
# The canonical demo goal. Its plan naturally yields exactly one ALLOW, one
# DELAY, and one BLOCK once the actions pass through the rulebook:
#   read_status        -> SAFE_READ_ALLOW   -> ALLOW
#   send_email         -> SENSITIVE_DELAY   -> DELAY
#   delete_system_file -> DANGEROUS_BLOCK   -> BLOCK
DEMO_GOAL = "triage_incident"

SCRIPTED_PLANS: Dict[str, List[str]] = {
    "triage_incident": ["read_status", "send_email", "delete_system_file"],
    "healthcheck": ["read_status", "get_metrics", "list_services"],
}

# Any unrecognized goal falls back to a single safe read.
DEFAULT_PLAN: List[str] = ["read_status"]


@dataclass
class AgentStep:
    """One proposal and the result the Controller returned for it."""
    proposed_action: ProposedAction
    result: ExecutorResult


class Agent:
    """Deterministic scripted planner. Proposes actions; never executes them."""

    def __init__(self, controller: Controller) -> None:
        # The Controller is the ONLY collaborator the agent is allowed to hold.
        self.controller = controller
        self._cursor_goal: Optional[str] = None
        self._cursor: int = 0

    # -- planning -----------------------------------------------------------
    def _plan_for(self, goal: str) -> List[str]:
        """Return the deterministic action sequence for a goal."""
        return SCRIPTED_PLANS.get(goal, DEFAULT_PLAN)

    def reset(self, goal: str) -> None:
        """Rewind the planning cursor to the start of ``goal``'s plan."""
        self._cursor_goal = goal
        self._cursor = 0

    def propose_next_action(
        self,
        goal: str,
        session_context: SessionContext,
    ) -> Optional[ProposedAction]:
        """
        Emit the next ProposedAction for ``goal``, or ``None`` when the scripted
        plan is exhausted. This is a *proposal only* — it is never executed here.
        """
        plan = self._plan_for(goal)
        if self._cursor_goal != goal:
            self.reset(goal)

        if self._cursor >= len(plan):
            return None

        index = self._cursor
        action_type = plan[index]
        self._cursor += 1

        return ProposedAction(
            action_id=f"{goal}-{index}",
            action_type=action_type,
            scenario_id=session_context.scenario_id,
            source="agent",
            payload={"goal": goal, "step": index},
        )

    # -- driving the loop (through the Controller only) ---------------------
    def run(
        self,
        goal: str,
        session_context: SessionContext,
    ) -> List[AgentStep]:
        """
        Run the scripted plan for ``goal``, routing every proposal through the
        Controller (and therefore the PolicyGate). Returns the ordered steps.
        """
        self.reset(goal)
        steps: List[AgentStep] = []
        while True:
            action = self.propose_next_action(goal, session_context)
            if action is None:
                break
            # The agent's ONLY effect on the world: hand the proposal to the
            # Controller. It cannot and does not touch the Executor or tools.
            result = self.controller.receive_action(action, session_context)
            steps.append(AgentStep(proposed_action=action, result=result))
        return steps


def run_demo(
    goal: str = DEMO_GOAL,
    session_context: Optional[SessionContext] = None,
) -> Tuple[List[AgentStep], Dict]:
    """
    Convenience demonstration: wire a fresh workflow, run the agent against a
    goal, and return (steps, ledger_summary). Used by tests and later by the
    API layer. Imported lazily to keep the Agent class free of wiring concerns.
    """
    from .workflow import build_workflow

    controller = build_workflow(session_id=goal)
    if session_context is None:
        session_context = SessionContext(
            session_id=goal,
            workflow_id=f"wf-{goal}",
            scenario_id="stable_deployment",
            runtime_state="STABLE",
            risk_level="LOW",
        )

    agent = Agent(controller)
    steps = agent.run(goal, session_context)
    return steps, controller.ledger.summary()
