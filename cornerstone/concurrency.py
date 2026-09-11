"""
CORNERSTONE Phase 1 — non-blocking / multi-workflow demonstration.

The architecture already supports two workflows in flight: each ``build_workflow``
call produces an independent Controller with its own queue, executor, and ledger.
A DELAY parks an item in *that* workflow's queue and returns immediately; it does
not block any other workflow or any later action. No threads, async, or shared
mutable state are needed to show this — the isolation is structural.

This module interleaves two workflows to make the behavior visible, and shows
multiple pending items in one workflow resolving independently and out of order.
Deterministic and timestamp-free.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import ProposedAction, SessionContext
from .workflow import build_workflow

_LINE = "=" * 37
_RULE = "-" * 37


def _ctx(name: str) -> SessionContext:
    return SessionContext(
        session_id=name,
        workflow_id=name,
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def build_concurrency_report() -> Tuple[str, bool]:
    """Run the multi-workflow demonstration; return (report_text, passed)."""
    out: List[str] = []

    def line(text: str = "") -> None:
        out.append(text)

    a = build_workflow("workflow-A")
    b = build_workflow("workflow-B")
    ctx_a, ctx_b = _ctx("workflow-A"), _ctx("workflow-B")

    line(_LINE)
    line("CORNERSTONE NON-BLOCKING DEMO")
    line(_LINE)
    line()

    # 1. Workflow A proposes a sensitive action -> DELAY -> parked, returns now.
    a_delay = a.receive_action(ProposedAction("A1", "send_email"), ctx_a)
    line("Workflow A: send_email")
    line(f"  -> {a_delay.value} (parked, {len(a.queue_manager.pending())} pending)")
    line()

    # 2. Workflow B proceeds independently while A waits (non-blocking).
    b_allow = b.receive_action(ProposedAction("B1", "read_status"), ctx_b)
    line("Workflow B: read_status  (while A is waiting)")
    line(f"  -> {b_allow.value}")
    line()

    # 3. Workflow B hits a hard block — prevented, still independent of A.
    b_block = b.receive_action(ProposedAction("B2", "delete_system_file"), ctx_b)
    line("Workflow B: delete_system_file")
    line(f"  -> {b_block.value} (prevented)")
    line()

    # 4. A's human approval arrives later; A resumes and executes.
    a_item = a.queue_manager.pending()[0]
    a_decision = a.approve(a_item.approval_id, "demo-user")
    line("Workflow A: human APPROVE")
    line(f"  -> {a_decision.resulting_fate.value}")
    line()
    line(_RULE)
    line()

    # --- Independent, out-of-order resolution of multiple pending items ----
    c = build_workflow("workflow-C")
    ctx_c = _ctx("workflow-C")
    c.receive_action(ProposedAction("C1", "send_email"), ctx_c)       # apr-1
    c.receive_action(ProposedAction("C2", "approve_payment"), ctx_c)  # apr-2
    line("Workflow C: two pending items")
    line(f"  pending = {len(c.queue_manager.pending())}")
    # Resolve the second one first, then the first — order-independent.
    c.approve("apr-2", "demo-user")
    line("  approve apr-2 (second) -> resolved first")
    c.deny("apr-1", "demo-user")
    line("  deny    apr-1 (first)  -> resolved second")
    line(f"  pending now = {len(c.queue_manager.pending())}")
    line()
    line(_RULE)
    line()

    # --- Verify isolation --------------------------------------------------
    a_exec = a.executor.execution_log
    b_exec = b.executor.execution_log
    checks = {
        "A DELAY'd, B still executed (non-blocking)": (
            a_delay.value == "WAITING" and b_allow.value == "EXECUTED"
        ),
        "B BLOCK did not touch A's queue": len(a.queue_manager.pending()) == 0,
        "A resumed and executed after approval": a_exec == ["A1"],
        "B executed only its own allowed action": b_exec == ["B1"],
        "queues are independent objects": a.queue_manager is not b.queue_manager,
        "C resolved both pending out of order": len(c.queue_manager.pending()) == 0,
    }
    line("Isolation checks:")
    for label, ok in checks.items():
        line(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    line()

    passed = all(checks.values())
    line("PASS" if passed else "FAIL")
    return "\n".join(out), passed


def run_concurrency(printer=print) -> bool:
    """Print the non-blocking demonstration report; return True if it passed."""
    report, passed = build_concurrency_report()
    printer(report)
    return passed
