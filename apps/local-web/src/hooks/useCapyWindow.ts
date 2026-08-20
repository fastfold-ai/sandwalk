import { useCallback, useEffect, useState } from 'react'

import {
  CAPY_OPEN_EVENT,
  CAPY_REVEAL_MINIMIZED_EVENT,
  type CapyWindowState,
  clampCapyWindow,
  readCapyWindow,
  shouldRevealCapyMinimized,
  writeCapyWindow
} from '@/lib/capy-ui'

export function useCapyWindow() {
  const [state, setState] = useState<CapyWindowState>(() => readCapyWindow())

  const persist = useCallback((next: CapyWindowState) => {
    const clamped = clampCapyWindow(next)
    setState(clamped)
    writeCapyWindow(clamped)
  }, [])

  useEffect(() => {
    const onOpen = () => {
      persist({ ...readCapyWindow(), open: true, minimized: false })
    }
    const onRevealMinimized = () => {
      const current = readCapyWindow()
      if (!shouldRevealCapyMinimized(current)) return
      persist({ ...current, open: false, minimized: true })
    }
    const onResize = () => persist(readCapyWindow())
    window.addEventListener(CAPY_OPEN_EVENT, onOpen)
    window.addEventListener(CAPY_REVEAL_MINIMIZED_EVENT, onRevealMinimized)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener(CAPY_OPEN_EVENT, onOpen)
      window.removeEventListener(CAPY_REVEAL_MINIMIZED_EVENT, onRevealMinimized)
      window.removeEventListener('resize', onResize)
    }
  }, [persist])

  return { state, persist }
}
