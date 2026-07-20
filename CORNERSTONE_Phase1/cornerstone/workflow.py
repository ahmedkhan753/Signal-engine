"""
CORNERSTONE Phase 1 — workflow wiring (Milestone 3).

Composition root for the control layer: builds a Controller with its PolicyGate,
Executor, QueueManager, and WorkflowLedger wired together. This is assembly
only — it contains no agent loop and no decision logic of its own.
"""

from __future__ import annotations

from .controller import Controller
from .executor import Executor
from .ledger import WorkflowLedger
from .policy_gate import PolicyGate
from .queue_manager import QueueManager


def build_workflow(session_id: str = "default") -> Controller:
    """Assemble and return a fully wired Controller for a session."""
    return Controller(
        policy_gate=PolicyGate(),
        executor=Executor(),
        queue_manager=QueueManager(),
        ledger=WorkflowLedger(session_id=session_id),
    )
