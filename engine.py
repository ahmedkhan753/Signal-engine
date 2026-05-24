from facets import evaluate_facets
from conflicts import detect_conflicts
from formatter import format_cli_output

def compute_risk_level(score, conflicts):
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
            
    return risk

def make_decision(score, risk_level, conflicts):
    # Hard constraints logic
    if risk_level == "CRITICAL":
        return "BLOCK"
        
    for c in conflicts:
        if c["severity"] == "CRITICAL":
            return "BLOCK"
            
    if score >= 70:
        return "ALLOW"
    elif score >= 40:
        return "DELAY"
    return "BLOCK"
    
def get_decision_summary_and_result(decision, risk_level, conflicts):
    if decision == "ALLOW":
        return "Execution allowed: system conditions are stable and aligned.", "Execution allowed."
    elif decision == "DELAY":
        if conflicts:
            return "Execution delayed: conflicting signals introduce uncertainty and elevated risk.", "Execution delayed due to conflicting signals."
        else:
            return "Execution delayed: local operational indicators present elevated risk.", "Execution delayed due to operational instability."
    else:
        if risk_level == "CRITICAL" or any(c["severity"] == "CRITICAL" for c in conflicts):
            return "Execution blocked: critical hard constraint or security breach detected.", "Execution blocked due to critical hard constraint."
        else:
            return "Execution blocked: multiple critical risk signals detected.", "Execution blocked due to critical system risk."

def generate_global_trace(facets_result, conflicts, decision):
    trace = []
    
    for f in facets_result:
        if f["status"] == "DEGRADED":
            trace.append(f"Degraded {f['facet']} indicators reduced overall confidence.")
        elif f["status"] == "CRITICAL":
            trace.append(f"Critical drop in {f['facet']} introduced severe operational instability.")
            
    for c in conflicts:
        if c["severity"] == "CRITICAL":
            trace.append(f"Hard constraint violation triggered: {c['message']}")
        else:
            trace.append(f"Contradictory signals detected: {c['message']}")
            
    if not trace:
        trace.append("All operational facets indicate healthy system state.")
        
    trace.append(f"Final operational posture resulted in {decision}.")
    return trace

def evaluate_signals(scenario_name, signals):
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
    
    # 5. Compute Risk & Decision
    risk_level = compute_risk_level(score, conflicts)
    decision = make_decision(score, risk_level, conflicts)
    
    # 6. Generate Summaries & Trace
    decision_summary, result_summary = get_decision_summary_and_result(decision, risk_level, conflicts)
    global_trace = generate_global_trace(facets_result, conflicts, decision)
    
    # 7. Alignment change reasoning
    if score == 100:
        reason = "perfect alignment"
    elif conflicts:
        if any(c["severity"] == "CRITICAL" for c in conflicts):
            reason = "critical hard constraint violation"
        else:
            reason = "severe operational contradictions detected"
    else:
        reason = "elevated operational risk factors"
        
    response = {
        "scenario": scenario_name,
        "system_alignment_score": score,
        "decision": decision,
        "risk_level": risk_level,
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
