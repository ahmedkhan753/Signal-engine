/**
 * @param {{
 *  operationalSummary: string;
 *  overallAlignment: 'SAFE'|'CAUTION'|'STOP';
 *  overallDecision: 'ALLOW'|'DELAY'|'BLOCK';
 *  risk: 'low'|'medium'|'high';
 *  conflictsCount: number;
 * }} props
 */
export function DashboardHeader({
  operationalSummary,
  overallAlignment,
  overallDecision,
  risk,
  conflictsCount,
}) {
  const RISK_LABEL = { low: 'Low', medium: 'Medium', high: 'High' }
  const alignmentLower = overallAlignment.toLowerCase()
  const ALIGNMENT_WORD = { SAFE: 'Clear', CAUTION: 'Caution', STOP: 'Stop' }

  return (
    <header className="main-header">
      <div>
        <h1 className="main-title">VECTOR governance console</h1>
        <p className="main-sub">{operationalSummary}</p>
      </div>
      <div className="header-right">
        <div className="status-cluster">
          <span className={`status-pill status-${alignmentLower}`} title="Worst facet posture">
            {ALIGNMENT_WORD[overallAlignment]}
          </span>
          <span className="status-label">Outcome: {overallDecision}</span>
        </div>
        <div className="status-cluster">
          <span className={`status-label risk-text risk-${risk}`}>Risk: {RISK_LABEL[risk]}</span>
          <span className={`status-label conflict-text ${conflictsCount > 0 ? 'conflict-yes' : 'conflict-no'}`}>
            Conflicts: {conflictsCount > 0 ? conflictsCount : 'None'}
          </span>
        </div>
      </div>
    </header>
  )
}
