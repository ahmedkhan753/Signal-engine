import { useEffect, useRef, useState } from 'react'
import { useAnimatedPercent } from '../hooks/useAnimatedPercent.js'
import { confidenceColor, valuePillClass } from '../utils/signals.js'
import { SlideDisclosure } from './SlideDisclosure.jsx'

function statusToDecisionClass(status) {
  if (status === 'SAFE') return 'facet-safe'
  if (status === 'CAUTION') return 'facet-caution'
  return 'facet-stop'
}

function statusLabel(status) {
  if (status === 'SAFE') return 'SAFE'
  if (status === 'CAUTION') return 'CAUTION'
  return 'STOP'
}

function decisionCardHighlight(decision) {
  if (decision === 'ALLOW') return 'highlight-ok'
  if (decision === 'DELAY') return 'highlight-warn'
  return 'highlight-critical'
}

/**
 * @param {unknown} row
 * @returns {import('../model/dashboardViewModel.js').DashboardSignalRow | null}
 */
function normalizeSignalRow(row) {
  if (row === null || row === undefined || typeof row !== 'object') return null
  const conf = Number(/** @type {{ conf?: unknown }} */ (row).conf)
  if (!Number.isFinite(conf)) return null
  const r = /** @type {import('../model/dashboardViewModel.js').DashboardSignalRow} */ (row)
  if (typeof r.source !== 'string' || typeof r.metric !== 'string') return null
  return { ...r, conf: Math.min(1, Math.max(0, conf)) }
}

/**
 * @param {{
 *  facets: import('../model/dashboardViewModel.js').DashboardViewModel['facets'];
 *  overallDecision: 'ALLOW'|'DELAY'|'BLOCK';
 *  animationKey: string|number;
 * }} props
 */
export function EvaluationFacets({ facets, overallDecision, animationKey }) {
  return (
    <div className={`card facets-card ${decisionCardHighlight(overallDecision)}`.trim()}>
      <div className="card-label">Governance facets</div>
      <div className="facet-grid">
        {facets.map((facet) => (
          <FacetCard
            key={facet.id}
            facet={facet}
            emphasize={facet.status !== 'SAFE'}
            animationKey={animationKey}
          />
        ))}
      </div>
    </div>
  )
}

/**
 * @param {{
 *  facet: import('../model/dashboardViewModel.js').DashboardFacet;
 *  emphasize: boolean;
 *  animationKey: string|number;
 * }} props
 */
function FacetCard({ facet, emphasize, animationKey }) {
  const prevStatus = useRef(facet.status)
  const [isEmphasizing, setIsEmphasizing] = useState(false)

  useEffect(() => {
    const shifted = prevStatus.current !== facet.status && facet.status !== 'SAFE'
    prevStatus.current = facet.status
    if (!shifted || !emphasize) return
    setIsEmphasizing(true)
    const id = window.setTimeout(() => setIsEmphasizing(false), 900)
    return () => window.clearTimeout(id)
  }, [facet.status, emphasize])

  return (
    <section className={`facet-card ${statusToDecisionClass(facet.status)} ${isEmphasizing ? 'facet-shift' : ''}`.trim()}>
      <div className="facet-head">
        <div className="facet-title">{facet.label}</div>
        <div className="facet-meta">
          <span className={`facet-status-pill ${statusToDecisionClass(facet.status)}`.trim()}>
            {statusLabel(facet.status)}
          </span>
          <span className="facet-subscore">{facet.subScore}/100</span>
        </div>
      </div>

      <div className="facet-section">
        <div className="facet-subtitle">Contributing signals</div>
        <table className="facet-sig-table" aria-label={`${facet.label} signals`}>
          <tbody>
            {(Array.isArray(facet.contributingSignals) ? facet.contributingSignals : [])
              .map(normalizeSignalRow)
              .filter(Boolean)
              .map((row, idx) => {
                const pct = Math.round(row.conf * 100)
                const barColor = confidenceColor(row.conf)
                return (
                  <tr key={`${facet.id}-sig-${idx}-${row.source}-${row.metric}`}>
                    <td>
                      <div className="src-cell facet-sig-src">
                        <div className="src-icon facet-sig-icon">{row.icon ?? '·'}</div>
                        <div>
                          <div className="facet-sig-label">{row.sourceLabel ?? row.source}</div>
                          <div className="facet-sig-metric">{row.metricLabel ?? row.metric}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`val-cell ${valuePillClass(row.value)}`}>{row.statusLabel}</span>
                    </td>
                    <td>
                      <SignalConfidenceBar
                        targetPct={pct}
                        barColor={barColor}
                        animationKey={animationKey}
                      />
                    </td>
                  </tr>
                )
              })}
          </tbody>
        </table>
      </div>

      <div className="facet-section">
        <div className="facet-subtitle">Readout</div>
        <p className="facet-plain">{facet.localExplanationPlain}</p>
      </div>

      <div className="facet-section">
        <SlideDisclosure label="Technical trace" className="technical-trace-disclosure">
          <p className="technical-trace-body">{facet.localTraceTechnical}</p>
        </SlideDisclosure>
      </div>
    </section>
  )
}

/**
 * @param {{ targetPct: number; barColor: string; animationKey: string|number }} props
 */
function SignalConfidenceBar({ targetPct, barColor, animationKey }) {
  const pct = useAnimatedPercent(targetPct, animationKey)
  return (
    <div className="conf-wrap facet-sig-conf">
      <div className="conf-track">
        <div className="conf-bar conf-bar--animated" style={{ width: `${pct}%`, background: barColor }} />
      </div>
      <span className="conf-pct">{pct}%</span>
    </div>
  )
}
