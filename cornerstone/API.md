# CORNERSTONE — Runtime API (Phase 1 Demo)

The runtime API exposes the CORNERSTONE live enforcement loop as a Flask
**Blueprint** (`cornerstone_bp`, defined in [`cornerstone/api.py`](api.py)). It is
pure orchestration over the existing components (`build_workflow`, the scripted
`Agent`, the Controller approval runtime, and the Section 7 contract builders in
[`contracts.py`](contracts.py) — documented in [`CONTRACTS.md`](CONTRACTS.md)).

The blueprint is **not** a standalone app. A host application registers it:

```python
from flask import Flask
from cornerstone.api import cornerstone_bp

app = Flask(__name__)
app.register_blueprint(cornerstone_bp)
```

### Demo session model

There is exactly **one** in-memory demo session — no database, persistence,
auth, threading, or cache. Calling `GET /cornerstone/demo` (re)starts it: a fresh
workflow is built and the scripted agent runs `triage_incident`, which produces
one ALLOW (`read_status`), one DELAY (`send_email`, parked for approval), and one
BLOCK (`delete_system_file`). All queue transitions go through the Controller;
the API never calls the Executor or mutates the ledger directly.

All response bodies use the Section 7 contracts. Enum values serialize as
strings; timestamps are UTC ISO-8601.

---

## GET `/cornerstone/demo`

Start (or restart) the demo. Returns the run steps (trace-entry contracts), the
run summary, and the current pending set.

**Response** (abridged; see [`CONTRACTS.md`](CONTRACTS.md) for full field tables):
```json
{
  "goal": "triage_incident",
  "steps": [
    { "event_type": "EXECUTED", "workflow_id": "triage_incident", "action_id": "triage_incident-0",
      "decision": "ALLOW", "executor_result": "EXECUTED",
      "message": "read_status -> ALLOW (SAFE_READ_ALLOW) -> EXECUTED",
      "timestamp": "2026-07-04T08:22:17.211932+00:00", "sequence_index": 0 },
    { "event_type": "QUEUED", "action_id": "triage_incident-1", "decision": "DELAY",
      "executor_result": "WAITING", "message": "send_email -> DELAY (SENSITIVE_DELAY) -> WAITING",
      "sequence_index": 1, "workflow_id": "triage_incident", "timestamp": "..." },
    { "event_type": "BLOCKED", "action_id": "triage_incident-2", "decision": "BLOCK",
      "executor_result": "BLOCKED", "message": "delete_system_file -> BLOCK (DANGEROUS_BLOCK) -> BLOCKED",
      "sequence_index": 2, "workflow_id": "triage_incident", "timestamp": "..." }
  ],
  "summary": {
    "total_allow": 1, "total_delay": 1, "total_block": 1,
    "workflow_counts": [ { "workflow_id": "triage_incident", "human_interventions": 2 } ]
  },
  "pending": [
    { "id": "apr-1", "workflow_id": "triage_incident",
      "proposed_action": { "action_id": "triage_incident-1", "action_type": "send_email",
        "source": "agent", "scenario_id": "stable_deployment", "risk_level": null,
        "payload": { "goal": "triage_incident", "step": 1 } },
      "reason_held": "Action is sensitive and is deferred for human approval.",
      "timestamp": "...", "status": "PENDING",
      "resolution": { "verdict": null, "user_credential": null,
        "decision_timestamp": null, "resulting_fate": null } }
  ]
}
```

---

## GET `/cornerstone/pending`

List the current pending-approval items (empty array if no demo is running).
Each item is a **pending-approval contract**.

**Response:**
```json
{ "items": [ { "id": "apr-1", "status": "PENDING", "proposed_action": { "action_type": "send_email", "...": "..." }, "resolution": { "verdict": null, "user_credential": null, "decision_timestamp": null, "resulting_fate": null }, "...": "..." } ] }
```

---

## POST `/cornerstone/approve`

Approve a queued item and **resume** its execution through the Controller
(reusing the same Executor, exactly once).

**Request body:**
```json
{ "queue_item_id": "apr-1", "user_credential": "demo-user" }
```
`user_credential` is optional and defaults to `"demo-user"` (no authentication).

**Response** `200` (`trace` is the full updated ledger, trace-entry contracts):
```json
{
  "decision": "APPROVED",
  "result": "EXECUTED",
  "trace": [
    { "event_type": "EXECUTED", "action_id": "triage_incident-0", "...": "..." },
    { "event_type": "QUEUED", "action_id": "triage_incident-1", "...": "..." },
    { "event_type": "BLOCKED", "action_id": "triage_incident-2", "...": "..." },
    { "event_type": "APPROVED", "action_id": "triage_incident-1", "executor_result": null, "...": "..." },
    { "event_type": "EXECUTED_AFTER_APPROVAL", "action_id": "triage_incident-1", "executor_result": "EXECUTED", "...": "..." }
  ]
}
```

**Errors:** `400` missing `queue_item_id` · `404` unknown id · `409` already
resolved (repeated approval/denial) or no active demo session. Error body:
`{ "error": "..." }`.

---

## POST `/cornerstone/deny`

Deny a queued item. It **never executes**; its fate is `KILLED`. Same request
body and error semantics as approve.

**Response** `200`:
```json
{
  "decision": "DENIED",
  "result": "KILLED",
  "trace": [
    { "event_type": "QUEUED", "action_id": "triage_incident-1", "...": "..." },
    { "event_type": "DENIED", "action_id": "triage_incident-1", "executor_result": null, "...": "..." },
    { "event_type": "KILLED_AFTER_DENIAL", "action_id": "triage_incident-1", "executor_result": "KILLED", "...": "..." }
  ]
}
```

---

## GET `/cornerstone/summary`

Return the **run-summary contract** for the active session (zeros + empty
`workflow_counts` if no demo has been started).

**Response:**
```json
{
  "total_allow": 1,
  "total_delay": 1,
  "total_block": 1,
  "workflow_counts": [ { "workflow_id": "triage_incident", "human_interventions": 2 } ]
}
```

---

### Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/cornerstone/demo` | start/restart the demo; returns steps + summary + pending |
| GET | `/cornerstone/pending` | list pending-approval items |
| POST | `/cornerstone/approve` | approve → resume execution (EXECUTED) |
| POST | `/cornerstone/deny` | deny → kill execution (KILLED) |
| GET | `/cornerstone/summary` | run summary aggregates |

The request body for `/approve` and `/deny` matches the **approval-request
contract** (`build_approval_request`): `{ queue_item_id, verdict, user_credential }`
— the endpoint infers `verdict` from the route, so the body needs only
`queue_item_id` (+ optional `user_credential`).
