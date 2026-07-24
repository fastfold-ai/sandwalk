import { useCallback, useEffect, useState } from 'react'

const SESSION_TAB_COLORS_KEY = 'fastfold.session-tab-colors'
const SESSION_TAB_COLORS_EVENT = 'sandwalk:session-tab-colors'

export function readSessionTabColors(): Record<string, string> {
  try {
    const raw = localStorage.getItem(SESSION_TAB_COLORS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, string>
    if (!parsed || typeof parsed !== 'object') return {}
    return Object.fromEntries(
      Object.entries(parsed).filter(
        ([id, color]) =>
          typeof id === 'string' &&
          typeof color === 'string' &&
          color.length > 0
      )
    )
  } catch {
    return {}
  }
}

export function writeSessionTabColors(colors: Record<string, string>) {
  try {
    localStorage.setItem(SESSION_TAB_COLORS_KEY, JSON.stringify(colors))
    window.dispatchEvent(new Event(SESSION_TAB_COLORS_EVENT))
  } catch {
    // ignore storage failures
  }
}

/** Shared session-tab colors (top tabs + sidebar), kept in sync across views. */
export function useSessionTabColors() {
  const [tabColors, setTabColors] = useState<Record<string, string>>(() =>
    readSessionTabColors()
  )

  useEffect(() => {
    const sync = () => setTabColors(readSessionTabColors())
    window.addEventListener(SESSION_TAB_COLORS_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(SESSION_TAB_COLORS_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const setTabColor = useCallback((sessionId: string, color: string | null) => {
    setTabColors(current => {
      const next = { ...current }
      if (color) next[sessionId] = color
      else delete next[sessionId]
      writeSessionTabColors(next)
      return next
    })
  }, [])

  return { tabColors, setTabColor }
}
