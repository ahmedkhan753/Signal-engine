def detect_conflicts(signals):
    conflicts = []
    
    stability = signals.get('system_stability')
    error_rate = signals.get('error_rate')
    security_threat = signals.get('security_threat')
    deployment_risk = signals.get('deployment_risk')
    
    if stability == 'HIGH' and error_rate == 'HIGH':
        conflicts.append("Stability HIGH conflicts with Error Rate HIGH")
    if stability == 'LOW' and error_rate == 'LOW':
        conflicts.append("Stability LOW conflicts with Error Rate LOW")
    if security_threat == 'HIGH' and deployment_risk == 'LOW':
        conflicts.append("Security Threat HIGH conflicts with Deployment Risk LOW")
        
    return conflicts

def get_signal_display_name(key):
    return key.replace("_", " ").capitalize()

def calculate_score(signals, conflicts, trace_steps):
    score = 100
    
    positive_signals = {'system_stability', 'network_reliability'}
    negative_signals = {'error_rate', 'deployment_risk', 'security_threat', 'data_loss_risk'}
    
    for key, value in signals.items():
        name = get_signal_display_name(key)
        if key in positive_signals:
            if value == 'HIGH':
                trace_steps.append(f"{name} is HIGH -> no penalty")
            elif value == 'MEDIUM':
                score -= 5
                trace_steps.append(f"{name} is MEDIUM -> -5")
            elif value == 'LOW':
                score -= 10
                trace_steps.append(f"{name} is LOW -> -10")
        elif key in negative_signals:
            if value == 'HIGH':
                score -= 15
                trace_steps.append(f"{name} is HIGH -> -15")
            elif value == 'MEDIUM':
                score -= 8
                trace_steps.append(f"{name} is MEDIUM -> -8")
            elif value == 'LOW':
                trace_steps.append(f"{name} is LOW -> no penalty")
        else:
            trace_steps.append(f"{name} is {value} -> no penalty")
                
    for conflict in conflicts:
        score -= 8
        trace_steps.append("Conflict detected -> -8")
        
    return max(0, min(100, score))

def make_decision(score):
    if score >= 70:
        return 'ALLOW'
    elif score >= 40:
        return 'DELAY'
    return 'BLOCK'

def generate_trace(scenario_name, score, decision, conflicts, trace_steps):
    lines = []
    lines.append("=" * 40)
    lines.append(f"SCENARIO: {scenario_name}")
    lines.append("=" * max(40, len(f"SCENARIO: {scenario_name}")))
    lines.append("")
    lines.append(f"Alignment Score: {score} / 100")
    lines.append(f"Decision: {decision}")
    
    if score < 100:
        if conflicts:
            lines.append(f"Alignment Change: 100 -> {score} (drop due to conflicts)")
        else:
            lines.append(f"Alignment Change: 100 -> {score} (drop due to penalties)")
    else:
        lines.append("Alignment Change: 100 -> 100 (Perfect alignment)")
        
    lines.append("")
    
    if conflicts:
        lines.append("Conflicts Detected:")
        for c in conflicts:
            lines.append(f"- {c}")
        lines.append("")
        
    lines.append("Trace:")
    for step in trace_steps:
        lines.append(f"- {step}")
        
    lines.append(f"- Final score = {score} -> {decision}")
    lines.append("")
    lines.append("=" * 40)
    lines.append("")
    
    return "\n".join(lines)

def evaluate_signals(scenario_name, signals):
    trace_steps = []
    
    conflicts = detect_conflicts(signals)
    score = calculate_score(signals, conflicts, trace_steps)
    decision = make_decision(score)
    
    trace_output = generate_trace(scenario_name, score, decision, conflicts, trace_steps)
    print(trace_output)
    
    return {
        "score": score,
        "decision": decision,
        "conflicts": conflicts
    }
