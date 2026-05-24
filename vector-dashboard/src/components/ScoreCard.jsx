import { RING_CIRCUMFERENCE } from '../constants/decision'

/**
 * @param {{
 *   score: number;
 *   strokeColor: string;
 *   highlightClass: string;
 * }} props
 */
export function ScoreCard({ score, strokeColor, highlightClass }) {
  const offset = RING_CIRCUMFERENCE - (score / 100) * RING_CIRCUMFERENCE

  return (
    <div className={`card score-card ${highlightClass}`.trim()}>
      <div className="card-label">Alignment score</div>
      <div className="score-card-inner">
        <div className="score-figures">
          <span className="score-num" style={{ color: strokeColor }}>
            {score}
          </span>
          <span className="score-denom">/100</span>
        </div>
        <div className="score-ring-wrap">
          <svg viewBox="0 0 120 120" width="120" height="120" aria-hidden>
            <circle className="ring-track" cx="60" cy="60" r="52" />
            <circle
              className="ring-arc"
              cx="60"
              cy="60"
              r="52"
              stroke={strokeColor}
              strokeDasharray={RING_CIRCUMFERENCE}
              strokeDashoffset={offset}
            />
          </svg>
          <div className="ring-center">
            <span>{score}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
