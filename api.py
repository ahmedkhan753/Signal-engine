"""
VECTOR V2 — Lightweight backend API layer.

A thin Flask wrapper around the existing deterministic governance engine.
It does NOT add governance logic: it receives a scenario_id, runs the
untouched engine, and reshapes the result into the stable API contract the
frontend dashboard consumes.

Run:
    pip install flask
    python api.py
    # -> http://localhost:8000

Endpoints:
    GET  /health    -> {"status": "ok"}
    POST /evaluate  -> stable governance response (see CONTRACT below)
"""

from flask import Flask, jsonify, request

from engine import evaluate_signals
from scenarios import scenarios
from facets import POSITIVE_SIGNALS, NEGATIVE_SIGNALS, evaluate_signal, get_signal_display_name

app = Flask(__name__)

# --------------------------------------------------------------------------
# Scenario registry — maps a stable URL-safe slug to the engine scenario name.
# Built from the existing scenario library so it stays in sync automatically.
# --------------------------------------------------------------------------

def _slugify(name):
    return name.strip().lower().replace(" ", "_").replace("-", "_")

SCENARIO_REGISTRY = {_slugify(name): name for name in scenarios}

# Demo-flow metadata. The canonical 4-step demo cycles in this order:
#   Normal -> Conflict -> Escalation -> Hard Constraint Block
# Scenarios outside the canonical flow carry `demo_step: None` and are still
# fully runnable via the dashboard scenario picker.
SCENARIO_METADATA = {
    "stable_deployment":           {"demo_step": "Normal",      "demo_order": 1},
    "hidden_instability":          {"demo_step": "Conflict",    "demo_order": 2},
    "cascading_degradation":       {"demo_step": "Escalation",  "demo_order": 3},
    "policy_constraint_violation": {"demo_step": "Block",       "demo_order": 4},
    "observability_disagreement":  {"demo_step": None,          "demo_order": None},
    "orchestration_conflict":      {"demo_step": None,          "demo_order": None},
    "rollback_trigger":            {"demo_step": None,          "demo_order": None},
    "security_concern":            {"demo_step": None,          "demo_order": None},
    "recovery_validation":         {"demo_step": None,          "demo_order": None},
}

# --------------------------------------------------------------------------
# V3 Phase 1 — Runtime governance layer (additive, deterministic).
#
# These add four new fields to every /evaluate response:
#   runtime_state, recommended_action, timeline_events, evidence_packet
#
# No engine logic is altered. Mappings are keyed by scenario_id and remain
# fully deterministic. A small fallback derives the same fields from engine
# output for any new scenario without an explicit mapping.
# --------------------------------------------------------------------------

RUNTIME_STATES = (
    "STABLE", "CONTRADICTORY", "DEGRADED",
    "RECOVERY_PENDING", "CONSTRAINT_LOCKED", "HUMAN_REVIEW_REQUIRED",
)

RECOMMENDED_ACTIONS = (
    "CONTINUE", "DELAY_AND_REVIEW", "ESCALATE_TO_OPERATOR",
    "BLOCK_EXECUTION", "VALIDATE_RECOVERY",
    "MONITOR_FOR_DRIFT", "VALIDATE_READINESS",
)

# Per-scenario runtime mapping. Deterministic by scenario_id.
SCENARIO_RUNTIME_MAPPING = {
    "stable_deployment":           ("STABLE",           "CONTINUE"),
    "hidden_instability":          ("CONTRADICTORY",    "DELAY_AND_REVIEW"),
    "observability_disagreement":  ("CONTRADICTORY",    "DELAY_AND_REVIEW"),
    "orchestration_conflict":      ("CONTRADICTORY",    "VALIDATE_READINESS"),
    "rollback_trigger":            ("DEGRADED",         "ESCALATE_TO_OPERATOR"),
    "cascading_degradation":       ("DEGRADED",         "ESCALATE_TO_OPERATOR"),
    "security_concern":            ("STABLE",           "MONITOR_FOR_DRIFT"),
    "policy_constraint_violation": ("CONSTRAINT_LOCKED", "BLOCK_EXECUTION"),
    "recovery_validation":         ("RECOVERY_PENDING", "VALIDATE_RECOVERY"),
}


