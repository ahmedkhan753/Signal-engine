POSITIVE_SIGNALS = {
    "infrastructure_stability",
    "deployment_readiness",
    "orchestration_readiness"
}

NEGATIVE_SIGNALS = {
    "service_latency",
    "error_rate",
    "rollback_trigger",
    "policy_violation",
    "security_threat",
    "active_breach",
    "observability_disagreement"
}

FACET_MAP = {
    "System Health": ["infrastructure_stability", "service_latency", "error_rate"],
    "Operational Risk": ["deployment_readiness", "rollback_trigger", "policy_violation"],
    "Security": ["security_threat", "active_breach"],
    "Execution Confidence": ["orchestration_readiness", "observability_disagreement"]
}

def get_signal_display_name(key):
    return key.replace("_", " ").capitalize()

def evaluate_signal(signal_name, value):
    """Returns (penalty_points, trace_message)."""
    display_name = get_signal_display_name(signal_name)
    penalty = 0
    message = f"{display_name} is {value} -> no penalty"

    if signal_name in POSITIVE_SIGNALS:
        if value == "MEDIUM":
            penalty = 5
        elif value == "LOW":
            penalty = 10
    elif signal_name in NEGATIVE_SIGNALS:
        if value == "HIGH":
            penalty = 15
        elif value == "MEDIUM":
            penalty = 8
            
    if penalty > 0:
        message = f"{display_name} is {value} -> -{penalty} points"
        
    return penalty, message

def get_facet_status_and_summary(facet_name, score, local_signals):
    """Determines the status string and summary based on the facet score."""
    status = "HEALTHY"
    if score < 70:
        status = "DEGRADED"
    if score < 40:
        status = "CRITICAL"
        
    if facet_name == "System Health":
        if status == "HEALTHY":
            return status, "System metrics indicate stable operational behavior."
        elif status == "DEGRADED":
            return status, "Service latency and elevated error rates indicate unstable system behavior."
        else:
            return status, "Critical infrastructure instability detected."
            
    elif facet_name == "Operational Risk":
        if status == "HEALTHY":
            return status, "No significant operational risks identified."
        elif status == "DEGRADED":
            return status, "Elevated operational risk due to deployment or policy factors."
        else:
            return status, "Severe operational risk, rollback or policy breach detected."
            
    elif facet_name == "Security":
        if status == "HEALTHY":
            return status, "No active security threat detected."
        elif status == "DEGRADED":
            return status, "Elevated security threat detected requiring attention."
        else:
            return status, "Critical security breach detected."
            
    elif facet_name == "Execution Confidence":
        if status == "HEALTHY":
            return status, "Execution confidence is high with solid observability."
        elif status == "DEGRADED":
            return status, "Execution confidence reduced because observability signals disagree."
        else:
            return status, "Execution confidence critically low due to orchestration failures."
            
    return status, "Evaluated successfully."

def evaluate_facets(signals):
    facets_result = []
    
    for facet_name, related_signals in FACET_MAP.items():
        score = 100
        trace = []
        local_signals = {}
        
        for sig in related_signals:
            if sig in signals:
                val = signals[sig]
                local_signals[sig] = val
                penalty, msg = evaluate_signal(sig, val)
                score -= penalty
                trace.append(msg)
                
        score = max(0, score)
        status, summary = get_facet_status_and_summary(facet_name, score, local_signals)
        
        facets_result.append({
            "facet": facet_name,
            "score": score,
            "status": status,
            "signals": local_signals,
            "summary": summary,
            "trace": trace
        })
        
    return facets_result
