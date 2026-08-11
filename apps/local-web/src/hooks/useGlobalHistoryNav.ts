import { useEffect, useState } from 'react'
import {
  useLocation,
  useNavigate,
  useNavigationType
} from 'react-router-dom'

function historyIdx(): number {
  const idx = window.history.state?.idx
  return typeof idx === 'number' ? idx : 0
}

/**
 * Global in-app back/forward against the React Router stack.
 * Tracks a high-water index so Forward stays available after Back until a
 * new PUSH/REPLACE truncates the forward entries.
 */
export function useGlobalHistoryNav() {
  const navigate = useNavigate()
  const location = useLocation()
  const navType = useNavigationType()
  const [idx, setIdx] = useState(historyIdx)
  const [maxIdx, setMaxIdx] = useState(historyIdx)

  useEffect(() => {
    const current = historyIdx()
    setIdx(current)
    if (navType === 'POP') return
    setMaxIdx(current)
  }, [location, navType])

  return {
    canGoBack: idx > 0,
    canGoForward: idx < maxIdx,
    goBack: () => {
      if (idx > 0) navigate(-1)
    },
    goForward: () => {
      if (idx < maxIdx) navigate(1)
    }
  }
}
