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
from .contracts import (
    build_pending_approval,
    build_run_summary,
    build_trace_entry,
)
from .controller import Controller
from .models import SessionContext
from .policy_rules import match_rule
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


def _start_demo(goal: str = DEMO_GOAL) -> _DemoSession:
    """
    (Re)initialize the single demo session: fresh workflow + a scripted agent
    run. Mirrors ``run_demo`` but retains the Controller so the stateful
    approval endpoints can act on the same queue/ledger.
    """
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
    return [
        build_pending_approval(
            item,
            workflow_id=wf,
            reason_held=match_rule(item.action.action_type).reason,
        )
        for item in controller.queue_manager.pending()
    ]


def _error(message: str, status: int):
    return jsonify({"error": message}), status


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@cornerstone_bp.get("/demo")
def demo():
    """Start (or restart) the demo and return its steps, summary, and pending set."""
    session = _start_demo(DEMO_GOAL)
    controller = session.controller
    return jsonify({
        "goal": session.goal,
        "steps": _serialize_trace(controller),
        "summary": build_run_summary(controller.ledger),
        "pending": _serialize_pending(controller),
    })


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
