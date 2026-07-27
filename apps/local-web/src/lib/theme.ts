import {
  setDockIcon,
  setSidebarGlassOptions,
  syncSidebarGlassTheme
} from '@/lib/desktop'

export type ThemeMode = 'light' | 'dark' | 'system'

/** Dock tile variant (macOS desktop only). */
export type DockIconId = 'dark' | 'light' | 'golden'

/** Color palette layered on top of light/dark mode. */
export type ThemePaletteId =
  | 'default'
  | 'sandwalk'
  | 'mirage'
  | 'mahal'
  | 'darwin'
  | 'ember'
  | 'verdant'
  | 'tritanopia'
  | 'protanopia'
  | 'custom'

export type ThemePaletteMeta = {
  id: ThemePaletteId
  name: string
  description: string
  /** Preview swatches shown in General → Themes. */
  swatches: [string, string, string]
  /**
   * The palette's own selected/hover pill color — shown as the "Default"
   * dot in Accent color so it visibly tracks whichever palette is active.
   */
  accentSwatch: string
}

/** Sidebar selected/hover pill color — layered independently of the palette. */
export type AccentColorId =
  | 'none'
  | 'blue'
  | 'teal'
  | 'green'
  | 'red'
  | 'pink'
  | 'purple'
  | 'orange'

export type AccentColorMeta = {
  id: AccentColorId
  label: string
  /** Swatch shown in the picker. */
  swatch: string
}

export const ACCENT_COLORS: AccentColorMeta[] = [
  { id: 'none', label: 'Default', swatch: '#9CA3AF' },
  { id: 'blue', label: 'Blue', swatch: '#3B82F6' },
  { id: 'teal', label: 'Teal', swatch: '#14B8A6' },
  { id: 'green', label: 'Green', swatch: '#22C55E' },
  { id: 'red', label: 'Red', swatch: '#EF4444' },
  { id: 'pink', label: 'Pink', swatch: '#EC4899' },
  { id: 'purple', label: 'Purple', swatch: '#8B5CF6' },
  { id: 'orange', label: 'Orange', swatch: '#F97316' }
]

/**
 * Native `NSGlassEffectView` material — every variant the private Apple API
 * exposes (raw, unfiltered; all "experimental" per Apple and may render
 * identically to each other depending on macOS version).
 */
export type GlassMaterialId =
  | 'regular'
  | 'clear'
  | 'dock'
  | 'app_icons'
  | 'widgets'
  | 'text'
  | 'avplayer'
  | 'facetime'
  | 'control_center'
  | 'notification_center'
  | 'monogram'
  | 'bubbles'
  | 'identity'
  | 'focus_border'
  | 'focus_platter'
  | 'keyboard'
  | 'sidebar'
  | 'abutted_sidebar'
  | 'inspector'
  | 'control'
  | 'loupe'
  | 'slider'
  | 'camera'
  | 'cartouche_popover'

export type GlassMaterialMeta = {
  id: GlassMaterialId
  label: string
}

export const GLASS_MATERIALS: GlassMaterialMeta[] = [
  { id: 'regular', label: 'Regular' },
  { id: 'clear', label: 'Clear' },
  { id: 'dock', label: 'Dock' },
  { id: 'app_icons', label: 'App Icons' },
  { id: 'widgets', label: 'Widgets' },
  { id: 'text', label: 'Text' },
  { id: 'avplayer', label: 'AVPlayer' },
  { id: 'facetime', label: 'FaceTime' },
  { id: 'control_center', label: 'Control Center' },
  { id: 'notification_center', label: 'Notification Center' },
  { id: 'monogram', label: 'Monogram' },
  { id: 'bubbles', label: 'Bubbles' },
  { id: 'identity', label: 'Identity' },
  { id: 'focus_border', label: 'Focus Border' },
  { id: 'focus_platter', label: 'Focus Platter' },
  { id: 'keyboard', label: 'Keyboard' },
  { id: 'sidebar', label: 'Sidebar' },
  { id: 'abutted_sidebar', label: 'Abutted Sidebar' },
  { id: 'inspector', label: 'Inspector' },
  { id: 'control', label: 'Control' },
  { id: 'loupe', label: 'Loupe' },
  { id: 'slider', label: 'Slider' },
  { id: 'camera', label: 'Camera' },
  { id: 'cartouche_popover', label: 'Cartouche Popover' }
]

