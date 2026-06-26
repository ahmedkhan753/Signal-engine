"""
VECTOR V2 backend tests (no server required).

Exercises the deterministic engine and the API transformation layer in-process.
Run:  python test_backend.py
"""
import json
import sys
import io
import contextlib

from engine import evaluate_signals
from scenarios import scenarios
from api import (
    SCENARIO_METADATA,
    SCENARIO_REGISTRY,
    RUNTIME_STATES,
    RECOMMENDED_ACTIONS,
    _slugify,
    to_contract,
)

# --- V2 contract (unchanged) ---
V2_CONTRACT_FIELDS = [
    "scenario_id", "scenario_name", "alignment_score", "alignment_change",
    "decision", "risk_level", "overall_status", "reason", "decision_summary",
    "conflicts", "conflict_count", "facets", "global_trace", "technical_trace",
    "hard_constraint_triggered",
]

# --- V3 Phase 1 (additive) ---
V3_CONTRACT_FIELDS = [
    "runtime_state", "recommended_action", "timeline_events", "evidence_packet",
]

REQUIRED_CONTRACT_FIELDS = V2_CONTRACT_FIELDS + V3_CONTRACT_FIELDS

REQUIRED_FACET_FIELDS = ["id", "label", "status", "score", "summary", "trace", "signals"]
REQUIRED_SIGNAL_FIELDS = ["source", "sourceLabel", "metric", "metricLabel",
                          "statusLabel", "icon", "value", "conf"]

REQUIRED_EVIDENCE_FIELDS = [
    "triggering_signals", "triggering_conflicts", "risk_basis",
    "decision_basis", "recommended_action_basis",
]

# Expected deterministic engine output. Drift here means engine calibration changed.
# V3: also asserts runtime_state / recommended_action per the V3 mapping spec.
EXPECTED_MATRIX = {
    "stable_deployment":           {"decision": "ALLOW", "status": "SAFE",    "risk": "LOW",      "score": 100, "conflicts": 0, "hard": False, "runtime": "STABLE",            "action": "CONTINUE"},
    "hidden_instability":          {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 72,  "conflicts": 1, "hard": False, "runtime": "CONTRADICTORY",     "action": "DELAY_AND_REVIEW"},
    "observability_disagreement":  {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 75,  "conflicts": 1, "hard": False, "runtime": "CONTRADICTORY",     "action": "DELAY_AND_REVIEW"},
    "cascading_degradation":       {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 63,  "conflicts": 1, "hard": False, "runtime": "DEGRADED",          "action": "ESCALATE_TO_OPERATOR"},
    "orchestration_conflict":      {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 77,  "conflicts": 1, "hard": False, "runtime": "CONTRADICTORY",     "action": "VALIDATE_READINESS"},
    "rollback_trigger":            {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 68,  "conflicts": 1, "hard": False, "runtime": "DEGRADED",          "action": "ESCALATE_TO_OPERATOR"},
    "security_concern":            {"decision": "ALLOW", "status": "SAFE",    "risk": "LOW",      "score": 96,  "conflicts": 0, "hard": False, "runtime": "STABLE",            "action": "MONITOR_FOR_DRIFT"},
    "policy_constraint_violation": {"decision": "BLOCK", "status": "STOP",    "risk": "CRITICAL", "score": 0,   "conflicts": 2, "hard": True,  "runtime": "CONSTRAINT_LOCKED", "action": "BLOCK_EXECUTION"},
    "recovery_validation":         {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 74,  "conflicts": 1, "hard": False, "runtime": "RECOVERY_PENDING",  "action": "VALIDATE_RECOVERY"},
}

failures = []

def check(label, condition, detail=""):
    if not condition:
        msg = f"FAIL: {label}" + (f" — {detail}" if detail else "")
        failures.append(msg)
        print(f"  {msg}")


def run_engine_quiet(name, signals):
    """Run the engine while suppressing its CLI print output."""
    with contextlib.redirect_stdout(io.StringIO()):
        return evaluate_signals(name, signals)


# --- 1. Registry / metadata ------------------------------------------------
print("[1] Scenario registry & metadata")
check("registry covers every engine scenario", set(SCENARIO_REGISTRY.values()) == set(scenarios.keys()))
check("metadata covers every registry id", set(SCENARIO_METADATA.keys()) == set(SCENARIO_REGISTRY.keys()))
demo_steps = sorted(
    [(m["demo_order"], m["demo_step"]) for m in SCENARIO_METADATA.values() if m["demo_order"] is not None]
)
check(
    "canonical demo flow Normal→Conflict→Escalation→Block",
    [s for _, s in demo_steps] == ["Normal", "Conflict", "Escalation", "Block"],
    str(demo_steps),
)

