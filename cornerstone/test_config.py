"""
CORNERSTONE Phase 1 — configuration layer tests (Track 5).

Covers presentation + scenario loading, validation, safe fallback, the three
seeded scenarios, and scaling to a new scenario with no code change (a JSON file
dropped in a temp dir). Also confirms config never touches the enforcement core.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cornerstone.config import (
    DEFAULT_PRESENTATION,
    DEFAULT_SCENARIO,
    ConfigValidationError,
    build_config_payload,
    discover_scenarios,
    load_presentation,
    load_presentation_safe,
    load_scenario,
    parse_scenario,
    select_scenario,
)

SEEDED = {"financial_tech", "medical_tech", "insurance_tech"}


def write_json(directory: Path, name: str, obj) -> Path:
    path = directory / f"{name}.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


VALID_SCENARIO = {
    "id": "energy_tech",
    "title": "Energy Tech",
    "industry": "energy",
    "framing": "SAMPLE",
    "goal": "balance the grid load",
    "context": {"scenario_id": "energy_tech", "runtime_state": "STABLE", "risk_level": "LOW"},
    "actions": [
        {"action_type": "read_status", "label": "Read grid status"},
        {"action_type": "send_email", "label": "Notify operator"},
    ],
    "sample_rules": [],
}


class TestPresentationConfig(unittest.TestCase):
    def test_valid_bundled_presentation_loads(self) -> None:
        p = load_presentation()
        self.assertTrue(p.client_name)
        self.assertIn("trace", p.panel_titles)

    def test_missing_required_field_raises(self) -> None:
        with TemporaryDirectory() as d:
            path = write_json(Path(d), "presentation", {"panel_titles": {}})
            with self.assertRaises(ConfigValidationError):
                load_presentation(path)

    def test_malformed_json_raises(self) -> None:
        with TemporaryDirectory() as d:
            path = Path(d) / "presentation.json"
            path.write_text("{ not valid json ", encoding="utf-8")
            with self.assertRaises(ConfigValidationError):
                load_presentation(path)

    def test_safe_loader_falls_back_to_default(self) -> None:
        with TemporaryDirectory() as d:
            path = write_json(Path(d), "presentation", {"oops": True})
            self.assertIs(load_presentation_safe(path), DEFAULT_PRESENTATION)


class TestScenarioConfig(unittest.TestCase):
    def test_seeded_scenarios_discoverable(self) -> None:
        ids = {s["id"] for s in discover_scenarios()}
        self.assertTrue(SEEDED.issubset(ids))

    def test_load_each_seeded_scenario(self) -> None:
        for sid in SEEDED:
            scenario = load_scenario(sid)
            self.assertEqual(scenario.id, sid)
            self.assertTrue(scenario.actions)
            self.assertTrue(scenario.goal)

    def test_missing_required_field_raises(self) -> None:
        bad = dict(VALID_SCENARIO)
        del bad["goal"]
        with self.assertRaises(ConfigValidationError):
            parse_scenario(bad)

    def test_empty_actions_raises(self) -> None:
        bad = dict(VALID_SCENARIO, actions=[])
        with self.assertRaises(ConfigValidationError):
            parse_scenario(bad)

    def test_action_without_action_type_raises(self) -> None:
        bad = dict(VALID_SCENARIO, actions=[{"label": "no type"}])
        with self.assertRaises(ConfigValidationError):
            parse_scenario(bad)

    def test_unknown_scenario_id_strict_raises(self) -> None:
        with self.assertRaises(ConfigValidationError):
            load_scenario("does_not_exist")

    def test_select_unknown_scenario_falls_back(self) -> None:
        self.assertIs(select_scenario("does_not_exist"), DEFAULT_SCENARIO)
        self.assertIs(select_scenario(None), DEFAULT_SCENARIO)

    def test_select_valid_scenario_returns_it(self) -> None:
        scenario = select_scenario("financial_tech")
        self.assertEqual(scenario.id, "financial_tech")


class TestScenarioScaling(unittest.TestCase):
    def test_new_scenario_needs_no_code_change(self) -> None:
        # Drop a brand-new scenario JSON into a temp dir and load it — no Python
        # change required to add a scenario.
        with TemporaryDirectory() as d:
            directory = Path(d)
            write_json(directory, "energy_tech", VALID_SCENARIO)
            ids = {s["id"] for s in discover_scenarios(directory)}
            self.assertIn("energy_tech", ids)
            scenario = load_scenario("energy_tech", directory)
            self.assertEqual(scenario.title, "Energy Tech")

    def test_invalid_file_skipped_by_discovery(self) -> None:
        with TemporaryDirectory() as d:
            directory = Path(d)
            write_json(directory, "good", VALID_SCENARIO)
            (directory / "bad.json").write_text("{ broken", encoding="utf-8")
            ids = {s["id"] for s in discover_scenarios(directory)}
            self.assertEqual(ids, {"energy_tech"})  # bad file skipped, not fatal


class TestScenarioAutonomousBlock(unittest.TestCase):
    AUTO = {
        "goal": "do the unauthorized thing now",
        "tools": [
            {"action_type": "read_status", "label": "Read", "description": "read", "keywords": ["read"]},
            {"action_type": "disable_security_controls", "label": "Force it",
             "description": "bypass controls", "keywords": ["bypass", "unauthorized"]},
        ],
    }

    def test_valid_autonomous_block_parses(self) -> None:
        scenario = parse_scenario(dict(VALID_SCENARIO, autonomous=self.AUTO))
        self.assertEqual(scenario.autonomous_goal, "do the unauthorized thing now")
        self.assertEqual(len(scenario.autonomous_tools), 2)
        self.assertEqual(scenario.autonomous_tools[1].action_type, "disable_security_controls")
        self.assertEqual(scenario.autonomous_tools[1].keywords, ["bypass", "unauthorized"])

    def test_absent_autonomous_block_is_optional(self) -> None:
        scenario = parse_scenario(VALID_SCENARIO)  # no autonomous key
        self.assertIsNone(scenario.autonomous_goal)
        self.assertEqual(scenario.autonomous_tools, [])

    def test_autonomous_missing_goal_raises(self) -> None:
        bad = dict(self.AUTO)
        del bad["goal"]
        with self.assertRaises(ConfigValidationError):
            parse_scenario(dict(VALID_SCENARIO, autonomous=bad))

    def test_autonomous_empty_tools_raises(self) -> None:
        with self.assertRaises(ConfigValidationError):
            parse_scenario(dict(VALID_SCENARIO, autonomous=dict(self.AUTO, tools=[])))

    def test_autonomous_tool_missing_action_type_raises(self) -> None:
        bad = {"goal": "x", "tools": [{"label": "no type", "keywords": []}]}
        with self.assertRaises(ConfigValidationError):
            parse_scenario(dict(VALID_SCENARIO, autonomous=bad))

    def test_seeded_verticals_have_autonomous_blocks(self) -> None:
        for sid in SEEDED:
            scenario = load_scenario(sid)
            self.assertTrue(scenario.autonomous_goal, sid)
            self.assertTrue(scenario.autonomous_tools, sid)

    def test_new_vertical_autonomous_needs_config_only(self) -> None:
        # Adding a vertical autonomous demo is pure config — no new Python.
        with TemporaryDirectory() as d:
            directory = Path(d)
            write_json(directory, "energy_tech", dict(VALID_SCENARIO, autonomous=self.AUTO))
            scenario = load_scenario("energy_tech", directory)
            self.assertEqual(scenario.autonomous_tools[1].action_type, "disable_security_controls")


class TestConfigPayload(unittest.TestCase):
    def test_payload_shape(self) -> None:
        payload = build_config_payload()
        self.assertEqual(set(payload), {"presentation", "scenarios"})
        self.assertIn("client_name", payload["presentation"])
        self.assertTrue(all({"id", "title", "industry"} <= set(s) for s in payload["scenarios"]))

    def test_payload_is_json_serializable(self) -> None:
        json.dumps(build_config_payload())  # must not raise


class TestConfigIsolation(unittest.TestCase):
    def test_config_module_does_not_import_enforcement_core(self) -> None:
        import inspect

        import cornerstone.config as config_module
        src = inspect.getsource(config_module)
        for forbidden in ("from .policy_gate", "from .policy_rules",
                          "from .executor", "from .controller"):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
