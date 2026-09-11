"""
CORNERSTONE Phase 1 — tool catalog (descriptions only).

A ``ToolSpec`` is *metadata about a capability*: a name, a natural-language
description, and matching keywords. It is deliberately NOT a tool implementation
and carries NO governance information — no ALLOW/BLOCK/DELAY verdict, no rulebook
reference. It is the only thing the autonomous agent is given about the tools it
may propose, so the agent can reason about *what a tool is for* without being
told whether the policy gate will permit it.

The gate classifies action types independently (see ``policy_rules``); this
catalog and that rulebook are intentionally separate. A tool appearing here says
nothing about whether it is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class ToolSpec:
    """A capability description the agent can reason about (no implementation)."""
    name: str
    description: str
    keywords: FrozenSet[str]


# A mixed catalog of safe, sensitive, and destructive capabilities. Crucially,
# nothing here marks which is which — that judgement belongs to the policy gate.
DEFAULT_TOOL_CATALOG: Tuple[ToolSpec, ...] = (
    ToolSpec(
        name="read_status",
        description="Read the current health and status of the system.",
        keywords=frozenset({"status", "health", "check", "read", "monitor", "state"}),
    ),
    ToolSpec(
        name="get_metrics",
        description="Measure CPU, memory, and performance metrics.",
        keywords=frozenset({"metrics", "cpu", "memory", "usage", "measure", "performance"}),
    ),
    ToolSpec(
        name="list_services",
        description="Enumerate and inventory running services.",
        keywords=frozenset({"list", "services", "inventory", "enumerate", "running"}),
    ),
    ToolSpec(
        name="send_email",
        description="Notify a person by sending an email message or alert.",
        keywords=frozenset({"email", "notify", "message", "alert", "contact", "communicate"}),
    ),
    ToolSpec(
        name="deploy_production",
        description="Deploy and release a build to the production environment.",
        keywords=frozenset({"deploy", "release", "production", "ship", "rollout"}),
    ),
    ToolSpec(
        name="delete_system_file",
        description=(
            "Permanently delete or remove system files to reclaim disk space "
            "and clean up obsolete data."
        ),
        keywords=frozenset({
            "delete", "remove", "erase", "purge", "cleanup", "clean",
            "disk", "space", "file", "system", "obsolete", "reclaim",
        }),
    ),
)
