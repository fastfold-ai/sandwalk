import type { ITheme } from '@xterm/xterm'

import {
  getStoredPalette,
  PALETTE_CHANGE_EVENT,
  THEME_CHANGE_EVENT,
  type ThemePaletteId} from '@/lib/theme'

type AnsiTheme = Pick<
  ITheme,
  | 'black'
  | 'red'
  | 'green'
  | 'yellow'
  | 'blue'
  | 'magenta'
  | 'cyan'
  | 'white'
  | 'brightBlack'
  | 'brightRed'
  | 'brightGreen'
  | 'brightYellow'
  | 'brightBlue'
  | 'brightMagenta'
  | 'brightCyan'
  | 'brightWhite'
>

const DEFAULT_LIGHT_ANSI: AnsiTheme = {
  black: '#24292F',
  red: '#CF222E',
  green: '#1A7F37',
  yellow: '#9A6700',
  blue: '#0969DA',
  magenta: '#8250DF',
  cyan: '#1B7C83',
  white: '#EAEEF2',
  brightBlack: '#6E7781',
  brightRed: '#FF8182',
  brightGreen: '#2DA44E',
  brightYellow: '#D4A72C',
  brightBlue: '#218BFF',
  brightMagenta: '#A475F9',
  brightCyan: '#3192AA',
  brightWhite: '#FFFFFF'
}

const DEFAULT_DARK_ANSI: AnsiTheme = {
  black: '#484F58',
  red: '#FF7B72',
  green: '#3FB950',
  yellow: '#D29922',
  blue: '#58A6FF',
  magenta: '#BC8CFF',
  cyan: '#39C5CF',
  white: '#B1BAC4',
  brightBlack: '#6E7681',
  brightRed: '#FFA198',
  brightGreen: '#56D364',
  brightYellow: '#E3B341',
  brightBlue: '#79C0FF',
  brightMagenta: '#D2A8FF',
  brightCyan: '#56D4DD',
  brightWhite: '#FFFFFF'
}

/**
 * Palette-tinted ANSI sets so the terminal feels native to Mirage / Mahal /
 * Darwin / Fabienk / Dune / Neon Noir. Newer palettes (Ember, Verdant,
 * Custom) fall back to the default ANSI set — `readDocumentPalette()`
 * already maps them to "default".
 */
const PALETTE_ANSI: Partial<
  Record<Exclude<ThemePaletteId, 'default'>, { light: AnsiTheme; dark: AnsiTheme }>
