# VECTOR V2 — Integrated Prototype Handoff (+ V3 Phase 1)

**Status:** V2 functionally complete, operationally coherent, deterministic.
**V3 Phase 1:** runtime governance layer additive on top of V2 — same engine,
new response fields, one new scenario.
**Date:** 2026-06-11
**Audience:** Frontend engineers, reviewers, future V3 planning.

This document is the canonical engineering handoff for VECTOR V2 with the V3
Phase 1 extension. A deeper integration walkthrough (mapping table,
file-by-file scope) lives in [INTEGRATION.md](INTEGRATION.md); both documents
describe the same system.

> V3 Phase 1 additions are summarised in [§13 below](#13-v3-phase-1--runtime-governance-layer-additive).
> §1–§12 describe the V2 system that V3 sits on top of, unchanged.

---

## 1. System Overview

VECTOR V2 is a deterministic governance evaluator with a live React dashboard.
A scenario of typed signals is sent to a Flask API; an untouched rule-based
engine produces a fully-resolved governance verdict (score, decision, risk,
status, conflicts, facets, trace); the dashboard renders that verdict directly.

There is no model, no probability, no learning. Every output is fully derived
from rules in [engine.py](engine.py), [facets.py](facets.py),
[conflicts.py](conflicts.py), [formatter.py](formatter.py) and the scenario
inputs in [scenarios.py](scenarios.py).

**Hard guarantees:**
- Byte-identical output for repeated runs of the same scenario.
- All eight scenarios produce a stable, contract-shaped response.
- The frontend never derives governance meaning — the backend owns it.

---

## 2. Architecture Summary

```
Browser (React + Vite dashboard, :5173)
   │  GET /scenarios            POST /evaluate { scenario_id }
   ▼
api.py  (Flask API layer, :8000)
   │  evaluate_signals(scenario_name, signals)
   ▼
engine.py · facets.py · conflicts.py · formatter.py · scenarios.py
   (deterministic engine — untouched by integration work)
```

| Layer | Files | Responsibility |
|---|---|---|
| Deterministic engine | [engine.py](engine.py), [facets.py](facets.py), [conflicts.py](conflicts.py), [formatter.py](formatter.py), [scenarios.py](scenarios.py) | Score, decide, escalate, explain. No I/O. |
| API layer | [api.py](api.py) | Flask routes, scenario registry, contract shaping. No governance logic. |
| Tests | [test_backend.py](test_backend.py), [vector-dashboard/scripts/smoke-test.mjs](vector-dashboard/scripts/smoke-test.mjs) | In-process backend tests + live end-to-end smoke test. |
| Dashboard | [vector-dashboard/](vector-dashboard/) | React + Vite UI. Renders the backend response. |

---

## 3. Run Instructions

### Backend (terminal 1)

```powershell
cd D:\PROJECTS\signal-engine
pip install -r requirements.txt       # first time only — single dep: flask
python api.py
# -> http://localhost:8000
```

### Frontend (terminal 2)

```powershell
cd D:\PROJECTS\signal-engine\vector-dashboard
npm install                            # first time only
npm run dev
# -> http://localhost:5173 (or next free port)
```

### Required ports

| Port | Service | Configurable via |
|---|---|---|
| `8000` | Flask API (`api.py`) | edit `app.run(...)` |
| `5173` | Vite dev server | Vite picks next free port automatically |

### Startup order

1. Start the backend first. The dashboard polls `GET /health` on mount; if the
   backend is down the dashboard renders a "backend unreachable" banner instead
   of evaluations.
2. Start the frontend second. No state needs to be primed.

### Health endpoint

```http
GET http://localhost:8000/health
-> { "status": "ok", "scenarios": ["cascading_degradation", "hidden_instability", ...] }
```

### Backend URL override

```powershell
$env:VITE_API_BASE_URL = "http://localhost:9000"
npm run dev
```

---

## 4. API Documentation

Three endpoints. All responses are `application/json`. CORS is permissive
(`Access-Control-Allow-Origin: *`) for local dev.

### `GET /health`

Returns server liveness and the registry of available scenario slugs.

```http
GET /health
```
```json
{
  "status": "ok",
  "scenarios": ["cascading_degradation", "hidden_instability",
                "observability_disagreement", "orchestration_conflict",
                "policy_constraint_violation", "rollback_trigger",
                "security_concern", "stable_deployment"]
}
```

### `GET /scenarios`

Catalogue of wired scenarios with display metadata. Canonical demo scenarios
appear first, in `demo_order`; non-canonical scenarios follow alphabetically.

```http
GET /scenarios
```
```json
{
  "scenarios": [
    { "scenario_id": "stable_deployment",           "scenario_name": "Stable Deployment",           "demo_step": "Normal",     "demo_order": 1 },
    { "scenario_id": "hidden_instability",          "scenario_name": "Hidden Instability",          "demo_step": "Conflict",   "demo_order": 2 },
    { "scenario_id": "cascading_degradation",       "scenario_name": "Cascading Degradation",       "demo_step": "Escalation", "demo_order": 3 },
    { "scenario_id": "policy_constraint_violation", "scenario_name": "Policy Constraint Violation", "demo_step": "Block",      "demo_order": 4 },
    { "scenario_id": "observability_disagreement",  "scenario_name": "Observability Disagreement",  "demo_step": null,         "demo_order": null },
    { "scenario_id": "orchestration_conflict",      "scenario_name": "Orchestration Conflict",      "demo_step": null,         "demo_order": null },
    { "scenario_id": "rollback_trigger",            "scenario_name": "Rollback Trigger",            "demo_step": null,         "demo_order": null },
    { "scenario_id": "security_concern",            "scenario_name": "Security Concern",            "demo_step": null,         "demo_order": null }
  ]
}
```

### `POST /evaluate`

Runs the deterministic engine for one scenario and returns the contract-shaped
response.

**Request:**
```http
POST /evaluate
Content-Type: application/json

{ "scenario_id": "policy_constraint_violation" }
```

**Success response:** see §5 (the schema) and §6 (full sample responses).

**Errors:**

| Status | Cause | Body |
|---|---|---|
| `400` | `scenario_id` missing or empty | `{"error": "Missing required field 'scenario_id'."}` |
| `404` | unknown `scenario_id` | `{"error": "Unknown scenario_id '...'.", "available": [...]}` |

```json
// 404 example
{
  "error": "Unknown scenario_id 'does_not_exist'.",
  "available": ["cascading_degradation", "hidden_instability", "..."]
}
```

The resolver accepts the URL slug, the original engine name (e.g.
`"Stable Deployment"`), or a loosely-cased slug — all three resolve to the same
scenario.

---

## 5. Final Response Schema

The fields below are **stable frontend contract fields** — the dashboard relies
on every one of them, and they should not be renamed without coordinated
frontend changes.

| Field | Type | Description |
|---|---|---|
| `scenario_id` | string | URL-safe slug (e.g. `stable_deployment`). |
| `scenario_name` | string | Human-readable name. |
| `alignment_score` | int (0–100) | Final alignment score after facet penalties + conflict penalties. |
| `alignment_change` | `{initial:int, final:int, reason:string}` | Score trajectory and one-line reason. |
| `decision` | `"ALLOW" \| "DELAY" \| "BLOCK"` | Final governance decision. |
| `risk_level` | `"LOW" \| "MODERATE" \| "HIGH" \| "CRITICAL"` | Engine risk band (4-level). |
| `overall_status` | `"SAFE" \| "CAUTION" \| "STOP"` | Backend-owned status. Render directly — do not derive. |
| `reason` | string | Same string as `alignment_change.reason`, lifted for convenience. |
| `decision_summary` | string | One-sentence operator-facing summary. |
| `conflicts` | `[{severity, message}]` | Detected conflicts (severities: CRITICAL / HIGH / MEDIUM). |
| `conflict_count` | int | `len(conflicts)`. |
| `facets` | array of 4 facets (see below) | System Health, Operational Risk, Security, Execution Confidence — always all four, in this order. |
| `global_trace` | array of strings | Operational narrative, one sentence per item. |
| `technical_trace` | array of strings | Per-facet / per-conflict point-deduction breakdown. |
| `hard_constraint_triggered` | boolean | `true` iff any conflict has `severity === "CRITICAL"`. |

**Facet shape:**

| Field | Type | Description |
|---|---|---|
| `id` | string | Facet slug (e.g. `system_health`). |
| `label` | string | Display label. |
| `status` | `"SAFE" \| "CAUTION" \| "STOP"` | Per-facet status (backend-owned). |
| `score` | int (0–100) | Per-facet score. |
| `summary` | string | Operator-facing facet summary. |
| `trace` | array of strings | Per-signal evaluation lines for this facet. |
| `signals` | array of signal rows (see below) | Only the signals that were present on the scenario input. |

**Signal row shape:**

| Field | Type | Description |
|---|---|---|
| `source` | string | Raw signal key (e.g. `error_rate`). |
| `sourceLabel` | string | Human label. |
| `metric` | string | Same as `source` (kept for symmetry with future telemetry sources). |
| `metricLabel` | `"Readiness signal" \| "Risk signal"` | Positive vs negative signal. |
| `statusLabel` | string | Capitalised raw value (`"High"`, `"Medium"`, `"Low"`). |
| `icon` | string | Single-character/glyph for the pill. |
| `value` | `"normal" \| "high" \| "proceed"` | Drives pill colour. `proceed` = healthy readiness; `high` = contributes risk; `normal` = neutral. |
| `conf` | float in [0,1] | Per-signal confidence. Deterministic engine → always `1.0`. |

---

## 6. Sample Responses

### `stable_deployment` (full sample)

```json
{
  "scenario_id": "stable_deployment",
  "scenario_name": "Stable Deployment",
  "alignment_score": 100,
  "alignment_change": { "initial": 100, "final": 100, "reason": "perfect alignment" },
  "decision": "ALLOW",
  "risk_level": "LOW",
  "overall_status": "SAFE",
  "reason": "perfect alignment",
  "decision_summary": "Execution allowed: system conditions are stable and aligned.",
  "conflicts": [],
  "conflict_count": 0,
  "facets": [
    {
      "id": "system_health", "label": "System Health", "status": "SAFE", "score": 100,
      "summary": "System metrics indicate stable operational behavior.",
      "trace": ["Infrastructure stability is HIGH -> no penalty", "Service latency is LOW -> no penalty", "Error rate is LOW -> no penalty"],
      "signals": [
        { "source": "infrastructure_stability", "sourceLabel": "Infrastructure stability", "metric": "infrastructure_stability", "metricLabel": "Readiness signal", "statusLabel": "High", "icon": "🏗", "value": "proceed", "conf": 1.0 },
        { "source": "service_latency", "sourceLabel": "Service latency", "metric": "service_latency", "metricLabel": "Risk signal", "statusLabel": "Low", "icon": "⏱", "value": "normal", "conf": 1.0 },
        { "source": "error_rate", "sourceLabel": "Error rate", "metric": "error_rate", "metricLabel": "Risk signal", "statusLabel": "Low", "icon": "⚠", "value": "normal", "conf": 1.0 }
      ]
    }
    /* + Operational Risk, Security, Execution Confidence — all SAFE/100 */
  ],
  "global_trace": [
    "All operational facets indicate healthy system state.",
    "Final operational posture resulted in ALLOW."
  ],
  "technical_trace": [
    "[System Health] Infrastructure stability is HIGH -> no penalty",
    "[System Health] Service latency is LOW -> no penalty",
    "[System Health] Error rate is LOW -> no penalty",
    "[Operational Risk] Deployment readiness is HIGH -> no penalty",
    "[Operational Risk] Rollback trigger is LOW -> no penalty",
    "[Operational Risk] Policy violation is LOW -> no penalty",
    "[Security] Security threat is LOW -> no penalty",
    "[Security] Active breach is LOW -> no penalty",
    "[Execution Confidence] Orchestration readiness is HIGH -> no penalty",
    "[Execution Confidence] Observability disagreement is LOW -> no penalty",
    "[Decision] ALLOW at alignment score 100/100."
  ],
  "hard_constraint_triggered": false
}
```

### `rollback_trigger` (full sample)

```json
{
  "scenario_id": "rollback_trigger",
  "scenario_name": "Rollback Trigger",
  "alignment_score": 68,
  "alignment_change": { "initial": 100, "final": 68, "reason": "unresolved operational conflicts detected" },
  "decision": "DELAY",
  "risk_level": "HIGH",
  "overall_status": "CAUTION",
  "reason": "unresolved operational conflicts detected",
  "decision_summary": "Execution delayed: unresolved conflicts require operational review before proceeding.",
  "conflicts": [
    { "severity": "HIGH", "message": "Rollback trigger accompanied by elevated error rates indicates a severe operational fault." }
  ],
  "conflict_count": 1,
  "facets": [
    { "id": "system_health", "label": "System Health", "status": "SAFE", "score": 70, "summary": "System metrics indicate stable operational behavior.",
      "trace": ["Service latency is HIGH -> -15 points", "Error rate is HIGH -> -15 points"],
      "signals": [
        { "source": "service_latency", "sourceLabel": "Service latency", "metric": "service_latency", "metricLabel": "Risk signal", "statusLabel": "High", "icon": "⏱", "value": "high", "conf": 1.0 },
        { "source": "error_rate", "sourceLabel": "Error rate", "metric": "error_rate", "metricLabel": "Risk signal", "statusLabel": "High", "icon": "⚠", "value": "high", "conf": 1.0 }
      ]
    },
    { "id": "operational_risk", "label": "Operational Risk", "status": "SAFE", "score": 85, "summary": "No significant operational risks identified.",
      "trace": ["Rollback trigger is HIGH -> -15 points"],
      "signals": [
        { "source": "rollback_trigger", "sourceLabel": "Rollback trigger", "metric": "rollback_trigger", "metricLabel": "Risk signal", "statusLabel": "High", "icon": "↩", "value": "high", "conf": 1.0 }
      ]
    },
    { "id": "security", "label": "Security", "status": "SAFE", "score": 100, "summary": "No active security threat detected.", "trace": [], "signals": [] },
    { "id": "execution_confidence", "label": "Execution Confidence", "status": "SAFE", "score": 100, "summary": "Execution confidence is high with solid observability.", "trace": [], "signals": [] }
  ],
  "global_trace": [
    "Unresolved conflict escalated governance posture: Rollback trigger accompanied by elevated error rates indicates a severe operational fault.",
    "Elevated uncertainty required execution to be paused. Final posture: DELAY."
  ],
  "technical_trace": [
    "[System Health] Service latency is HIGH -> -15 points",
    "[System Health] Error rate is HIGH -> -15 points",
    "[Operational Risk] Rollback trigger is HIGH -> -15 points",
    "[Conflict/HIGH] Rollback trigger accompanied by elevated error rates indicates a severe operational fault. (-20)",
    "[Decision] DELAY at alignment score 68/100."
  ],
  "hard_constraint_triggered": false
}
```

### `policy_constraint_violation` (full sample)

```json
{
  "scenario_id": "policy_constraint_violation",
  "scenario_name": "Policy Constraint Violation",
  "alignment_score": 0,
  "alignment_change": { "initial": 100, "final": 0, "reason": "critical hard constraint violation" },
  "decision": "BLOCK",
  "risk_level": "CRITICAL",
  "overall_status": "STOP",
  "reason": "critical hard constraint violation",
  "decision_summary": "Execution blocked: critical hard constraint or security breach detected.",
  "conflicts": [
    { "severity": "CRITICAL", "message": "Critical security breach detected." },
    { "severity": "CRITICAL", "message": "Policy constraint violation detected." }
  ],
  "conflict_count": 2,
  "facets": [
    { "id": "system_health", "label": "System Health", "status": "SAFE", "score": 100, "summary": "System metrics indicate stable operational behavior.", "trace": [], "signals": [] },
    { "id": "operational_risk", "label": "Operational Risk", "status": "SAFE", "score": 85, "summary": "No significant operational risks identified.",
      "trace": ["Deployment readiness is HIGH -> no penalty", "Policy violation is HIGH -> -15 points"],
      "signals": [
        { "source": "deployment_readiness", "sourceLabel": "Deployment readiness", "metric": "deployment_readiness", "metricLabel": "Readiness signal", "statusLabel": "High", "icon": "🚀", "value": "proceed", "conf": 1.0 },
        { "source": "policy_violation", "sourceLabel": "Policy violation", "metric": "policy_violation", "metricLabel": "Risk signal", "statusLabel": "High", "icon": "◆", "value": "high", "conf": 1.0 }
      ]
    },
    { "id": "security", "label": "Security", "status": "SAFE", "score": 85, "summary": "No active security threat detected.",
      "trace": ["Active breach is HIGH -> -15 points"],
      "signals": [
        { "source": "active_breach", "sourceLabel": "Active breach", "metric": "active_breach", "metricLabel": "Risk signal", "statusLabel": "High", "icon": "🔓", "value": "high", "conf": 1.0 }
      ]
    },
    { "id": "execution_confidence", "label": "Execution Confidence", "status": "SAFE", "score": 100, "summary": "Execution confidence is high with solid observability.", "trace": [], "signals": [] }
  ],
  "global_trace": [
    "Hard constraint violation triggered: Critical security breach detected.",
    "Hard constraint violation triggered: Policy constraint violation detected.",
    "Operational posture could not satisfy governance thresholds. Final posture: BLOCK."
  ],
  "technical_trace": [
    "[Operational Risk] Deployment readiness is HIGH -> no penalty",
    "[Operational Risk] Policy violation is HIGH -> -15 points",
    "[Security] Active breach is HIGH -> -15 points",
    "[Conflict/CRITICAL] Critical security breach detected. (-50)",
    "[Conflict/CRITICAL] Policy constraint violation detected. (-50)",
    "[Decision] BLOCK at alignment score 0/100."
  ],
  "hard_constraint_triggered": true
}
```

### Remaining scenarios (one-line summaries)

| `scenario_id` | One-line behaviour |
|---|---|
| `hidden_instability` | Score 72, but a HIGH-severity observability conflict escalates to **DELAY/CAUTION**. Dashboard shows `Engine risk · HIGH` chip + 1 conflict. |
| `observability_disagreement` | Score 75 with a HIGH observability conflict → **DELAY/CAUTION**. Same escalation path as hidden_instability. |
| `orchestration_conflict` | Score 77; deployment-readiness-vs-orchestration HIGH conflict → **DELAY/CAUTION**. |
| `cascading_degradation` | Score 63; multiple facet penalties + HIGH rollback conflict → **DELAY/CAUTION** (canonical Escalation demo step). |
| `security_concern` | HIGH `security_threat` alone → -15 facet penalty, no cross-facet conflict, score 96 → **ALLOW/SAFE**. See §8 on calibration. |

---

## 7. Scenario Matrix

The full deterministic matrix. Asserted by [test_backend.py](test_backend.py)
and [vector-dashboard/scripts/smoke-test.mjs](vector-dashboard/scripts/smoke-test.mjs);
drift breaks the build.

| `scenario_id` | Score | Decision | Status | Risk | Conflicts | Hard | Demo step |
|---|---:|---|---|---|---:|---|---|
| `stable_deployment`           | 100 | ALLOW | SAFE    | LOW      | 0 | — | Normal |
| `hidden_instability`          |  72 | DELAY | CAUTION | HIGH     | 1 | — | Conflict |
| `observability_disagreement`  |  75 | DELAY | CAUTION | HIGH     | 1 | — | — |
| `orchestration_conflict`      |  77 | DELAY | CAUTION | HIGH     | 1 | — | — |
| `rollback_trigger`            |  68 | DELAY | CAUTION | HIGH     | 1 | — | — |
| `cascading_degradation`       |  63 | DELAY | CAUTION | HIGH     | 1 | — | Escalation |
| `security_concern`            |  96 | ALLOW | SAFE    | LOW      | 0 | — | — |
| `policy_constraint_violation` |   0 | BLOCK | STOP    | CRITICAL | 2 | ✓ | Block |

Breakdown: **2 × ALLOW · 5 × DELAY · 1 × BLOCK** — all three governance paths
are exercised, and the hard-constraint render path is exercised once.

---

## 8. Governance Calibration Rules

These rules live in [engine.py](engine.py) and govern how raw facet
penalties become a final `decision` / `risk_level` / `overall_status`. They are
intentional and operationally motivated.

### Score → risk band

```
score ≥ 85  → LOW
score ≥ 70  → MODERATE
score ≥ 40  → HIGH
score <  40 → CRITICAL
```

### Risk escalation from conflicts

A conflict can only **raise** risk, never lower it.

| Conflict severity | Effect on risk |
|---|---|
| `CRITICAL` | Risk forced to `CRITICAL`. |
| `HIGH` | Risk raised to `HIGH` if currently `LOW` / `MODERATE`. |
| `MEDIUM` | Risk raised to `MODERATE` if currently `LOW`. |

### Decision rules

```
1. risk_level == CRITICAL                       → BLOCK
2. any conflict.severity == CRITICAL            → BLOCK
3. risk_level == HIGH AND any HIGH conflict     → DELAY (minimum)
4. score ≥ 70                                   → ALLOW
5. score ≥ 40                                   → DELAY
6. otherwise                                    → BLOCK
```

Rule 3 — **HIGH risk + unresolved HIGH-severity contradiction ⇒ DELAY at
minimum** — is the operational coherence guarantee. It exists so a scenario
cannot present as `ALLOW` while the engine simultaneously reports `risk=HIGH`
and an unresolved cross-facet conflict. The dashboard chip strip would show
contradictory state if this rule were absent (e.g. `Decision ALLOW · Risk HIGH
· 1 conflict`). The five DELAY scenarios in §7 all hit this path.

### `overall_status` (frontend-render only)

```
ALLOW → SAFE
DELAY → CAUTION
BLOCK → STOP
```

This is a 1:1 map and is computed by the backend so the frontend never derives
governance meaning.

### `hard_constraint_triggered`

```
true  iff  any conflict.severity == "CRITICAL"
```

This is the **STOP-path signal**. The dashboard renders a red
`⚠ Hard constraint triggered` chip when this is true. Reserved for genuine
escalation paths — `BLOCK` from low score alone does *not* set it. Only the
two hard-constraint rules in [conflicts.py](conflicts.py)
(`active_breach=HIGH` and `policy_violation=HIGH`) can produce it.

### Why these rules

- **`BLOCK` is reserved for critical paths.** A merely low score should DELAY,
  not BLOCK. BLOCK signals "an explicit governance boundary was hit" — either
  the risk band collapsed to CRITICAL or a hard constraint conflict fired.
- **HIGH risk + HIGH conflict cannot be ALLOW.** This is the operational
  coherence rule (see Rule 3 above). It prevents the dashboard ever showing
  `Decision: ALLOW` next to an unresolved HIGH-severity conflict.
- **Conflicts only escalate, never relax.** Risk is monotonic with respect to
  conflicts so the operator never sees a "softening" effect from contradictory
  evidence.

---

## 9. Frontend Integration Notes

### Source of truth

| Concern | Owner |
|---|---|
| `decision`, `overall_status`, facet `status`, `hard_constraint_triggered` | **Backend.** Frontend renders directly; never derives. |
| `risk_level` (4-level: LOW/MODERATE/HIGH/CRITICAL) | **Backend.** |
| Risk *pill* (3-level: low/medium/high) | Frontend — derived from `risk_level` via the adapter (`CRITICAL`+`HIGH` → `high`, `MODERATE` → `medium`, `LOW` → `low`). The full 4-level label is still shown verbatim in the chip strip. |
| Score animation, layout, theming, copy ordering | **Frontend.** |

### How the frontend consumes responses

1. [src/hooks/useDashboardController.js](vector-dashboard/src/hooks/useDashboardController.js)
   fetches `GET /scenarios` on mount, then `POST /evaluate` per active scenario.
2. The raw contract is passed through
   [src/adapters/mapGovernanceResponseToViewModel.js](vector-dashboard/src/adapters/mapGovernanceResponseToViewModel.js)
   — the **only file** that should change when the API contract changes.
3. The view model drives all components; no other file inspects raw API fields.
4. The `Run demo` button cycles through scenarios with `demo_order` set (1–4),
   holding each for ~3.4 s.

### Mapping philosophy

- Backend → Frontend mapping is **structural only** (field renaming, joining
  arrays, slug derivation). No governance semantics are added or removed in the
  adapter.
- If a render decision feels semantic ("should this be red?"), it belongs in
  the backend. Open an engine PR, not a dashboard PR.

### Compatibility expectations

- All 15 stable fields in §5 are guaranteed present on every successful
  `POST /evaluate` response (asserted by tests).
- `facets` is always length-4, in the order: System Health, Operational Risk,
  Security, Execution Confidence.
- `conflicts` is always an array (possibly empty); `conflict_count` always
  matches `len(conflicts)`.
- Per-signal `conf` is always `1.0` today (deterministic engine); the field
  exists to future-proof against telemetry confidence later.

The full field-by-field mapping table is in
[INTEGRATION.md §4](INTEGRATION.md#4-frontend--backend-field-mapping).

---

## 10. Known Limitations

Intentionally out of scope for V2. Listed here to preserve scope clarity for
V3 planning:

- **No persistence.** Every `POST /evaluate` is independent. No history, no
  audit log, no DB. The engine state is purely the function input.
- **No authentication or authorisation.** All endpoints are open.
- **No cloud deployment.** Runs on the dev server (`flask.app.run`). Production
  would need a real WSGI server and a non-`*` CORS origin.
- **No adaptive learning.** The engine is fixed-rule; nothing is learned from
  prior evaluations.
- **No real-time telemetry.** The dashboard only renders scenarios chosen by
  the operator. No streaming, no push, no subscriptions.
- **No autonomous governance.** Nothing acts on a decision — `BLOCK` does not
  halt anything outside the dashboard, `DELAY` schedules nothing.
- **No database.** Scenario definitions live in [scenarios.py](scenarios.py)
  as Python literals.
- **Uniform per-signal confidence (`1.0`).** The deterministic engine has no
  telemetry-confidence concept; confidence bars are decorative.

---

## 11. Validation / Test Results

All validations are reproducible from this commit.

### Backend (in-process, no server)

```powershell
python test_backend.py
```
- ✅ Registry covers every engine scenario, metadata covers every registry id.
- ✅ Canonical demo flow is `Normal → Conflict → Escalation → Block`.
- ✅ Each scenario is byte-identical across repeated runs (determinism).
- ✅ Each scenario matches the expected matrix (score / decision / risk /
  conflict count) — drift = build failure.
- ✅ Every response has all 15 stable fields, 4 facets, valid status / decision
  enums, valid signal rows with `conf ∈ [0,1]`.
- ✅ Slug resolver round-trips.

**Result: PASS — all backend tests passed.**

### Frontend build / lint

```powershell
cd vector-dashboard
npm run lint     # clean
npm run build    # clean — Vite production bundle succeeds
```

### End-to-end (backend must be running)

```powershell
node vector-dashboard/scripts/smoke-test.mjs
```
- ✅ `/scenarios` returns all 8 wired scenarios in correct demo order.
- ✅ `/evaluate` for every scenario returns a contract-shaped response.
- ✅ The **real** dashboard adapter produces a renderable view model.
- ✅ Expected matrix matches the view model (decision / alignment / risk /
  score / conflicts / hard-constraint flag).
- ✅ Two consecutive calls per scenario are byte-identical.
- ✅ Unknown `scenario_id` → 404. Missing `scenario_id` → 400.

### Summary

| Check | Status |
|---|---|
| Deterministic repeatability | ✅ Verified (backend + e2e) |
| Smoke tests | ✅ Passing |
| Frontend build | ✅ Passing |
| API contract stability | ✅ 15/15 stable fields present on every scenario |
| Schema regressions | ✅ None — matrix matches `test_backend.py` and `smoke-test.mjs` |

---

## 12. Future V3 Considerations (brief)

Not commitments — just the surface area V3 planning should weigh.

- **Engine calibration cleanup.** `security_concern` (96 → ALLOW with zero
  conflicts) is an engine choice: a HIGH `security_threat` alone gives only a
  -15 facet penalty and fires no cross-facet conflict. If `security_concern`
  should escalate, the cleanest path is a conflict-rule clause on
  `security_threat=HIGH`, not adapter / dashboard work.
- **Telemetry confidence.** If per-signal `conf` should ever be informative,
  the engine needs a confidence concept; the contract field already exists.
- **Persistence / history.** Even an in-memory ring buffer of recent
  evaluations would enable a timeline view without committing to a DB.
- **Production hardening.** Real WSGI server (`waitress` / `gunicorn`), a
  scoped CORS origin, an auth model.
- **`GET /scenarios` caching.** Currently fetched once on mount — fine for the
  prototype, may need ETags for production.

---

---

## 13. V3 Phase 1 — Runtime Governance Layer (additive)

V3 Phase 1 is an **additive layer on top of V2**. The deterministic engine
(`engine.py`, `facets.py`, `conflicts.py`, `formatter.py`) is unchanged. All V2
contract fields are preserved unchanged. No new endpoints. No new dependencies.
No database, no auth, no persistence. The frontend remains a renderer; runtime
governance meaning is backend-owned.

### 13.1 What's new

Every `/evaluate` response now includes four new top-level fields:

| Field | Type | Description |
|---|---|---|
| `runtime_state` | enum | Runtime governance state (see §13.2). |
| `recommended_action` | enum | Recommended operator action (see §13.3). |
| `timeline_events` | array of `{code, label}` | Deterministic milestone-level governance phases. |
| `evidence_packet` | object | Structured facts behind the runtime state and action. |

One new scenario was added: **`recovery_validation`** (see §13.5).

### 13.2 `runtime_state` enum

| Value | Meaning |
|---|---|
| `STABLE` | System is operationally aligned; no contradictions. |
| `CONTRADICTORY` | Signals contradict each other; coherence rule has fired. |
| `DEGRADED` | One or more facets show real degradation, not just contradiction. |
| `RECOVERY_PENDING` | System is returning from a degraded state but governance validation is still required. |
| `CONSTRAINT_LOCKED` | A hard governance constraint has been violated (CRITICAL conflict). |
| `HUMAN_REVIEW_REQUIRED` | Reserved — supported by the enum but **not assigned** to any scenario in Phase 1. |

### 13.3 `recommended_action` enum

| Value | Meaning |
|---|---|
| `CONTINUE` | Proceed; no operator action needed. |
| `DELAY_AND_REVIEW` | Pause and review the contradictions before resuming. |
| `ESCALATE_TO_OPERATOR` | Escalate to a human operator — degradation is real. |
| `BLOCK_EXECUTION` | Do not proceed; a hard constraint was hit. |
| `VALIDATE_RECOVERY` | Re-validate before resuming after a recovery. |
| `MONITOR_FOR_DRIFT` | Allowed, but watch for the elevated signal trending worse. |
| `VALIDATE_READINESS` | Re-check orchestration / deployment readiness before proceeding. |

### 13.4 Scenario → runtime mapping

The mapping is keyed by `scenario_id` and lives in
[api.py](api.py) as `SCENARIO_RUNTIME_MAPPING`. A deterministic fallback
derives the same fields from engine output for any future scenario without an
explicit mapping (not exercised today).

| `scenario_id` | `runtime_state` | `recommended_action` |
|---|---|---|
| `stable_deployment` | `STABLE` | `CONTINUE` |
| `hidden_instability` | `CONTRADICTORY` | `DELAY_AND_REVIEW` |
| `observability_disagreement` | `CONTRADICTORY` | `DELAY_AND_REVIEW` |
| `orchestration_conflict` | `CONTRADICTORY` | `VALIDATE_READINESS` |
| `rollback_trigger` | `DEGRADED` | `ESCALATE_TO_OPERATOR` |
| `cascading_degradation` | `DEGRADED` | `ESCALATE_TO_OPERATOR` |
| `security_concern` | `STABLE` | `MONITOR_FOR_DRIFT` |
| `policy_constraint_violation` | `CONSTRAINT_LOCKED` | `BLOCK_EXECUTION` |
| `recovery_validation` | `RECOVERY_PENDING` | `VALIDATE_RECOVERY` |

### 13.5 New scenario — `recovery_validation`

**Purpose.** A system that is recovering from a degraded state, but
governance validation is still required before execution can proceed.

**Signals** (defined in [scenarios.py](scenarios.py)):
```python
"Recovery Validation": {
    "infrastructure_stability": "HIGH",   # back online
    "deployment_readiness":     "HIGH",   # deployment is ready
    "orchestration_readiness":  "MEDIUM", # still validating
    "error_rate":               "MEDIUM", # clearing
    "service_latency":          "MEDIUM"  # clearing
}
```

These signals naturally fire the existing
`deployment_readiness=HIGH + orchestration_readiness ∈ {LOW,MEDIUM}` HIGH-severity
conflict rule in [conflicts.py](conflicts.py). The engine then escalates risk
to HIGH and the existing coherence rule (HIGH risk + HIGH conflict → DELAY at
minimum) produces the target posture. **No engine changes were required.**

Resulting posture:
- `alignment_score` 74 · `decision` DELAY · `overall_status` CAUTION ·
  `risk_level` HIGH · 1 HIGH conflict · `hard_constraint_triggered` false.
- `runtime_state` RECOVERY_PENDING · `recommended_action` VALIDATE_RECOVERY.

### 13.6 `timeline_events` shape

Deterministic, milestone-level. Each event is `{code: string, label: string}`.
The order is fixed:

```
REQUEST_RECEIVED
FACETS_EVALUATED
CONFLICT_ANALYZED          ← only when conflicts > 0
RISK_ESCALATED             ← only when engine raised risk above score-band base
RUNTIME_STATE_ASSIGNED
RECOMMENDED_ACTION_ASSIGNED
DECISION_FINALIZED
```

Events are never one-per-signal; they are governance phases. Labels embed
deterministic facts (counts, codes, scores) — no generated narrative.

### 13.7 `evidence_packet` shape

```jsonc
{
  "triggering_signals": [
    { "facet": "System Health", "signal": "service_latency", "value": "MEDIUM", "penalty": 8 }
    /* one entry per signal that contributed a penalty */
  ],
  "triggering_conflicts": [
    { "severity": "HIGH", "message": "..." }   // exact mirror of conflicts[]
  ],
  "risk_basis": {
    "final": "HIGH",                    // == response.risk_level
    "base_from_score": "MODERATE",      // band the score alone would give
    "escalated_by": ["HIGH"]            // severities that escalated risk; [] if no escalation
  },
  "decision_basis": "high_risk_high_conflict_escalation",
  "recommended_action_basis": "scenario_mapping"
}
```

`decision_basis` is one of:
`critical_hard_constraint`, `critical_risk_band`,
`high_risk_high_conflict_escalation`, `score_band_allow`, `score_band_delay`,
`score_band_block`.

`recommended_action_basis` is `scenario_mapping` (all 9 scenarios today) or
`derived_from_engine` (fallback for future scenarios without explicit mapping).

Evidence is composed only of facts already present in the evaluation — no
generated text.

### 13.8 Updated scenario matrix (V3 view)

| `scenario_id` | Score | Decision | Status | Risk | Conf | Hard | `runtime_state` | `recommended_action` |
|---|---:|---|---|---|---:|---|---|---|
| `stable_deployment`           | 100 | ALLOW | SAFE    | LOW      | 0 | — | `STABLE`            | `CONTINUE` |
| `hidden_instability`          |  72 | DELAY | CAUTION | HIGH     | 1 | — | `CONTRADICTORY`     | `DELAY_AND_REVIEW` |
| `observability_disagreement`  |  75 | DELAY | CAUTION | HIGH     | 1 | — | `CONTRADICTORY`     | `DELAY_AND_REVIEW` |
| `orchestration_conflict`      |  77 | DELAY | CAUTION | HIGH     | 1 | — | `CONTRADICTORY`     | `VALIDATE_READINESS` |
| `rollback_trigger`            |  68 | DELAY | CAUTION | HIGH     | 1 | — | `DEGRADED`          | `ESCALATE_TO_OPERATOR` |
| `cascading_degradation`       |  63 | DELAY | CAUTION | HIGH     | 1 | — | `DEGRADED`          | `ESCALATE_TO_OPERATOR` |
| `security_concern`            |  96 | ALLOW | SAFE    | LOW      | 0 | — | `STABLE`            | `MONITOR_FOR_DRIFT` |
| `policy_constraint_violation` |   0 | BLOCK | STOP    | CRITICAL | 2 | ✓ | `CONSTRAINT_LOCKED` | `BLOCK_EXECUTION` |
| `recovery_validation`         |  74 | DELAY | CAUTION | HIGH     | 1 | — | `RECOVERY_PENDING`  | `VALIDATE_RECOVERY` |

Asserted by [test_backend.py](test_backend.py) and
[vector-dashboard/scripts/smoke-test.mjs](vector-dashboard/scripts/smoke-test.mjs).

### 13.9 Sample V3 response (`recovery_validation`, abridged)

Full V2 fields are unchanged from §5; the additive V3 fields look like:

```json
{
  /* ... all V2 fields unchanged ... */
  "runtime_state": "RECOVERY_PENDING",
  "recommended_action": "VALIDATE_RECOVERY",
  "timeline_events": [
    { "code": "REQUEST_RECEIVED",            "label": "Evaluation request accepted for scenario 'Recovery Validation'." },
    { "code": "FACETS_EVALUATED",            "label": "4 facets evaluated; alignment score 74/100." },
    { "code": "CONFLICT_ANALYZED",           "label": "1 conflict(s) detected (severities: HIGH)." },
    { "code": "RISK_ESCALATED",              "label": "Risk escalated from base MODERATE to HIGH by conflict severity." },
    { "code": "RUNTIME_STATE_ASSIGNED",      "label": "Runtime state assigned: RECOVERY_PENDING." },
    { "code": "RECOMMENDED_ACTION_ASSIGNED", "label": "Recommended action: VALIDATE_RECOVERY." },
    { "code": "DECISION_FINALIZED",          "label": "Final decision: DELAY." }
  ],
  "evidence_packet": {
    "triggering_signals": [
      { "facet": "System Health",         "signal": "service_latency",        "value": "MEDIUM", "penalty": 8 },
      { "facet": "System Health",         "signal": "error_rate",             "value": "MEDIUM", "penalty": 8 },
      { "facet": "Execution Confidence",  "signal": "orchestration_readiness","value": "MEDIUM", "penalty": 5 }
    ],
    "triggering_conflicts": [
      { "severity": "HIGH", "message": "Deployment readiness conflicts with orchestration capability, introducing execution uncertainty." }
    ],
    "risk_basis":   { "final": "HIGH", "base_from_score": "MODERATE", "escalated_by": ["HIGH"] },
    "decision_basis": "high_risk_high_conflict_escalation",
    "recommended_action_basis": "scenario_mapping"
  }
}
```

### 13.10 Frontend mapping updates

The dashboard adapter
([mapGovernanceResponseToViewModel.js](vector-dashboard/src/adapters/mapGovernanceResponseToViewModel.js))
adds four pass-through fields on the view model:

| View-model field | API field | Notes |
|---|---|---|
| `runtimeState` | `runtime_state` | Validated against the 6-value enum, defaults to `STABLE` on missing/invalid input. |
| `recommendedAction` | `recommended_action` | Validated against the 7-value enum, defaults to `CONTINUE` on missing/invalid input. |
| `timelineEvents` | `timeline_events` | Filtered to `{code, label}` objects with truthy `code`. |
| `evidencePacket` | `evidence_packet` | Pass-through; `null` if missing. |

The active-scenario strip (`ActiveScenarioStrip` in
[App.jsx](vector-dashboard/src/App.jsx)) renders two new chips:
**Runtime · `{runtimeState}`** (colour-tinted by state) and
**Action · `{recommendedAction}`**. No other component was touched.

### 13.11 V3 validation

```powershell
python test_backend.py                         # PASS — V2 + V3 + 9-scenario matrix + evidence shape
cd vector-dashboard
npm run lint                                   # clean
npm run build                                  # clean
node scripts/smoke-test.mjs                    # PASS — 9 scenarios, all V3 fields, byte-identical
```

The smoke test asserts:
- All 9 scenarios listed by `/scenarios`.
- All 15 V2 fields + all 4 V3 fields present on every response.
- `runtime_state` ∈ enum and matches expected per scenario.
- `recommended_action` ∈ enum and matches expected per scenario.
- `timeline_events` includes the 5 mandatory codes plus `CONFLICT_ANALYZED`
  when conflicts > 0 and `RISK_ESCALATED` when the engine raised risk.
- `evidence_packet` has all 5 required keys; `triggering_conflicts` length
  matches `conflict_count`; `risk_basis.final` matches `risk_level`.
- Every scenario's `/evaluate` response is byte-identical across two calls.

### 13.12 V3 known limitations (Phase 1)

- `HUMAN_REVIEW_REQUIRED` is reserved in the enum but no scenario triggers it.
- `runtime_state` and `recommended_action` are still deterministic per
  scenario — there is no real-time signal stream, no learned behaviour.
- `evidence_packet.triggering_signals` only includes signals that contributed
  a non-zero penalty; "healthy" signals are not listed (they would only add
  noise to the evidence).
- The frontend renders the new fields as chips only; no separate
  timeline / evidence panel exists yet. The view model fields are present so
  a future component can consume them.

---

## Pointers

- Deeper file-by-file walkthrough + frontend mapping table:
  [INTEGRATION.md](INTEGRATION.md)
- CLI demo (no API, no dashboard): [README.md](README.md) →
  `python main.py --list` / `python main.py --run "Stable Deployment"`
- API entrypoint: [api.py](api.py)
- Engine entrypoint: [engine.py](engine.py) → `evaluate_signals(name, signals)`
- Backend tests: [test_backend.py](test_backend.py)
- End-to-end smoke test: [vector-dashboard/scripts/smoke-test.mjs](vector-dashboard/scripts/smoke-test.mjs)
