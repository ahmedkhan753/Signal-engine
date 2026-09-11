# CORNERSTONE — Frontend Data Contracts (Section 7)

These are the **stable wire shapes** the CORNERSTONE dashboard consumes. The
frontend can be built against them now; the backend will expose them verbatim
through endpoints in a later milestone without changing their structure.

All shapes are produced by pure serializers in
[`cornerstone/contracts.py`](contracts.py). The builders **only serialize** —
they contain no business logic, mint no ids or timestamps, and recompute no
aggregates. Every builder returns a plain JSON-serializable `dict` with
**exactly** the keys documented below (no missing, no extra fields), which the
contract tests in [`test_contracts.py`](test_contracts.py) enforce.

> Conventions: all enum values are serialized as their **string** value
> (`"ALLOW"`, `"APPROVED"`, `"EXECUTED"`, …). `null` marks an unresolved or
> absent value. Timestamps are UTC ISO-8601 strings.

---

## 1. Decision Record — `build_decision_record(record)`

The gate's ruling on one proposed action. Maps directly from `DecisionRecord`.
Exposed to the frontend (Panel A drill-down) via `GET /cornerstone/decisions`
(list) and `GET /cornerstone/decisions/<action_id>` (lookup) — see `API.md`.
Decision records are retained for the whole session, so a trace row can be
expanded to its decision detail even after the action has been approved/denied.

| field | type | description |
|---|---|---|
| `action_id` | string | id of the action that was ruled on |
| `workflow_id` | string | workflow the action belongs to |
| `decision` | string | `ALLOW` \| `BLOCK` \| `DELAY` |
| `reason` | string | human-readable rationale from the rulebook |
| `rule_id` | string | rulebook entry that produced the decision |
| `live_state` | object | snapshot of session/runtime state read at decision time |
| `timestamp` | string | when the decision was made (UTC ISO-8601) |
| `sequence_index` | number | monotonic position of this decision in the gate's life |

```json
{
  "action_id": "act-1",
  "workflow_id": "wf-1",
  "decision": "ALLOW",
  "reason": "Action is a safe read with no side effects and is allowed.",
  "rule_id": "SAFE_READ_ALLOW",
  "live_state": {
    "session_id": "wf-1",
    "workflow_id": "wf-1",
    "scenario_id": "stable_deployment",
    "runtime_state": "STABLE",
    "recommended_action": null,
    "risk_level": "LOW",
    "operator_id": null,
    "read_at": "2026-07-04T08:02:14.218378+00:00"
  },
  "timestamp": "2026-07-04T08:02:14.218383+00:00",
  "sequence_index": 1
}
```

---

## 2. Pending Approval Object — `build_pending_approval(approval, workflow_id=None, reason_held=None)`

A DELAY'd action parked for a human, plus its resolution. The `resolution`
block is **all-null while `PENDING`** and is filled in on `APPROVED`/`DENIED`.
`workflow_id` and `reason_held` are passed as context (the queued item does not
carry them itself).

| field | type | description |
|---|---|---|
| `id` | string | approval/queue item id |
| `workflow_id` | string | workflow the held action belongs to |
| `proposed_action` | object | the serialized action awaiting approval |
| `reason_held` | string | why the action was held (gate reason) |
| `timestamp` | string | when the item was queued |
| `status` | string | `PENDING` \| `APPROVED` \| `DENIED` |
| `resolution.verdict` | string \| null | resolved status, else `null` |
| `resolution.user_credential` | string \| null | demo credential that resolved it |
| `resolution.decision_timestamp` | string \| null | when it was resolved |
| `resolution.resulting_fate` | string \| null | `EXECUTED` (approved) \| `KILLED` (denied) |

**PENDING:**
```json
{
  "id": "apr-1",
  "workflow_id": "wf-1",
  "proposed_action": {
    "action_id": "act-2",
    "action_type": "send_email",
    "source": null,
    "scenario_id": null,
    "risk_level": null,
    "payload": {}
  },
  "reason_held": "Action is sensitive and is deferred for human approval.",
  "timestamp": "2026-07-04T08:02:14.218451+00:00",
  "status": "PENDING",
  "resolution": {
    "verdict": null,
    "user_credential": null,
    "decision_timestamp": null,
    "resulting_fate": null
  }
}
```

> **`reason_held` is durable audit data and survives resolution.** It is the
> gate's reason for holding the action, stored on the queue item at enqueue
> time. Approving or denying an item **never** erases it — an APPROVED or DENIED
> item still carries the original `reason_held`.

