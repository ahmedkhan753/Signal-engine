"""
CORNERSTONE Phase 1 — PolicyGate (Milestone 2 implementation).

The PolicyGate is the single decision point of the control layer: given a
proposed action and the current session context, it returns a deterministic
ruling (ALLOW / BLOCK / DELAY) wrapped in a ``DecisionRecord``.

Determinism: the ruling is a pure function of ``action.action_type`` against
the in-memory rulebook (``policy_rules``). No LLM, no randomness. The same
action always yields the same decision, reason, and rule_id.

Live state: every evaluation reads a fresh snapshot of ``session_context`` and
records it on the DecisionRecord. This satisfies the client's "live state"
requirement — a decision is always accompanied by the state it was made under.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .models import DecisionRecord, ProposedAction, SessionContext
from .policy_rules import match_rule


def _now_iso() -> str:
    """UTC ISO-8601 timestamp for a decision."""
    return datetime.now(timezone.utc).isoformat()


class PolicyGate:
    """Evaluates proposed actions against the deterministic rulebook."""

    def __init__(self) -> None:
        # Monotonic evaluation counter — position of a ruling in this gate's life.
        self._sequence_index: int = 0
        # Observability counter: how many times live state has been read.
        self.live_state_read_count: int = 0

    def _read_live_state(self, session_context: SessionContext) -> Dict[str, Any]:
        """
        Read a fresh snapshot of the session's live state.

        Called on *every* evaluation so a ruling always reflects the state it
        was made under. Returns a plain dict (decoupled from the dataclass) so
        the snapshot is safe to serialize and store on the DecisionRecord.
        """
        self.live_state_read_count += 1
        return {
            "session_id": session_context.session_id,
            "workflow_id": session_context.workflow_id,
            "scenario_id": session_context.scenario_id,
            "runtime_state": session_context.runtime_state,
            "recommended_action": session_context.recommended_action,
            "risk_level": session_context.risk_level,
            "operator_id": session_context.operator_id,
            "read_at": _now_iso(),
        }

    def evaluate(
        self,
        proposed_action: ProposedAction,
        session_context: SessionContext,
    ) -> DecisionRecord:
        """Return a deterministic DecisionRecord (ALLOW/BLOCK/DELAY) for the action."""
        # Sequence advances once per evaluation.
        self._sequence_index += 1

        # Consult live state on every evaluation (client "live state" requirement).
        live_state_snapshot = self._read_live_state(session_context)

        # Deterministic ruling from the in-memory rulebook.
        rule = match_rule(proposed_action.action_type)

        return DecisionRecord(
            action_id=proposed_action.action_id,
            workflow_id=session_context.workflow_id,
            decision=rule.decision,
            reason=rule.reason,
            rule_id=rule.rule_id,
            live_state_snapshot=live_state_snapshot,
            timestamp=_now_iso(),
            sequence_index=self._sequence_index,
        )