> = {
  mirage: {
    light: {
      black: '#2A2118',
      red: '#C53A2E',
      green: '#6B8F3C',
      yellow: '#B8891F',
      blue: '#8B5E3C',
      magenta: '#A85A4A',
      cyan: '#9A7B2E',
      white: '#F4EFE6',
      brightBlack: '#7A6A58',
      brightRed: '#E84B3C',
      brightGreen: '#8CB85A',
      brightYellow: '#E2B045',
      brightBlue: '#C48A5A',
      brightMagenta: '#D47B6A',
      brightCyan: '#C9A227',
      brightWhite: '#FFFBF5'
    },
    dark: {
      black: '#3D3229',
      red: '#E84B3C',
      green: '#9BBB5C',
      yellow: '#E2B045',
      blue: '#D4A574',
      magenta: '#E07A6A',
      cyan: '#C9A227',
      white: '#E8DFD0',
      brightBlack: '#8A7A68',
      brightRed: '#FF6B5C',
      brightGreen: '#B4D47A',
      brightYellow: '#F0C45A',
      brightBlue: '#E8C09A',
      brightMagenta: '#F0A090',
      brightCyan: '#E2C45A',
      brightWhite: '#FFF8F0'
    }
  },
  mahal: {
    light: {
      black: '#3A2418',
      red: '#A8482E',
      green: '#6B7A3A',
      yellow: '#B8891F',
      blue: '#8E5C3C',
      magenta: '#9A5A48',
      cyan: '#A07A40',
      white: '#F7EBD4',
      brightBlack: '#8A6E55',
      brightRed: '#C45A3C',
      brightGreen: '#8A9A4A',
      brightYellow: '#E1B34C',
      brightBlue: '#B07A50',
      brightMagenta: '#C47A60',
      brightCyan: '#D4B060',
      brightWhite: '#FFF6E8'
    },
    dark: {
      black: '#4A3424',
      red: '#E07A5A',
      green: '#A8B86A',
      yellow: '#E1B34C',
      blue: '#D4A06A',
      magenta: '#E09A7A',
      cyan: '#D4B86A',
      white: '#F2D9A0',
      brightBlack: '#9A7E60',
      brightRed: '#F09070',
      brightGreen: '#C0D080',
      brightYellow: '#F0C86A',
      brightBlue: '#E8B888',
      brightMagenta: '#F0B090',
      brightCyan: '#E8D080',
      brightWhite: '#FFF4DC'
    }
  },
  darwin: {
    light: {
      black: '#1B4332',
      red: '#C44536',
      green: '#2D6A4F',
      yellow: '#8A7A30',
      blue: '#3A6B7A',
      magenta: '#6B5A7A',
      cyan: '#2D7A6A',
      white: '#E8F5E9',
      brightBlack: '#52796F',
      brightRed: '#E06A5A',
      brightGreen: '#52B788',
      brightYellow: '#B8A84A',
      brightBlue: '#5A9AAA',
      brightMagenta: '#8A7AAA',
      brightCyan: '#4AABA0',
      brightWhite: '#F4FFF6'
    },
    dark: {
      black: '#2D4A3C',
      red: '#E07A6A',
      green: '#52B788',
      yellow: '#D4C05A',
      blue: '#6AB0C0',
      magenta: '#A090C0',
      cyan: '#5AC0B0',
      white: '#D8F3DC',
      brightBlack: '#6A9080',
      brightRed: '#F09080',
      brightGreen: '#74C69D',
      brightYellow: '#E8D870',
      brightBlue: '#8AC8D8',
      brightMagenta: '#C0B0E0',
      brightCyan: '#7AD8C8',
      brightWhite: '#F0FFF2'
    }
  },
  fabienk: {
    light: {
      black: '#0A0A0A',
      red: '#C45A3C',
      green: '#6B8F3C',
      yellow: '#B8891F',
      blue: '#8B6B3C',
      magenta: '#A85A4A',
      cyan: '#9A7B2E',
      white: '#F5F0E6',
      brightBlack: '#6A6A6A',
      brightRed: '#E07A5A',
      brightGreen: '#8CB85A',
      brightYellow: '#F8B144',
      brightBlue: '#C49A5A',
      brightMagenta: '#D47B6A',
      brightCyan: '#E2C45A',
      brightWhite: '#FFFFFF'
    },
    dark: {
      black: '#1A1A1A',
      red: '#E07A5A',
      green: '#9BBB5C',
      yellow: '#F8B144',
      blue: '#D4A574',
      magenta: '#E07A6A',
      cyan: '#C9A227',
      white: '#E8E0D0',
      brightBlack: '#7A7A7A',
      brightRed: '#FF8A6A',
      brightGreen: '#B4D47A',
      brightYellow: '#FFC857',
      brightBlue: '#E8C09A',
      brightMagenta: '#F0A090',
      brightCyan: '#E2C45A',
      brightWhite: '#FFFFFF'
    }
  },
  dune: {
    light: {
      black: '#2A1610',
      red: '#A8482E',
      green: '#6B8F3C',
      yellow: '#B8891F',
      blue: '#5A7A7A',
      magenta: '#8E5C3C',
      cyan: '#6A9A9A',
      white: '#E8F0F0',
      brightBlack: '#7A6A58',
      brightRed: '#C45A3C',
      brightGreen: '#8CB85A',
      brightYellow: '#D4A373',
      brightBlue: '#8BB6B6',
      brightMagenta: '#C48A5A',
      brightCyan: '#A5C5C5',
      brightWhite: '#F5FAFA'
    },
    dark: {
      black: '#3D2118',
      red: '#E07A5A',
      green: '#9BBB5C',
      yellow: '#E09030',
      blue: '#8BB6B6',
      magenta: '#D4A373',
      cyan: '#C9A227',
      white: '#E8DFD0',
      brightBlack: '#8A7A68',
      brightRed: '#F09070',
      brightGreen: '#B4D47A',
      brightYellow: '#F0B85A',
      brightBlue: '#A5C5C5',
      brightMagenta: '#E8C49A',
      brightCyan: '#E2C45A',
      brightWhite: '#FFF8F0'
    }
  },
  neonnoir: {
    light: {
      black: '#0A0614',
      red: '#C4456A',
      green: '#5A8A7A',
      yellow: '#C49A5A',
      blue: '#3A2DB0',
      magenta: '#E83A8A',
      cyan: '#4A6A9A',
      white: '#F0E8F4',
      brightBlack: '#6A5A7A',
      brightRed: '#E85A8A',
      brightGreen: '#7AB8A0',
      brightYellow: '#E8C49A',
      brightBlue: '#5C8AE0',
      brightMagenta: '#FF4DA6',
      brightCyan: '#7A9AD0',
      brightWhite: '#FFF5FA'
    },
    dark: {
      black: '#1A0A2E',
      red: '#E85A8A',
      green: '#7AB8A0',
      yellow: '#E8C49A',
      blue: '#5C8AE0',
      magenta: '#E83A8A',
      cyan: '#7A9AD0',
      white: '#E8D8F0',
      brightBlack: '#7A6A8A',
      brightRed: '#FF6AA0',
      brightGreen: '#9AD4B8',
      brightYellow: '#F0D0A0',
      brightBlue: '#7AA8F0',
      brightMagenta: '#FF4DA6',
      brightCyan: '#A0C0E8',
      brightWhite: '#FFF5FA'
    }
  }
}