**APPROVED** (same structure; denial is identical with `status: "DENIED"`,
`verdict: "DENIED"`, `resulting_fate: "KILLED"`). Note `reason_held` is retained:
```json
{
  "id": "apr-1",
  "workflow_id": "wf-1",
  "proposed_action": { "action_id": "act-2", "action_type": "send_email", "source": "agent", "scenario_id": "stable_deployment", "risk_level": null, "payload": {} },
  "reason_held": "Action is sensitive and is deferred for human approval.",
  "timestamp": "2026-07-04T08:02:14.218451+00:00",
  "status": "APPROVED",
  "resolution": {
    "verdict": "APPROVED",
    "user_credential": "demo-user:alice",
    "decision_timestamp": "2026-07-04T08:02:14.218534+00:00",
    "resulting_fate": "EXECUTED"
  }
}
```

---

## 3. Trace Entry — `build_trace_entry(entry, workflow_id=None, sequence_index=None)`

One append-only audit event from the WorkflowLedger. `workflow_id` and
`sequence_index` are passed as context (the ledger owns ordering).

| field | type | description |
|---|---|---|
| `event_type` | string | `QUEUED` \| `APPROVED` \| `DENIED` \| `EXECUTED_AFTER_APPROVAL` \| `KILLED_AFTER_DENIAL` \| `EXECUTED` \| `BLOCKED` |
| `workflow_id` | string | workflow this event belongs to |
| `action_id` | string | action the event concerns |
| `decision` | string \| null | gate decision, when applicable |
| `executor_result` | string \| null | `EXECUTED` \| `BLOCKED` \| `KILLED` \| `WAITING` |
| `message` | string | human-readable event description |
| `timestamp` | string | when the event was recorded |
| `sequence_index` | number | position of the entry in the ledger |

```json
{
  "event_type": "QUEUED",
  "workflow_id": "wf-1",
  "action_id": "act-2",
  "decision": "DELAY",
  "executor_result": "WAITING",
  "message": "send_email -> DELAY (SENSITIVE_DELAY) -> WAITING",
  "timestamp": "2026-07-04T08:02:14.218493+00:00",
  "sequence_index": 0
}
```

---

## 4. Run Summary — `build_run_summary(ledgers)`

Aggregate view for the dashboard header. Accepts one `WorkflowLedger` or an
iterable of them, and **consumes each ledger's own `summary()` decision counts**
— no counts are recomputed from raw entries here. A ledger is scoped to one
workflow; its `session_id` is used as the `workflow_id`.

**Intervention semantics** (per workflow):
- `human_interventions` counts **DELAY only** — actions a human must rule on.
  Approving/denying one later does **not** re-increment it (lifecycle trace
  entries carry no gate decision, so there is no double-counting).
- `autonomous_denials` counts **BLOCK only** — the gate refused it with no human
  in the loop.
- ALLOW increments neither.

| field | type | description |
|---|---|---|
| `total_allow` | number | total ALLOW decisions across ledgers |
| `total_delay` | number | total DELAY decisions across ledgers |
| `total_block` | number | total BLOCK decisions across ledgers |
| `workflow_counts` | array | per-workflow rows |
| `workflow_counts[].workflow_id` | string | the workflow id |
| `workflow_counts[].human_interventions` | number | DELAY count (human-in-the-loop) for that workflow |
| `workflow_counts[].autonomous_denials` | number | BLOCK count (autonomous gate denial) for that workflow |

```json
{
  "total_allow": 0,
  "total_delay": 1,
  "total_block": 1,
  "workflow_counts": [
    { "workflow_id": "wf-1", "human_interventions": 1, "autonomous_denials": 1 }
  ]
}
```

---

## 5. Approval Request — `build_approval_request(queue_item_id, verdict, user_credential="demo-user")`

The **request-body shape** for the approval endpoints (`POST /cornerstone/approve`
and `POST /cornerstone/deny`). The endpoint infers `verdict` from the route, so
the live request body needs only `queue_item_id` (+ optional `user_credential`);
this builder documents the full canonical shape. See `API.md`.

| field | type | description |
|---|---|---|
| `queue_item_id` | string | id of the pending approval to resolve |
| `verdict` | string | `APPROVE` \| `DENY` |
| `user_credential` | string | demo credential (no authentication in Phase 1) |

```json
{
  "queue_item_id": "apr-1",
  "verdict": "APPROVE",
  "user_credential": "demo-user"
}
```

---

_These contracts are stable. Endpoints added later will return/accept them
unchanged._
