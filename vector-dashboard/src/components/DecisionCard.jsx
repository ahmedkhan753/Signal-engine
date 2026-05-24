import { DecisionIcon } from './DecisionIcon.jsx'
import { useEffect, useRef, useState } from 'react'

function decisionCardHighlight(decision) {
  if (decision === 'ALLOW') return 'highlight-ok'
  if (decision === 'DELAY') return 'highlight-warn'
  return 'highlight-critical'
}

/**
 * @param {{ decision: import('../model/dashboardViewModel.js').DashboardViewModel['decision'] }} props
 */
export function DecisionCard({ decision }) {
  const d = decision.toLowerCase()
  const borderClass = decisionCardHighlight(decision)
  const prevDecision = useRef(decision)
  const [isShifted, setIsShifted] = useState(false)

  useEffect(() => {
    const shiftedToRisk = prevDecision.current !== decision && decision !== 'ALLOW'
    prevDecision.current = decision
    if (!shiftedToRisk) return
    setIsShifted(true)
    const id = window.setTimeout(() => setIsShifted(false), 900)
    return () => window.clearTimeout(id)
  }, [decision])

  return (
    <div className={`card decision-metric ${borderClass} ${isShifted ? 'decision-shift' : ''}`.trim()}>
      <div className="card-label">Outcome</div>
      <div className={`decision-panel ${d}`}>
        <div className="decision-wrap">
          <div className={`decision-badge ${d}`}>
            <span className="d-icon" aria-hidden>
              <DecisionIcon decision={decision} />
            </span>
            <span className="d-text">{decision}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
