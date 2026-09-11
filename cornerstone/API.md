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

### Presenter / stepped flow

For a stepped presenter, each "beat" is a discrete endpoint call:

1. `POST /cornerstone/reset` — clear the session between beats.
2. `GET /cornerstone/demo` (optionally `?scenario=<id>`) — run the scripted
   governance beat (ALLOW/DELAY/BLOCK).
3. `POST /cornerstone/approve` / `deny` — resolve the parked DELAY.
4. `GET /cornerstone/autonomous?scenario=<id>` — run the autonomous beat.
5. Read-only polling: `GET /cornerstone/pending` · `/summary` · `/decisions`.

**Only `/demo` and `/autonomous` create state.** After `/reset`, the read-only
polling endpoints return empty/zeroed results and cannot recreate stale state by
polling. This keeps demo beats cleanly separated.

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
    "workflow_counts": [ { "workflow_id": "triage_incident", "human_interventions": 1, "autonomous_denials": 1 } ]
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
Each item is a **pending-approval contract**. `reason_held` is the gate's stored
reason for holding the item and survives resolution unchanged (see `CONTRACTS.md §2`).

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
`workflow_counts` if no demo has been started). `human_interventions` counts
**DELAY** (human-in-the-loop); `autonomous_denials` counts **BLOCK** (autonomous
gate denial); ALLOW counts as neither. Resolving a DELAY later does not
re-increment `human_interventions`.

**Response:**
```json
{
  "total_allow": 1,
  "total_delay": 1,
  "total_block": 1,
  "workflow_counts": [ { "workflow_id": "triage_incident", "human_interventions": 1, "autonomous_denials": 1 } ]
}
```

---

## GET `/cornerstone/decisions`

List every retained gate **decision record** for the active session — the source
for the Panel A drill-down. Returns `{ "items": [] }` if no demo is running.
Records persist for the whole session, so they remain available after an action
is approved or denied.

**Response:**
```json
{
  "items": [
    { "action_id": "triage_incident-0", "workflow_id": "triage_incident", "decision": "ALLOW",
      "reason": "Action is a safe read with no side effects and is allowed.",
      "rule_id": "SAFE_READ_ALLOW", "live_state": { "runtime_state": "STABLE", "read_at": "..." },
      "timestamp": "...", "sequence_index": 1 },
    { "action_id": "triage_incident-1", "decision": "DELAY", "rule_id": "SENSITIVE_DELAY", "...": "..." },
    { "action_id": "triage_incident-2", "decision": "BLOCK", "rule_id": "DANGEROUS_BLOCK", "...": "..." }
  ]
}
```

## GET `/cornerstone/decisions/<action_id>`

Return the single **decision record** for `action_id` (the full decision-record
contract). Used by the frontend when a trace row is clicked.

**Response** `200`: a decision-record object (see `CONTRACTS.md §1`).
**Errors:** `404` unknown `action_id` → `{ "error": "..." }`.

```json
{
  "action_id": "triage_incident-2",
  "workflow_id": "triage_incident",
  "decision": "BLOCK",
  "reason": "Action is classified as dangerous/irreversible and is blocked.",
  "rule_id": "DANGEROUS_BLOCK",
  "live_state": { "runtime_state": "STABLE", "risk_level": "LOW", "read_at": "..." },
  "timestamp": "...",
  "sequence_index": 3
}
```

---

## POST `/cornerstone/reset`

Reset the presenter/demo session to empty (clean separation between beats).
After reset the read-only endpoints return empty/zeroed results and **cannot
recreate stale state by polling** — only an explicit `/demo` or `/autonomous`
call starts a new session.

**Response** `200`:
```json
{ "status": "reset", "active": false, "pending": [] }
```

---

## GET `/cornerstone/autonomous`

Run the autonomous agent as a discrete presenter step. The agent independently
derives an action from the goal + tool descriptions; the **PolicyGate decides
independently** (the verdict is never supplied by the agent or config). Optional
`?scenario=<id>` selects a vertical; without it, the generic autonomous demo runs.
The resulting controller is retained, so `/decisions` and `/summary` reflect this
step.

Vertical → domain-appropriate attempted action (all independently **BLOCK**ed):

| scenario | attempted action (agent-derived) | `action_type` | gate |
|---|---|---|---|
| `financial_tech` | unauthorized transfer (bypass fraud controls) | `disable_security_controls` | BLOCK |
| `medical_tech` | bulk-export patient records | `drop_database` | BLOCK |
| `insurance_tech` | delete claim audit trail to auto-approve | `delete_system_file` | BLOCK |

**Response** `200`:
```json
{
  "scenario": "financial_tech",
  "goal": "immediately move the flagged client funds out of the settlement account, bypassing the blocked-payment controls",
  "attempted_action": {
    "action_id": "auto-1",
    "action_type": "disable_security_controls",
    "label": "Force an unauthorized transfer by bypassing fraud controls"
  },
  "reasoning": [
    { "tool": "disable_security_controls", "label": "Force an unauthorized transfer by bypassing fraud controls", "score": 8 },
    { "tool": "read_status", "label": "Read settlement batch status", "score": 1 },
    { "tool": "approve_payment", "label": "Release a vendor payment", "score": 1 }
  ],
  "decision": { "action_id": "auto-1", "decision": "BLOCK", "rule_id": "DANGEROUS_BLOCK", "reason": "...", "live_state": { "...": "..." }, "workflow_id": "autonomous-financial_tech", "timestamp": "...", "sequence_index": 1 },
  "executed": false,
  "trace": [ { "event_type": "BLOCKED", "action_id": "auto-1", "decision": "BLOCK", "...": "..." } ]
}
```

