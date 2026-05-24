import { VECTOR } from '../constants/decision'

export function confidenceColor(confidence) {
  if (confidence >= 0.9) return VECTOR.success
  if (confidence >= 0.75) return VECTOR.warning
  return VECTOR.danger
}

export function valuePillClass(value) {
  if (value === 'normal') return 'val-normal'
  if (value === 'high') return 'val-high'
  if (value === 'proceed') return 'val-proceed'
  return ''
}
