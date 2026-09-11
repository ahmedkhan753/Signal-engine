# CORNERSTONE Phase 1 — Acceptance

This document is the reviewer's entry point. It shows what Phase 1 delivers, how
to run the demonstration, the expected output, and which acceptance criteria are
proven automatically.

Phase 1 is a **runtime governance-control layer** that sits in front of action
execution: an agent may only *propose* actions; a policy gate rules on each one
(ALLOW / BLOCK / DELAY); allowed actions execute, blocked actions never run, and
delayed actions wait for a human who can approve (resume) or deny (kill) them.
Every step is recorded in an append-only ledger.

---

## Architecture

```
            proposes only (no executor access)
  Agent ───────────────────────────────────────┐
                                                ▼
                                         Controller.receive_action()
                                                │
                                                ▼
                                          PolicyGate.evaluate()          reads live
                                                │                         session state
                        ┌───────────────────────┼───────────────────────┐
                     ALLOW                     BLOCK                    DELAY
                        │                        │                        │
                        ▼                        ▼                        ▼
                 Executor.execute()        (never executes)      QueueManager.enqueue()
                        │                        │                        │
                        ▼                        ▼                        ▼
                   EXECUTED                   BLOCKED                  WAITING ── pending
                                                                         │
                                              Human approve / deny ──────┤
                                                                         │
                                     approve ──▶ Executor.execute() ─▶ EXECUTED (once)
                                     deny    ──▶ (never executes)   ─▶ KILLED
                        └──────────────── every step ▶ WorkflowLedger (audit) ───────┘
```

Components (all in `cornerstone/`): `agent.py`, `controller.py`, `policy_gate.py`
+ `policy_rules.py`, `executor.py`, `queue_manager.py`, `ledger.py`,
`workflow.py`, `models.py`. Serialization contracts live in `contracts.py`
(see [`CONTRACTS.md`](CONTRACTS.md)); the runtime API is `api.py` (see
[`API.md`](API.md)).

---

## How to run the demo

From the repository root:

```bash
python -m cornerstone.demo_runner                 # deterministic acceptance demo
python -m cornerstone.demo_runner --mode autonomous   # autonomous agent → BLOCK demo
python -m cornerstone.demo_runner --mode autonomous --scenario financial_tech  # vertical
python -m cornerstone.demo_runner --mode autonomous --scenario medical_tech    # vertical
python -m cornerstone.demo_runner --mode autonomous --scenario insurance_tech  # vertical
python -m cornerstone.demo_runner --mode concurrency  # non-blocking multi-workflow demo
```

Exit code `0` = PASS, `1` = FAIL. Every report is deterministic (no timestamps).
See [README.md](README.md) for the full run guide, the API/Flask demo, and
scenario/config selection.

Programmatic use:

```python
from cornerstone.demo_runner import run
from cornerstone.acceptance import validate_phase1

run()                      # prints the report, returns True/False
validate_phase1()["passed"]  # -> True
```

## Expected output

```
=====================================
CORNERSTONE PHASE 1 DEMO
=====================================

Goal:
triage_incident

Step 1
read_status
ALLOW
EXECUTED

Step 2
send_email
DELAY
WAITING

Queue:
1 pending

Human:
APPROVE

Result:
EXECUTED

Step 3
delete_system_file
BLOCK

Executor:
NOT EXECUTED

-------------------------------------

Deny Path (fresh workflow)

Queue:
1 pending

Human:
DENY

Result:
KILLED

Executor:
NOT EXECUTED

-------------------------------------

Workflow Summary

ALLOW: 1
DELAY: 1
BLOCK: 1

Human interventions (DELAY): 1
Autonomous denials (BLOCK): 1

PASS
```

---

## Acceptance checklist

Each item is verified automatically by `validate_phase1()` (in `acceptance.py`)
and covered by `test_acceptance.py`.

| # | Criterion | Check id | How it's proven |
|---|---|---|---|
| 1 | A blocked tool never executes | `blocked_tool_never_executes` | BLOCK ruling → executor log empty |
| 2 | A delayed item is queued | `delayed_item_queued` | DELAY → WAITING, one pending item |
| 3 | Approval resumes execution | `approval_resumes` | approve → fate EXECUTED, action ran |
| 4 | Denial kills execution | `denial_kills` | deny → fate KILLED, executor untouched |
| 5 | Queue supports multiple pending | `queue_supports_multiple_pending` | 3 sensitive actions → 3 pending |
| 6 | Non-blocking behavior | `non_blocking_behavior` | a DELAY parks; later action still flows |
| 7 | Workflow intervention count | `workflow_intervention_count` | summary reports human_interventions=1 (DELAY), autonomous_denials=1 (BLOCK) |
| 8 | Live state evaluated | `live_state_evaluated` | gate reads state each eval; snapshot filled |
| 9 | Executor inaccessible to agent | `executor_inaccessible_to_agent` | no import / attribute / execute on agent |
| 10 | Controller path mandatory | `controller_mandatory` | dispatch needs a decision; gate precedes exec; BLOCK guarded |
| 11 | Deterministic output | `deterministic_output` | repeated runs produce identical ledgers |

`validate_phase1()` returns `{"passed": true, "checks": [ {id, description,
passed, detail}, ... ]}`.

---

## Known limitations

* **Deterministic scripted agent** — the "LLM" is a fixed plan lookup, not a
  real model. Planning is intentionally sandboxed and repeatable.
* **In-memory only** — no persistence; restarting the process (or calling
  `GET /cornerstone/demo`) resets all state.
* **Single demo session** in the API layer; one workflow at a time over HTTP.
* **No authentication** — `user_credential` is an honestly-stored demo string.
* **Executor tools are stubs** — sandboxed handlers with no real side effects.
* **Fixed rulebook** — a small deterministic action→decision table, not a
  policy engine.

## Out of scope for Phase 1

* Frontend / dashboard UI (contracts are published in `CONTRACTS.md` for it).
* Registering the blueprint into the main app / production routing.
* Real LLM integration, external tool execution, or network calls.
* Persistence, database, queueing infrastructure, threading/async, caching.
* Multi-session / multi-tenant runtime and authn/authz.
* Any change to the VECTOR V2/V3 engine or its API — Phase 1 is fully additive.

---

## Test coverage

The full `cornerstone/` suite (`python -m unittest discover -s cornerstone -p
"test_*.py"`) covers the gate, controller/executor enforcement, agent loop,
approval runtime, Section 7 contracts, the runtime API, and this acceptance
layer.
