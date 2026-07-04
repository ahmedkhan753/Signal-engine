"""
CORNERSTONE Phase 1 — typed models and enums.

Architecture only. These dataclasses define the *shape* of the runtime
governance-control layer that sits in front of action execution. They carry
no behavior and no business logic; they are the contract that the Phase 1
components (Controller, PolicyGate, Executor, QueueManager, WorkflowLedger)
exchange.

They are intentionally additive and do not touch or import any VECTOR V3
engine/API code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class Decision(str, Enum):
    """Outcome of a PolicyGate evaluation for a single proposed action."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    DELAY = "DELAY"


class ApprovalStatus(str, Enum):
    """Lifecycle state of an action held in the approval queue."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"


class ExecutorResult(str, Enum):
    """Terminal (or holding) outcome reported by the Executor for an action."""
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    KILLED = "KILLED"
    WAITING = "WAITING"


# --------------------------------------------------------------------------
# Data models
# --------------------------------------------------------------------------
@dataclass
class SessionContext:
    """
    Governance context threaded through a single evaluation/execution flow.

    Carries the V3 runtime signals (runtime_state, risk_level) that a policy
    decision may depend on, without the control layer having to re-run the
    engine.
    """
    session_id: str
    workflow_id: Optional[str] = None
    scenario_id: Optional[str] = None
    runtime_state: Optional[str] = None
    recommended_action: Optional[str] = None
    risk_level: Optional[str] = None
    operator_id: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProposedAction:
    """An action proposed for governed execution, before any policy ruling."""
    action_id: str
    action_type: str
    scenario_id: Optional[str] = None
    source: Optional[str] = None          # engine | operator | external
    payload: Dict[str, Any] = field(default_factory=dict)
    risk_level: Optional[str] = None
    proposed_at: Optional[str] = None


@dataclass
class DecisionRecord:
    """
    Immutable record of a single PolicyGate ruling on a ProposedAction.

    ``live_state_snapshot`` captures the session/runtime state that was read
    at evaluation time — the client's "live state" requirement. ``rule_id``
    names the deterministic rulebook entry that produced the decision, and
    ``sequence_index`` is the monotonic position of this evaluation within a
    gate's lifetime.
    """
    action_id: str
    workflow_id: Optional[str]
    decision: Decision
    reason: str
    rule_id: str
    live_state_snapshot: Dict[str, Any]
    timestamp: str
    sequence_index: int


@dataclass
class PendingApproval:
    """A proposed action parked in the queue awaiting a human ruling."""
    approval_id: str
    action: ProposedAction
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    reason: Optional[str] = None
    # Human-approval runtime fields (demo credential + terminal fate).
    user_credential: Optional[str] = None
    resulting_fate: Optional["ExecutorResult"] = None


@dataclass
class ApprovalDecision:
    """
    Audit record of a single human approval ruling on a queued action.

    Captures exactly what the Phase 1 spec requires per decision: the resolved
    approval_status, the (demo) user_credential that resolved it, the
    decision_timestamp, and the resulting_fate (EXECUTED or KILLED).
    """
    approval_id: str
    action_id: str
    approval_status: ApprovalStatus
    user_credential: str
    decision_timestamp: str
    resulting_fate: ExecutorResult


@dataclass
class TraceEntry:
    """One append-only event in the workflow ledger."""
    entry_id: str
    timestamp: str
    session_id: str
    actor: str                             # controller | gate | executor | operator
    message: str
    action_id: Optional[str] = None
    decision: Optional[Decision] = None
    executor_result: Optional[ExecutorResult] = None
    is_intervention: bool = False
    # Named lifecycle event: QUEUED | APPROVED | DENIED |
    # EXECUTED_AFTER_APPROVAL | KILLED_AFTER_DENIAL | EXECUTED | BLOCKED.
    event_type: Optional[str] = None
    user_credential: Optional[str] = None  # demo credential, when human-resolved


@dataclass
class WorkflowLedger:
    """
    Serializable state of a session's workflow ledger.

    This is the *data* model — the append-only list of trace entries plus
    session-level metadata. The operational component that reads/writes it
    lives in ``cornerstone.ledger.WorkflowLedger`` (see that module's note).
    """
    session_id: str
    entries: List[TraceEntry] = field(default_factory=list)
    intervention_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
