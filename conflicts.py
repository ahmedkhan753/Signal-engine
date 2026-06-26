def detect_conflicts(signals):
    """
    Evaluates cross-facet conflicts and hard constraints.
    Returns a list of conflict dicts: {"severity": "...", "message": "...", "penalty": int}
    """
    conflicts = []
    
    # Hard constraints
    if signals.get("active_breach") == "HIGH":
        conflicts.append({
            "severity": "CRITICAL",
            "message": "Critical security breach detected.",
            "penalty": 50
        })
        
    if signals.get("policy_violation") == "HIGH":
        conflicts.append({
            "severity": "CRITICAL",
            "message": "Policy constraint violation detected.",
            "penalty": 50
        })
        
    # Relational conflicts
    if signals.get("rollback_trigger") == "HIGH":
        if signals.get("error_rate") == "HIGH" or signals.get("service_latency") == "HIGH":
            conflicts.append({
                "severity": "HIGH",
                "message": "Rollback trigger accompanied by elevated error rates indicates a severe operational fault.",
                "penalty": 20
            })
        else:
            conflicts.append({
                "severity": "MEDIUM",
                "message": "Rollback trigger introduced operational instability.",
                "penalty": 10
            })
            
    if signals.get("deployment_readiness") == "HIGH" and signals.get("orchestration_readiness") in ("LOW", "MEDIUM"):
        conflicts.append({
            "severity": "HIGH",
            "message": "Deployment readiness conflicts with orchestration capability, introducing execution uncertainty.",
            "penalty": 20
        })
        
    if signals.get("observability_disagreement") == "HIGH":
        if signals.get("infrastructure_stability") == "HIGH":
            conflicts.append({
                "severity": "HIGH",
                "message": "Observability indicators conflict with reported infrastructure stability.",
                "penalty": 20
            })
        else:
            conflicts.append({
                "severity": "MEDIUM",
                "message": "Contradictory readiness signals increased escalation severity.",
                "penalty": 10
            })

    if signals.get("infrastructure_stability") == "HIGH" and signals.get("error_rate") == "HIGH":
        conflicts.append({
            "severity": "MEDIUM",
            "message": "Decision conflict: system stability reports HIGH while error rate is also HIGH.",
            "penalty": 10
        })
            
    return conflicts
