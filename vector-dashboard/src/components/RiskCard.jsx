const RISK_LABEL = { low: 'Low', medium: 'Medium', high: 'High' }

/**
 * @param {{ risk: import('../model/dashboardViewModel.js').DashboardViewModel['risk'] }} props
 */
export function RiskCard({ risk }) {
  return (
    <div className="card">
      <div className="card-label">Risk level</div>
      <div className="risk-badge-wrap">
        <div className={`risk-pill ${risk}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span>{RISK_LABEL[risk]}</span>
        </div>
      </div>
    </div>
  )
}
