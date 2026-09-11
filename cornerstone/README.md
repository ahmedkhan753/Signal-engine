# CORNERSTONE — Phase 1 Prototype

CORNERSTONE is an additive, in-memory **governance enforcement seam** that sits
in front of action execution. An agent proposes actions toward a goal; a policy
gate independently rules **ALLOW / DELAY / BLOCK**; only allowed actions execute,
delayed actions wait for a human, and blocked actions never run.

```
Agent  ->  Controller  ->  PolicyGate  ->  ALLOW / DELAY / BLOCK  ->  Executor / Queue
```

The package is **isolated and additive**: it imports nothing from and modifies
nothing in the VECTOR V2/V3 engine. It is pure Python + Flask, fully
deterministic, in-memory (no database, no auth, no threads).

---

## 1. Prerequisites

- **Python 3.9+** (developed and tested on 3.13)
- **pip**
- The only third-party dependency is **Flask** (used by the API blueprint).

## 2. Installation / setup (fresh checkout)

From the repository root:

```bash
# (recommended) create and activate a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
```

Verify a clean import:

```bash
python -c "import cornerstone; print('CORNERSTONE import OK')"
```

## 3. Run the tests

```bash
python -m unittest discover -s cornerstone -p "test_*.py"
```

Expected: **OK** (149 tests). Optional static check:

```bash
python -m pyflakes cornerstone/
```

## 4. Deterministic Phase 1 acceptance demo

```bash
python -m cornerstone.demo_runner
```

This runs the scripted acceptance walkthrough (ALLOW → DELAY → approve → BLOCK,
plus a deny path) and the acceptance validator. Expected final line: **`PASS`**
(exit code `0`). The output is byte-for-byte deterministic. The summary reports
`Human interventions (DELAY): 1` and `Autonomous denials (BLOCK): 1`.

## 5. Autonomous agent demo

```bash
python -m cornerstone.demo_runner --mode autonomous                          # generic
python -m cornerstone.demo_runner --mode autonomous --scenario financial_tech
python -m cornerstone.demo_runner --mode autonomous --scenario medical_tech
python -m cornerstone.demo_runner --mode autonomous --scenario insurance_tech
```

A **local deterministic reasoning simulator** (not an external LLM — see
[known limitations](#10-known-limitations)) is given only a goal and a catalog of
tool *descriptions*. It scores the tools against the goal, **independently
selects** the violating action, proposes it through the Controller, and the policy
gate **BLOCKs** it — the restricted executor never runs it. Expected: **`PASS`**.

Each vertical derives a **domain-appropriate** violating action (the gate decides
independently — the verdict is never hardcoded):

| scenario | agent-derived attempt | `action_type` | gate |
|---|---|---|---|
| `financial_tech` | unauthorized transfer (bypass fraud controls) | `disable_security_controls` | BLOCK |
| `medical_tech` | bulk-export patient records | `drop_database` | BLOCK |
| `insurance_tech` | delete claim audit trail to auto-approve | `delete_system_file` | BLOCK |

## 6. Non-blocking / multi-workflow demo

```bash
python -m cornerstone.demo_runner --mode concurrency
```

Shows two independent workflows in flight: A is DELAY'd and parked while B
executes and is blocked independently, then A resumes on approval — plus multiple
pending items resolving out of order. Expected: **`PASS`**.

## 7. Flask / API demo

The API is a Flask **blueprint** (`cornerstone_bp`); register it in any Flask app:

```python
from flask import Flask
from cornerstone.api import cornerstone_bp

app = Flask(__name__)
app.register_blueprint(cornerstone_bp)
app.run(port=5000)
```

Then:

```bash
curl http://localhost:5000/cornerstone/demo         # start/restart the demo beat
curl http://localhost:5000/cornerstone/pending      # pending approvals
curl http://localhost:5000/cornerstone/summary      # run summary (DELAY vs BLOCK)
curl http://localhost:5000/cornerstone/decisions     # decision records (Panel A)
curl http://localhost:5000/cornerstone/decisions/triage_incident-2
curl -X POST http://localhost:5000/cornerstone/approve \
     -H "Content-Type: application/json" -d '{"queue_item_id":"apr-1"}'
```

### Presenter / stepped flow

```bash
curl -X POST http://localhost:5000/cornerstone/reset               # clear between beats
curl "http://localhost:5000/cornerstone/autonomous?scenario=financial_tech"  # autonomous beat
```

`POST /reset` clears the session so read-only polling (`/pending`, `/summary`,
`/decisions`) returns empty and cannot recreate stale state — only `/demo` and
`/autonomous` start a new beat.

Full request/response shapes are in [API.md](API.md) and [CONTRACTS.md](CONTRACTS.md).
For the stepped-presenter beat sequence and the exact endpoint each panel uses,
see **Frontend coordination (stepped presenter)** in [API.md](API.md) — the
autonomous / score-table beat reuses `GET /cornerstone/autonomous`; no new
endpoint is required.

## 8. Selecting scenarios / editing config

Presentation copy and demo scenarios are plain JSON under
[`config/`](config/) — editable **without touching Python**. See
[CONFIG.md](CONFIG.md) for the full guide.

```bash
curl http://localhost:5000/cornerstone/config                 # presentation + scenario list
curl "http://localhost:5000/cornerstone/demo?scenario=financial_tech"
curl "http://localhost:5000/cornerstone/demo?scenario=medical_tech"
curl "http://localhost:5000/cornerstone/demo?scenario=insurance_tech"
```

Three sample scenarios ship (Financial / Medical / Insurance Tech). Add a new one
by dropping a JSON file in `config/scenarios/` — no code change. Invalid config
never crashes the demo; it falls back to a known-good default.

## 9. Expected result

Every demo ends in **`PASS`** (exit `0`), the full test suite reports **OK**, and
`pyflakes` is clean.

## 10. Known limitations

- **The autonomous agent is a local deterministic reasoning simulator, not a
  real LLM.** The project has no LLM dependency. It genuinely *derives* its
  action from goal + tool descriptions (it is not handed the target action), but
  the "reasoning" is transparent lexical scoring, not a neural model.
- In-memory only: no persistence, no database, no authentication (`user_credential`
  is a demo string), no real concurrency infrastructure (isolation is structural,
  demonstrated sequentially/interleaved).
- The policy rulebook is a small deterministic sample set. `sample_rules` in
  scenario config is placeholder content and is **not** applied to the gate in
  Phase 1 — the deterministic rulebook is authoritative.
- The blueprint is intentionally left **unregistered**; a host app registers it.
- Phase 2 sequencing / combination-risk is out of scope.

## Documentation map

| File | Contents |
|---|---|
| [API.md](API.md) | HTTP endpoints, request/response shapes |
| [CONTRACTS.md](CONTRACTS.md) | stable frontend data contracts |
| [CONFIG.md](CONFIG.md) | how a non-developer edits config/scenarios |
| [PHASE1_ACCEPTANCE.md](PHASE1_ACCEPTANCE.md) | acceptance criteria + checklist |
