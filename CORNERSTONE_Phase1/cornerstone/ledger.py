"""
CORNERSTONE Phase 1 — WorkflowLedger operational component (Milestone 3).

Note on naming: ``cornerstone.models.WorkflowLedger`` is the *data* record
(the serializable append-only state). This module's ``WorkflowLedger`` is the
*operational* component that appends entries, summarizes the session, and
counts human interventions. The data model is imported here as
``WorkflowLedgerData`` to keep the two unambiguous.

An "intervention" is any control-layer decision that stopped or deferred an
action rather than allowing it — i.e. a BLOCK or a DELAY (``TraceEntry.
is_intervention``). ALLOW is not an intervention.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from .models import TraceEntry
from .models import WorkflowLedger as WorkflowLedgerData


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowLedger:
    """Append-only ledger of governance events for a single session."""

    def __init__(self, session_id: str = "default") -> None:
        self.session_id = session_id
        self._entries: List[TraceEntry] = []
        self.created_at: str = _now_iso()
        self.updated_at: str = self.created_at

    def append(self, entry: TraceEntry) -> None:
        """Append a TraceEntry to the ledger (append-only, never mutated)."""
        self._entries.append(entry)
        self.updated_at = _now_iso()

    def entries(self) -> List[TraceEntry]:
        """Return a shallow copy of the recorded entries (read-only view)."""
        return list(self._entries)

    def count_interventions(self) -> int:
        """Return the number of intervention events (BLOCK/DELAY) recorded."""
        return sum(1 for e in self._entries if e.is_intervention)

    def summary(self) -> Dict[str, Any]:
        """Return a summary view of the ledger for this session."""
        decisions = Counter(
            e.decision.value for e in self._entries if e.decision is not None
        )
        results = Counter(
            e.executor_result.value
            for e in self._entries
            if e.executor_result is not None
        )
        return {
            "session_id": self.session_id,
            "total_entries": len(self._entries),
            "decisions": dict(decisions),
            "results": dict(results),
            "intervention_count": self.count_interventions(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def snapshot(self) -> WorkflowLedgerData:
        """Return the serializable data record for the current ledger state."""
        return WorkflowLedgerData(
            session_id=self.session_id,
            entries=list(self._entries),
            intervention_count=self.count_interventions(),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
