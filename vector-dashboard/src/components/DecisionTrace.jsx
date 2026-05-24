import { SlideDisclosure } from './SlideDisclosure'

/**
 * @param {{ operationalTrace: string; technicalTrace: string }} props
 */
export function DecisionTrace({ operationalTrace, technicalTrace }) {
  return (
    <div className="card trace-card">
      <div className="card-label">Operational summary</div>
      <div className="trace-panel">
        <p className="trace-operational">{operationalTrace}</p>
        <SlideDisclosure label="Technical trace" className="technical-trace-disclosure">
          <p className="technical-trace-body">{technicalTrace}</p>
        </SlideDisclosure>
      </div>
    </div>
  )
}
