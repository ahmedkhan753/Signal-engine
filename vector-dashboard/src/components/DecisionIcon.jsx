/**
 * @param {{ decision: import('../model/dashboardViewModel.js').DashboardViewModel['decision'] }} props
 */
export function DecisionIcon({ decision }) {
  if (decision === 'ALLOW') {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
        <path d="M20 6L9 17l-5-5" />
      </svg>
    )
  }
  if (decision === 'DELAY') {
    return (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
      </svg>
    )
  }
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  )
}