/** App-wide UI text font. "default" restores the bundled Inter stack. */
export type AppFontId =
  | 'default'
  | 'system'
  | 'arial'
  | 'georgia'
  | 'verdana'
  | 'noto-sans'
  | 'roboto-mono'
  | 'comic-sans'
  | 'atkinson'
  | 'open-dyslexic'

export type AppFontMeta = {
  id: AppFontId
  label: string
  /** CSS `font-family` value used both for the live preview and the applied style. */
  stack: string
}

export const APP_FONTS: AppFontMeta[] = [
  {
    id: 'default',
    label: 'Inter (Default)',
    stack:
      "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  },
  {
    id: 'system',
    label: 'San Francisco Pro (System)',
    stack: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  },
  { id: 'arial', label: 'Arial', stack: 'Arial, Helvetica, sans-serif' },
  {
    id: 'atkinson',
    label: 'Atkinson Hyperlegible Next',
    stack: "'Atkinson Hyperlegible Next', 'Atkinson Hyperlegible', sans-serif"
  },
  {
    id: 'comic-sans',
    label: 'Comic Sans',
    stack: "'Comic Sans MS', 'Comic Sans', cursive"
  },
  { id: 'georgia', label: 'Georgia', stack: "Georgia, 'Times New Roman', serif" },
  { id: 'noto-sans', label: 'Noto Sans', stack: "'Noto Sans', sans-serif" },
  {
    id: 'open-dyslexic',
    label: 'OpenDyslexic',
    stack: "'OpenDyslexic', sans-serif"
  },
  {
    id: 'roboto-mono',
    label: 'Roboto Mono',
    stack: "'Roboto Mono', ui-monospace, monospace"
  },
  { id: 'verdana', label: 'Verdana', stack: 'Verdana, Geneva, sans-serif' }
]

const THEME_STORAGE_KEY = 'fastfold.theme'
const PALETTE_STORAGE_KEY = 'sandwalk.theme-palette'
const LIQUID_GLASS_STORAGE_KEY = 'sandwalk.liquid-glass'
const UI_FONT_SIZE_STORAGE_KEY = 'sandwalk.ui-font-size'
const GLASS_MATERIAL_STORAGE_KEY = 'sandwalk.glass-material'
const GLASS_TINT_STRENGTH_STORAGE_KEY = 'sandwalk.glass-tint-strength'
const DOCK_ICON_STORAGE_KEY = 'sandwalk.dock-icon'
const ACCENT_COLOR_STORAGE_KEY = 'sandwalk.accent-color'
const CUSTOM_THEME_STORAGE_KEY = 'sandwalk.custom-theme'
const APP_FONT_STORAGE_KEY = 'sandwalk.app-font'

export const THEME_CHANGE_EVENT = 'sandwalk:theme-change'
export const PALETTE_CHANGE_EVENT = 'sandwalk:palette-change'
export const LIQUID_GLASS_CHANGE_EVENT = 'sandwalk:liquid-glass-change'
export const UI_FONT_SIZE_CHANGE_EVENT = 'sandwalk:ui-font-size-change'
export const GLASS_MATERIAL_CHANGE_EVENT = 'sandwalk:glass-material-change'
export const GLASS_TINT_STRENGTH_CHANGE_EVENT = 'sandwalk:glass-tint-strength-change'
export const DOCK_ICON_CHANGE_EVENT = 'sandwalk:dock-icon-change'
export const ACCENT_COLOR_CHANGE_EVENT = 'sandwalk:accent-color-change'
export const CUSTOM_THEME_CHANGE_EVENT = 'sandwalk:custom-theme-change'
export const APP_FONT_CHANGE_EVENT = 'sandwalk:app-font-change'

const CUSTOM_GRADIENT_CLASS = 'sandwalk-custom-gradient'
const CUSTOM_TEXT_CLASS = 'sandwalk-custom-text'

const LIQUID_GLASS_OFF_CLASS = 'sandwalk-liquid-glass-off'

export const UI_FONT_SIZE_MIN = 12
export const UI_FONT_SIZE_MAX = 18
export const UI_FONT_SIZE_DEFAULT = 14

/** Native glass tint alpha — how strongly the color wash reads through the blur. */
export const GLASS_TINT_STRENGTH_MIN = 0
export const GLASS_TINT_STRENGTH_MAX = 100
export const GLASS_TINT_STRENGTH_DEFAULT = 80

export const THEME_PALETTES: ThemePaletteMeta[] = [
  {
    id: 'default',
    name: 'Default',
    description: 'Neutral light and dark — the current sandwalk look.',
    // radial: mid gray → charcoal → near-black rim
    swatches: ['#A3A3A3', '#4B4B4F', '#111111'],
    accentSwatch: '#9CA3AF'
  },
  {
    id: 'sandwalk',
    name: 'Sandwalk',
    description:
      'Golden dune palette matching the Dorado dock icon — cream, gold, terracotta.',
    // radial: gold → cream → deep bronze (matches Dorado icon)
    swatches: ['#E1B34C', '#F2D9A0', '#3D2A18'],
    accentSwatch: '#8E5C3C'
  },
  {
    id: 'ember',
    name: 'Ember',
    description: 'Crimson red with a navy selected pill — gradient sidebar.',
    // radial: crimson → navy → near-black
    swatches: ['#9C0000', '#070C52', '#050510'],
    accentSwatch: '#070C52'
  },
  {
    id: 'verdant',
    name: 'Verdant',
    description: 'Lavender with a green selected pill — gradient sidebar.',
    // radial: lavender → green → deep plum
    swatches: ['#BEB0FF', '#71D18F', '#1E1630'],
    accentSwatch: '#71D18F'
  },
  {
    id: 'mirage',
    name: 'Mirage',
    description: 'Coral red primary with sand gold accents from the Mirage plate.',
    // radial: coral → sand gold → dark umber
    swatches: ['#E84B3C', '#E2B045', '#2A2118'],
    accentSwatch: '#E84B3C'
  },
  {
    id: 'mahal',
    name: 'Mahal',
    description: 'Terracotta, gold, and cream — warm architectural tones.',
    // radial: cream → gold → terracotta
    swatches: ['#F2D9A0', '#E1B34C', '#8E5C3C'],
    accentSwatch: '#8E5C3C'
  },
  {
    id: 'darwin',
    name: 'Darwin',
    description: 'Forest green primary with sage surfaces — calm and scientific.',
    // radial: sage → mint → deep forest
    swatches: ['#52B788', '#D8F3DC', '#0B1F14'],
    accentSwatch: '#2D6A4F'
  },
  {
    id: 'tritanopia',
    name: 'Tritanopia',
    description: 'Indigo and magenta — tuned for blue/yellow color vision deficiency.',
    // radial: indigo → magenta → deep navy
    swatches: ['#3949AB', '#D6336C', '#0A0A1A'],
    accentSwatch: '#3949AB'
  },
  {
    id: 'protanopia',
    name: 'Protanopia & Deuteranopia',
    description: 'Violet and steel blue — tuned for red/green color vision deficiency.',
    // radial: violet → steel → deep indigo
    swatches: ['#7C3AED', '#2C5AA0', '#12081F'],
    accentSwatch: '#7C3AED'
  }
]

/**
 * The active palette's own accent color — used as the "Default" swatch in
 * Accent color so it visibly tracks whichever palette/custom theme is
 * active, until the user picks an explicit override color.
 */
export function resolvePaletteAccentSwatch(
  palette: ThemePaletteId,
  customColors: CustomThemeColors = getStoredCustomTheme()
): string {
  if (palette === 'custom') return customColors.selected
  return (
    THEME_PALETTES.find(item => item.id === palette)?.accentSwatch ?? '#9CA3AF'
  )
}

/** "Custom theme" — four independently editable colors, Slack-style. */
export type CustomThemeColors = {
  /** "System navigation" — sidebar background. */
  nav: string
  /** "Selected items" — sidebar selected/hover pill. */
  selected: string
  /** "Presence indication" — the server-running status dot. */
  presence: string
  /** "Text color" — sidebar label/foreground text. `null` = follow light/dark mode. */
  text: string | null
  /** Blend nav + selected colors into a gradient sidebar background. */
  gradient: boolean
}

export const CUSTOM_THEME_DEFAULT: CustomThemeColors = {
  nav: '#BEB0FF',
  selected: '#71D18F',
  presence: '#00FF50',
  text: null,
  gradient: true
}

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
      value === 'custom' ||
      THEME_PALETTES.some(item => item.id === value)
    ) {
      return value as ThemePaletteId
    }
  } catch {
    // ignore
  }
  return 'default'
}