def _base_risk_from_score(score):
    """Risk band from score alone — the input to the engine's conflict escalation."""
    if score >= 85:
        return "LOW"
    if score >= 70:
        return "MODERATE"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"


def _decision_basis(engine_response):
    """Identifies which rule in engine.make_decision produced the final decision."""
    conflicts = engine_response["conflicts"]
    risk = engine_response["risk_level"]
    score = engine_response["system_alignment_score"]
    if any(c["severity"] == "CRITICAL" for c in conflicts):
        return "critical_hard_constraint"
    if risk == "CRITICAL":
        return "critical_risk_band"
    if risk == "HIGH" and any(c["severity"] == "HIGH" for c in conflicts):
        return "high_risk_high_conflict_escalation"
    if score >= 70:
        return "score_band_allow"
    if score >= 40:
        return "score_band_delay"
    return "score_band_block"


def derive_runtime_state_and_action(scenario_id, engine_response):
    """
    Return (runtime_state, recommended_action, basis_label).
    Primary path: per-scenario mapping. Fallback: derive from engine output.
    """
    if scenario_id in SCENARIO_RUNTIME_MAPPING:
        state, action = SCENARIO_RUNTIME_MAPPING[scenario_id]
        return state, action, "scenario_mapping"

    # Deterministic fallback — keeps the layer principled if a new scenario
    # is added without an explicit mapping.
    conflicts = engine_response["conflicts"]
    decision = engine_response["decision"]
    hard = any(c["severity"] == "CRITICAL" for c in conflicts)
    if hard:
        return "CONSTRAINT_LOCKED", "BLOCK_EXECUTION", "derived_from_engine"
    if decision == "BLOCK":
        return "DEGRADED", "ESCALATE_TO_OPERATOR", "derived_from_engine"
    if decision == "DELAY":
        if any(c["severity"] == "HIGH" for c in conflicts):
            return "CONTRADICTORY", "DELAY_AND_REVIEW", "derived_from_engine"
        return "DEGRADED", "ESCALATE_TO_OPERATOR", "derived_from_engine"
    return "STABLE", "CONTINUE", "derived_from_engine"


def build_timeline_events(scenario_name, engine_response, runtime_state, recommended_action):
    """
    Milestone-level deterministic timeline. One event per governance phase,
    never one per signal. Operator-readable.
    """
    score = engine_response["system_alignment_score"]
    decision = engine_response["decision"]
    risk_level = engine_response["risk_level"]
    conflicts = engine_response["conflicts"]
    base_risk = _base_risk_from_score(score)

    events = [
        {"code": "REQUEST_RECEIVED",
         "label": f"Evaluation request accepted for scenario '{scenario_name}'."},
        {"code": "FACETS_EVALUATED",
         "label": f"{len(engine_response['facets'])} facets evaluated; alignment score {score}/100."},
    ]
    if conflicts:
        severities = ",".join(c["severity"] for c in conflicts)
        events.append({
            "code": "CONFLICT_ANALYZED",
            "label": f"{len(conflicts)} conflict(s) detected (severities: {severities}).",
        })
    if risk_level != base_risk:
        events.append({
            "code": "RISK_ESCALATED",
            "label": f"Risk escalated from base {base_risk} to {risk_level} by conflict severity.",
        })
    events.append({
        "code": "RUNTIME_STATE_ASSIGNED",
        "label": f"Runtime state assigned: {runtime_state}.",
    })
    events.append({
        "code": "RECOMMENDED_ACTION_ASSIGNED",
        "label": f"Recommended action: {recommended_action}.",
    })
    events.append({
        "code": "DECISION_FINALIZED",
        "label": f"Final decision: {decision}.",
    })
    return events


