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
    """Reshape the engine response into the stable API contract."""
    conflicts = engine_response["conflicts"]
    decision = engine_response["decision"]

    return {
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
