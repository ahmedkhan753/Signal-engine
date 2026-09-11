"""
CORNERSTONE Phase 1 — acceptance validator.

``validate_phase1()`` runs one deterministic check per Phase 1 acceptance
criterion and returns a structured result. Each check reuses the existing
components (no new architecture, no duplicated business logic) and asserts an
observable behavior of the live enforcement loop.

    {
        "passed": bool,
        "checks": [ {"id", "description", "passed", "detail"}, ... ]
    }
"""

from __future__ import annotations

import inspect
from typing import Callable, Dict, List, Tuple

from . import agent as agent_module
from .agent import DEMO_GOAL, Agent
from .contracts import build_run_summary
from .controller import Controller
from .executor import Executor
from .ledger import WorkflowLedger
from .models import ExecutorResult, ProposedAction, SessionContext
from .policy_gate import PolicyGate
from .queue_manager import QueueManager
from .workflow import build_workflow


# --------------------------------------------------------------------------
# small builders (reused by the checks)
# --------------------------------------------------------------------------
def _ctx(goal: str = "acceptance") -> SessionContext:
    return SessionContext(
        session_id=goal,
        workflow_id=goal,
        scenario_id="stable_deployment",
        runtime_state="STABLE",
        risk_level="LOW",
    )


def _pa(action_type: str, action_id: str) -> ProposedAction:
    return ProposedAction(action_id=action_id, action_type=action_type)


CheckResult = Tuple[bool, str]


# --------------------------------------------------------------------------
# individual acceptance checks
# --------------------------------------------------------------------------
def _check_blocked_never_executes() -> CheckResult:
    c = build_workflow("acc-block")
    result = c.receive_action(_pa("delete_system_file", "b1"), _ctx())
    ok = result is ExecutorResult.BLOCKED and c.executor.execution_log == []
    return ok, f"result={result.value}, executed={c.executor.execution_log}"


def _check_delayed_item_queued() -> CheckResult:
    c = build_workflow("acc-delay")
    result = c.receive_action(_pa("send_email", "d1"), _ctx())
    pending = c.queue_manager.pending()
    ok = result is ExecutorResult.WAITING and len(pending) == 1
    return ok, f"result={result.value}, pending={len(pending)}"


def _check_approval_resumes() -> CheckResult:
    c = build_workflow("acc-approve")
    c.receive_action(_pa("send_email", "a1"), _ctx())
    item = c.queue_manager.pending()[0]
    decision = c.approve(item.approval_id, "demo-user")
    ok = decision.resulting_fate is ExecutorResult.EXECUTED and c.executor.execution_log == ["a1"]
    return ok, f"fate={decision.resulting_fate.value}, executed={c.executor.execution_log}"


def _check_denial_kills() -> CheckResult:
    c = build_workflow("acc-deny")
    c.receive_action(_pa("send_email", "k1"), _ctx())
    item = c.queue_manager.pending()[0]
    decision = c.deny(item.approval_id, "demo-user")
    ok = decision.resulting_fate is ExecutorResult.KILLED and c.executor.execution_log == []
    return ok, f"fate={decision.resulting_fate.value}, executed={c.executor.execution_log}"


def _check_multiple_pending() -> CheckResult:
    c = build_workflow("acc-multi")
    for i, action_type in enumerate(("send_email", "approve_payment", "deploy_production")):
        c.receive_action(_pa(action_type, f"m{i}"), _ctx())
    pending = c.queue_manager.pending()
    ok = len(pending) == 3
    return ok, f"pending={len(pending)}"


def _check_non_blocking() -> CheckResult:
    # A DELAY parks an item but does not block subsequent processing.
    c = build_workflow("acc-nonblock")
    c.receive_action(_pa("send_email", "n1"), _ctx())     # queued (WAITING)
    c.receive_action(_pa("read_status", "n2"), _ctx())    # still flows through
    ok = len(c.queue_manager.pending()) == 1 and c.executor.execution_log == ["n2"]
    return ok, f"pending={len(c.queue_manager.pending())}, executed={c.executor.execution_log}"


def _check_intervention_count() -> CheckResult:
    # DELAY counts as a human intervention; BLOCK counts as an autonomous denial.
    # The demo produces exactly one of each (send_email DELAY, delete BLOCK).
    c = build_workflow(DEMO_GOAL)
    Agent(c).run(DEMO_GOAL, _ctx(DEMO_GOAL))
    wf = build_run_summary(c.ledger)["workflow_counts"][0]
    human = wf["human_interventions"]
    autonomous = wf["autonomous_denials"]
    ok = human == 1 and autonomous == 1
    return ok, f"human_interventions={human}, autonomous_denials={autonomous}"


