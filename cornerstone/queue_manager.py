"""
CORNERSTONE Phase 1 — QueueManager (Human Approval Runtime).

Holds actions that a policy ruling deferred (DELAY) for human approval and owns
the PendingApproval *state machine*:

    PENDING --approve(cred)--> APPROVED
    PENDING --deny(cred)-----> DENIED

These methods are deterministic state transitions only — they store the demo
``user_credential`` and the decision timestamp, but they do NOT execute
anything. Resuming (or killing) execution is orchestrated by the Controller so
that the existing Executor path is reused rather than duplicated.

A transition is only valid from PENDING; approving or denying an
already-resolved item raises, which is what guarantees an approved action can
resume execution exactly once. In-memory only for Phase 1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from .models import ApprovalStatus, PendingApproval, ProposedAction


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QueueManager:
    """Manages the approval queue and lifecycle for deferred (DELAY) actions."""

    def __init__(self) -> None:
        self._approvals: Dict[str, PendingApproval] = {}
        self._seq: int = 0

    def enqueue(self, action: ProposedAction) -> PendingApproval:
        """Park an action awaiting approval; return its PendingApproval."""
        self._seq += 1
        approval = PendingApproval(
            approval_id=f"apr-{self._seq}",
            action=action,
            status=ApprovalStatus.PENDING,
            requested_at=_now_iso(),
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def get(self, approval_id: str) -> PendingApproval:
        """Return a PendingApproval by id (KeyError if unknown)."""
        return self._approvals[approval_id]

    def _resolve(
        self,
        approval_id: str,
        user_credential: str,
        status: ApprovalStatus,
    ) -> PendingApproval:
        """Transition a PENDING item to a terminal status, storing the credential."""
        approval = self._approvals[approval_id]
        if approval.status is not ApprovalStatus.PENDING:
            raise ValueError(
                f"Approval {approval_id} is already {approval.status.value}; "
                f"cannot {status.value.lower()} it again."
            )
        approval.status = status
        approval.resolved_at = _now_iso()
        approval.resolved_by = user_credential
        approval.user_credential = user_credential
        return approval

    def approve(self, approval_id: str, user_credential: str) -> PendingApproval:
        """Transition PENDING -> APPROVED (no execution here). Returns the item."""
        return self._resolve(approval_id, user_credential, ApprovalStatus.APPROVED)

    def deny(self, approval_id: str, user_credential: str) -> PendingApproval:
        """Transition PENDING -> DENIED (never executes). Returns the item."""
        return self._resolve(approval_id, user_credential, ApprovalStatus.DENIED)

    def pending(self) -> List[PendingApproval]:
        """Return all approvals still in the PENDING state."""
        return [
            a for a in self._approvals.values()
            if a.status == ApprovalStatus.PENDING
        ]
