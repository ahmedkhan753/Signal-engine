"""
CORNERSTONE Phase 1 — deterministic policy rulebook.

A small, in-memory, fully deterministic rule set consumed by ``PolicyGate``.
No LLM, no randomness: an action's ``action_type`` is matched against the
rulebook and the first matching rule wins. An unknown action falls through to
``DEFAULT_RULE`` which fails *safe* by deferring for human approval (DELAY).

Rules are ordered most-restrictive first so a type that (incorrectly) appears
in more than one bucket can never be silently downgraded to ALLOW.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional

from .models import Decision


@dataclass(frozen=True)
class PolicyRule:
    """One deterministic rulebook entry."""
    rule_id: str
    decision: Decision
    reason: str
    action_types: FrozenSet[str]


# --------------------------------------------------------------------------
# Action buckets (sample rule set)
# --------------------------------------------------------------------------
# Safe, side-effect-free reads.
SAFE_READ_ACTIONS: FrozenSet[str] = frozenset({
    "read_file",
    "read_status",
    "get_metrics",
    "list_services",
    "view_dashboard",
})

# Destructive / irreversible operations that must never auto-run.
DANGEROUS_ACTIONS: FrozenSet[str] = frozenset({
    "delete_system_file",
    "drop_database",
    "shutdown_host",
    "wipe_volume",
    "disable_security_controls",
})

# Reversible-but-consequential operations requiring human sign-off.
SENSITIVE_ACTIONS: FrozenSet[str] = frozenset({
    "send_email",
    "approve_payment",
    "deploy_production",
    "rotate_credentials",
    "scale_cluster",
})


# --------------------------------------------------------------------------
# Rulebook (evaluated in order; most-restrictive first)
# --------------------------------------------------------------------------
RULEBOOK = (
    PolicyRule(
        rule_id="DANGEROUS_BLOCK",
        decision=Decision.BLOCK,
        reason="Action is classified as dangerous/irreversible and is blocked.",
        action_types=DANGEROUS_ACTIONS,
    ),
    PolicyRule(
        rule_id="SENSITIVE_DELAY",
        decision=Decision.DELAY,
        reason="Action is sensitive and is deferred for human approval.",
        action_types=SENSITIVE_ACTIONS,
    ),
    PolicyRule(
        rule_id="SAFE_READ_ALLOW",
        decision=Decision.ALLOW,
        reason="Action is a safe read with no side effects and is allowed.",
        action_types=SAFE_READ_ACTIONS,
    ),
)

# Fail-safe default: anything unrecognized is deferred, never allowed.
DEFAULT_RULE = PolicyRule(
    rule_id="DEFAULT_DELAY",
    decision=Decision.DELAY,
    reason="Action is unknown; defaulting safely to human approval (DELAY).",
    action_types=frozenset(),
)


def match_rule(action_type: Optional[str]) -> PolicyRule:
    """Return the first rulebook entry matching ``action_type``, else DEFAULT_RULE."""
    for rule in RULEBOOK:
        if action_type in rule.action_types:
            return rule
    return DEFAULT_RULE
