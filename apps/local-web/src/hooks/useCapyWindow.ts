import { useCallback, useEffect, useState } from 'react'

import {
  type CapyWindowState,
  CAPY_OPEN_EVENT,
  clampCapyWindow,
  readCapyWindow,
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
    const onResize = () => persist(readCapyWindow())
    window.addEventListener(CAPY_OPEN_EVENT, onOpen)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener(CAPY_OPEN_EVENT, onOpen)
      window.removeEventListener('resize', onResize)
    }
  }, [persist])

  return { state, persist }
}