/** macOS desktop sidebar glass — enabled by default. */
export function getStoredLiquidGlass(): boolean {
  try {
    const value = localStorage.getItem(LIQUID_GLASS_STORAGE_KEY)
    if (value === 'off' || value === '0' || value === 'false') return false
  } catch {
    // ignore
  }
  return true
}

/** Persist liquid-glass preference and update the document class immediately. */
export function applyLiquidGlass(enabled: boolean) {
  document.documentElement.classList.toggle(LIQUID_GLASS_OFF_CLASS, !enabled)
  try {
    localStorage.setItem(LIQUID_GLASS_STORAGE_KEY, enabled ? 'on' : 'off')
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<boolean>(LIQUID_GLASS_CHANGE_EVENT, { detail: enabled })
  )
}

/** Base UI font size (px) — scales rem-based Tailwind spacing/type together. */
export function getStoredUiFontSize(): number {
  try {
    const value = Number(localStorage.getItem(UI_FONT_SIZE_STORAGE_KEY))
    if (Number.isFinite(value) && value >= UI_FONT_SIZE_MIN && value <= UI_FONT_SIZE_MAX) {
      return value
    }
  } catch {
    // ignore
  }
  return UI_FONT_SIZE_DEFAULT
}

export function applyUiFontSize(size: number) {
  const clamped = Math.min(UI_FONT_SIZE_MAX, Math.max(UI_FONT_SIZE_MIN, size))
  document.documentElement.style.fontSize = `${clamped}px`
  try {
    localStorage.setItem(UI_FONT_SIZE_STORAGE_KEY, String(clamped))
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<number>(UI_FONT_SIZE_CHANGE_EVENT, { detail: clamped })
  )
}

