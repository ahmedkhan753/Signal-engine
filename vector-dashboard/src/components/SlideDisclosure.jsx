import { useId, useState } from 'react'

/**
 * Collapsible with height slide (CSS grid 0fr → 1fr). Prefer over native `<details>` for smooth motion.
 * @param {{
 *   label: string;
 *   children: import('react').ReactNode;
 *   className?: string;
 * }} props
 */
export function SlideDisclosure({ label, children, className = '' }) {
  const [open, setOpen] = useState(false)
  const baseId = useId().replace(/:/g, '')
  const panelId = `slide-panel-${baseId}`
  const triggerId = `slide-trigger-${baseId}`

  return (
    <div className={`slide-disclosure ${open ? 'is-open' : ''} ${className}`.trim()}>
      <button
        type="button"
        id={triggerId}
        className="slide-disclosure-trigger"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="slide-disclosure-chevron" aria-hidden>
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
        {label}
      </button>
      <div
        id={panelId}
        role="region"
        aria-labelledby={triggerId}
        className="slide-disclosure-panel"
        {...(!open ? { inert: true } : {})}
      >
        <div className="slide-disclosure-inner">{children}</div>
      </div>
    </div>
  )
}
