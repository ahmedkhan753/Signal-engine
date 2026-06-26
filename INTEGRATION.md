# VECTOR V2 Integrated Prototype — Complete

**Phase:** Integration completion + stabilization (Day 2)
**Status:** Complete — all 8 scenarios wired, validated, and deterministic.
**Date:** 2026-05-29

> The canonical engineering handoff doc is [V2_HANDOFF.md](V2_HANDOFF.md).
> This file is the deeper integration walkthrough — file-by-file scope and the
> frontend ↔ backend field-mapping table.

---

## 1. What this prototype is now

A deterministic governance evaluator with a live React dashboard, end-to-end.

```
Browser (React dashboard, :5173)
   │  GET /scenarios            POST /evaluate { scenario_id }
   ▼
api.py  (Flask API layer, :8000)
   │  evaluate_signals(name, signals)
   ▼
engine.py · facets.py · conflicts.py · formatter.py   (untouched)
```

- All 9 scenarios are wired and selectable from the dashboard (8 V2 +
  `recovery_validation` added in V3 Phase 1).
- All four governance paths render correctly (`SAFE`, `CAUTION`, `STOP`, plus
  the explicit *hard-constraint* indicator).
- Output is byte-identical across repeated runs (verified in tests).
- No database, no auth, no persistence, no new governance logic.
- V3 Phase 1 adds four additive response fields (`runtime_state`,
  `recommended_action`, `timeline_events`, `evidence_packet`) — derived in the
  API layer, not the engine. See
  [V2_HANDOFF.md §13](V2_HANDOFF.md#13-v3-phase-1--runtime-governance-layer-additive).

---

## 2. Files in scope

### Backend
| File | Role |
|------|------|
| `engine.py`, `facets.py`, `conflicts.py`, `formatter.py`, `scenarios.py`, `main.py` | Untouched deterministic engine + CLI. |
| `api.py` | Flask API layer (`POST /evaluate`, `GET /scenarios`, `GET /health`). |
| `test_backend.py` | In-process tests — registry, determinism, contract shape, expected matrix. |
| `requirements.txt` | Single dep: `flask`. |

### Frontend (`vector-dashboard/`)
| File | Role |
|------|------|
| `src/config/apiConfig.js` | Backend base URL (env-overridable via `VITE_API_BASE_URL`). |
| `src/api/governanceClient.js` | `fetchEvaluation`, `fetchScenarios`. |
| `src/adapters/mapGovernanceResponseToViewModel.js` | API contract → dashboard view model. *Only file to touch when the schema changes.* |
| `src/hooks/useDashboardController.js` | Fetches `/scenarios` + per-scenario `/evaluate`, drives canonical demo flow. |
| `src/components/RunScenarioCard.jsx` | Quick-run buttons + "All scenarios" picker. |
| `src/App.jsx` | Adds connection banner + active-scenario chip + hard-constraint indicator. |
| `src/model/governanceApi.js` · `src/model/dashboardViewModel.js` | JSDoc typedefs for the locked contract + view model. |
| `scripts/smoke-test.mjs` | End-to-end test of the full data path (no browser). |

Untouched: every dashboard component / stylesheet / hook beyond the controller
and `RunScenarioCard`. `src/data/mockGovernanceResponses.js` is left in place
but no longer imported.

---

## 3. Locked API contract

The field names below are **stable** and can be relied on by the frontend.

### `GET /scenarios`
```json
{
  "scenarios": [
    { "scenario_id": "stable_deployment",           "scenario_name": "Stable Deployment",           "demo_step": "Normal",     "demo_order": 1 },
    { "scenario_id": "hidden_instability",          "scenario_name": "Hidden Instability",          "demo_step": "Conflict",   "demo_order": 2 },
    { "scenario_id": "cascading_degradation",       "scenario_name": "Cascading Degradation",       "demo_step": "Escalation", "demo_order": 3 },
    { "scenario_id": "policy_constraint_violation", "scenario_name": "Policy Constraint Violation", "demo_step": "Block",      "demo_order": 4 },
    { "scenario_id": "observability_disagreement",  "scenario_name": "Observability Disagreement",  "demo_step": null,         "demo_order": null },
    { "scenario_id": "recovery_validation",         "scenario_name": "Recovery Validation",         "demo_step": null,         "demo_order": null }
    // ...
  ]
}
```

### `POST /evaluate`
Request:
```json
{ "scenario_id": "policy_constraint_violation" }
```

Response (locked field set):
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
    {
      "id": "system_health",
      "label": "System Health",
      "status": "SAFE",         // SAFE | CAUTION | STOP — backend-owned
      "score": 100,
      "summary": "...",
      "trace": ["..."],
      "signals": [
        {
          "source": "infrastructure_stability",
          "sourceLabel": "Infrastructure stability",
          "metric": "infrastructure_stability",
          "metricLabel": "Readiness signal",
          "statusLabel": "High",
          "icon": "🏗",
          "value": "proceed",     // 'normal' | 'high' | 'proceed' — drives pill colour
          "conf": 1.0             // deterministic engine → always 1.0
        }
      ]
    }
    // 4 facets total
  ],
  "global_trace": ["..."],          // operational narrative, array of sentences
  "technical_trace": ["..."],       // per-facet point-deduction breakdown
  "hard_constraint_triggered": true // true iff any conflict.severity === 'CRITICAL'
}
```

**Governance meaning is backend-owned.** `decision`, `overall_status`, each
facet `status`, and `hard_constraint_triggered` are returned ready to render.
The frontend never derives them.

Errors:
- `400` — `scenario_id` missing
- `404` — `scenario_id` not in the registry (includes the valid list in the body)

---

## 4. Frontend → backend field mapping

| View model field | API field | Notes |
|---|---|---|
| `scenarioId` | `scenario_id` | URL slug. |
| `scenarioTitle` | `scenario_name` | Human label, rendered in the active-scenario chip. |
| `score` | `alignment_score` | Animated via `useAnimatedScore`. |
| `alignmentChange` | `alignment_change` | Initial → final shown as a chip when they differ. |
| `decision` | `decision` | `ALLOW` / `DELAY` / `BLOCK`. |
| `alignment` | `overall_status` | `SAFE` / `CAUTION` / `STOP` — direct pass-through. |
| `risk` | `risk_level` | 4-level engine risk → 3-level pill (`CRITICAL+HIGH→high`, `MODERATE→medium`, `LOW→low`). |
| `riskLabel` | `risk_level` | Raw label shown in the chip strip. |
| `conflicts` | `conflicts[].message` | Conflict objects flattened to strings for the panel. |
| `facets[].status` | `facets[].status` | Direct (`SAFE`/`CAUTION`/`STOP`). |
| `facets[].subScore` | `facets[].score` | 0–100. |
| `facets[].contributingSignals` | `facets[].signals` | Each row carries `value`, `statusLabel`, `icon`, `conf`. |
| `facets[].localTraceTechnical` | `facets[].trace` | Joined with newlines for the technical disclosure. |
| `operationalSummary` | `decision_summary` | Header sub-title. |
| `operationalTrace` | `global_trace` | Joined sentences. |
| `technicalTrace` | `technical_trace` | Joined per-facet point-deduction breakdown. |
| `hardConstraintTriggered` | `hard_constraint_triggered` | Renders the red `⚠ Hard constraint triggered` chip. |
| `runtimeState` | `runtime_state` | V3 — pass-through enum. Renders the `Runtime · …` chip (colour-tinted by state). |
| `recommendedAction` | `recommended_action` | V3 — pass-through enum. Renders the `Action · …` chip. |
| `timelineEvents` | `timeline_events` | V3 — `{code, label}[]`. Carried on the view model for a future timeline panel. |
| `evidencePacket` | `evidence_packet` | V3 — pass-through. Carried on the view model for a future evidence panel. |

---

## 5. Deterministic scenario matrix

Captured against the live engine (`python test_backend.py` re-asserts these
every run; drift breaks the build).

| `scenario_id` | Score | Decision | Status | Risk | Conflicts | Hard | Demo step | `runtime_state` | `recommended_action` |
|---|---:|---|---|---|---:|---|---|---|---|
| `stable_deployment`           | 100 | ALLOW | SAFE    | LOW      | 0 | — | Normal     | `STABLE`            | `CONTINUE` |
| `hidden_instability`          |  72 | DELAY | CAUTION | HIGH     | 1 | — | Conflict   | `CONTRADICTORY`     | `DELAY_AND_REVIEW` |
| `observability_disagreement`  |  75 | DELAY | CAUTION | HIGH     | 1 | — | —          | `CONTRADICTORY`     | `DELAY_AND_REVIEW` |
| `orchestration_conflict`      |  77 | DELAY | CAUTION | HIGH     | 1 | — | —          | `CONTRADICTORY`     | `VALIDATE_READINESS` |
| `rollback_trigger`            |  68 | DELAY | CAUTION | HIGH     | 1 | — | —          | `DEGRADED`          | `ESCALATE_TO_OPERATOR` |
| `cascading_degradation`       |  63 | DELAY | CAUTION | HIGH     | 1 | — | Escalation | `DEGRADED`          | `ESCALATE_TO_OPERATOR` |
| `security_concern`            |  96 | ALLOW | SAFE    | LOW      | 0 | — | —          | `STABLE`            | `MONITOR_FOR_DRIFT` |
| `policy_constraint_violation` |   0 | BLOCK | STOP    | CRITICAL | 2 | ✓ | Block      | `CONSTRAINT_LOCKED` | `BLOCK_EXECUTION` |
| `recovery_validation`         |  74 | DELAY | CAUTION | HIGH     | 1 | — | —          | `RECOVERY_PENDING`  | `VALIDATE_RECOVERY` |

---

## 6. Calibration observations (separate from integration work)

These are **engine calibration observations** — the integration faithfully
displays whatever the engine emits. Adjusting these is governance work, not
integration work, and was explicitly out of scope.

1. **HIGH risk + HIGH-severity conflict now escalates to DELAY at minimum.**
   `hidden_instability` (72), `observability_disagreement` (75),
   `orchestration_conflict` (77), and `rollback_trigger` (68) all sit at scores
   that would have been `ALLOW` under a purely score-driven rule, but the
   engine's coherence rule (`make_decision` in `engine.py`) requires `DELAY`
   when `risk_level == HIGH` and there is at least one HIGH-severity conflict.
   See [V2_HANDOFF.md §8](V2_HANDOFF.md#8-governance-calibration-rules) for the
   full rule set and rationale.
2. **`security_concern` evaluates to ALLOW (96) with zero conflicts.** A `HIGH`
   `security_threat` alone gives only a -15 facet penalty and triggers no
   cross-facet conflict, so the overall posture is `SAFE`. If `Security Concern`
   is meant to surface caution, either the conflict rules need a
   `security_threat=HIGH` clause or the facet penalty needs increasing.
3. **`BLOCK` is reserved for critical escalation paths.** Only
   `policy_constraint_violation` reaches BLOCK today — via two CRITICAL
   conflicts (`active_breach=HIGH`, `policy_violation=HIGH`) that force
   `risk_level=CRITICAL` and set `hard_constraint_triggered=true`.
4. **Per-signal confidence is uniform `1.0`.** The deterministic engine has no
   telemetry-confidence concept, so every confidence bar is full and green. This
   is honest (deterministic = certain), but it makes the bars decorative rather
   than informative.

---

## 7. How to run

**Backend** (terminal 1, from the repo root):
```powershell
cd D:\PROJECTS\signal-engine
pip install -r requirements.txt
python api.py
# -> http://localhost:8000
```

**Frontend** (terminal 2):
```powershell
cd D:\PROJECTS\signal-engine\vector-dashboard
npm install        # first time only
npm run dev
# -> http://localhost:5173 (or next free port)
```

Open the dashboard URL. If the backend is down, a banner says so.

**Override the backend URL** (optional):
```powershell
$env:VITE_API_BASE_URL = "http://localhost:9000"
npm run dev
```

---

## 8. Testing

### Backend (in-process, no server needed)
```powershell
python test_backend.py
```
Asserts the registry, determinism (each scenario byte-identical across runs),
the expected governance matrix, contract shape, and the slug resolver.

### Frontend build + lint
```powershell
cd vector-dashboard
npm run lint     # clean
npm run build    # clean
```

### End-to-end (backend must be running)
```powershell
cd vector-dashboard
node scripts/smoke-test.mjs
```
Exercises `/scenarios`, every scenario via `/evaluate`, runs each response
through the **real** dashboard adapter, asserts the deterministic matrix and
contract shape, repeats every call to verify byte-identical determinism, and
checks error paths (`400` / `404`).

---

## 9. Demo flow

The dashboard's **Run demo** button cycles the canonical four-step flow:

```
Normal              → ALLOW / SAFE    / risk LOW
   (Stable Deployment)