/** App-wide UI text font. */
export function getStoredAppFont(): AppFontId {
  try {
    const value = localStorage.getItem(APP_FONT_STORAGE_KEY)
    if (APP_FONTS.some(item => item.id === value)) {
      return value as AppFontId
    }
  } catch {
    // ignore
  }
  return 'default'
}

export function applyAppFont(id: AppFontId) {
  const meta = APP_FONTS.find(item => item.id === id)
  document.body.style.fontFamily = id === 'default' ? '' : (meta?.stack ?? '')
  try {
    localStorage.setItem(APP_FONT_STORAGE_KEY, id)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<AppFontId>(APP_FONT_CHANGE_EVENT, { detail: id })
  )
}

/** Native glass material (blur/vibrancy character). */
export function getStoredGlassMaterial(): GlassMaterialId {
  try {
    const value = localStorage.getItem(GLASS_MATERIAL_STORAGE_KEY)
    if (GLASS_MATERIALS.some(item => item.id === value)) {
      return value as GlassMaterialId
    }
  } catch {
    // ignore
  }
  return 'sidebar'
}

/** Native glass tint alpha, 0-100 (how strong the color wash reads). */
export function getStoredGlassTintStrength(): number {
  try {
    const value = Number(localStorage.getItem(GLASS_TINT_STRENGTH_STORAGE_KEY))
    if (
      Number.isFinite(value) &&
      value >= GLASS_TINT_STRENGTH_MIN &&
      value <= GLASS_TINT_STRENGTH_MAX
    ) {
      return value
    }
  } catch {
    // ignore
  }
  return GLASS_TINT_STRENGTH_DEFAULT
}