# --- 2. Engine determinism & expected matrix --------------------------------
print("\n[2] Engine determinism & expected matrix")
engine_runs = {}
for name, signals in scenarios.items():
    a = run_engine_quiet(name, signals)
    b = run_engine_quiet(name, signals)
    sid = _slugify(name)
    check(f"{sid}: byte-identical between runs", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
    engine_runs[sid] = a
    expected = EXPECTED_MATRIX[sid]
    check(f"{sid}: decision",     a["decision"] == expected["decision"],
          f"{a['decision']} != {expected['decision']}")
    check(f"{sid}: risk_level",   a["risk_level"] == expected["risk"],
          f"{a['risk_level']} != {expected['risk']}")
    check(f"{sid}: score",        a["system_alignment_score"] == expected["score"],
          f"{a['system_alignment_score']} != {expected['score']}")
    check(f"{sid}: conflict count", len(a["conflicts"]) == expected["conflicts"],
          f"{len(a['conflicts'])} != {expected['conflicts']}")

# --- 3. Contract shape ------------------------------------------------------
print("\n[3] API contract shape")
for sid, engine_response in engine_runs.items():
    name = SCENARIO_REGISTRY[sid]
    contract = to_contract(sid, name, engine_response)
    for field in REQUIRED_CONTRACT_FIELDS:
        check(f"{sid}: contract.{field}", field in contract)
    check(f"{sid}: overall_status in {{SAFE,CAUTION,STOP}}",
          contract["overall_status"] in ("SAFE", "CAUTION", "STOP"))
    check(f"{sid}: decision in {{ALLOW,DELAY,BLOCK}}",
          contract["decision"] in ("ALLOW", "DELAY", "BLOCK"))
    check(f"{sid}: 4 facets",
          len(contract["facets"]) == 4)
    for f in contract["facets"]:
        for ff in REQUIRED_FACET_FIELDS:
            check(f"{sid}/{f.get('id','?')}: facet.{ff}", ff in f)
        check(f"{sid}/{f['id']}: facet.status in {{SAFE,CAUTION,STOP}}",
              f["status"] in ("SAFE", "CAUTION", "STOP"))
        for s in f["signals"]:
            for sf in REQUIRED_SIGNAL_FIELDS:
                check(f"{sid}/{f['id']}: signal.{sf}", sf in s)
            check(f"{sid}/{f['id']}: signal.conf in [0,1]",
                  isinstance(s["conf"], (int, float)) and 0 <= s["conf"] <= 1)
    expected = EXPECTED_MATRIX[sid]
    check(f"{sid}: overall_status matches expected",
          contract["overall_status"] == expected["status"],
          f"{contract['overall_status']} != {expected['status']}")
    check(f"{sid}: hard_constraint_triggered matches expected",
          contract["hard_constraint_triggered"] == expected["hard"])

# --- 4. V3 runtime layer ----------------------------------------------------
print("\n[4] V3 runtime layer (runtime_state, recommended_action, timeline_events, evidence_packet)")
for sid, engine_response in engine_runs.items():
    name = SCENARIO_REGISTRY[sid]
    contract = to_contract(sid, name, engine_response)
    expected = EXPECTED_MATRIX[sid]

    # runtime_state / recommended_action enums + mappings
    check(f"{sid}: runtime_state valid enum",
          contract["runtime_state"] in RUNTIME_STATES,
          str(contract["runtime_state"]))
    check(f"{sid}: recommended_action valid enum",
          contract["recommended_action"] in RECOMMENDED_ACTIONS,
          str(contract["recommended_action"]))
    check(f"{sid}: runtime_state matches expected",
          contract["runtime_state"] == expected["runtime"],
          f"{contract['runtime_state']} != {expected['runtime']}")
    check(f"{sid}: recommended_action matches expected",
          contract["recommended_action"] == expected["action"],
          f"{contract['recommended_action']} != {expected['action']}")

    # timeline_events shape
    events = contract["timeline_events"]
    check(f"{sid}: timeline_events is list", isinstance(events, list) and len(events) >= 5)
    codes = [e.get("code") for e in events]
    for required_code in ("REQUEST_RECEIVED", "FACETS_EVALUATED",
                          "RUNTIME_STATE_ASSIGNED", "RECOMMENDED_ACTION_ASSIGNED",
                          "DECISION_FINALIZED"):
        check(f"{sid}: timeline has {required_code}", required_code in codes)
    if expected["conflicts"] > 0:
        check(f"{sid}: timeline has CONFLICT_ANALYZED", "CONFLICT_ANALYZED" in codes)
    # RISK_ESCALATED iff the engine raised risk above the score-band base
    if expected["risk"] != ("LOW" if expected["score"] >= 85 else
                            "MODERATE" if expected["score"] >= 70 else
                            "HIGH" if expected["score"] >= 40 else "CRITICAL"):
        check(f"{sid}: timeline has RISK_ESCALATED", "RISK_ESCALATED" in codes)

    # evidence_packet shape
    evidence = contract["evidence_packet"]
    check(f"{sid}: evidence_packet is dict", isinstance(evidence, dict))
    for field in REQUIRED_EVIDENCE_FIELDS:
        check(f"{sid}: evidence_packet.{field}", field in evidence)
    check(f"{sid}: triggering_conflicts count matches",
          len(evidence["triggering_conflicts"]) == expected["conflicts"])
    check(f"{sid}: risk_basis.final matches contract risk",
          evidence["risk_basis"]["final"] == contract["risk_level"])

# --- 5. Slug / resolver edge cases ------------------------------------------
print("\n[5] Slug + resolver")
check("slugify normalizes spaces",   _slugify("Stable Deployment") == "stable_deployment")
check("slugify strips and lowercases", _slugify("  Hidden Instability  ") == "hidden_instability")
check("slugify recovers recovery_validation", _slugify("Recovery Validation") == "recovery_validation")

# --- 6. V2 backward compatibility -------------------------------------------
print("\n[6] V2 backward compatibility — all V2 fields present and unchanged")
for sid, engine_response in engine_runs.items():
    name = SCENARIO_REGISTRY[sid]
    contract = to_contract(sid, name, engine_response)
    for v2_field in V2_CONTRACT_FIELDS:
        check(f"{sid}: V2 field {v2_field} preserved", v2_field in contract)

# --- summary ---------------------------------------------------------------
print(f"\n{'PASS: ALL BACKEND TESTS PASSED' if not failures else f'FAIL: {len(failures)} BACKEND TEST(S) FAILED'}")
sys.exit(0 if not failures else 1)