def _check_live_state_evaluated() -> CheckResult:
    gate = PolicyGate()
    before = gate.live_state_read_count
    record = gate.evaluate(_pa("read_status", "l1"), _ctx())
    ok = (
        gate.live_state_read_count == before + 1
        and record.live_state_snapshot.get("runtime_state") == "STABLE"
    )
    return ok, f"reads={gate.live_state_read_count}, snapshot_state={record.live_state_snapshot.get('runtime_state')}"


def _check_executor_inaccessible_to_agent() -> CheckResult:
    src = inspect.getsource(agent_module)
    a = Agent(build_workflow("acc-agent"))
    ok = (
        "from .executor" not in src
        and not hasattr(agent_module, "Executor")
        and not hasattr(a, "executor")
        and not hasattr(a, "execute")
    )
    return ok, "agent has no executor import/attribute/execute method"


def _check_controller_mandatory() -> CheckResult:
    # (a) dispatch cannot be called without a DecisionRecord (no signature bypass)
    c = build_workflow("acc-mand")
    try:
        c.dispatch(_pa("read_status", "c1"))  # type: ignore[call-arg]
        signature_ok = False
    except TypeError:
        signature_ok = True

    # (b) the gate always runs before the executor
    order: List[str] = []
    gate, executor = PolicyGate(), Executor()
    real_eval, real_exec = gate.evaluate, executor.execute

    def spy_eval(action, ctx):
        order.append("gate")
        return real_eval(action, ctx)

    def spy_exec(action):
        order.append("exec")
        return real_exec(action)

    gate.evaluate = spy_eval        # type: ignore[assignment]
    executor.execute = spy_exec     # type: ignore[assignment]
    Controller(gate, executor, QueueManager(), WorkflowLedger("acc-mand2")).receive_action(
        _pa("read_status", "c2"), _ctx()
    )
    order_ok = order == ["gate", "exec"]

    # (c) a BLOCK never reaches the executor
    c3 = build_workflow("acc-mand3")
    c3.receive_action(_pa("delete_system_file", "c3"), _ctx())
    block_ok = c3.executor.execution_log == []

    ok = signature_ok and order_ok and block_ok
    return ok, f"signature={signature_ok}, order={order}, block_guarded={block_ok}"


def _check_deterministic_output() -> CheckResult:
    def signature():
        c = build_workflow("acc-det")
        Agent(c).run(DEMO_GOAL, _ctx("acc-det"))
        return [
            (e.event_type,
             e.decision.value if e.decision else None,
             e.executor_result.value if e.executor_result else None)
            for e in c.ledger.entries()
        ]
    first, second = signature(), signature()
    ok = first == second
    return ok, f"repeatable={ok}"


# --------------------------------------------------------------------------
# registry + entry point
# --------------------------------------------------------------------------
_CHECKS: List[Tuple[str, str, Callable[[], CheckResult]]] = [
    ("blocked_tool_never_executes", "A BLOCK'd tool never executes.", _check_blocked_never_executes),
    ("delayed_item_queued", "A DELAY'd item is queued for approval.", _check_delayed_item_queued),
    ("approval_resumes", "Approval resumes execution of the queued action.", _check_approval_resumes),
    ("denial_kills", "Denial kills the queued action (never executes).", _check_denial_kills),
    ("queue_supports_multiple_pending", "The queue holds multiple pending items.", _check_multiple_pending),
    ("non_blocking_behavior", "A DELAY does not block subsequent processing.", _check_non_blocking),
    ("workflow_intervention_count", "Workflow intervention count is tracked.", _check_intervention_count),
    ("live_state_evaluated", "Live state is evaluated on every decision.", _check_live_state_evaluated),
    ("executor_inaccessible_to_agent", "The agent cannot access the executor.", _check_executor_inaccessible_to_agent),
    ("controller_mandatory", "The controller/gate path is mandatory (no bypass).", _check_controller_mandatory),
    ("deterministic_output", "The demonstration is deterministic.", _check_deterministic_output),
]


def validate_phase1() -> Dict:
    """Run every Phase 1 acceptance check and return a structured result."""
    checks = []
    passed_all = True
    for check_id, description, fn in _CHECKS:
        ok, detail = fn()
        passed_all = passed_all and ok
        checks.append({
            "id": check_id,
            "description": description,
            "passed": ok,
            "detail": detail,
        })
    return {"passed": passed_all, "checks": checks}