def build_evidence_packet(scenario_id, engine_response, action_basis):
    """
    Structured governance evidence. Only facts already present in the
    evaluation; no generated narrative.
    """
    conflicts = engine_response["conflicts"]
    score = engine_response["system_alignment_score"]
    risk = engine_response["risk_level"]
    base_risk = _base_risk_from_score(score)

    # Triggering signals = those that contributed any penalty in any facet.
    triggering_signals = []
    for facet in engine_response["facets"]:
        for sig_name, value in facet.get("signals", {}).items():
            penalty, _ = evaluate_signal(sig_name, value)
            if penalty > 0:
                triggering_signals.append({
                    "facet": facet["facet"],
                    "signal": sig_name,
                    "value": value,
                    "penalty": penalty,
                })

    triggering_conflicts = [
        {"severity": c["severity"], "message": c["message"]} for c in conflicts
    ]

    risk_basis = {
        "final": risk,
        "base_from_score": base_risk,
        "escalated_by": [c["severity"] for c in conflicts] if risk != base_risk else [],
    }

    return {
        "triggering_signals": triggering_signals,
        "triggering_conflicts": triggering_conflicts,
        "risk_basis": risk_basis,
        "decision_basis": _decision_basis(engine_response),
        "recommended_action_basis": action_basis,
    }

# Per-signal display icons (presentation only — not governance data).
SIGNAL_ICONS = {
    "infrastructure_stability": "\U0001F3D7",   # building construction
    "deployment_readiness": "\U0001F680",       # rocket
    "orchestration_readiness": "\U0001F517",    # link
    "service_latency": "⏱",                # stopwatch
    "error_rate": "⚠",                     # warning
    "rollback_trigger": "↩",               # leftwards hook
    "policy_violation": "◆",               # black diamond
    "security_threat": "\U0001F6E1",            # shield
    "active_breach": "\U0001F513",              # open lock
    "observability_disagreement": "\U0001F441", # eye
}

# --------------------------------------------------------------------------
# Deterministic status mapping
# --------------------------------------------------------------------------

# Engine decision -> governance status the frontend renders directly.
# The frontend MUST NOT derive this; the backend owns it.
DECISION_TO_STATUS = {"ALLOW": "SAFE", "DELAY": "CAUTION", "BLOCK": "STOP"}

# Engine facet health -> facet status the frontend renders directly.
FACET_STATUS_TO_GOVERNANCE = {"HEALTHY": "SAFE", "DEGRADED": "CAUTION", "CRITICAL": "STOP"}


def resolve_scenario(scenario_id):
    """Accept a slug, an exact engine name, or a loosely-cased slug."""
    if scenario_id is None:
        return None
    if scenario_id in SCENARIO_REGISTRY:
        return SCENARIO_REGISTRY[scenario_id]
    if scenario_id in scenarios:
        return scenario_id
    loose = _slugify(str(scenario_id))
    return SCENARIO_REGISTRY.get(loose)


def build_signal_row(signal_name, value):
    """Reshape one engine signal (HIGH/MEDIUM/LOW) into a frontend signal row."""
    penalty, _msg = evaluate_signal(signal_name, value)
    is_positive = signal_name in POSITIVE_SIGNALS

    if penalty > 0:
        pill_value = "high"          # contributes risk -> emphasised pill
    elif is_positive:
        pill_value = "proceed"       # healthy readiness signal
    else:
        pill_value = "normal"        # negative signal, but within tolerance

    metric_label = "Readiness signal" if is_positive else "Risk signal"

    return {
        "source": signal_name,
        "sourceLabel": get_signal_display_name(signal_name),
        "metric": signal_name,
        "metricLabel": metric_label,
        "value": pill_value,
        "statusLabel": str(value).capitalize(),
        "icon": SIGNAL_ICONS.get(signal_name, "●"),
        # The deterministic engine has no per-signal telemetry confidence;
        # every rule evaluation is fully certain. Reported as 1.0.
        "conf": 1.0,
    }


def map_facet(facet):
    """Reshape one engine facet into the frontend facet contract."""
    return {
        "id": _slugify(facet["facet"]),
        "label": facet["facet"],
        "status": FACET_STATUS_TO_GOVERNANCE.get(facet["status"], "SAFE"),
        "score": facet["score"],
        "summary": facet["summary"],
        "trace": facet.get("trace", []),
        "signals": [build_signal_row(k, v) for k, v in facet.get("signals", {}).items()],
    }