The `decision` object is the full **decision-record contract** (`CONTRACTS.md §1`);
`trace` entries are **trace contracts** (`CONTRACTS.md §3`). Both reuse the
existing serializers — no duplicated serialization.

> **Honesty note.** The autonomous agent is a **local deterministic reasoning
> simulator, not an LLM**. It genuinely derives the action by lexical scoring of
> tool descriptions against the goal (different goals → different actions); it is
> not handed the target action, and the gate rules independently.

---

### Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/cornerstone/demo` | start/restart the demo (`?scenario=<id>` optional); steps + summary + pending |
| GET | `/cornerstone/pending` | list pending-approval items |
| POST | `/cornerstone/approve` | approve → resume execution (EXECUTED) |
| POST | `/cornerstone/deny` | deny → kill execution (KILLED) |
| GET | `/cornerstone/summary` | run summary aggregates (DELAY vs BLOCK counts) |
| GET | `/cornerstone/decisions` | list retained decision records (Panel A source) |
| GET | `/cornerstone/decisions/<action_id>` | single decision record; `404` if unknown |
| GET | `/cornerstone/config` | presentation config + scenario dropdown list |
| POST | `/cornerstone/reset` | clear the session between presenter beats |
| GET | `/cornerstone/autonomous` | autonomous step (`?scenario=<id>`); agent-derived action → gate BLOCK |

The request body for `/approve` and `/deny` matches the **approval-request
contract** (`build_approval_request`): `{ queue_item_id, verdict, user_credential }`
— the endpoint infers `verdict` from the route, so the body needs only
`queue_item_id` (+ optional `user_credential`).

---

## Frontend coordination (stepped presenter)

The endpoints below are everything the presenter walkthrough needs. **No new
endpoint is required for the autonomous / score-table beat — it reuses the
existing `GET /cornerstone/autonomous`.** All response bodies are the same
Section 7 contracts documented above; enums serialize as strings.

| Presenter action | Method + path | Query / body | Returns |
|---|---|---|---|
| Reset (between runs) | `POST /cornerstone/reset` | — | `{ status, active:false, pending:[] }` |
| Deterministic demo beat | `GET /cornerstone/demo` | `?scenario=<id>` (optional) | `{ goal, steps, summary, pending }` |
| Autonomous / score-table beat | `GET /cornerstone/autonomous` | `?scenario=<id>` (optional) | `{ scenario, goal, attempted_action, reasoning, decision, executed, trace }` |
| Pending approvals | `GET /cornerstone/pending` | — | `{ items:[pending-approval] }` |
| Approve | `POST /cornerstone/approve` | `{ queue_item_id }` | `{ decision, result, trace }` |
| Deny | `POST /cornerstone/deny` | `{ queue_item_id }` | `{ decision, result, trace }` |
| Decision drill-down (list) | `GET /cornerstone/decisions` | — | `{ items:[decision-record] }` |
| Decision drill-down (one) | `GET /cornerstone/decisions/<action_id>` | — | decision-record · `404` if unknown |
| Run summary | `GET /cornerstone/summary` | — | `{ total_allow, total_delay, total_block, workflow_counts[] }` |
| Config + scenario list | `GET /cornerstone/config` | — | `{ presentation, scenarios[] }` |

**Recommended beat sequence**

1. `GET /cornerstone/config` — load client name, labels, scenario dropdown (once).
2. `POST /cornerstone/reset` — clean slate for a run.
3. `GET /cornerstone/demo?scenario=<id>` — governance beat (ALLOW → DELAY → BLOCK).
4. `GET /cornerstone/pending` → `POST /cornerstone/approve` (or `/deny`) — resolve the DELAY.
5. `GET /cornerstone/autonomous?scenario=<id>` — autonomous beat: `attempted_action`
   (agent-derived) + `reasoning` (the score table) + `decision` (gate BLOCK).
6. Poll `GET /cornerstone/decisions`, `/summary`, `/pending` for panel state after
   any beat. These are **read-only** — after `/reset` they return empty/zeroed and
   never recreate state, so polling is safe between beats.

**Scenario ids:** `financial_tech`, `medical_tech`, `insurance_tech` (from
`GET /cornerstone/config`). An unknown/missing id falls back to a known-good
default. Each vertical's autonomous beat derives a different domain-appropriate
action (see the `GET /cornerstone/autonomous` table above), and the PolicyGate
independently returns the verdict — the frontend never computes governance logic.

**Note on hosting:** the CORNERSTONE blueprint (`cornerstone_bp`) is additive and
must be registered on a Flask app by the host (see the top of this document).
This package does not ship a standalone host app or CORS configuration; if the
integrated environment adds those, they live in that host layer, not here.
