"""
CORNERSTONE Phase 1 — runtime API layer (demo wiring).

A Flask **Blueprint** (``cornerstone_bp``) that exposes the live enforcement
loop as the first public interface. It is pure orchestration: it wires together
components that already exist — ``build_workflow`` (gate + executor + queue +
ledger), the scripted ``Agent``, the Controller's approval runtime, and the
Section 7 contract builders — and holds exactly ONE in-memory demo session.

No standalone app is created here; a host application registers the blueprint.
No database, persistence, auth, threading, or cache. Restart the demo by calling
``GET /cornerstone/demo`` again.

Invariants honored:
  * No duplicated business logic — endpoints only orchestrate.
  * All queue transitions go through ``Controller.approve`` / ``Controller.deny``.
  * No direct Executor calls and no direct ledger manipulation.
  * Every response body is produced by ``cornerstone.contracts`` builders.
"""

from __future__ import annotations

from typing import List, Optional

from flask import Blueprint, jsonify, request

from .agent import DEMO_GOAL, Agent, AgentStep
from .autonomous import autonomous_payload
from .contracts import (
    build_decision_record,
    build_pending_approval,
    build_run_summary,
    build_trace_entry,
)
from .config import build_config_payload, select_scenario
from .controller import Controller
from .models import ProposedAction, SessionContext
from .workflow import build_workflow

cornerstone_bp = Blueprint("cornerstone", __name__, url_prefix="/cornerstone")


# --------------------------------------------------------------------------
# Single in-memory demo session
# --------------------------------------------------------------------------
class _DemoSession:
    """Holds the one live demo session (controller + context + run steps)."""

    def __init__(self) -> None:
        self.goal: str = DEMO_GOAL
        self.controller: Optional[Controller] = None
        self.session_context: Optional[SessionContext] = None
        self.steps: List[AgentStep] = []

    @property
    def workflow_id(self) -> str:
        # The ledger is scoped to one workflow; its session_id is the key used
        # across every contract (decision / pending / trace / summary).
        return self.controller.ledger.session_id if self.controller else self.goal


_session = _DemoSession()


def _reset_session() -> None:
    """
    Clear the single demo session back to empty.

    After reset the controller is None, so the read-only polling endpoints
    (/pending, /summary, /decisions) return empty/zeroed results and cannot
    recreate stale state. Only an explicit beat trigger (GET /demo or
    GET /autonomous) creates a new session.
    """
    _session.goal = DEMO_GOAL
    _session.controller = None
    _session.session_context = None
    _session.steps = []


def _start_demo(scenario_id: Optional[str] = None) -> _DemoSession:
    """
    (Re)initialize the single demo session, retaining the Controller so the
    stateful approval endpoints act on the same queue/ledger.

    Default (no scenario): the scripted acceptance agent runs ``triage_incident``
    — behavior identical to before. With a ``scenario_id``, the selected (safe,
    validated) scenario config supplies the context, goal, and demo actions,
    which are proposed through the same enforcement core (the gate still rules
    independently — config selects inputs, never the verdict).
    """
    if scenario_id:
        return _start_scenario_demo(scenario_id)

    goal = DEMO_GOAL
    controller = build_workflow(session_id=goal)
    context = SessionContext(
        session_id=goal,
        workflow_id=goal,
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )
    agent = Agent(controller)
    steps = agent.run(goal, context)

    _session.goal = goal
    _session.controller = controller
    _session.session_context = context
    _session.steps = steps
    return _session


def _start_scenario_demo(scenario_id: str) -> _DemoSession:
    """Run a config-selected scenario's actions through the enforcement core."""
    scenario = select_scenario(scenario_id)  # safe: falls back to a known-good default
    controller = build_workflow(session_id=scenario.id)
    context = SessionContext(
        session_id=scenario.id,
        workflow_id=scenario.id,
        scenario_id=scenario.context.get("scenario_id", scenario.id),
        runtime_state=scenario.context.get("runtime_state"),
        risk_level=scenario.context.get("risk_level"),
    )
    for i, action in enumerate(scenario.actions):
        controller.receive_action(
            ProposedAction(
                action_id=f"{scenario.id}-{i}",
                action_type=action.action_type,
                scenario_id=context.scenario_id,
                source="scenario",
                payload={"label": action.label, "goal": scenario.goal},
            ),
            context,
        )

    _session.goal = scenario.goal
    _session.controller = controller
    _session.session_context = context
    _session.steps = []
    return _session


# --------------------------------------------------------------------------
# Serialization helpers (contracts only)
# --------------------------------------------------------------------------
def _serialize_trace(controller: Controller) -> list:
    wf = controller.ledger.session_id
    return [
        build_trace_entry(entry, workflow_id=wf, sequence_index=i)
        for i, entry in enumerate(controller.ledger.entries())
    ]


