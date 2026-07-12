export type ThemeMode = 'light' | 'dark' | 'system'

const THEME_STORAGE_KEY = 'fastfold.theme'

export function getStoredTheme(): ThemeMode {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    if (value === 'light' || value === 'dark' || value === 'system')
      return value
  } catch {
    // ignore
  }
  return 'system'
}

export function resolveDark(mode: ThemeMode = getStoredTheme()) {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle('dark', resolveDark(mode))
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // ignore
  }
}
