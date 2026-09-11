"""
CORNERSTONE Phase 1 — Controller (with Human Approval Runtime).

The Controller is the entry point and the enforcement path of the control
layer. Every *new* proposed action follows exactly one route:

    receive_action()
        -> evaluate()          # PolicyGate.evaluate  (MANDATORY)
        -> Decision
        -> dispatch()
            -> Executor.execute()   when ALLOW  -> EXECUTED
            -> QueueManager.enqueue when DELAY   -> WAITING  (QUEUED)
            -> (no execution)       when BLOCK   -> BLOCKED

A DELAY parks the action for human approval. The Controller then owns the
resolution of those parked items — the *approval runtime*:

    approve(id, cred): QueueManager PENDING->APPROVED, then RESUME the original
        action through the SAME Executor (reused, executed exactly once)
        -> EXECUTED  (EXECUTED_AFTER_APPROVAL)
    deny(id, cred):    QueueManager PENDING->DENIED, action never executes
        -> KILLED    (KILLED_AFTER_DENIAL)

Every decision and every lifecycle transition is appended to the WorkflowLedger
in chronological order; every approval ruling is also recorded as an
ApprovalDecision in the approval audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .executor import Executor
from .ledger import WorkflowLedger
from .models import (
    ApprovalDecision,
    Decision,
    DecisionRecord,
    ExecutorResult,
    PendingApproval,
    ProposedAction,
    SessionContext,
    TraceEntry,
)
from .policy_gate import PolicyGate
from .queue_manager import QueueManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Base decision -> lifecycle event name for the initial-run trace entry.
_DECISION_EVENT = {
    Decision.ALLOW: "EXECUTED",
    Decision.BLOCK: "BLOCKED",
    Decision.DELAY: "QUEUED",
}


class Controller:
    """Orchestrates the mandatory gate path and the human approval runtime."""

    def __init__(
        self,
        policy_gate: PolicyGate,
        executor: Executor,
        queue_manager: QueueManager,
        ledger: WorkflowLedger,
    ) -> None:
        self.policy_gate = policy_gate
        self.executor = executor
        self.queue_manager = queue_manager
        self.ledger = ledger
        # Audit trail of human approval rulings (in-memory, chronological).
        self.approval_audit: List[ApprovalDecision] = []
        # Decision-record store for Panel A drill-down. Every gate ruling is
        # retained (chronological list + by-action_id index) so a trace row can
        # be expanded to its full DecisionRecord after the demo/approve/deny
        # lifecycle. This is read-only bookkeeping; it never affects routing.
        self._decision_records: List[DecisionRecord] = []
        self._decision_by_action: Dict[str, DecisionRecord] = {}

    # ----------------------------------------------------------------------
    # Mandatory enforcement path (unchanged behavior)
    # ----------------------------------------------------------------------
    def receive_action(
        self,
        proposed_action: ProposedAction,
        session_context: SessionContext,
    ) -> ExecutorResult:
        """Intake -> gate -> dispatch, recording a TraceEntry for every action."""
        decision_record = self.evaluate(proposed_action, session_context)
        self._retain_decision(proposed_action, decision_record)
        result = self.dispatch(proposed_action, decision_record)
        self._record_decision(proposed_action, session_context, decision_record, result)
        return result

    def evaluate(
        self,
        proposed_action: ProposedAction,
        session_context: SessionContext,
    ) -> DecisionRecord:
        """Ask the PolicyGate for a ruling on the action (the only decision point)."""
        return self.policy_gate.evaluate(proposed_action, session_context)

    def dispatch(
        self,
        proposed_action: ProposedAction,
        decision: DecisionRecord,
    ) -> ExecutorResult:
        """Route per ruling. Requires a DecisionRecord — no bypass to the Executor."""
        if decision.decision is Decision.ALLOW:
            return self.executor.execute(proposed_action)

        if decision.decision is Decision.BLOCK:
            return ExecutorResult.BLOCKED

        if decision.decision is Decision.DELAY:
            # Persist the gate's reason as durable audit data (reason_held) so it
            # survives the later approve/deny resolution.
            self.queue_manager.enqueue(proposed_action, reason=decision.reason)
            return ExecutorResult.WAITING

        return ExecutorResult.BLOCKED

    # ----------------------------------------------------------------------
    # Human approval runtime
    # ----------------------------------------------------------------------
    def approve(self, approval_id: str, user_credential: str) -> ApprovalDecision:
        """
        Approve a queued action and RESUME it through the existing Executor.

        Reuses ``self.executor`` (no duplicated execution logic). The
        QueueManager only permits a PENDING item to transition once, so the
        resumed action executes exactly once.
        """
        approval = self.queue_manager.approve(approval_id, user_credential)
        self._record_lifecycle(approval, "APPROVED", executor_result=None)

        # Resume the original proposed action through the reused Executor.
        result = self.executor.execute(approval.action)
        approval.resulting_fate = result
        self._record_lifecycle(approval, "EXECUTED_AFTER_APPROVAL", executor_result=result)

        return self._audit(approval, result)

    def deny(self, approval_id: str, user_credential: str) -> ApprovalDecision:
        """
        Deny a queued action. It never reaches the Executor; its fate is KILLED.
        """
        approval = self.queue_manager.deny(approval_id, user_credential)
        self._record_lifecycle(approval, "DENIED", executor_result=None)

        approval.resulting_fate = ExecutorResult.KILLED
        self._record_lifecycle(
            approval, "KILLED_AFTER_DENIAL", executor_result=ExecutorResult.KILLED
        )

        return self._audit(approval, ExecutorResult.KILLED)

    # ----------------------------------------------------------------------
    # Decision-record store (Panel A drill-down)
    # ----------------------------------------------------------------------
    def _retain_decision(
        self,
        proposed_action: ProposedAction,
        decision_record: DecisionRecord,
    ) -> None:
        """Retain a gate ruling for later drill-down by action_id (last wins)."""
        self._decision_records.append(decision_record)
        self._decision_by_action[proposed_action.action_id] = decision_record

    def decision_records(self) -> List[DecisionRecord]:
        """Return every retained gate ruling, in chronological order."""
        return list(self._decision_records)

    def get_decision_record(self, action_id: str) -> Optional[DecisionRecord]:
        """Return the retained gate ruling for ``action_id``, or None if unknown."""
        return self._decision_by_action.get(action_id)

    # ----------------------------------------------------------------------
    # Ledger / audit helpers
    # ----------------------------------------------------------------------
    def _record_decision(
        self,
        proposed_action: ProposedAction,
        session_context: SessionContext,
        decision: DecisionRecord,
        result: ExecutorResult,
    ) -> None:
        """Append the initial gate-decision TraceEntry for an action."""
        is_intervention = decision.decision in (Decision.BLOCK, Decision.DELAY)
        self.ledger.append(TraceEntry(
            entry_id=uuid.uuid4().hex,
            timestamp=_now_iso(),
            session_id=session_context.session_id,
            actor="controller",
            message=(
                f"{proposed_action.action_type} -> {decision.decision.value} "
                f"({decision.rule_id}) -> {result.value}"
            ),
            action_id=proposed_action.action_id,
            decision=decision.decision,
            executor_result=result,
            is_intervention=is_intervention,
            event_type=_DECISION_EVENT.get(decision.decision),
        ))

    def _record_lifecycle(
        self,
        approval: PendingApproval,
        event_type: str,
        executor_result: Optional[ExecutorResult],
    ) -> None:
        """Append an approval-lifecycle TraceEntry (APPROVED/DENIED/…)."""
        self.ledger.append(TraceEntry(
            entry_id=uuid.uuid4().hex,
            timestamp=_now_iso(),
            session_id=approval.action.scenario_id or "approval",
            actor="approval-runtime",
            message=(
                f"{approval.approval_id} {approval.action.action_type} "
                f"-> {event_type}"
            ),
            action_id=approval.action.action_id,
            executor_result=executor_result,
            event_type=event_type,
            user_credential=approval.user_credential,
        ))

    def _audit(
        self,
        approval: PendingApproval,
        fate: ExecutorResult,
    ) -> ApprovalDecision:
        """Record and return the ApprovalDecision for this ruling."""
        decision = ApprovalDecision(
            approval_id=approval.approval_id,
            action_id=approval.action.action_id,
            approval_status=approval.status,
            user_credential=approval.user_credential,
            decision_timestamp=approval.resolved_at,
            resulting_fate=fate,
        )
        self.approval_audit.append(decision)
        return decision
