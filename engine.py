from facets import evaluate_facets
from conflicts import detect_conflicts
from formatter import format_cli_output


def compute_risk_level(score, conflicts):
    """Derive risk level from score, then escalate based on conflict severity."""
    # Base risk level from score
    if score >= 85:
        risk = "LOW"
    elif score >= 70:
        risk = "MODERATE"
    elif score >= 40:
        risk = "HIGH"
    else:
        risk = "CRITICAL"

    # Escalation from conflicts
    for c in conflicts:
        if c["severity"] == "CRITICAL":
            return "CRITICAL"
        elif c["severity"] == "HIGH" and risk in ("LOW", "MODERATE"):
            risk = "HIGH"
        elif c["severity"] == "MEDIUM" and risk == "LOW":
            risk = "MODERATE"

    return risk


def compute_overall_status(decision):
    """Maps decision to a coherent overall_status label."""
    if decision == "ALLOW":
        return "SAFE"
    elif decision == "DELAY":
        return "CAUTION"
    return "STOP"


def make_decision(score, risk_level, conflicts):
    """Determine final governance decision with coherence constraints."""
    # Hard constraints: CRITICAL always blocks
    if risk_level == "CRITICAL":
        return "BLOCK"

    for c in conflicts:
        if c["severity"] == "CRITICAL":
            return "BLOCK"

    # Governance coherence: HIGH risk with active conflicts must delay at minimum
    has_conflicts = len(conflicts) > 0
    has_high_conflict = any(c["severity"] == "HIGH" for c in conflicts)

    if risk_level == "HIGH" and has_high_conflict:
        # HIGH risk + HIGH severity conflict -> DELAY at minimum
        if score >= 70:
            return "DELAY"
        elif score >= 40:
            return "DELAY"
        return "BLOCK"

    # Standard score-based decision
    if score >= 70:
        return "ALLOW"
    elif score >= 40:
        return "DELAY"
    return "BLOCK"


def get_decision_summary_and_result(decision, risk_level, conflicts, overall_status):
    """Generate coherent summary and result strings aligned to the decision."""
    if decision == "ALLOW":
        if conflicts:
            # Justified ALLOW with residual signals (only MEDIUM or lower conflicts reach here)
            summary = "Execution allowed with advisory: minor contradictions noted but operationally acceptable."
            result = "Execution allowed with advisory."
        else:
            summary = "Execution allowed: system conditions are stable and aligned."
            result = "Execution allowed."
    elif decision == "DELAY":
        if any(c["severity"] == "HIGH" for c in conflicts):
            summary = "Execution delayed: unresolved conflicts require operational review before proceeding."
            result = "Execution delayed due to unresolved operational conflicts."
        elif conflicts:
            summary = "Execution delayed: conflicting signals introduce uncertainty and elevated risk."
            result = "Execution delayed due to conflicting signals."
        else:
            summary = "Execution delayed: local operational indicators present elevated risk."
            result = "Execution delayed due to operational instability."
    else:
        if risk_level == "CRITICAL" or any(c["severity"] == "CRITICAL" for c in conflicts):
            summary = "Execution blocked: critical hard constraint or security breach detected."
            result = "Execution blocked due to critical hard constraint."
        else:
            summary = "Execution blocked: multiple critical risk signals detected."
            result = "Execution blocked due to critical system risk."

    return summary, result


def generate_global_trace(facets_result, conflicts, decision, risk_level):
    """Build an operational narrative trace aligned to the final decision."""
    trace = []

    for f in facets_result:
        if f["status"] == "DEGRADED":
            trace.append(f"Degraded {f['facet']} indicators reduced overall confidence.")
        elif f["status"] == "CRITICAL":
            trace.append(f"Critical drop in {f['facet']} introduced severe operational instability.")

    for c in conflicts:
        if c["severity"] == "CRITICAL":
            trace.append(f"Hard constraint violation triggered: {c['message']}")
        elif c["severity"] == "HIGH":
            trace.append(f"Unresolved conflict escalated governance posture: {c['message']}")
        else:
            trace.append(f"Advisory contradiction noted: {c['message']}")

    if not trace:
        trace.append("All operational facets indicate healthy system state.")

    # Final posture statement must match decision
    if decision == "ALLOW":
        if conflicts:
            trace.append("Residual contradictions assessed as operationally tolerable. Execution permitted with advisory.")
        else:
            trace.append("Final operational posture resulted in ALLOW.")
    elif decision == "DELAY":
        trace.append(f"Elevated uncertainty required execution to be paused. Final posture: DELAY.")
    else:
        trace.append(f"Operational posture could not satisfy governance thresholds. Final posture: BLOCK.")

    return trace


def evaluate_signals(scenario_name, signals):
    """Core orchestration: evaluate facets, detect conflicts, produce governance response."""
    # 1. Evaluate facets
    facets_result = evaluate_facets(signals)

    # 2. Base global score is average of facet scores
    if facets_result:
        avg_facet_score = sum(f["score"] for f in facets_result) / len(facets_result)
    else:
        avg_facet_score = 100

    score = avg_facet_score

    # 3. Detect conflicts
    conflicts = detect_conflicts(signals)

    # 4. Apply conflict penalties
    for c in conflicts:
        score -= c["penalty"]

    score = max(0, min(100, int(score)))

    # 5. Compute Risk, Decision, Status
    risk_level = compute_risk_level(score, conflicts)
    decision = make_decision(score, risk_level, conflicts)
    overall_status = compute_overall_status(decision)

    # 6. Generate Summaries & Trace
    decision_summary, result_summary = get_decision_summary_and_result(
        decision, risk_level, conflicts, overall_status
    )
    global_trace = generate_global_trace(facets_result, conflicts, decision, risk_level)

    # 7. Alignment change reasoning
    if score == 100:
        reason = "perfect alignment"
    elif any(c["severity"] == "CRITICAL" for c in conflicts):
        reason = "critical hard constraint violation"
    elif any(c["severity"] == "HIGH" for c in conflicts):
        reason = "unresolved operational conflicts detected"
    elif conflicts:
        reason = "minor operational contradictions detected"
    else:
        reason = "elevated operational risk factors"

    response = {
        "scenario": scenario_name,
        "system_alignment_score": score,
        "decision": decision,
        "risk_level": risk_level,
        "overall_status": overall_status,
        "decision_summary": decision_summary,
        "alignment_change": {
            "initial": 100,
            "final": score,
            "reason": reason
        },
        "conflicts": conflicts,
        "facets": facets_result,
        "global_trace": global_trace,
        "result": result_summary
    }

    trace_output = format_cli_output(response)
    print(trace_output)

    return response
