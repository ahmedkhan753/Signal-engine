def format_cli_output(response):
    lines = []

    scenario_name = response.get("scenario", "Unknown Scenario")
    lines.append("=" * 50)
    lines.append(f"SCENARIO: {scenario_name}")
    lines.append("=" * max(28, len(f"SCENARIO: {scenario_name}")))
    lines.append("")

    score = response.get("system_alignment_score", 0)
    decision = response.get("decision", "BLOCK")
    risk_level = response.get("risk_level", "CRITICAL")
    overall_status = response.get("overall_status", "STOP")

    lines.append(f"System Alignment Score: {score} / 100")
    lines.append(f"Decision: {decision}")
    lines.append(f"Risk Level: {risk_level}")
    lines.append(f"Overall Status: {overall_status}")
    lines.append("")

    alignment = response.get("alignment_change", {})
    initial = alignment.get("initial", 100)
    final = alignment.get("final", score)
    reason = alignment.get("reason", "")

    lines.append(f"System Alignment Change: {initial} -> {final}")
    lines.append(f"Reason: {reason}")
    lines.append("")

    lines.append("Decision Summary:")
    lines.append(response.get("decision_summary", ""))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## FACET RESULTS")
    lines.append("")

    for facet in response.get("facets", []):
        lines.append(f"[{facet['facet']}]")
        lines.append(f"Score: {facet['score']}")
        lines.append(f"Status: {facet['status']}")
        lines.append("Summary:")
        lines.append(facet['summary'])
        if facet.get("trace"):
            lines.append("Local Trace:")
            for t in facet["trace"]:
                lines.append(f"  - {t}")
        lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## CONFLICTS DETECTED")
    lines.append("")
    conflicts = response.get("conflicts", [])
    if conflicts:
        for c in conflicts:
            lines.append(f"Severity: {c['severity']}")
            lines.append(c['message'])
            lines.append("")
    else:
        lines.append("None")
        lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## GLOBAL TRACE")
    lines.append("")
    for t in response.get("global_trace", []):
        lines.append(f"* {t}")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Result:")
    lines.append(response.get("result", ""))

    lines.append("=" * 50)
    lines.append("")

    return "\n".join(lines)