Conflict            → DELAY / CAUTION / risk HIGH  + 1 conflict
   (Hidden Instability)
Escalation          → DELAY / CAUTION / risk HIGH  + 1 conflict
   (Cascading Degradation)
Hard Constraint Block → BLOCK / STOP  / risk CRITICAL + 2 conflicts + ⚠ hard constraint
   (Policy Constraint Violation)
```

Each step holds for ~3.4 s. The three quick-run buttons (`Run Normal`,
`Run Conflict`, `Run Stop`) map to steps 1, 2, and 4 — the `Stop` button jumps
straight to the hard-constraint scenario. The **All scenarios** dropdown gives
direct access to every wired scenario, including the four not on the canonical
flow.

---

## 10. Known remaining items (V-next, brief)

See [V2_HANDOFF.md §10–§12](V2_HANDOFF.md#10-known-limitations) for the full
limitations list and V3 considerations. Headline items:

- **Engine calibration** — `security_concern` (96 / ALLOW / zero conflicts)
  remains a candidate for a `security_threat=HIGH` conflict rule.
- **Persistence / history** — no scenario history is kept. Out of scope.
- **`GET /scenarios` caching** — frontend currently fetches it once on mount.
  Fine for the prototype.
- **Signal confidence** — `conf` is always `1.0`. If telemetry confidence
  becomes governance-relevant, the engine + contract + adapter need a shared
  definition.
- **Production hardening** — `app.run(...)` is the dev server. Production
  would need a real WSGI server (`gunicorn`/`waitress`) and a non-`*` CORS
  origin.