/**
 * xterm only parses `#rrggbb` and comma-separated `rgb()` / `rgba()`.
 * `hsl(0 0% 100%)` and any color with alpha fall through to a canvas
 * probe that rejects transparency, and the viewport's stylesheet
 * background is `#000`. A translucent white (`rgba(246, 246, 247, 0.62)`)
 * therefore composites over that black and paints a flat `#989898`.
 * Always hand xterm an opaque hex, or a comma-rgba for selections.
 */
function hslChannelsToHex(raw: string): string | null {
  const match = raw.trim().match(/^([\d.]+)\s+([\d.]+)%\s+([\d.]+)%$/)
  if (!match) return null
  const h = Number(match[1])
  const s = Number(match[2]) / 100
  const l = Number(match[3]) / 100
  const chroma = s * Math.min(l, 1 - l)
  const channel = (n: number) => {
    const k = (n + h / 30) % 12
    const color = l - chroma * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color)
  }
  const hex = [channel(0), channel(8), channel(4)]
    .map(value => value.toString(16).padStart(2, '0'))
    .join('')
  return `#${hex.toUpperCase()}`
}

function hexToRgba(hex: string, alpha: number): string {
  const n = Number.parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function cssTokenHex(token: `--${string}`, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim()
  if (!raw) return fallback
  return hslChannelsToHex(raw) ?? fallback
}

function cssTokenRgba(
  token: `--${string}`,
  alpha: number,
  fallback: string
): string {
  const hex = cssTokenHex(token, '')
  return hex ? hexToRgba(hex, alpha) : fallback
}

export function readDocumentPalette(): ThemePaletteId {
  if (typeof document === 'undefined') return getStoredPalette()
  const attr = document.documentElement.getAttribute('data-palette')
  if (
    attr === 'mirage' ||
    attr === 'mahal' ||
    attr === 'darwin' ||
    attr === 'fabienk' ||
    attr === 'dune' ||
    attr === 'neonnoir'
  ) {
    return attr
  }
  return 'default'
}

export const TERMINAL_THEME_STORAGE_KEY = 'sandwalk.terminal-theme'
export const TERMINAL_THEME_EVENT = 'sandwalk:terminal-theme'
export const TERMINAL_SURFACE_MENU_EVENT = 'sandwalk:terminal-theme-menu'
export const TERMINAL_PASTE_EVENT = 'sandwalk:terminal-paste'
export const TERMINAL_COPY_EVENT = 'sandwalk:terminal-copy'

export const TERMINAL_SCHEMES = [
  { id: 'auto', label: 'Match app' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
  { id: 'solarized-light', label: 'Solarized Light' },
  { id: 'solarized-dark', label: 'Solarized Dark' },
  { id: 'dracula', label: 'Dracula' }
] as const

export type TerminalSchemeId = (typeof TERMINAL_SCHEMES)[number]['id']

const SOLARIZED_ANSI: AnsiTheme = {
  black: '#073642',
  red: '#DC322F',
  green: '#859900',
  yellow: '#B58900',
  blue: '#268BD2',
  magenta: '#D33682',
  cyan: '#2AA198',
  white: '#EEE8D5',
  brightBlack: '#002B36',
  brightRed: '#CB4B16',
  brightGreen: '#586E75',
  brightYellow: '#657B83',
  brightBlue: '#839496',
  brightMagenta: '#6C71C4',
  brightCyan: '#93A1A1',
  brightWhite: '#FDF6E3'
}

const DRACULA_ANSI: AnsiTheme = {
  black: '#21222C',
  red: '#FF5555',
  green: '#50FA7B',
  yellow: '#F1FA8C',
  blue: '#BD93F9',
  magenta: '#FF79C6',
  cyan: '#8BE9FD',
  white: '#F8F8F2',
  brightBlack: '#6272A4',
  brightRed: '#FF6E6E',
  brightGreen: '#69FF94',
  brightYellow: '#FFFFA5',
  brightBlue: '#D6ACFF',
  brightMagenta: '#FF92DF',
  brightCyan: '#A4FFFF',
  brightWhite: '#FFFFFF'
}

function solidTheme(
  background: string,
  foreground: string,
  cursor: string,
  ansi: AnsiTheme
): ITheme {
  return {
    background,
    foreground,
    cursor,
    cursorAccent: background,
    selectionBackground: hexToRgba(cursor, 0.28),
    selectionForeground: foreground,
    ...ansi
  }
}

const PRESET_THEMES: Record<Exclude<TerminalSchemeId, 'auto'>, ITheme> = {
  light: solidTheme('#FAFAFA', '#24292F', '#0969DA', DEFAULT_LIGHT_ANSI),
  dark: solidTheme('#0D1117', '#E6EDF3', '#58A6FF', DEFAULT_DARK_ANSI),
  'solarized-light': solidTheme('#FDF6E3', '#657B83', '#268BD2', SOLARIZED_ANSI),
  'solarized-dark': solidTheme('#002B36', '#839496', '#268BD2', SOLARIZED_ANSI),
  dracula: solidTheme('#282A36', '#F8F8F2', '#F8F8F2', DRACULA_ANSI)
}

export function isTerminalSchemeId(value: string): value is TerminalSchemeId {
  return TERMINAL_SCHEMES.some(scheme => scheme.id === value)
}

export function getTerminalScheme(): TerminalSchemeId {
  if (typeof localStorage === 'undefined') return 'auto'
  try {
    const value = localStorage.getItem(TERMINAL_THEME_STORAGE_KEY)
    if (value && isTerminalSchemeId(value)) return value
  } catch {
    // Private mode or a blocked storage API — follow the app theme.
  }
  return 'auto'
}

export function setTerminalScheme(scheme: TerminalSchemeId): void {
  localStorage.setItem(TERMINAL_THEME_STORAGE_KEY, scheme)
  window.dispatchEvent(new Event(TERMINAL_THEME_EVENT))
}

/** Open the terminal context menu at a right-click on the surface. */
export function openTerminalThemeMenu(x: number, y: number, terminalId: string) {
  window.dispatchEvent(
    new CustomEvent(TERMINAL_SURFACE_MENU_EVENT, {
      detail: { x, y, terminalId }
    })
  )
}

export function requestTerminalPaste(terminalId: string) {
  window.dispatchEvent(
    new CustomEvent(TERMINAL_PASTE_EVENT, { detail: { terminalId } })
  )
}

export function requestTerminalCopy(terminalId: string) {
  window.dispatchEvent(
    new CustomEvent(TERMINAL_COPY_EVENT, { detail: { terminalId } })
  )
}

/** Desktop liquid glass is on and the window is focused. */
export function isLiquidGlassActive(): boolean {
  if (typeof document === 'undefined') return false
  const root = document.documentElement
  return (
    root.classList.contains('sandwalk-mac-glass-active') &&
    !root.classList.contains('sandwalk-liquid-glass-off')
  )
}

export function isDocumentDark(): boolean {
  return (
    typeof document !== 'undefined' &&
    document.documentElement.classList.contains('dark')
  )
}

/** Swatch shown next to a scheme in the terminal theme menu. */
export function terminalSchemeSwatch(
  scheme: TerminalSchemeId,
  dark: boolean = isDocumentDark(),
  palette: ThemePaletteId = readDocumentPalette()
): string {
  if (scheme === 'auto') {
    return String(buildTerminalTheme(dark, palette, 'auto').background)
  }
  return String(PRESET_THEMES[scheme].background)
}

/**
 * Build an xterm theme. `auto` follows light/dark + the app palette.
 * Any other scheme is a fixed terminal palette, independent of the app.
 * Backgrounds are always opaque — see `hslChannelsToHex`.
 */
export function buildTerminalTheme(
  dark: boolean = isDocumentDark(),
  palette: ThemePaletteId = readDocumentPalette(),
  scheme: TerminalSchemeId = getTerminalScheme()
): ITheme {
  if (scheme !== 'auto') return { ...PRESET_THEMES[scheme] }

  const ansi =
    (palette === 'default' ? undefined : PALETTE_ANSI[palette])?.[
      dark ? 'dark' : 'light'
    ] ?? (dark ? DEFAULT_DARK_ANSI : DEFAULT_LIGHT_ANSI)

  // Same frost bases as the shell, but opaque. Translucent white over
  // xterm's black viewport is what made the pane a flat gray.
  const background = isLiquidGlassActive()
    ? dark
      ? '#1C1C1F'
      : '#F6F6F7'
    : cssTokenHex('--card', dark ? '#0D1117' : '#FAFAFA')
  const foreground = cssTokenHex(
    '--foreground',
    dark ? '#E6EDF3' : '#24292F'
  )
  const cursor = cssTokenHex('--primary', dark ? '#58A6FF' : '#0969DA')

  return {
    background,
    foreground,
    cursor,
    cursorAccent: background,
    selectionBackground: cssTokenRgba(
      '--primary',
      dark ? 0.28 : 0.22,
      dark ? 'rgba(88, 166, 255, 0.28)' : 'rgba(9, 105, 218, 0.22)'
    ),
    selectionForeground: foreground,
    ...ansi
  }
}

type ThemeListener = (theme: ITheme) => void

const themeListeners = new Set<ThemeListener>()
let themeWatcherStop: (() => void) | null = null

/**
 * One document-level watcher shared by every terminal. With dozens of
 * xterm instances mounted, a per-terminal watcher meant N × (getComputedStyle
 * → term.options.theme) and each theme write mutates a `<style>` tag, so the
 * next read forced a full style recalc: layout thrash scaling with the
 * number of terminals. Now the theme is read once per change and fanned out.
 */
function startThemeWatcher() {
  // A palette click updates the DOM attribute and then dispatches an event.
  // Both would rebuild every xterm theme. Coalesce to one frame.
  let frame = 0
  const schedule = () => {
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0
      const theme = buildTerminalTheme(isDocumentDark())
      for (const listener of themeListeners) listener(theme)
    })
  }
  const root = document.documentElement
  const observer = new MutationObserver(schedule)
  observer.observe(root, {
    attributes: true,
    attributeFilter: ['class', 'data-palette']
  })
  window.addEventListener(THEME_CHANGE_EVENT, schedule)
  window.addEventListener(PALETTE_CHANGE_EVENT, schedule)
  window.addEventListener(TERMINAL_THEME_EVENT, schedule)
  themeWatcherStop = () => {
    if (frame) cancelAnimationFrame(frame)
    observer.disconnect()
    window.removeEventListener(THEME_CHANGE_EVENT, schedule)
    window.removeEventListener(PALETTE_CHANGE_EVENT, schedule)
    window.removeEventListener(TERMINAL_THEME_EVENT, schedule)
  }
}

/** Subscribe to light/dark + palette changes that should refresh xterm. */
export function watchTerminalTheme(onChange: ThemeListener): () => void {
  if (themeListeners.size === 0) startThemeWatcher()
  themeListeners.add(onChange)
  return () => {
    themeListeners.delete(onChange)
    if (themeListeners.size === 0 && themeWatcherStop) {
      themeWatcherStop()
      themeWatcherStop = null
    }
  }
}
