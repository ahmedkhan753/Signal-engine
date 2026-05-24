/**
 * UI-facing view model produced by `mapGovernanceResponseToViewModel`.
 *
 * @typedef {{ source: string; sourceLabel: string; metricLabel: string; statusLabel: string; icon: string; metric: string; value: string; conf: number }} DashboardSignalRow
 *
 * @typedef {{
 *   id: string;
 *   label: string;
 *   status: 'SAFE'|'CAUTION'|'STOP';
 *   subScore: number;
 *   contributingSignals: DashboardSignalRow[];
 *   localExplanationPlain: string;
 *   localTraceTechnical: string;
 * }} DashboardFacet
 *
 * @typedef {{
 *   scenarioId: string;
 *   scenarioTitle: string;
 *   scenarioSubtitle: string;
 *   demoScenarioLabel: string;
 *   score: number;
 *   alignmentChange: { initial: number; final: number; reason: string };
 *   decision: 'ALLOW'|'DELAY'|'BLOCK';
 *   alignment: 'SAFE'|'CAUTION'|'STOP';
 *   risk: 'low'|'medium'|'high';
 *   riskLabel: string;
 *   conflicts: string[];
 *   facets: DashboardFacet[];
 *   operationalSummary: string;
 *   operationalTrace: string;
 *   technicalTrace: string;
 *   hardConstraintTriggered: boolean;
 *   signals: DashboardSignalRow[];
 * }} DashboardViewModel
 */

export {}
