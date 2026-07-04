"""
CORNERSTONE Phase 1 — runtime governance-control layer (architecture scaffold).

This package sits *in front of* action execution. Where VECTOR V3 decides what
the recommended action is, CORNERSTONE governs whether and how that action is
actually carried out: PolicyGate rules on it, the Executor performs it, the
QueueManager holds deferred actions for human approval, and the WorkflowLedger
records every step.

Phase 1 is architecture only — typed models, enums, and placeholder components
with no business logic. Nothing here imports or modifies the V3 engine/API.
"""

from __future__ import annotations

from .agent import DEMO_GOAL, Agent, AgentStep, run_demo
from .api import cornerstone_bp
from .contracts import (
    build_approval_request,
    build_decision_record,
    build_pending_approval,
    build_run_summary,
    build_trace_entry,
)
from .controller import Controller
from .executor import Executor
from .ledger import WorkflowLedger
from .models import (
    ApprovalDecision,
    ApprovalStatus,
    Decision,
    DecisionRecord,
    ExecutorResult,
    PendingApproval,
    ProposedAction,
    SessionContext,
    TraceEntry,
)
from .models import WorkflowLedger as WorkflowLedgerData
from .policy_gate import PolicyGate
from .policy_rules import DEFAULT_RULE, RULEBOOK, PolicyRule, match_rule
from .queue_manager import QueueManager
from .workflow import build_workflow

__all__ = [
    # Enums
    "Decision",
    "ApprovalStatus",
    "ExecutorResult",
    # Data models
    "ProposedAction",
    "DecisionRecord",
    "PendingApproval",
    "ApprovalDecision",
    "TraceEntry",
    "WorkflowLedgerData",
    "SessionContext",
    # Components
    "Controller",
    "PolicyGate",
    "Executor",
    "QueueManager",
    "WorkflowLedger",
    "build_workflow",
    # Rulebook
    "PolicyRule",
    "RULEBOOK",
    "DEFAULT_RULE",
    "match_rule",
    # Agent loop
    "Agent",
    "AgentStep",
    "DEMO_GOAL",
    "run_demo",
    # Section 7 frontend contracts
    "build_decision_record",
    "build_pending_approval",
    "build_trace_entry",
    "build_run_summary",
    "build_approval_request",
    # Runtime API
    "cornerstone_bp",
]
