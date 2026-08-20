import { useEffect, useState } from 'react'

/**
 * Monitor fingerprint — screen resolution × DPR. Stage Manager pattern:
 * layouts saved on a docked 4K screen shouldn't dictate the shape on a
 * MacBook 13" when the user undocks.
 */
export function getMonitorFingerprint(): string {
  if (typeof window === 'undefined') return 'default'
  const w = Math.round(window.screen.width)
  const h = Math.round(window.screen.height)
  const dpr = Math.round(window.devicePixelRatio || 1)
  return `${w}x${h}@${dpr}`
}

/**
 * Reactive version — recomputes on `resize` events, which is how Safari
 * signals a monitor change on macOS.
 */
export function useMonitorFingerprint(): string {
  const [fp, setFp] = useState(() => getMonitorFingerprint())
  useEffect(() => {
    const update = () => {
      const next = getMonitorFingerprint()
      setFp(prev => (prev === next ? prev : next))
    }
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])
  return fp
}
