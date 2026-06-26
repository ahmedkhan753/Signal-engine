/**
 * Maps the VECTOR backend governance response into the dashboard view model.
 * When the API schema changes, update this file only — not the React tree.
 *
 * Governance precedence:
 * - `decision` and `overall_status` come straight from the backend.
 * - The frontend does NOT derive governance meaning; it only normalises
 *   types and adapts presentation (e.g. collapsing the 4-level engine
 *   risk into the 3-level risk pill the dashboard renders).
 *
 * @param {import('../model/governanceApi.js').GovernanceApiResponse} raw
 * @returns {import('../model/dashboardViewModel.js').DashboardViewModel}
 */
export function mapGovernanceResponseToViewModel(raw) {
  const safe = raw && typeof raw === 'object' ? raw : {}
  const facets = (Array.isArray(safe.facets) ? safe.facets : []).map(mapFacet)

  return {
    scenarioId: String(safe.scenario_id ?? 'unknown'),
    scenarioTitle: String(safe.scenario_name ?? 'Evaluation'),
    scenarioSubtitle: String(safe.reason ?? ''),
    demoScenarioLabel: String(safe.scenario_name ?? 'Scenario'),
    score: clampScore(safe.alignment_score),
    alignmentChange: normalizeAlignmentChange(safe.alignment_change, safe.alignment_score),
    decision: normalizeDecision(safe.decision),
    // Returned directly by the backend — never derived here.
    alignment: normalizeStatus(safe.overall_status),
    risk: normalizeRisk(safe.risk_level),
    riskLabel: String(safe.risk_level ?? '').toUpperCase() || 'UNKNOWN',
    conflicts: mapConflicts(safe.conflicts),
    facets,
    operationalSummary: String(safe.decision_summary ?? '').trim() || '—',
    operationalTrace: joinTrace(safe.global_trace),
    technicalTrace: joinTrace(safe.technical_trace),
    hardConstraintTriggered: Boolean(safe.hard_constraint_triggered),
    // V3 Phase 1 — backend-owned runtime governance state. Pass-through only.
    runtimeState: normalizeRuntimeState(safe.runtime_state),
    recommendedAction: normalizeRecommendedAction(safe.recommended_action),
    timelineEvents: normalizeTimelineEvents(safe.timeline_events),
    evidencePacket: safe.evidence_packet && typeof safe.evidence_packet === 'object'
      ? safe.evidence_packet
      : null,
    signals: [],
  }
}

const RUNTIME_STATE_ENUM = new Set([
  'STABLE', 'CONTRADICTORY', 'DEGRADED',
  'RECOVERY_PENDING', 'CONSTRAINT_LOCKED', 'HUMAN_REVIEW_REQUIRED',
])
const RECOMMENDED_ACTION_ENUM = new Set([
  'CONTINUE', 'DELAY_AND_REVIEW', 'ESCALATE_TO_OPERATOR',
  'BLOCK_EXECUTION', 'VALIDATE_RECOVERY',
  'MONITOR_FOR_DRIFT', 'VALIDATE_READINESS',
])

function normalizeRuntimeState(s) {
  const u = String(s || '').toUpperCase()
  return RUNTIME_STATE_ENUM.has(u) ? u : 'STABLE'
}

function normalizeRecommendedAction(a) {
  const u = String(a || '').toUpperCase()
  return RECOMMENDED_ACTION_ENUM.has(u) ? u : 'CONTINUE'
}

function normalizeTimelineEvents(events) {
  if (!Array.isArray(events)) return []
  return events
    .map((e) => {
      if (!e || typeof e !== 'object') return null
      const code = String(e.code ?? '')
      const label = String(e.label ?? '')
      return code ? { code, label } : null
    })
    .filter(Boolean)
}

function normalizeAlignmentChange(change, fallbackScore) {
  const c = change && typeof change === 'object' ? change : {}
  return {
    initial: clampScore(c.initial ?? 100),
    final: clampScore(c.final ?? fallbackScore),
    reason: String(c.reason ?? ''),
  }
}

/** @param {import('../model/governanceApi.js').GovernanceApiFacet} f */
function mapFacet(f) {
  const facet = f && typeof f === 'object' ? f : {}
  return {
    id: String(facet.id ?? ''),
    label: String(facet.label ?? ''),
    status: normalizeStatus(facet.status),
    subScore: clampScore(facet.score),
    contributingSignals: (Array.isArray(facet.signals) ? facet.signals : [])
      .map(normalizeSignal)
      .filter(Boolean),
    localExplanationPlain: String(facet.summary ?? ''),
    localTraceTechnical: joinTrace(facet.trace),
  }
}

/** @param {import('../model/governanceApi.js').GovernanceApiSignalRow | null | undefined} row */
function normalizeSignal(row) {
  if (row == null || typeof row !== 'object') return null
  const conf = Number(row.conf)
  if (!Number.isFinite(conf)) return null
  if (typeof row.source !== 'string' || typeof row.metric !== 'string') return null
  return { ...row, conf: Math.min(1, Math.max(0, conf)) }
}

/** Backend conflicts are { severity, message } objects; the panel renders strings. */
function mapConflicts(conflicts) {
  if (!Array.isArray(conflicts)) return []
  return conflicts
    .map((c) => (typeof c === 'string' ? c : String(c?.message ?? '')))
    .filter(Boolean)
}

/** Trace fields arrive as string arrays; the trace components render strings. */
function joinTrace(trace) {
  if (Array.isArray(trace)) return trace.join('\n')
  return String(trace ?? '')
}

/** @param {unknown} d */
function normalizeDecision(d) {
  const u = String(d || '').toUpperCase()
  if (u === 'BLOCK' || u === 'DELAY' || u === 'ALLOW') return u
  return 'ALLOW'
}

/** @param {unknown} s */
function normalizeStatus(s) {
  const u = String(s || '').toUpperCase()
  if (u === 'STOP' || u === 'CAUTION' || u === 'SAFE') return u
  return 'SAFE'
}

/**
 * Collapse the engine's 4-level risk (LOW / MODERATE / HIGH / CRITICAL)
 * into the dashboard's 3-level risk pill. Presentation only.
 * @param {unknown} r
 */
function normalizeRisk(r) {
  const u = String(r || '').toUpperCase()
  if (u === 'CRITICAL' || u === 'HIGH') return 'high'
  if (u === 'MODERATE' || u === 'MEDIUM') return 'medium'
  return 'low'
}

/** @param {unknown} n */
function clampScore(n) {
  const v = Math.round(Number(n))
  if (!Number.isFinite(v)) return 0
  return Math.min(100, Math.max(0, v))
}
