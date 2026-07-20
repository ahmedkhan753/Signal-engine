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
        self.assertEqual(summary["workflow_counts"][0]["workflow_id"], "triage_incident")


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
