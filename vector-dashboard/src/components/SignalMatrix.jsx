import { confidenceColor, valuePillClass } from '../utils/signals.js'

/**
 * @param {{
 *   signals: import('../model/dashboardViewModel.js').DashboardViewModel['signals'];
 *   hasConflicts: boolean;
 * }} props
 */
export function SignalMatrix({ signals, hasConflicts }) {
  return (
    <div
      className={`card signals-card ${hasConflicts ? 'highlight-warn' : 'highlight-ok'}`.trim()}
    >
      <div className="card-label">Signal matrix</div>
      <table className="sig-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Metric</th>
            <th>Status</th>
            <th style={{ minWidth: '180px' }}>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((row) => {
            const pct = Math.round(row.conf * 100)
            const barColor = confidenceColor(row.conf)
            return (
              <tr key={`${row.source}-${row.metric}`}>
                <td>
                  <div className="src-cell">
                    <div className="src-icon">{row.icon}</div>
                    {row.sourceLabel}
                  </div>
                </td>
                <td>
                  <span className="metric-cell">{row.metricLabel}</span>
                </td>
                <td>
                  <span className={`val-cell ${valuePillClass(row.value)}`}>{row.statusLabel}</span>
                </td>
                <td>
                  <div className="conf-wrap">
                    <div className="conf-track">
                      <div
                        className="conf-bar"
                        style={{ width: `${pct}%`, background: barColor }}
                      />
                    </div>
                    <span className="conf-pct">{pct}%</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
