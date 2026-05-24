import { useEffect, useState } from 'react'

/**
 * @param {{ conflicts: string[]; pulseKey: number; overallDecision: 'ALLOW'|'DELAY'|'BLOCK' }} props
 */
export function ConflictsPanel({ conflicts, pulseKey, overallDecision }) {
  const hasConflicts = conflicts.length > 0
  const [isPulsing, setIsPulsing] = useState(false)

  const borderClass = !hasConflicts
    ? 'highlight-ok'
    : overallDecision === 'BLOCK'
      ? 'highlight-critical'
      : 'highlight-warn'

  const pulseClass =
    isPulsing && hasConflicts
      ? overallDecision === 'BLOCK'
        ? 'conflict-pulse-critical'
        : 'conflict-pulse'
      : ''

  useEffect(() => {
    let startId = 0
    let endId = 0
    if (!hasConflicts) {
      startId = window.setTimeout(() => setIsPulsing(false), 0)
      return () => window.clearTimeout(startId)
    }
    startId = window.setTimeout(() => setIsPulsing(true), 0)
    endId = window.setTimeout(() => setIsPulsing(false), 1000)
    return () => {
      window.clearTimeout(startId)
      window.clearTimeout(endId)
    }
  }, [pulseKey, hasConflicts])

  return (
    <div className={`card conflict-card ${borderClass} ${pulseClass}`.trim()}>
      <div className="card-label">Signal conflicts</div>
      <div className="conflicts-body">
        {!hasConflicts ? (
          <div className="conflict-empty">
            <div className="icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <h3>No conflicts detected</h3>
          </div>
        ) : (
          conflicts.map((text) => (
            <div key={text} className="conflict-item">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
              </svg>
              <span>{text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
