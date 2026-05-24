import { useEffect, useRef, useState } from 'react'
import { lerp } from '../utils/math'

/** Same duration and easing as `useAnimatedScore` for a consistent feel. */
const DURATION_MS = 650

function reducedMotion() {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Animates a 0–100 percentage when `targetPct` or `animationKey` changes.
 * @param {number} targetPct
 * @param {string|number} animationKey
 */
export function useAnimatedPercent(targetPct, animationKey) {
  const [value, setValue] = useState(0)
  const fromRef = useRef(0)

  useEffect(() => {
    const to = Math.min(100, Math.max(0, Math.round(Number(targetPct) || 0)))
    if (reducedMotion()) {
      const id = window.setTimeout(() => {
        fromRef.current = to
        setValue(to)
      }, 0)
      return () => window.clearTimeout(id)
    }
    const from = fromRef.current
    let rafId = 0
    const start = performance.now()

    const step = (now) => {
      const t = Math.min((now - start) / DURATION_MS, 1)
      const eased = 1 - (1 - t) ** 3
      setValue(Math.round(lerp(from, to, eased)))
      if (t < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        fromRef.current = to
      }
    }

    rafId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(rafId)
  }, [targetPct, animationKey])

  return value
}
