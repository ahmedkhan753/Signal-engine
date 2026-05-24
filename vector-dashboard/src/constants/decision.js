/** Ring radius must match `r` on the score SVG for stroke math. */
export const RING_RADIUS = 52

export const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

/** VECTOR accent palette (hex for SVG / inline use). */
export const VECTOR = {
  success: '#3FB950',
  warning: '#F5C542',
  danger: '#FF5C5C',
  secondary: '#1F6FEB',
}

/**
 * Alignment score ring color: high / medium / low bands.
 * @param {number} score
 */
export function getAlignmentColor(score) {
  if (score >= 75) return VECTOR.success
  if (score >= 50) return VECTOR.warning
  return VECTOR.danger
}
