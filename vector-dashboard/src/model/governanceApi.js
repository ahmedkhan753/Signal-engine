/**
 * VECTOR governance API contract (V2 backend integration).
 *
 * This is the stable response shape returned by `POST /evaluate` from the
 * lightweight backend API layer (`api.py`). The dashboard maps this through
 * `mapGovernanceResponseToViewModel`.
 *
 * Request:  { "scenario_id": "stable_deployment" }
 *
 * Governance meaning is owned by the backend:
 * - `decision` is authoritative (ALLOW / DELAY / BLOCK).
 * - `overall_status` is returned directly (SAFE / CAUTION / STOP) — the
 *   frontend renders it as-is and never derives it.
 * - Each facet `status` is likewise returned as SAFE / CAUTION / STOP.
 *
 * @typedef {{
 *   source: string;
 *   sourceLabel: string;
 *   metric: string;
 *   metricLabel: string;
 *   statusLabel: string;
 *   icon: string;
 *   value: string;
 *   conf: number;
 * }} GovernanceApiSignalRow
 *
 * @typedef {{
 *   id: string;
 *   label: string;
 *   status: 'SAFE'|'CAUTION'|'STOP';
 *   score: number;
 *   summary: string;
 *   trace: string[];
 *   signals: GovernanceApiSignalRow[];
 * }} GovernanceApiFacet
 *
 * @typedef {{ severity: string; message: string }} GovernanceApiConflict
 *
 * @typedef {{ initial: number; final: number; reason: string }} GovernanceApiAlignmentChange
 *
 * @typedef {{
 *   scenario_id: string;
 *   scenario_name: string;
 *   alignment_score: number;
 *   alignment_change: GovernanceApiAlignmentChange;
 *   decision: 'ALLOW'|'DELAY'|'BLOCK';
 *   risk_level: 'LOW'|'MODERATE'|'HIGH'|'CRITICAL';
 *   overall_status: 'SAFE'|'CAUTION'|'STOP';
 *   reason: string;
 *   decision_summary: string;
 *   conflicts: GovernanceApiConflict[];
 *   conflict_count: number;
 *   facets: GovernanceApiFacet[];
 *   global_trace: string[];
 *   technical_trace: string[];
 *   hard_constraint_triggered: boolean;
 * }} GovernanceApiResponse
 */

export {}
