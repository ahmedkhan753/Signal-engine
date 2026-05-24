import { useEffect, useRef, useState } from 'react'
import { lerp } from '../utils/math'

const DURATION_MS = 650

/**
 * Animates the displayed score when `targetScore` or `animationKey` changes.
 * @param {number} targetScore
 * @param {string|number} animationKey  e.g. scenario id — restarts animation when scenario changes
 */
export function useAnimatedScore(targetScore, animationKey) {
  const [value, setValue] = useState(targetScore)
  const fromRef = useRef(targetScore)

  useEffect(() => {
    const from = fromRef.current
    const to = targetScore
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
  }, [targetScore, animationKey])

  return value
}
