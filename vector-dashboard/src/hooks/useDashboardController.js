import { useCallback, useEffect, useRef, useState } from 'react'
import { mapGovernanceResponseToViewModel } from '../adapters/mapGovernanceResponseToViewModel'
import { fetchEvaluation, fetchScenarios } from '../api/governanceClient'

/** Hold each demo step long enough for score ring + layout to settle. */
const DEMO_STEP_MS = 3400

/**
 * Fallback catalogue used only if `GET /scenarios` is unreachable on first paint.
 * Keeps the canonical Normal / Conflict / Escalation / Block buttons functional.
 */
const FALLBACK_SCENARIOS = [
  { scenario_id: 'stable_deployment',           scenario_name: 'Stable Deployment',           demo_step: 'Normal',     demo_order: 1 },
  { scenario_id: 'hidden_instability',          scenario_name: 'Hidden Instability',          demo_step: 'Conflict',   demo_order: 2 },
  { scenario_id: 'cascading_degradation',       scenario_name: 'Cascading Degradation',       demo_step: 'Escalation', demo_order: 3 },
  { scenario_id: 'policy_constraint_violation', scenario_name: 'Policy Constraint Violation', demo_step: 'Block',      demo_order: 4 },
]

/** Neutral view model rendered before the first backend response arrives. */
const INITIAL_VIEW_MODEL = mapGovernanceResponseToViewModel({})

/** Picks the canonical Normal / Conflict / Block ids for the 3 quick-run buttons. */
function pickQuickRunIds(catalogue) {
  const byStep = (step) => catalogue.find((s) => s.demo_step === step)?.scenario_id
  const normal = byStep('Normal') ?? catalogue[0]?.scenario_id ?? 'stable_deployment'
  const conflict = byStep('Conflict') ?? normal
  const block = byStep('Block') ?? byStep('Escalation') ?? conflict
  return [normal, conflict, block]
}

/** Demo cycle = scenarios with a `demo_order`, ordered by it. */
function pickDemoSequence(catalogue) {
  return catalogue
    .filter((s) => typeof s.demo_order === 'number')
    .slice()
    .sort((a, b) => a.demo_order - b.demo_order)
    .map((s) => s.scenario_id)
}

export function useDashboardController() {
  const [viewModel, setViewModel] = useState(INITIAL_VIEW_MODEL)
  const [scenarioCatalogue, setScenarioCatalogue] = useState(FALLBACK_SCENARIOS)
  const [activeScenarioId, setActiveScenarioId] = useState(FALLBACK_SCENARIOS[0].scenario_id)
  /** Bumps on every navigation so UI (e.g. conflict pulse) can react even when scenario repeats. */
  const [scenarioNonce, setScenarioNonce] = useState(0)
  /** 'loading' | 'ready' | 'error' */
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const demoTimeoutsRef = useRef([])
  /** Guards against out-of-order responses when scenarios are switched quickly. */
  const requestIdRef = useRef(0)

  const clearDemoTimeout = useCallback(() => {
    demoTimeoutsRef.current.forEach((t) => window.clearTimeout(t))
    demoTimeoutsRef.current = []
  }, [])

  /**
   * Async fetch + apply for a single scenario id.
   * State is written only after the `await`, so this is safe to call from an
   * effect without triggering synchronous cascading renders.
   */
  const runEvaluation = useCallback(async (scenarioId) => {
    if (!scenarioId) return
    const requestId = (requestIdRef.current += 1)
    try {
      const raw = await fetchEvaluation(scenarioId)
      if (requestId !== requestIdRef.current) return // a newer request superseded this one
      setViewModel(mapGovernanceResponseToViewModel(raw))
      setStatus('ready')
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      setError(err?.message || 'Unable to reach the governance backend.')
      setStatus('error')
    }
  }, [])

  /** Synchronous navigation — marks loading then kicks off the fetch. For user actions. */
  const goToScenarioId = useCallback(
    (scenarioId) => {
      if (!scenarioId) return
      setActiveScenarioId(scenarioId)
      setScenarioNonce((n) => n + 1)
      setStatus('loading')
      setError(null)
      runEvaluation(scenarioId)
    },
    [runEvaluation],
  )

  // Mount: fetch catalogue + the first scenario in parallel. setState only runs
  // inside the async promise callbacks (never synchronously in the effect body).
  useEffect(() => {
    let cancelled = false
    const requestId = (requestIdRef.current += 1)

    fetchScenarios()
      .then((data) => {
        if (cancelled) return
        const list = Array.isArray(data?.scenarios) && data.scenarios.length > 0
          ? data.scenarios
          : FALLBACK_SCENARIOS
        setScenarioCatalogue(list)
        setActiveScenarioId(list[0].scenario_id)
      })
      .catch(() => {
        /* Keep fallback catalogue; the evaluation call below will surface any
           backend-down state via the connection banner. */
      })

    fetchEvaluation(FALLBACK_SCENARIOS[0].scenario_id)
      .then((raw) => {
        if (cancelled || requestId !== requestIdRef.current) return
        setViewModel(mapGovernanceResponseToViewModel(raw))
        setStatus('ready')
      })
      .catch((err) => {
        if (cancelled || requestId !== requestIdRef.current) return
        setError(err?.message || 'Unable to reach the governance backend.')
        setStatus('error')
      })

    return () => {
      cancelled = true
      clearDemoTimeout()
    }
  }, [clearDemoTimeout])

  /** Index-based selection used by the existing 3 quick-run buttons. */
  const selectScenario = useCallback(
    (index) => {
      clearDemoTimeout()
      const quickIds = pickQuickRunIds(scenarioCatalogue)
      const next = Math.min(Math.max(0, index), quickIds.length - 1)
      goToScenarioId(quickIds[next])
    },
    [clearDemoTimeout, goToScenarioId, scenarioCatalogue],
  )

  /** Id-based selection used by the scenario picker dropdown. */
  const selectScenarioById = useCallback(
    (scenarioId) => {
      clearDemoTimeout()
      goToScenarioId(scenarioId)
    },
    [clearDemoTimeout, goToScenarioId],
  )

  const resetDemo = useCallback(() => {
    clearDemoTimeout()
    const quickIds = pickQuickRunIds(scenarioCatalogue)
    goToScenarioId(quickIds[0])
  }, [clearDemoTimeout, goToScenarioId, scenarioCatalogue])

  /**
   * Canonical demo flow: Normal -> Conflict -> Escalation -> Hard Constraint Block.
   * Driven by `demo_order` on the live scenario catalogue (falls back to the
   * built-in 4-step sequence if the catalogue is unavailable).
   */
  const runDemo = useCallback(() => {
    clearDemoTimeout()
    const sequence = pickDemoSequence(scenarioCatalogue)
    if (sequence.length === 0) return
    goToScenarioId(sequence[0])
    const timeouts = []
    for (let i = 1; i < sequence.length; i += 1) {
      const id = sequence[i]
      timeouts.push(window.setTimeout(() => goToScenarioId(id), DEMO_STEP_MS * i))
    }
    demoTimeoutsRef.current = timeouts
  }, [clearDemoTimeout, goToScenarioId, scenarioCatalogue])

  return {
    viewModel,
    scenarioCatalogue,
    activeScenarioId,
    scenarioNonce,
    status,
    error,
    selectScenario,
    selectScenarioById,
    resetDemo,
    runDemo,
  }
}