/** Pushes the current material + tint strength to the native glass effect. */
function syncNativeGlassOptions() {
  void setSidebarGlassOptions(
    getStoredGlassMaterial(),
    getStoredGlassTintStrength()
  )
}

export function applyGlassMaterial(id: GlassMaterialId) {
  try {
    localStorage.setItem(GLASS_MATERIAL_STORAGE_KEY, id)
  } catch {
    // ignore
  }
  syncNativeGlassOptions()
  window.dispatchEvent(
    new CustomEvent<GlassMaterialId>(GLASS_MATERIAL_CHANGE_EVENT, { detail: id })
  )
}

export function applyGlassTintStrength(percent: number) {
  const clamped = Math.min(
    GLASS_TINT_STRENGTH_MAX,
    Math.max(GLASS_TINT_STRENGTH_MIN, percent)
  )
  try {
    localStorage.setItem(GLASS_TINT_STRENGTH_STORAGE_KEY, String(clamped))
  } catch {
    // ignore
  }
  syncNativeGlassOptions()
  window.dispatchEvent(
    new CustomEvent<number>(GLASS_TINT_STRENGTH_CHANGE_EVENT, {
      detail: clamped
    })
  )
}

/** Dock tile (macOS desktop) — defaults to dark. */
export function getStoredDockIcon(): DockIconId {
  try {
    const value = localStorage.getItem(DOCK_ICON_STORAGE_KEY)
    if (value === 'dark' || value === 'light' || value === 'golden') {
      return value
    }
    // Older builds used "system" for the dark/default tile.
    if (value === 'system') {
      try {
        localStorage.setItem(DOCK_ICON_STORAGE_KEY, 'dark')
      } catch {
        // ignore
      }
      return 'dark'
    }
  } catch {
    // ignore
  }
  return 'dark'
}

