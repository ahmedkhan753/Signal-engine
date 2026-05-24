import { API_BASE_URL } from '../config/apiConfig'

/**
 * Fetches the catalogue of wired scenarios with demo-flow metadata.
 *
 * @returns {Promise<{scenarios: Array<{scenario_id: string, scenario_name: string, demo_step: string|null, demo_order: number|null}>}>}
 * @throws {Error} when the backend is unreachable or returns a non-2xx status
 */
export async function fetchScenarios() {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/scenarios`)
  } catch {
    throw new Error(`Cannot reach the governance backend at ${API_BASE_URL}.`)
  }
  if (!response.ok) {
    throw new Error(`Scenario catalogue unavailable (HTTP ${response.status}).`)
  }
  return response.json()
}

/**
 * Calls the VECTOR backend governance engine for a single scenario.
 *
 * @param {string} scenarioId stable scenario slug, e.g. 'stable_deployment'
 * @returns {Promise<import('../model/governanceApi.js').GovernanceApiResponse>}
 * @throws {Error} when the backend is unreachable or returns a non-2xx status
 */
export async function fetchEvaluation(scenarioId) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/evaluate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId }),
    })
  } catch {
    throw new Error(`Cannot reach the governance backend at ${API_BASE_URL}.`)
  }

  if (!response.ok) {
    let detail = ''
    try {
      detail = (await response.json())?.error ?? ''
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail || `Evaluation failed (HTTP ${response.status}).`)
  }

  return response.json()
}
