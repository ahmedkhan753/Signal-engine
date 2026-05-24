/**
 * VECTOR V2 end-to-end integration smoke test (no browser required).
 *
 * Exercises the full data path on the live system:
 *   backend engine -> /scenarios + /evaluate -> adapter -> view model
 *
 * Asserts:
 *   - the /scenarios catalogue lists all 8 wired scenarios
 *   - every scenario returns a contract-shaped response with valid types
 *   - the adapter produces a renderable view model
 *   - decisions / statuses match the expected deterministic matrix
 *   - repeated executions produce byte-identical contracts (determinism)
 *   - invalid scenario ids return 404; missing ids return 400
 *
 * Prerequisite: the backend is running (`python api.py`).
 * Run from the vector-dashboard directory:  node scripts/smoke-test.mjs
 */
import { mapGovernanceResponseToViewModel } from '../src/adapters/mapGovernanceResponseToViewModel.js'

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** Expected deterministic governance matrix — used to detect engine calibration drift. */
const EXPECTED = {
  stable_deployment:           { decision: 'ALLOW', alignment: 'SAFE',    risk: 'low',    score: 100, conflicts: 0, hard: false },
  hidden_instability:          { decision: 'ALLOW', alignment: 'SAFE',    risk: 'high',   score: 72,  conflicts: 1, hard: false },
  observability_disagreement:  { decision: 'ALLOW', alignment: 'SAFE',    risk: 'high',   score: 75,  conflicts: 1, hard: false },
  cascading_degradation:       { decision: 'DELAY', alignment: 'CAUTION', risk: 'high',   score: 63,  conflicts: 1, hard: false },
  orchestration_conflict:      { decision: 'ALLOW', alignment: 'SAFE',    risk: 'high',   score: 77,  conflicts: 1, hard: false },
  rollback_trigger:            { decision: 'DELAY', alignment: 'CAUTION', risk: 'high',   score: 68,  conflicts: 1, hard: false },
  security_concern:            { decision: 'ALLOW', alignment: 'SAFE',    risk: 'low',    score: 96,  conflicts: 0, hard: false },
  policy_constraint_violation: { decision: 'BLOCK', alignment: 'STOP',    risk: 'high',   score: 0,   conflicts: 2, hard: true  },
}

async function getJson(path, init) {
  const res = await fetch(`${API_BASE_URL}${path}`, init)
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status} ${path}: ${body}`)
  }
  return res.json()
}

function evaluate(scenarioId) {
  return getJson('/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId }),
  })
}

const REQUIRED_CONTRACT_FIELDS = [
  'scenario_id', 'scenario_name', 'alignment_score', 'alignment_change',
  'decision', 'risk_level', 'overall_status', 'reason', 'decision_summary',
  'conflicts', 'conflict_count', 'facets', 'global_trace', 'technical_trace',
  'hard_constraint_triggered',
]

let failures = 0
function check(label, ok, detail = '') {
  if (!ok) {
    failures += 1
    console.log(`  ✗ ${label}${detail ? ' — ' + detail : ''}`)
  }
}

// --- 1. /scenarios catalogue ------------------------------------------------
console.log('\n[1] /scenarios catalogue')
const catalogue = await getJson('/scenarios')
check('returns scenarios array', Array.isArray(catalogue.scenarios))
check('lists all 8 wired scenarios', catalogue.scenarios.length === 8,
  `got ${catalogue.scenarios.length}`)
const demoSteps = catalogue.scenarios
  .filter((s) => s.demo_step)
  .map((s) => s.demo_step)
check(
  'canonical demo order is Normal → Conflict → Escalation → Block',
  demoSteps.join(',') === 'Normal,Conflict,Escalation,Block',
  demoSteps.join(','),
)

// --- 2. /evaluate for every scenario ---------------------------------------
console.log('\n[2] /evaluate — contract + view model + expected outcome')
for (const scenario of catalogue.scenarios) {
  const id = scenario.scenario_id
  const expected = EXPECTED[id]
  const raw = await evaluate(id)
  const vm = mapGovernanceResponseToViewModel(raw)

  console.log(
    `  ● ${id.padEnd(30)} ${vm.decision.padEnd(5)} ${vm.alignment.padEnd(7)} ${String(vm.score).padStart(3)}  ` +
    `risk=${vm.riskLabel}  conflicts=${vm.conflicts.length}${vm.hardConstraintTriggered ? '  [HARD CONSTRAINT]' : ''}`,
  )

  for (const field of REQUIRED_CONTRACT_FIELDS) {
    check(`${id}: contract has ${field}`, field in raw)
  }
  check(`${id}: 4 facets`, vm.facets.length === 4)
  check(`${id}: traces present`, vm.operationalTrace.length > 0 && vm.technicalTrace.length > 0)
  if (expected) {
    check(`${id}: decision matches expected`, vm.decision === expected.decision,
      `got ${vm.decision}, expected ${expected.decision}`)
    check(`${id}: alignment matches expected`, vm.alignment === expected.alignment,
      `got ${vm.alignment}, expected ${expected.alignment}`)
    check(`${id}: risk matches expected`, vm.risk === expected.risk,
      `got ${vm.risk}, expected ${expected.risk}`)
    check(`${id}: score matches expected`, vm.score === expected.score,
      `got ${vm.score}, expected ${expected.score}`)
    check(`${id}: conflict count matches expected`, vm.conflicts.length === expected.conflicts)
    check(`${id}: hard_constraint_triggered matches expected`, vm.hardConstraintTriggered === expected.hard)
  }
  for (const s of vm.facets.flatMap((f) => f.contributingSignals)) {
    check(`${id}: signal row well-formed`,
      typeof s.source === 'string' && Number.isFinite(s.conf) && s.conf >= 0 && s.conf <= 1)
  }
}

// --- 3. Determinism --------------------------------------------------------
console.log('\n[3] Determinism — repeated executions must be byte-identical')
for (const scenario of catalogue.scenarios) {
  const a = JSON.stringify(await evaluate(scenario.scenario_id))
  const b = JSON.stringify(await evaluate(scenario.scenario_id))
  check(`${scenario.scenario_id}: 2× identical`, a === b)
}

// --- 4. Error paths --------------------------------------------------------
console.log('\n[4] Error handling')
const bad = await fetch(`${API_BASE_URL}/evaluate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ scenario_id: 'does_not_exist' }),
})
check('unknown scenario_id → 404', bad.status === 404)
const missing = await fetch(`${API_BASE_URL}/evaluate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: '{}',
})
check('missing scenario_id → 400', missing.status === 400)

console.log(`\n${failures === 0 ? '✓ ALL CHECKS PASSED' : `✗ ${failures} CHECK(S) FAILED`}`)
process.exit(failures === 0 ? 0 : 1)
