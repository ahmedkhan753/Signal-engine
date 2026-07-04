"""
CORNERSTONE Phase 1 — Executor (Milestone 3 implementation).

The Executor is the *only* component permitted to carry out an action, and it
runs strictly downstream of a PolicyGate ALLOW ruling (enforced by the
Controller). It provides its own second line of defense: it will only run
action types registered as sandboxed stub tools. Anything else is refused with
a safe failure — an unknown tool is never executed.

Phase 1 tools are pure, in-memory stubs: no filesystem, no network, no real
side effects.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .models import ExecutorResult, ProposedAction


# --------------------------------------------------------------------------
# Sandboxed stub tool handlers (pure — no real I/O or side effects)
# --------------------------------------------------------------------------
def _tool_read_file(action: ProposedAction) -> Dict[str, Any]:
    return {"tool": "read_file", "content": "<stub: file contents>"}


def _tool_read_status(action: ProposedAction) -> Dict[str, Any]:
    return {"tool": "read_status", "status": "OK"}


def _tool_get_metrics(action: ProposedAction) -> Dict[str, Any]:
    return {"tool": "get_metrics", "metrics": {"cpu": 0.12, "mem": 0.34}}


def _tool_list_services(action: ProposedAction) -> Dict[str, Any]:
    return {"tool": "list_services", "services": ["api", "worker", "scheduler"]}


ToolHandler = Callable[[ProposedAction], Dict[str, Any]]


def _make_stub(name: str) -> ToolHandler:
    """Build a pure, side-effect-free stub handler for a sensitive tool."""
    def handler(action: ProposedAction) -> Dict[str, Any]:
        return {"tool": name, "status": "done", "sandboxed": True}
    return handler


# Sensitive tools are gated behind a DELAY -> human approval. They only reach
# the Executor after the Controller resumes an APPROVED item, so they are still
# registered here (as sandboxed stubs) rather than executed on first proposal.
# Dangerous tools (e.g. delete_system_file) are deliberately NOT registered.
_SENSITIVE_TOOLS = (
    "send_email",
    "approve_payment",
    "deploy_production",
    "rotate_credentials",
    "scale_cluster",
)


class Executor:
    """Carries out approved actions via a fixed registry of sandboxed stub tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolHandler] = {
            "read_file": _tool_read_file,
            "read_status": _tool_read_status,
            "get_metrics": _tool_get_metrics,
            "list_services": _tool_list_services,
        }
        for _name in _SENSITIVE_TOOLS:
            self._tools[_name] = _make_stub(_name)
        # Observability: action_ids actually executed, and the last tool output.
        self.execution_log: List[str] = []
        self.last_output: Optional[Dict[str, Any]] = None

    def available_tools(self) -> List[str]:
        """Return the names of the registered sandboxed tools."""
        return sorted(self._tools)

    def execute(self, action: ProposedAction) -> ExecutorResult:
        """
        Execute an action's tool and report the outcome.

        Defense in depth: only registered stub tools run. An unknown tool is
        never executed — it returns a safe failure (BLOCKED) and touches
        nothing.
        """
        handler = self._tools.get(action.action_type)
        if handler is None:
            # Unknown tool: refuse safely, execute nothing.
            self.last_output = None
            return ExecutorResult.BLOCKED

        self.last_output = handler(action)
        self.execution_log.append(action.action_id)
        return ExecutorResult.EXECUTED
