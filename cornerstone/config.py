"""
CORNERSTONE Phase 1 — configuration layer (presentation + swappable scenarios).

Two independent, non-developer-editable config surfaces loaded from JSON:

  * Presentation config — client name, logo reference, panel titles, labels,
    scenario framing, narrative copy.
  * Scenario config — a generic, schema-driven scenario definition (context +
    goal + demo actions + optional sample rules). New scenarios are added by
    dropping a JSON file in ``config/scenarios/`` — no Python changes required.

Hard safety boundaries:
  * This module imports NOTHING from the enforcement core (no PolicyGate, no
    executor, no rulebook). Configuration can select *inputs* (context, goal,
    which action types to propose) but can never alter the gate algorithm, the
    live-state semantics, the ALLOW/BLOCK/DELAY grammar, or create a bypass.
  * Validation happens on load. Invalid config raises ``ConfigValidationError``
    from the strict loaders, or is transparently replaced by a known-good
    default by the ``*_safe`` / ``select_scenario`` loaders — the demo never
    crashes and never runs partially-loaded invalid config.

``sample_rules`` in a scenario is placeholder governance content for the client
to author later. Phase 1 does NOT apply it to the gate — the deterministic
rulebook remains authoritative. Wiring scenario rules into enforcement is future
work and must go through the gate, never around it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_DIR = Path(__file__).parent / "config"
_SCENARIOS_DIR = _CONFIG_DIR / "scenarios"
_PRESENTATION_FILE = _CONFIG_DIR / "presentation.json"


class ConfigValidationError(Exception):
    """Raised by the strict loaders when config is missing/malformed/invalid."""


# --------------------------------------------------------------------------
# dataclasses
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PresentationConfig:
    client_name: str
    logo: Optional[str] = None
    panel_titles: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    scenario_framing: str = ""
    narrative: str = ""


@dataclass(frozen=True)
class ScenarioAction:
    action_type: str
    label: str


@dataclass(frozen=True)
class ScenarioTool:
    """
    A domain-flavored tool *description* the autonomous agent may reason over.

    ``action_type`` MUST be an action type the policy gate already classifies
    (this is what keeps enforcement authoritative and independent). ``label`` and
    ``description`` are presentation/narrative only; ``keywords`` drive the
    agent's lexical matching. Carries NO governance verdict.
    """
    action_type: str
    label: str
    description: str
    keywords: List[str]


@dataclass(frozen=True)
class ScenarioConfig:
    id: str
    title: str
    industry: str
    framing: str
    goal: str
    context: Dict[str, Any]
    actions: List[ScenarioAction]
    sample_rules: List[Dict[str, Any]]  # placeholder; NOT applied to the gate
    # Optional autonomous-demo config (goal + tool descriptions). Empty when the
    # scenario does not define an autonomous block; callers fall back to the
    # generic autonomous catalog/goal.
    autonomous_goal: Optional[str] = None
    autonomous_tools: List[ScenarioTool] = field(default_factory=list)


# --------------------------------------------------------------------------
# known-good defaults (fallback targets — never invalid)
# --------------------------------------------------------------------------
DEFAULT_PRESENTATION = PresentationConfig(
    client_name="CORNERSTONE Demo",
    logo=None,
    panel_titles={
        "trace": "Governance Trace",
        "pending": "Pending Approvals",
        "summary": "Run Summary",
    },
    labels={"approve": "Approve", "deny": "Deny"},
    scenario_framing="Deterministic Phase 1 enforcement demonstration.",
    narrative="Every agent action is governed by the policy gate.",
)

DEFAULT_SCENARIO = ScenarioConfig(
    id="default",
    title="Default Demo",
    industry="generic",
    framing="Known-good fallback scenario.",
    goal="triage_incident",
    context={"scenario_id": "default", "runtime_state": "STABLE", "risk_level": "LOW"},
    actions=[
        ScenarioAction("read_status", "Read status"),
        ScenarioAction("send_email", "Send notification"),
        ScenarioAction("delete_system_file", "Delete system file"),
    ],
    sample_rules=[],
)


# --------------------------------------------------------------------------
# parsing + validation
# --------------------------------------------------------------------------
def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigValidationError(message)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigValidationError(f"Config file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(f"Malformed JSON in {path}: {exc}") from exc
    _require(isinstance(data, dict), f"Config root must be an object: {path}")
    return data


def parse_presentation(data: Dict[str, Any]) -> PresentationConfig:
    """Validate and build a PresentationConfig (raises on invalid input)."""
    _require(isinstance(data, dict), "Presentation config must be an object.")
    _require(isinstance(data.get("client_name"), str) and data["client_name"].strip(),
             "Presentation config requires a non-empty 'client_name'.")
    panel_titles = data.get("panel_titles", {})
    labels = data.get("labels", {})
    _require(isinstance(panel_titles, dict), "'panel_titles' must be an object.")
    _require(isinstance(labels, dict), "'labels' must be an object.")
    return PresentationConfig(
        client_name=data["client_name"],
        logo=data.get("logo"),
        panel_titles={str(k): str(v) for k, v in panel_titles.items()},
        labels={str(k): str(v) for k, v in labels.items()},
        scenario_framing=str(data.get("scenario_framing", "")),
        narrative=str(data.get("narrative", "")),
    )


def parse_scenario(data: Dict[str, Any]) -> ScenarioConfig:
    """Validate and build a ScenarioConfig (raises on invalid input)."""
    _require(isinstance(data, dict), "Scenario config must be an object.")
    for key in ("id", "title", "goal"):
        _require(isinstance(data.get(key), str) and data[key].strip(),
                 f"Scenario config requires a non-empty '{key}'.")
    context = data.get("context", {})
    _require(isinstance(context, dict), "Scenario 'context' must be an object.")

    raw_actions = data.get("actions")
    _require(isinstance(raw_actions, list) and len(raw_actions) > 0,
             "Scenario 'actions' must be a non-empty list.")
    actions: List[ScenarioAction] = []
    for i, item in enumerate(raw_actions):
        _require(isinstance(item, dict), f"Scenario action #{i} must be an object.")
        _require(isinstance(item.get("action_type"), str) and item["action_type"].strip(),
                 f"Scenario action #{i} requires a non-empty 'action_type'.")
        actions.append(ScenarioAction(
            action_type=item["action_type"],
            label=str(item.get("label", item["action_type"])),
        ))

    sample_rules = data.get("sample_rules", [])
    _require(isinstance(sample_rules, list), "'sample_rules' must be a list.")

    autonomous_goal, autonomous_tools = _parse_autonomous(data.get("autonomous"))

    return ScenarioConfig(
        id=data["id"],
        title=data["title"],
        industry=str(data.get("industry", "generic")),
        framing=str(data.get("framing", "")),
        goal=data["goal"],
        context=dict(context),
        actions=actions,
        sample_rules=list(sample_rules),
        autonomous_goal=autonomous_goal,
        autonomous_tools=autonomous_tools,
    )


def _parse_autonomous(block: Any):
    """
    Validate the optional scenario ``autonomous`` block.

    Returns (goal, tools). If the block is absent, returns (None, []) so the
    caller falls back to the generic autonomous catalog. If present, it must be
    a well-formed object with a non-empty goal and a non-empty tools list.
    """
    if block is None:
        return None, []
    _require(isinstance(block, dict), "Scenario 'autonomous' must be an object.")
    _require(isinstance(block.get("goal"), str) and block["goal"].strip(),
             "Scenario 'autonomous' requires a non-empty 'goal'.")
    raw_tools = block.get("tools")
    _require(isinstance(raw_tools, list) and len(raw_tools) > 0,
             "Scenario 'autonomous.tools' must be a non-empty list.")
    tools: List[ScenarioTool] = []
    for i, item in enumerate(raw_tools):
        _require(isinstance(item, dict), f"autonomous.tools #{i} must be an object.")
        _require(isinstance(item.get("action_type"), str) and item["action_type"].strip(),
                 f"autonomous.tools #{i} requires a non-empty 'action_type'.")
        keywords = item.get("keywords", [])
        _require(isinstance(keywords, list), f"autonomous.tools #{i} 'keywords' must be a list.")
        tools.append(ScenarioTool(
            action_type=item["action_type"],
            label=str(item.get("label", item["action_type"])),
            description=str(item.get("description", "")),
            keywords=[str(k) for k in keywords],
        ))
    return block["goal"], tools


# --------------------------------------------------------------------------
# strict loaders (raise) + safe loaders (fallback)
# --------------------------------------------------------------------------
def load_presentation(path: Optional[Path] = None) -> PresentationConfig:
    """Strict: load + validate presentation config, raising on any problem."""
    return parse_presentation(_read_json(path or _PRESENTATION_FILE))


def load_presentation_safe(path: Optional[Path] = None) -> PresentationConfig:
    """Safe: return validated presentation config, or DEFAULT on any problem."""
    try:
        return load_presentation(path)
    except ConfigValidationError:
        return DEFAULT_PRESENTATION


def discover_scenarios(scenarios_dir: Optional[Path] = None) -> List[Dict[str, str]]:
    """
    Dropdown-compatible list of valid scenarios: [{id, title, industry}, ...].

    Invalid or unreadable scenario files are skipped (not fatal), so a single
    bad file never breaks the selector.
    """
    directory = scenarios_dir or _SCENARIOS_DIR
    if not directory.exists():
        return []
    found: List[Dict[str, str]] = []
    for json_file in sorted(directory.glob("*.json")):
        try:
            scenario = parse_scenario(_read_json(json_file))
        except ConfigValidationError:
            continue
        found.append({"id": scenario.id, "title": scenario.title, "industry": scenario.industry})
    return found


def load_scenario(scenario_id: str, scenarios_dir: Optional[Path] = None) -> ScenarioConfig:
    """Strict: load + validate a scenario by id, raising if missing/invalid."""
    directory = scenarios_dir or _SCENARIOS_DIR
    path = directory / f"{scenario_id}.json"
    return parse_scenario(_read_json(path))


def select_scenario(
    scenario_id: Optional[str],
    scenarios_dir: Optional[Path] = None,
) -> ScenarioConfig:
    """
    Safe: return the requested validated scenario, or DEFAULT_SCENARIO if the id
    is unknown/invalid/missing. Never raises; never returns partial config.
    """
    if not scenario_id:
        return DEFAULT_SCENARIO
    try:
        return load_scenario(scenario_id, scenarios_dir)
    except ConfigValidationError:
        return DEFAULT_SCENARIO


# --------------------------------------------------------------------------
# frontend payload
# --------------------------------------------------------------------------
def build_config_payload(scenarios_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Serialize presentation + scenario list for the frontend (dropdown-ready).
    Uses the safe loaders so a bad file degrades gracefully to defaults.
    """
    p = load_presentation_safe()
    return {
        "presentation": {
            "client_name": p.client_name,
            "logo": p.logo,
            "panel_titles": p.panel_titles,
            "labels": p.labels,
            "scenario_framing": p.scenario_framing,
            "narrative": p.narrative,
        },
        "scenarios": discover_scenarios(scenarios_dir),
    }