def _serialize_pending(controller: Controller) -> list:
    wf = controller.ledger.session_id
    # reason_held comes from the PendingApproval's stored gate reason (durable
    # audit data set at enqueue time), so it is consistent before and after
    # resolution rather than being re-derived here.
    return [
        build_pending_approval(item, workflow_id=wf)
        for item in controller.queue_manager.pending()
    ]


def _error(message: str, status: int):
    return jsonify({"error": message}), status


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@cornerstone_bp.get("/demo")
def demo():
    """
    Start (or restart) the demo and return its steps, summary, and pending set.

    Optional ``?scenario=<id>`` selects a config-driven scenario; without it, the
    default scripted acceptance demo runs. The response shape is identical in
    both cases.
    """
    session = _start_demo(request.args.get("scenario"))
    controller = session.controller
    return jsonify({
        "goal": session.goal,
        "steps": _serialize_trace(controller),
        "summary": build_run_summary(controller.ledger),
        "pending": _serialize_pending(controller),
    })


@cornerstone_bp.get("/config")
def config():
    """
    Return presentation config + the dropdown-ready scenario list for the
    frontend. Degrades to known-good defaults if a config file is invalid.
    """
    return jsonify(build_config_payload())


@cornerstone_bp.post("/reset")
def reset():
    """
    Reset the presenter/demo session to empty (clean beat separation).

    After reset the read-only endpoints (/pending, /summary, /decisions) return
    empty/zeroed results and cannot recreate stale state by polling — only an
    explicit beat trigger (/demo or /autonomous) starts a new session.
    """
    _reset_session()
    return jsonify({"status": "reset", "active": False, "pending": []})


@cornerstone_bp.get("/autonomous")
def autonomous():
    """
    Run the autonomous agent as a discrete presenter step and return the
    attempted (agent-derived) action, the gate's independent decision, and the
    trace. Optional ``?scenario=<id>`` selects a vertical (Financial/Medical/
    Insurance Tech); without it the generic autonomous demo runs.

    The gate rules independently — the agent proposes, the PolicyGate decides.
    The resulting controller is retained so /decisions and /summary reflect this
    step.
    """
    controller, payload = autonomous_payload(request.args.get("scenario"))
    _session.goal = payload["goal"]
    _session.controller = controller
    _session.session_context = None
    _session.steps = []
    return jsonify(payload)


@cornerstone_bp.get("/pending")
def pending():
    """Return the current pending-approval items (empty if no demo is running)."""
    if _session.controller is None:
        return jsonify({"items": []})
    return jsonify({"items": _serialize_pending(_session.controller)})


@cornerstone_bp.get("/summary")
def summary():
    """Return the run summary for the active demo session."""
    if _session.controller is None:
        return jsonify(build_run_summary([]))
    return jsonify(build_run_summary(_session.controller.ledger))


@cornerstone_bp.get("/decisions")
def decisions():
    """
    List every retained gate DecisionRecord for the active session (Panel A
    drill-down source). Empty list if no demo is running.
    """
    if _session.controller is None:
        return jsonify({"items": []})
    return jsonify({
        "items": [
            build_decision_record(record)
            for record in _session.controller.decision_records()
        ]
    })


@cornerstone_bp.get("/decisions/<action_id>")
def decision_detail(action_id: str):
    """Return the DecisionRecord for a single ``action_id``, or 404 if unknown."""
    controller = _session.controller
    record = controller.get_decision_record(action_id) if controller else None
    if record is None:
        return _error(f"Unknown action_id: {action_id}.", 404)
    return jsonify(build_decision_record(record))


@cornerstone_bp.post("/approve")
def approve():
    """Approve a queued item and resume its execution through the Controller."""
    return _resolve(approve=True)


@cornerstone_bp.post("/deny")
def deny():
    """Deny a queued item; it never executes (fate KILLED)."""
    return _resolve(approve=False)


def _resolve(approve: bool):
    """Shared approve/deny handler — routes through the Controller only."""
    controller = _session.controller
    if controller is None:
        return _error("No active demo session; call GET /cornerstone/demo first.", 409)

    body = request.get_json(silent=True) or {}
    queue_item_id = body.get("queue_item_id")
    user_credential = body.get("user_credential", "demo-user")
    if not queue_item_id:
        return _error("Missing required field: queue_item_id.", 400)

    try:
        if approve:
            decision = controller.approve(queue_item_id, user_credential)
        else:
            decision = controller.deny(queue_item_id, user_credential)
    except KeyError:
        return _error(f"Unknown queue_item_id: {queue_item_id}.", 404)
    except ValueError as exc:
        # Already resolved (repeated approval/denial) — nothing re-executes.
        return _error(str(exc), 409)

    return jsonify({
        "decision": decision.approval_status.value,
        "result": decision.resulting_fate.value,
        "trace": _serialize_trace(controller),
    })
