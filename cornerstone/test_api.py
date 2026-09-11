"""
CORNERSTONE Phase 1 — runtime API tests (Milestone 6).

Drives the ``cornerstone_bp`` blueprint through a Flask test client. Exercises
the demo/pending/approve/deny/summary endpoints, queue + trace updates,
exactly-once execution, determinism, and error paths. In-memory only.
"""

from __future__ import annotations

import unittest

from flask import Flask

from cornerstone.api import cornerstone_bp


def make_client():
    app = Flask(__name__)
    app.register_blueprint(cornerstone_bp)
    app.testing = True
    return app.test_client()


def pending_id(client) -> str:
    items = client.get("/cornerstone/pending").get_json()["items"]
    return items[0]["id"]


DECISION_KEYS = {
    "action_id", "workflow_id", "decision", "reason",
    "rule_id", "live_state", "timestamp", "sequence_index",
}


class TestConfigAndScenarioEndpoints(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()

    def test_config_endpoint_shape(self) -> None:
        cfg = self.client.get("/cornerstone/config").get_json()
        self.assertEqual(set(cfg), {"presentation", "scenarios"})
        self.assertIn("client_name", cfg["presentation"])
        ids = {s["id"] for s in cfg["scenarios"]}
        self.assertTrue({"financial_tech", "medical_tech", "insurance_tech"} <= ids)

    def test_scenario_demo_runs_through_enforcement(self) -> None:
        data = self.client.get("/cornerstone/demo?scenario=financial_tech").get_json()
        self.assertEqual(set(data), {"goal", "steps", "summary", "pending"})
        decisions = [s["decision"] for s in data["steps"]]
        self.assertEqual(decisions, ["ALLOW", "DELAY", "BLOCK"])
        self.assertEqual(len(data["pending"]), 1)

    def test_unknown_scenario_falls_back_to_default(self) -> None:
        data = self.client.get("/cornerstone/demo?scenario=bogus").get_json()
        self.assertEqual(data["goal"], "triage_incident")

    def test_default_demo_shape_unchanged_by_scenario_feature(self) -> None:
        data = self.client.get("/cornerstone/demo").get_json()
        self.assertEqual(set(data), {"goal", "steps", "summary", "pending"})
        self.assertEqual(data["goal"], "triage_incident")


class TestResetEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()

    def test_reset_clears_session(self) -> None:
        self.client.get("/cornerstone/demo")  # populate
        resp = self.client.post("/cornerstone/reset")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["status"], "reset")
        self.assertFalse(body["active"])

    def test_polling_does_not_recreate_state_after_reset(self) -> None:
        self.client.get("/cornerstone/demo")
        self.client.post("/cornerstone/reset")
        # Read-only polling endpoints must stay empty/zeroed.
        self.assertEqual(self.client.get("/cornerstone/pending").get_json(), {"items": []})
        self.assertEqual(self.client.get("/cornerstone/decisions").get_json(), {"items": []})
        summary = self.client.get("/cornerstone/summary").get_json()
        self.assertEqual(summary["workflow_counts"], [])
        self.assertEqual(summary["total_block"], 0)
        # Polling again still does not recreate state.
        self.assertEqual(self.client.get("/cornerstone/pending").get_json(), {"items": []})


class TestAutonomousEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()

    def test_autonomous_step_shape(self) -> None:
        data = self.client.get("/cornerstone/autonomous?scenario=financial_tech").get_json()
        self.assertEqual(
            set(data),
            {"scenario", "goal", "attempted_action", "reasoning", "decision", "executed", "trace"},
        )
        self.assertEqual(set(data["attempted_action"]), {"action_id", "action_type", "label"})

    def test_vertical_attempted_actions_and_block(self) -> None:
        expected = {
            "financial_tech": "disable_security_controls",
            "medical_tech": "drop_database",
            "insurance_tech": "delete_system_file",
        }
        for scenario_id, action_type in expected.items():
            data = self.client.get(f"/cornerstone/autonomous?scenario={scenario_id}").get_json()
            with self.subTest(scenario=scenario_id):
                self.assertEqual(data["attempted_action"]["action_type"], action_type)
                self.assertEqual(data["decision"]["decision"], "BLOCK")
                self.assertFalse(data["executed"])
                self.assertNotEqual(data["attempted_action"]["label"], action_type)  # domain label

    def test_autonomous_step_feeds_drilldown_and_summary(self) -> None:
        self.client.get("/cornerstone/autonomous?scenario=medical_tech")
        decisions = self.client.get("/cornerstone/decisions").get_json()["items"]
        self.assertEqual([d["decision"] for d in decisions], ["BLOCK"])
        wf = self.client.get("/cornerstone/summary").get_json()["workflow_counts"][0]
        self.assertEqual(wf["human_interventions"], 0)
        self.assertEqual(wf["autonomous_denials"], 1)

    def test_generic_autonomous_without_scenario(self) -> None:
        data = self.client.get("/cornerstone/autonomous").get_json()
        self.assertEqual(data["attempted_action"]["action_type"], "delete_system_file")
        self.assertEqual(data["decision"]["decision"], "BLOCK")


class TestDecisionsEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()
        self.client.get("/cornerstone/demo")

    def test_list_returns_all_decision_records(self) -> None:
        data = self.client.get("/cornerstone/decisions").get_json()
        # The scripted demo makes three governed proposals.
        self.assertEqual(len(data["items"]), 3)
        decisions = {d["decision"] for d in data["items"]}
        self.assertEqual(decisions, {"ALLOW", "DELAY", "BLOCK"})

    def test_list_item_exact_shape(self) -> None:
        item = self.client.get("/cornerstone/decisions").get_json()["items"][0]
        self.assertEqual(set(item), DECISION_KEYS)
        self.assertIn("read_at", item["live_state"])

    def test_lookup_by_action_id(self) -> None:
        action_id = "triage_incident-2"  # delete_system_file -> BLOCK
        rec = self.client.get(f"/cornerstone/decisions/{action_id}").get_json()
        self.assertEqual(set(rec), DECISION_KEYS)
        self.assertEqual(rec["action_id"], action_id)
        self.assertEqual(rec["decision"], "BLOCK")
        self.assertEqual(rec["rule_id"], "DANGEROUS_BLOCK")

    def test_unknown_action_id_returns_404(self) -> None:
        resp = self.client.get("/cornerstone/decisions/nope")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.get_json())

    def test_decision_records_survive_approve_lifecycle(self) -> None:
        # Drill-down of a DELAY'd action must still resolve after it is approved.
        pid = pending_id(self.client)
        self.client.post("/cornerstone/approve", json={"queue_item_id": pid})
        rec = self.client.get("/cornerstone/decisions/triage_incident-1").get_json()
        self.assertEqual(rec["decision"], "DELAY")
        self.assertEqual(rec["rule_id"], "SENSITIVE_DELAY")

    def test_decisions_empty_without_session(self) -> None:
        # Exercise the no-active-session branch by clearing the module session.
        import cornerstone.api as api_module
        saved = api_module._session.controller
        api_module._session.controller = None
        try:
            data = self.client.get("/cornerstone/decisions").get_json()
            self.assertEqual(data, {"items": []})
        finally:
            api_module._session.controller = saved


class TestDemoEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()

    def test_demo_returns_expected_shape(self) -> None:
        data = self.client.get("/cornerstone/demo").get_json()
        self.assertEqual(set(data), {"goal", "steps", "summary", "pending"})
        self.assertEqual(data["goal"], "triage_incident")
        self.assertTrue(len(data["steps"]) >= 3)
        self.assertEqual(len(data["pending"]), 1)

    def test_demo_summary_counts(self) -> None:
        data = self.client.get("/cornerstone/demo").get_json()
        summary = data["summary"]
        self.assertEqual(summary["total_allow"], 1)
        self.assertEqual(summary["total_delay"], 1)
        self.assertEqual(summary["total_block"], 1)

    def test_demo_is_deterministic(self) -> None:
        def signature():
            data = self.client.get("/cornerstone/demo").get_json()
            steps = [(s["event_type"], s["decision"], s["executor_result"])
                     for s in data["steps"]]
            return steps, data["summary"]

        self.assertEqual(signature(), signature())

    def test_demo_restarts_session(self) -> None:
        # Approve the pending item, then restart: the queue is fresh again.
        self.client.get("/cornerstone/demo")
        self.client.post("/cornerstone/approve",
                         json={"queue_item_id": pending_id(self.client),
                               "user_credential": "demo-user"})
        self.assertEqual(self.client.get("/cornerstone/pending").get_json()["items"], [])
        self.client.get("/cornerstone/demo")  # restart
        self.assertEqual(len(self.client.get("/cornerstone/pending").get_json()["items"]), 1)


class TestPendingEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()
        self.client.get("/cornerstone/demo")

    def test_pending_lists_one_item(self) -> None:
        items = self.client.get("/cornerstone/pending").get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["proposed_action"]["action_type"], "send_email")
        self.assertEqual(items[0]["status"], "PENDING")

    def test_pending_contract_shape(self) -> None:
        item = self.client.get("/cornerstone/pending").get_json()["items"][0]
        self.assertEqual(
            set(item),
            {"id", "workflow_id", "proposed_action", "reason_held", "timestamp",
             "status", "resolution"},
        )
        self.assertEqual(
            set(item["resolution"]),
            {"verdict", "user_credential", "decision_timestamp", "resulting_fate"},
        )

    def test_empty_queue_after_resolution(self) -> None:
        self.client.post("/cornerstone/deny",
                         json={"queue_item_id": pending_id(self.client)})
        self.assertEqual(self.client.get("/cornerstone/pending").get_json()["items"], [])


class TestApproveEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()
        self.client.get("/cornerstone/demo")

    def test_approve_resumes_execution(self) -> None:
        resp = self.client.post("/cornerstone/approve",
                                json={"queue_item_id": pending_id(self.client),
                                      "user_credential": "demo-user"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(set(data), {"decision", "result", "trace"})
        self.assertEqual(data["decision"], "APPROVED")
        self.assertEqual(data["result"], "EXECUTED")

    def test_approve_updates_trace(self) -> None:
        before = len(self.client.get("/cornerstone/demo").get_json()["steps"])
        data = self.client.post("/cornerstone/approve",
                                json={"queue_item_id": pending_id(self.client)}).get_json()
        events = [t["event_type"] for t in data["trace"]]
        self.assertIn("EXECUTED_AFTER_APPROVAL", events)
        self.assertGreater(len(data["trace"]), before)

    def test_approve_updates_queue(self) -> None:
        self.client.post("/cornerstone/approve",
                         json={"queue_item_id": pending_id(self.client)})
        self.assertEqual(self.client.get("/cornerstone/pending").get_json()["items"], [])

    def test_exactly_once_execution(self) -> None:
        pid = pending_id(self.client)
        data = self.client.post("/cornerstone/approve",
                                json={"queue_item_id": pid}).get_json()
        # Exactly one resume-execution event in the trace.
        events = [t["event_type"] for t in data["trace"]]
        self.assertEqual(events.count("EXECUTED_AFTER_APPROVAL"), 1)
        # A second approval is rejected — no re-execution.
        second = self.client.post("/cornerstone/approve", json={"queue_item_id": pid})
        self.assertEqual(second.status_code, 409)


class TestDenyEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()
        self.client.get("/cornerstone/demo")

    def test_deny_kills_execution(self) -> None:
        resp = self.client.post("/cornerstone/deny",
                                json={"queue_item_id": pending_id(self.client),
                                      "user_credential": "demo-user"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["decision"], "DENIED")
        self.assertEqual(data["result"], "KILLED")

    def test_deny_trace_has_kill_event(self) -> None:
        data = self.client.post("/cornerstone/deny",
                                json={"queue_item_id": pending_id(self.client)}).get_json()
        events = [t["event_type"] for t in data["trace"]]
        self.assertIn("KILLED_AFTER_DENIAL", events)
        self.assertNotIn("EXECUTED_AFTER_APPROVAL", events)


class TestSummaryEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()

    def test_summary_shape_and_counts(self) -> None:
        self.client.get("/cornerstone/demo")
        summary = self.client.get("/cornerstone/summary").get_json()
        self.assertEqual(set(summary),
                         {"total_allow", "total_delay", "total_block", "workflow_counts"})
        self.assertEqual(summary["total_allow"], 1)
        wf = summary["workflow_counts"][0]
        self.assertEqual(wf["workflow_id"], "triage_incident")
        # DELAY -> human intervention; BLOCK -> autonomous denial; verified on
        # the live API response (not just the contract/acceptance layers).
        self.assertEqual(set(wf), {"workflow_id", "human_interventions", "autonomous_denials"})
        self.assertEqual(wf["human_interventions"], 1)   # one DELAY (send_email)
        self.assertEqual(wf["autonomous_denials"], 1)    # one BLOCK (delete_system_file)

    def test_scenario_demo_summary_split(self) -> None:
        # The DELAY/BLOCK split also holds for a config-selected scenario.
        self.client.get("/cornerstone/demo?scenario=medical_tech")
        wf = self.client.get("/cornerstone/summary").get_json()["workflow_counts"][0]
        self.assertEqual(wf["human_interventions"], 1)   # send_email -> DELAY
        self.assertEqual(wf["autonomous_denials"], 1)    # drop_database -> BLOCK


class TestErrorPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.client = make_client()
        self.client.get("/cornerstone/demo")

    def test_invalid_id_returns_404(self) -> None:
        resp = self.client.post("/cornerstone/approve",
                                json={"queue_item_id": "does-not-exist"})
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.get_json())

    def test_missing_field_returns_400(self) -> None:
        resp = self.client.post("/cornerstone/approve", json={})
        self.assertEqual(resp.status_code, 400)

    def test_repeated_approval_rejected(self) -> None:
        pid = pending_id(self.client)
        self.assertEqual(
            self.client.post("/cornerstone/approve", json={"queue_item_id": pid}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/cornerstone/approve", json={"queue_item_id": pid}).status_code,
            409,
        )

    def test_repeated_denial_rejected(self) -> None:
        pid = pending_id(self.client)
        self.assertEqual(
            self.client.post("/cornerstone/deny", json={"queue_item_id": pid}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/cornerstone/deny", json={"queue_item_id": pid}).status_code,
            409,
        )

    def test_approve_after_denial_rejected(self) -> None:
        pid = pending_id(self.client)
        self.client.post("/cornerstone/deny", json={"queue_item_id": pid})
        resp = self.client.post("/cornerstone/approve", json={"queue_item_id": pid})
        self.assertEqual(resp.status_code, 409)


if __name__ == "__main__":
    unittest.main()
