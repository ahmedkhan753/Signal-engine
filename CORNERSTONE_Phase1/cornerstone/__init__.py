"""
CORNERSTONE Phase 1 — runtime governance-control layer (architecture scaffold).

This package sits *in front of* action execution. Where VECTOR V3 decides what
the recommended action is, CORNERSTONE governs whether and how that action is
actually carried out: PolicyGate rules on it, the Executor performs it, the
QueueManager holds deferred actions for human approval, and the WorkflowLedger
records every step.

Phase 1 is a complete, deterministic, in-memory implementation: the enforcement
loop (agent -> controller -> gate -> executor/queue), the human approval runtime,
the ledger audit trail, the Section 7 serialization contracts, the runtime API
blueprint, and an acceptance validator + demo runner. Nothing here imports or
modifies the VECTOR V3 engine/API.
"""

from __future__ import annotations

from .acceptance import validate_phase1
from .agent import DEMO_GOAL, Agent, AgentStep, run_demo
from .api import cornerstone_bp
from .demo_runner import build_report as build_demo_report
from .demo_runner import run as run_demo_report
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
    # Acceptance + demo
    "validate_phase1",
    "build_demo_report",
    "run_demo_report",
]
