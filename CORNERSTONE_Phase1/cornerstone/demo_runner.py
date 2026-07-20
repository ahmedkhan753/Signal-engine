"""
CORNERSTONE Phase 1 — runnable acceptance demonstration.

A deterministic, human-readable walkthrough a reviewer can execute to see the
live enforcement loop end to end:

    python -m cornerstone.demo_runner

It reuses the existing components only (build_workflow, the scripted Agent, the
Controller approval runtime, the contract summary) and finishes by running the
acceptance validator, printing PASS only if every Phase 1 criterion holds. The
printed report contains no timestamps, so the output is byte-for-byte
deterministic.
"""

from __future__ import annotations

from typing import List, Tuple

from .acceptance import validate_phase1
from .agent import DEMO_GOAL, Agent
from .contracts import build_run_summary
from .models import ProposedAction, SessionContext
from .workflow import build_workflow

_LINE = "=" * 37
_RULE = "-" * 37


def _ctx(goal: str) -> SessionContext:
    return SessionContext(
        session_id=goal,
        workflow_id=goal,
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def build_report() -> Tuple[str, bool]:
    """Run the demonstration and return (report_text, passed)."""
    out: List[str] = []

    def line(text: str = "") -> None:
        out.append(text)

    # --- Approve path: one full scripted workflow --------------------------
    controller = build_workflow(DEMO_GOAL)
    steps = Agent(controller).run(DEMO_GOAL, _ctx(DEMO_GOAL))
    entries = controller.ledger.entries()

    line(_LINE)
    line("CORNERSTONE PHASE 1 DEMO")
    line(_LINE)
    line()
    line("Goal:")
    line(DEMO_GOAL)
    line()

    # Step 1 — ALLOW, Step 2 — DELAY (the first two scripted actions).
    for idx in (0, 1):
        step, entry = steps[idx], entries[idx]
        line(f"Step {idx + 1}")
        line(step.proposed_action.action_type)
        line(entry.decision.value)
        line(step.result.value)
        line()

    # The DELAY'd item is now parked for a human.
    pending = controller.queue_manager.pending()
    line("Queue:")
    line(f"{len(pending)} pending")
    line()

    item = pending[0]
    decision = controller.approve(item.approval_id, "demo-user")
    line("Human:")
    line("APPROVE")
    line()
    line("Result:")
    line(decision.resulting_fate.value)
    line()

    # Step 3 — BLOCK (the third scripted action never executed).
    step3, entry3 = steps[2], entries[2]
    line("Step 3")
    line(step3.proposed_action.action_type)
    line(entry3.decision.value)
    line()
    line("Executor:")
    executed3 = step3.proposed_action.action_id in controller.executor.execution_log
    line("EXECUTED" if executed3 else "NOT EXECUTED")
    line()
    line(_RULE)
    line()

    # --- Deny path: a fresh workflow to prove the kill path ----------------
    deny_controller = build_workflow(DEMO_GOAL + "-deny")
    deny_controller.receive_action(ProposedAction("dn1", "send_email"), _ctx(DEMO_GOAL + "-deny"))
    deny_item = deny_controller.queue_manager.pending()[0]

    line("Deny Path (fresh workflow)")
    line()
    line("Queue:")
    line(f"{len(deny_controller.queue_manager.pending())} pending")
    line()
    deny_decision = deny_controller.deny(deny_item.approval_id, "demo-user")
    line("Human:")
    line("DENY")
    line()
    line("Result:")
    line(deny_decision.resulting_fate.value)
    line()
    line("Executor:")
    line("NOT EXECUTED" if deny_controller.executor.execution_log == [] else "EXECUTED")
    line()
    line(_RULE)
    line()

    # --- Summary + acceptance verdict --------------------------------------
    summary = build_run_summary(controller.ledger)
    line("Workflow Summary")
    line()
    line(f"ALLOW: {summary['total_allow']}")
    line(f"DELAY: {summary['total_delay']}")
    line(f"BLOCK: {summary['total_block']}")
    line()
    line(f"Human interventions: {summary['workflow_counts'][0]['human_interventions']}")
    line()

    verdict = validate_phase1()
    passed = verdict["passed"]
    if not passed:
        for check in verdict["checks"]:
            if not check["passed"]:
                line(f"FAILED: {check['id']} -> {check['detail']}")
    line("PASS" if passed else "FAIL")

    return "\n".join(out), passed


def run(printer=print) -> bool:
    """Print the demonstration report; return True if all criteria passed."""
    report, passed = build_report()
    printer(report)
    return passed


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(0 if run() else 1)
