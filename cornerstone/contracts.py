"""
CORNERSTONE Phase 1 — Section 7 frontend data contracts.

These builders are the *stable wire shapes* the dashboard consumes. They are
pure serializers: each takes the in-memory domain objects (DecisionRecord,
PendingApproval, TraceEntry, WorkflowLedger) plus any context the object does
not itself carry, and returns a plain JSON-serializable ``dict`` with exactly
the contracted keys — no more, no fewer.

Rules honored here:
  * No business logic. Builders only serialize; they never decide anything.
  * No recomputation of ledger aggregates — ``build_run_summary`` consumes the
    WorkflowLedger's own ``summary()`` decision counts (DELAY -> human_interventions,
    BLOCK -> autonomous_denials).
  * Deterministic: output is a pure function of the inputs (no clocks, no ids
    minted here).
  * In-memory only. No Flask, no endpoints, no persistence.

See ``CONTRACTS.md`` for the documented contract and JSON examples.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Union

from .ledger import WorkflowLedger
from .models import DecisionRecord, PendingApproval, ProposedAction, TraceEntry


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _enum(value: Any) -> Any:
    """Return an enum's string value, passing ``None`` and plain values through."""
    return value.value if isinstance(value, Enum) else value


def _serialize_action(action: ProposedAction) -> Dict[str, Any]:
    """Serialize a ProposedAction to a plain dict for embedding in a contract."""
    return {
        "action_id": action.action_id,
        "action_type": action.action_type,
        "source": action.source,
        "scenario_id": action.scenario_id,
        "risk_level": action.risk_level,
        "payload": dict(action.payload),
    }


# --------------------------------------------------------------------------
# 1. Decision Record
# --------------------------------------------------------------------------
def build_decision_record(record: DecisionRecord) -> Dict[str, Any]:
    """Serialize a DecisionRecord to the frontend decision-record contract."""
    return {
        "action_id": record.action_id,
        "workflow_id": record.workflow_id,
        "decision": _enum(record.decision),
        "reason": record.reason,
        "rule_id": record.rule_id,
        "live_state": dict(record.live_state_snapshot),
        "timestamp": record.timestamp,
        "sequence_index": record.sequence_index,
    }


# --------------------------------------------------------------------------
# 2. Pending Approval Object
# --------------------------------------------------------------------------
def build_pending_approval(
    approval: PendingApproval,
    workflow_id: Optional[str] = None,
    reason_held: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Serialize a PendingApproval to the frontend approval-object contract.

    The ``resolution`` block is all-null while PENDING and is filled in once the
    item is APPROVED or DENIED. ``workflow_id`` and ``reason_held`` are accepted
    as context because the queued item does not itself carry them.
    """
    resolved = approval.status.value != "PENDING"
    resolution = {
        "verdict": _enum(approval.status) if resolved else None,
        "user_credential": approval.user_credential if resolved else None,
        "decision_timestamp": approval.resolved_at if resolved else None,
        "resulting_fate": _enum(approval.resulting_fate) if resolved else None,
    }
    return {
        "id": approval.approval_id,
        "workflow_id": workflow_id,
        "proposed_action": _serialize_action(approval.action),
        "reason_held": reason_held if reason_held is not None else approval.reason,
        "timestamp": approval.requested_at,
        "status": _enum(approval.status),
        "resolution": resolution,
    }


# --------------------------------------------------------------------------
# 3. Trace Entry
# --------------------------------------------------------------------------
def build_trace_entry(
    entry: TraceEntry,
    workflow_id: Optional[str] = None,
    sequence_index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Serialize a TraceEntry to the frontend trace contract.

    ``workflow_id`` and ``sequence_index`` are accepted as context because a
    ledger entry does not itself carry them (the ledger owns ordering).
    """
    return {
        "event_type": entry.event_type,
        "workflow_id": workflow_id,
        "action_id": entry.action_id,
        "decision": _enum(entry.decision),
        "executor_result": _enum(entry.executor_result),
        "message": entry.message,
        "timestamp": entry.timestamp,
        "sequence_index": sequence_index,
    }


# --------------------------------------------------------------------------
# 4. Run Summary
# --------------------------------------------------------------------------
def build_run_summary(
    ledgers: Union[WorkflowLedger, Iterable[WorkflowLedger]],
) -> Dict[str, Any]:
    """
    Serialize one or more WorkflowLedgers to the frontend run-summary contract.

    Consumes each ledger's own ``summary()`` decision counts — no aggregation is
    recomputed from raw entries here. A ledger is scoped to a single workflow;
    its ``session_id`` is used as the ``workflow_id`` key.

    Intervention semantics (per workflow):
      * ``human_interventions`` counts DELAY only — an action a human must rule
        on. Approving or denying it later does NOT re-increment this count
        (lifecycle trace entries carry no gate decision).
      * ``autonomous_denials`` counts BLOCK — the gate refused it with no human
        in the loop.
      * ALLOW increments neither.
    """
    if isinstance(ledgers, WorkflowLedger):
        ledger_list: List[WorkflowLedger] = [ledgers]
    else:
        ledger_list = list(ledgers)

    total_allow = total_delay = total_block = 0
    workflow_counts: List[Dict[str, Any]] = []
    for ledger in ledger_list:
        decisions = ledger.summary()["decisions"]
        allow = decisions.get("ALLOW", 0)
        delay = decisions.get("DELAY", 0)
        block = decisions.get("BLOCK", 0)
        total_allow += allow
        total_delay += delay
        total_block += block
        workflow_counts.append({
            "workflow_id": ledger.session_id,
            "human_interventions": delay,      # DELAY only
            "autonomous_denials": block,       # BLOCK only
        })

    return {
        "total_allow": total_allow,
        "total_delay": total_delay,
        "total_block": total_block,
        "workflow_counts": workflow_counts,
    }


# --------------------------------------------------------------------------
# 5. Approval Request Contract
# --------------------------------------------------------------------------
def build_approval_request(
    queue_item_id: str,
    verdict: str,
    user_credential: str = "demo-user",
) -> Dict[str, Any]:
    """
    Build the request-body shape for the future approval endpoint.

    ``verdict`` is expected to be ``"APPROVE"`` or ``"DENY"``. This is a shape
    definition only — there is no endpoint yet.
    """
    return {
        "queue_item_id": queue_item_id,
        "verdict": verdict,
        "user_credential": user_credential,
    }
