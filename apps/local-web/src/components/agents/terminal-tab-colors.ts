const TERMINAL_TAB_COLORS_KEY = 'fastfold.terminal-tab-colors'

export function readTerminalTabColors(sessionId: string): Record<string, string> {
  try {
    const raw = localStorage.getItem(TERMINAL_TAB_COLORS_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Record<string, string>>
    const entry = parsed?.[sessionId]
    if (!entry || typeof entry !== 'object') return {}
    return Object.fromEntries(
      Object.entries(entry).filter(
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

export function writeTerminalTabColors(
  sessionId: string,
  colors: Record<string, string>
) {
  try {
    const raw = localStorage.getItem(TERMINAL_TAB_COLORS_KEY)
    const parsed = raw
      ? (JSON.parse(raw) as Record<string, Record<string, string>>)
      : {}
    parsed[sessionId] = colors
    localStorage.setItem(TERMINAL_TAB_COLORS_KEY, JSON.stringify(parsed))
  } catch {
    // ignore storage failures
  }
}
