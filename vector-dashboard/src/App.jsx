import { useDashboardController } from './hooks/useDashboardController'
import { useAnimatedScore } from './hooks/useAnimatedScore'
import { getAlignmentColor } from './constants/decision'
import { Sidebar } from './components/Sidebar'
import { DashboardHeader } from './components/DashboardHeader'
import { RunScenarioCard } from './components/RunScenarioCard'
import { ScoreCard } from './components/ScoreCard'
import { DecisionCard } from './components/DecisionCard'
import { RiskCard } from './components/RiskCard'
import { ConflictsPanel } from './components/ConflictsPanel'
import { DecisionTrace } from './components/DecisionTrace'
import { EvaluationFacets } from './components/EvaluationFacets'

function scoreCardHighlight(decision) {
  if (decision === 'ALLOW') return 'highlight-ok'
  if (decision === 'DELAY') return 'highlight-warn'
  return 'highlight-critical'
}

/** Minimal, additive connection banner — does not alter the existing dashboard design. */
function ConnectionBanner({ status, error }) {
  if (status === 'error') {
    return (
      <div
        role="alert"
        style={{
          background: '#3a1212',
          color: '#ff8a8a',
          border: '1px solid #FF5C5C',
          borderRadius: 8,
          padding: '10px 14px',
          marginBottom: 16,
          fontSize: 13,
          lineHeight: 1.5,
        }}
      >
        Governance backend unreachable — {error} Start it with{' '}
        <code style={{ fontFamily: 'monospace' }}>python api.py</code> (expects http://localhost:8000).
      </div>
    )
  }
  if (status === 'loading') {
    return (
      <div
        style={{
          color: '#8b949e',
          fontSize: 12,
          marginBottom: 16,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        Evaluating scenario via live backend…
      </div>
    )
  }
  return null
}

/** Active-scenario chip + optional hard-constraint badge, inline-styled to preserve the existing header design. */
function ActiveScenarioStrip({ scenarioTitle, riskLabel, hardConstraintTriggered, alignmentChange }) {
  const chip = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 9px',
    fontSize: 11,
    fontWeight: 500,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    borderRadius: 999,
    border: '1px solid rgba(230, 237, 243, 0.16)',
    color: '#c9d1d9',
    background: 'rgba(13, 17, 23, 0.45)',
    lineHeight: 1.4,
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', margin: '0 0 12px' }}>
      <span style={chip}>Scenario · {scenarioTitle}</span>
      {riskLabel && <span style={chip}>Engine risk · {riskLabel}</span>}
      {alignmentChange && alignmentChange.initial !== alignmentChange.final && (
        <span style={chip}>
          Alignment · {alignmentChange.initial} → {alignmentChange.final}
        </span>
      )}
      {hardConstraintTriggered && (
        <span
          style={{
            ...chip,
            color: '#FF8A8A',
            background: 'rgba(255, 92, 92, 0.12)',
            border: '1px solid rgba(255, 92, 92, 0.45)',
          }}
          title="One or more hard constraints were violated"
        >
          ⚠ Hard constraint triggered
        </span>
      )}
    </div>
  )
}

export default function App() {
  const {
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
  } = useDashboardController()
  const displayScore = useAnimatedScore(viewModel.score, viewModel.scenarioId)
  const alignmentColor = getAlignmentColor(displayScore)

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <ConnectionBanner status={status} error={error} />
        <DashboardHeader
          operationalSummary={viewModel.operationalSummary}
          overallAlignment={viewModel.alignment}
          overallDecision={viewModel.decision}
          risk={viewModel.risk}
          conflictsCount={viewModel.conflicts.length}
        />
        <ActiveScenarioStrip
          scenarioTitle={viewModel.scenarioTitle}
          riskLabel={viewModel.riskLabel}
          hardConstraintTriggered={viewModel.hardConstraintTriggered}
          alignmentChange={viewModel.alignmentChange}
        />
        <RunScenarioCard
          onRunScenario0={() => selectScenario(0)}
          onRunScenario1={() => selectScenario(1)}
          onRunScenario2={() => selectScenario(2)}
          onReset={resetDemo}
          onRunDemo={runDemo}
          scenarios={scenarioCatalogue}
          activeScenarioId={activeScenarioId}
          onSelectScenarioById={selectScenarioById}
        />
        <div className="main-surface scenario-surface-fade" key={viewModel.scenarioId}>
          <div className="row-mid">
            <ScoreCard
              score={displayScore}
              strokeColor={alignmentColor}
              highlightClass={scoreCardHighlight(viewModel.decision)}
            />
            <DecisionCard decision={viewModel.decision} />
            <RiskCard risk={viewModel.risk} />
          </div>
          <div className="row-bottom">
            <EvaluationFacets
              facets={viewModel.facets}
              overallDecision={viewModel.decision}
              animationKey={viewModel.scenarioId}
            />
            <ConflictsPanel
              conflicts={viewModel.conflicts}
              pulseKey={scenarioNonce}
              overallDecision={viewModel.decision}
            />
            <DecisionTrace
              operationalTrace={viewModel.operationalTrace}
              technicalTrace={viewModel.technicalTrace}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