export function applyDockIcon(id: DockIconId) {
  void setDockIcon(id)
  try {
    localStorage.setItem(DOCK_ICON_STORAGE_KEY, id)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<DockIconId>(DOCK_ICON_CHANGE_EVENT, { detail: id })
  )
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

/** DOM-only theme swap for hover preview — does not persist or emit. */
export function previewTheme(mode: ThemeMode) {
  document.documentElement.classList.toggle('dark', resolveDark(mode))
}

export function applyTheme(mode: ThemeMode) {
  const dark = resolveDark(mode)
  document.documentElement.classList.toggle('dark', dark)
  syncFavicon(dark)
  void syncSidebarGlassTheme(dark)
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

/** DOM-only palette swap for hover preview — does not persist or emit. */
export function previewPalette(palette: ThemePaletteId) {
  if (palette === 'default') {
    document.documentElement.removeAttribute('data-palette')
  } else {
    document.documentElement.setAttribute('data-palette', palette)
  }
}

export function getStoredAccentColor(): AccentColorId {
  try {
    const value = localStorage.getItem(ACCENT_COLOR_STORAGE_KEY)
    if (ACCENT_COLORS.some(item => item.id === value)) {
      return value as AccentColorId
    }
  } catch {
    // ignore
  }
  return 'none'
}

export function applyAccentColor(id: AccentColorId) {
  if (id === 'none') {
    document.documentElement.removeAttribute('data-accent')
  } else {
    document.documentElement.setAttribute('data-accent', id)
  }
  try {
    localStorage.setItem(ACCENT_COLOR_STORAGE_KEY, id)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<AccentColorId>(ACCENT_COLOR_CHANGE_EVENT, { detail: id })
  )
}

/** DOM-only accent swap for hover preview — does not persist or emit. */
export function previewAccentColor(id: AccentColorId) {
  if (id === 'none') {
    document.documentElement.removeAttribute('data-accent')
  } else {
    document.documentElement.setAttribute('data-accent', id)
  }
}

/** "#RRGGBB" → "H S% L%" (the space-separated triplet format our tokens use). */
function hexToHslTriplet(hex: string): string {
  const clean = hex.replace('#', '')
  const r = parseInt(clean.slice(0, 2), 16) / 255
  const g = parseInt(clean.slice(2, 4), 16) / 255
  const b = parseInt(clean.slice(4, 6), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return `0 0% ${Math.round(l * 100)}%`
  const delta = max - min
  const s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  let h: number
  if (max === r) h = ((g - b) / delta) % 6
  else if (max === g) h = (b - r) / delta + 2
  else h = (r - g) / delta + 4
  h = Math.round(h * 60)
  if (h < 0) h += 360
  return `${h} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}

/**
 * Auto sidebar text for a custom nav color — dark ink on light dunes,
 * light ink on dark nav. Avoids the common bug where dark-mode's gray
 * `--muted-foreground` sticks on a light custom sidebar.
 */
export function resolveAutoTextHex(navHex: string): string {
  const clean = navHex.replace('#', '')
  if (clean.length < 6) return '#1A1A1F'
  const channel = (start: number) => {
    const value = parseInt(clean.slice(start, start + 2), 16) / 255
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  const luminance =
    0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4)
  return luminance > 0.45 ? '#1A1A1F' : '#F1F1F3'
}

export function getStoredCustomTheme(): CustomThemeColors {
  try {
    const raw = localStorage.getItem(CUSTOM_THEME_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<CustomThemeColors>
      return { ...CUSTOM_THEME_DEFAULT, ...parsed }
    }
  } catch {
    // ignore
  }
  return CUSTOM_THEME_DEFAULT
}

/**
 * Push custom colors to CSS. These inline custom properties are harmless
 * when `data-palette` isn't "custom" — the tokens that actually drive the
 * UI (`--sidebar-background`, `--sidebar-accent`, …) only read them via a
 * `[data-palette='custom']`-scoped rule in index.css.
 */
export function applyCustomTheme(colors: CustomThemeColors) {
  const root = document.documentElement.style
  const textHex = colors.text ?? resolveAutoTextHex(colors.nav)
  root.setProperty('--sandwalk-custom-nav-hsl', hexToHslTriplet(colors.nav))
  root.setProperty('--sandwalk-custom-selected-hsl', hexToHslTriplet(colors.selected))
  root.setProperty('--sandwalk-custom-presence', colors.presence)
  root.setProperty('--sandwalk-custom-text-hsl', hexToHslTriplet(textHex))
  document.documentElement.classList.toggle(CUSTOM_GRADIENT_CLASS, colors.gradient)
  document.documentElement.classList.toggle(CUSTOM_TEXT_CLASS, Boolean(colors.text))
  try {
    localStorage.setItem(CUSTOM_THEME_STORAGE_KEY, JSON.stringify(colors))
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<CustomThemeColors>(CUSTOM_THEME_CHANGE_EVENT, {
      detail: colors
    })
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

/** Restore every Appearance preference to its factory default. */
export function resetAppearanceDefaults() {
  applyTheme('system')
  applyPalette('default')
  applyAccentColor('none')
  applyCustomTheme(CUSTOM_THEME_DEFAULT)
  applyLiquidGlass(true)
  applyGlassMaterial('sidebar')
  applyGlassTintStrength(GLASS_TINT_STRENGTH_DEFAULT)
  applyDockIcon('dark')
  applyAppFont('default')
  applyUiFontSize(UI_FONT_SIZE_DEFAULT)
}
