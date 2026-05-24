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
    _slugify,
    to_contract,
)

REQUIRED_CONTRACT_FIELDS = [
    "scenario_id", "scenario_name", "alignment_score", "alignment_change",
    "decision", "risk_level", "overall_status", "reason", "decision_summary",
    "conflicts", "conflict_count", "facets", "global_trace", "technical_trace",
    "hard_constraint_triggered",
]

REQUIRED_FACET_FIELDS = ["id", "label", "status", "score", "summary", "trace", "signals"]
REQUIRED_SIGNAL_FIELDS = ["source", "sourceLabel", "metric", "metricLabel",
                          "statusLabel", "icon", "value", "conf"]

# Expected deterministic engine output. Drift here means engine calibration changed.
EXPECTED_MATRIX = {
    "stable_deployment":           {"decision": "ALLOW", "status": "SAFE",    "risk": "LOW",      "score": 100, "conflicts": 0, "hard": False},
    "hidden_instability":          {"decision": "ALLOW", "status": "SAFE",    "risk": "HIGH",     "score": 72,  "conflicts": 1, "hard": False},
    "observability_disagreement":  {"decision": "ALLOW", "status": "SAFE",    "risk": "HIGH",     "score": 75,  "conflicts": 1, "hard": False},
    "cascading_degradation":       {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 63,  "conflicts": 1, "hard": False},
    "orchestration_conflict":      {"decision": "ALLOW", "status": "SAFE",    "risk": "HIGH",     "score": 77,  "conflicts": 1, "hard": False},
    "rollback_trigger":            {"decision": "DELAY", "status": "CAUTION", "risk": "HIGH",     "score": 68,  "conflicts": 1, "hard": False},
    "security_concern":            {"decision": "ALLOW", "status": "SAFE",    "risk": "LOW",      "score": 96,  "conflicts": 0, "hard": False},
    "policy_constraint_violation": {"decision": "BLOCK", "status": "STOP",    "risk": "CRITICAL", "score": 0,   "conflicts": 2, "hard": True},
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

# --- 4. Slug / resolver edge cases ------------------------------------------
print("\n[4] Slug + resolver")
check("slugify normalizes spaces",   _slugify("Stable Deployment") == "stable_deployment")
check("slugify strips and lowercases", _slugify("  Hidden Instability  ") == "hidden_instability")

# --- summary ---------------------------------------------------------------
print(f"\n{'PASS: ALL BACKEND TESTS PASSED' if not failures else f'FAIL: {len(failures)} BACKEND TEST(S) FAILED'}")
sys.exit(0 if not failures else 1)
