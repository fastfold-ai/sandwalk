export type ThemeMode = 'light' | 'dark' | 'system'

/** Color palette layered on top of light/dark mode. */
export type ThemePaletteId = 'default' | 'mirage' | 'mahal' | 'darwin'

export type ThemePaletteMeta = {
  id: ThemePaletteId
  name: string
  description: string
  /** Preview swatches shown in General → Themes. */
  swatches: [string, string, string]
}

const THEME_STORAGE_KEY = 'fastfold.theme'
const PALETTE_STORAGE_KEY = 'sandwalk.theme-palette'

export const THEME_CHANGE_EVENT = 'sandwalk:theme-change'
export const PALETTE_CHANGE_EVENT = 'sandwalk:palette-change'

export const THEME_PALETTES: ThemePaletteMeta[] = [
  {
    id: 'default',
    name: 'Default',
    description: 'Neutral light and dark — the current Sandwalk look.',
    swatches: ['#111111', '#F8F8F8', '#A3A3A3']
  },
  {
    id: 'mirage',
    name: 'Mirage',
    description: 'Coral red primary with sand gold accents from the Mirage plate.',
    swatches: ['#E84B3C', '#E2B045', '#2A2118']
  },
  {
    id: 'mahal',
    name: 'Mahal',
    description: 'Terracotta, gold, and cream — warm architectural tones.',
    swatches: ['#8E5C3C', '#E1B34C', '#F2D9A0']
  },
  {
    id: 'darwin',
    name: 'Darwin',
    description: 'Forest green primary with sage surfaces — calm and scientific.',
    swatches: ['#2D6A4F', '#52B788', '#D8F3DC']
  }
]

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

export function getStoredPalette(): ThemePaletteId {
  try {
    const value = localStorage.getItem(PALETTE_STORAGE_KEY)
    if (
      value === 'default' ||
      value === 'mirage' ||
      value === 'mahal' ||
      value === 'darwin'
    ) {
      return value
    }
  } catch {
    // ignore
  }
  return 'default'
}

export function resolveDark(mode: ThemeMode = getStoredTheme()) {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** Dark browser chrome needs a light Aura mark; light chrome needs dark. */
export function syncFavicon(dark: boolean = resolveDark()) {
  const href = dark ? '/favicon-light.svg' : '/favicon.svg'
  let link = document.querySelector<HTMLLinkElement>(
    'link[data-sandwalk-favicon]'
  )
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    link.type = 'image/svg+xml'
    link.dataset.sandwalkFavicon = '1'
    document.head.appendChild(link)
  }
  // Force a reload so Safari / Chrome pick up the swap.
  link.href = `${href}?v=${dark ? 'light' : 'dark'}`
}

export function applyTheme(mode: ThemeMode) {
  const dark = resolveDark(mode)
  document.documentElement.classList.toggle('dark', dark)
  syncFavicon(dark)
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<ThemeMode>(THEME_CHANGE_EVENT, { detail: mode })
  )
}

export function applyPalette(palette: ThemePaletteId) {
  if (palette === 'default') {
    document.documentElement.removeAttribute('data-palette')
  } else {
    document.documentElement.setAttribute('data-palette', palette)
  }
  try {
    localStorage.setItem(PALETTE_STORAGE_KEY, palette)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<ThemePaletteId>(PALETTE_CHANGE_EVENT, { detail: palette })
  )
}

/** Follow OS light/dark changes live while the mode is "system". */
export function watchSystemTheme(): () => void {
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => {
    if (getStoredTheme() === 'system') applyTheme('system')
  }
  media.addEventListener('change', onChange)
  return () => media.removeEventListener('change', onChange)
}
