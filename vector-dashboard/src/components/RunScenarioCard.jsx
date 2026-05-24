/**
 * @param {{
 *   onRunScenario0: () => void;
 *   onRunScenario1: () => void;
 *   onRunScenario2: () => void;
 *   onReset: () => void;
 *   onRunDemo: () => void;
 *   scenarios?: Array<{ scenario_id: string; scenario_name: string; demo_step: string|null }>;
 *   activeScenarioId?: string;
 *   onSelectScenarioById?: (id: string) => void;
 * }} props
 */
export function RunScenarioCard({
  onRunScenario0,
  onRunScenario1,
  onRunScenario2,
  onReset,
  onRunDemo,
  scenarios = [],
  activeScenarioId = '',
  onSelectScenarioById,
}) {
  const handlePick = (event) => {
    const id = event.target.value
    if (id && onSelectScenarioById) onSelectScenarioById(id)
  }

  return (
    <section className="card run-card" aria-labelledby="run-scenario-title">
      <div>
        <h2 id="run-scenario-title">Scenarios</h2>
        <p className="run-card-hint">
          Quick-run the canonical Normal / Conflict / Block scenarios, play the
          four-step demo, or pick any wired scenario from the catalogue.
        </p>
      </div>
      <div className="run-actions">
        <button type="button" className="btn btn-normal" onClick={onRunScenario0}>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M8 5v14l11-7z" />
          </svg>
          Run Normal
        </button>
        <button type="button" className="btn btn-conflict" onClick={onRunScenario1}>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
          </svg>
          Run Conflict
        </button>
        <button type="button" className="btn btn-stop" onClick={onRunScenario2}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
          Run Stop
        </button>
        <button type="button" className="btn btn-reset" onClick={onReset}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M23 4v6h-6M1 20v-6h6" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          Reset
        </button>
        <button type="button" className="btn btn-demo" onClick={onRunDemo}>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M8 5v14l11-7z" />
          </svg>
          Run demo
        </button>
        {scenarios.length > 0 && (
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 12,
              color: 'var(--text-muted, #8b949e)',
              marginLeft: 'auto',
            }}
          >
            <span style={{ letterSpacing: '0.04em', textTransform: 'uppercase' }}>All scenarios</span>
            <select
              value={activeScenarioId}
              onChange={handlePick}
              aria-label="Select a wired scenario"
              style={{
                background: 'rgba(13, 17, 23, 0.6)',
                color: 'var(--text, #e6edf3)',
                border: '1px solid rgba(230, 237, 243, 0.12)',
                borderRadius: 6,
                padding: '6px 10px',
                fontFamily: 'inherit',
                fontSize: 13,
                cursor: 'pointer',
                minWidth: 220,
              }}
            >
              {scenarios.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>
                  {s.scenario_name}
                  {s.demo_step ? ` · ${s.demo_step}` : ''}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </section>
  )
}
