scenarios = {
    "Stable Deployment": {
        "infrastructure_stability": "HIGH",
        "deployment_readiness": "HIGH",
        "orchestration_readiness": "HIGH",
        "service_latency": "LOW",
        "error_rate": "LOW",
        "rollback_trigger": "LOW",
        "policy_violation": "LOW",
        "security_threat": "LOW",
        "active_breach": "LOW",
        "observability_disagreement": "LOW"
    },
    "Hidden Instability": {
        "infrastructure_stability": "HIGH",
        "deployment_readiness": "HIGH",
        "observability_disagreement": "HIGH",
        "service_latency": "HIGH",
        "error_rate": "LOW"
    },
    "Observability Disagreement": {
        "infrastructure_stability": "HIGH",
        "observability_disagreement": "HIGH",
        "deployment_readiness": "MEDIUM"
    },
    "Cascading Degradation": {
        "infrastructure_stability": "LOW",
        "service_latency": "HIGH",
        "error_rate": "HIGH",
        "orchestration_readiness": "LOW",
        "rollback_trigger": "HIGH"
    },
    "Orchestration Conflict": {
        "deployment_readiness": "HIGH",
        "orchestration_readiness": "LOW",
        "infrastructure_stability": "HIGH"
    },
    "Rollback Trigger": {
        "rollback_trigger": "HIGH",
        "error_rate": "HIGH",
        "service_latency": "HIGH"
    },
    "Security Concern": {
        "security_threat": "HIGH",
        "deployment_readiness": "HIGH",
        "infrastructure_stability": "HIGH"
    },
    "Policy Constraint Violation": {
        "policy_violation": "HIGH",
        "active_breach": "HIGH",
        "deployment_readiness": "HIGH"
    }
}