def build_technical_trace(engine_response):
    """A per-facet / per-conflict point-deduction breakdown (technical view)."""
    lines = []
    for facet in engine_response["facets"]:
        for entry in facet.get("trace", []):
            lines.append(f"[{facet['facet']}] {entry}")
    for conflict in engine_response["conflicts"]:
        lines.append(
            f"[Conflict/{conflict['severity']}] {conflict['message']} (-{conflict['penalty']})"
        )
    lines.append(
        f"[Decision] {engine_response['decision']} at alignment score "
        f"{engine_response['system_alignment_score']}/100."
    )
    return lines


def to_contract(scenario_id, scenario_name, engine_response):
    """Reshape the engine response into the stable API contract.

    V2 fields are unchanged. V3 Phase 1 adds four additive fields:
    runtime_state, recommended_action, timeline_events, evidence_packet.
    """
    conflicts = engine_response["conflicts"]
    decision = engine_response["decision"]

    runtime_state, recommended_action, action_basis = derive_runtime_state_and_action(
        scenario_id, engine_response
    )
    timeline_events = build_timeline_events(
        scenario_name, engine_response, runtime_state, recommended_action
    )
    evidence_packet = build_evidence_packet(scenario_id, engine_response, action_basis)

    return {
        # --- V2 contract (unchanged) ---
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "alignment_score": engine_response["system_alignment_score"],
        "alignment_change": engine_response["alignment_change"],
        "decision": decision,
        "risk_level": engine_response["risk_level"],
        # overall_status is owned by the backend — the frontend renders it directly.
        "overall_status": DECISION_TO_STATUS.get(decision, "SAFE"),
        "reason": engine_response["alignment_change"]["reason"],
        "decision_summary": engine_response["decision_summary"],
        "conflicts": [
            {"severity": c["severity"], "message": c["message"]} for c in conflicts
        ],
        "conflict_count": len(conflicts),
        "facets": [map_facet(f) for f in engine_response["facets"]],
        "global_trace": engine_response["global_trace"],
        "technical_trace": build_technical_trace(engine_response),
        "hard_constraint_triggered": any(c["severity"] == "CRITICAL" for c in conflicts),
        # --- V3 Phase 1 (additive, deterministic) ---
        "runtime_state": runtime_state,
        "recommended_action": recommended_action,
        "timeline_events": timeline_events,
        "evidence_packet": evidence_packet,
    }


# --------------------------------------------------------------------------
# CORS — the dev dashboard runs on a different origin (Vite :5173).
# --------------------------------------------------------------------------

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "scenarios": sorted(SCENARIO_REGISTRY.keys())})


@app.route("/scenarios", methods=["GET"])
def list_scenarios():
    """Lists every wired scenario with display + demo-flow metadata."""
    entries = []
    for scenario_id, scenario_name in SCENARIO_REGISTRY.items():
        meta = SCENARIO_METADATA.get(scenario_id, {"demo_step": None, "demo_order": None})
        entries.append({
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "demo_step": meta["demo_step"],
            "demo_order": meta["demo_order"],
        })
    # Canonical demo scenarios first (in demo_order), then the rest alphabetically.
    entries.sort(key=lambda e: (
        e["demo_order"] is None,
        e["demo_order"] if e["demo_order"] is not None else 0,
        e["scenario_name"],
    ))
    return jsonify({"scenarios": entries})


@app.route("/evaluate", methods=["POST"])
def evaluate():
    payload = request.get_json(silent=True) or {}
    scenario_id = payload.get("scenario_id")

    if not scenario_id:
        return jsonify({"error": "Missing required field 'scenario_id'."}), 400

    scenario_name = resolve_scenario(scenario_id)
    if scenario_name is None:
        return jsonify({
            "error": f"Unknown scenario_id '{scenario_id}'.",
            "available": sorted(SCENARIO_REGISTRY.keys()),
        }), 404

    # Run the untouched deterministic engine.
    engine_response = evaluate_signals(scenario_name, scenarios[scenario_name])

    return jsonify(to_contract(_slugify(scenario_name), scenario_name, engine_response))


if __name__ == "__main__":
    print("VECTOR V2 API layer -> http://localhost:8000  (POST /evaluate)")
    app.run(host="127.0.0.1", port=8000, debug=False)
