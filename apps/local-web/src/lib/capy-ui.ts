export const CAPY_UI_STORAGE_KEY = 'capy.ui'

export type CapyWindowState = {
  open: boolean
  minimized: boolean
  locked: boolean
  x: number
  y: number
  width: number
  height: number
}

export const CAPY_WINDOW_DEFAULT: CapyWindowState = {
  open: false,
  minimized: false,
  locked: false,
  x: 24,
  y: 72,
  width: 520,
  height: 580
}

export const CAPY_MARGIN = 8
export const CAPY_MINIMIZED_SIZE = 56
export const CAPY_MIN_WIDTH = 380
export const CAPY_MIN_HEIGHT = 420

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n))
}

export function clampCapyWindow(
  state: CapyWindowState,
  viewport?: { width: number; height: number }
): CapyWindowState {
  const view =
    viewport ??
    (typeof window === 'undefined'
      ? { width: 1280, height: 800 }
      : { width: window.innerWidth, height: window.innerHeight })
  const margin = CAPY_MARGIN
  if (state.minimized && !state.open) {
    const size = CAPY_MINIMIZED_SIZE
    return {
      ...state,
      x: clamp(state.x, margin, Math.max(margin, view.width - size - margin)),
      y: clamp(state.y, margin, Math.max(margin, view.height - size - margin))
    }
  }
  const width = clamp(
    state.width,
    CAPY_MIN_WIDTH,
    Math.max(CAPY_MIN_WIDTH, view.width - margin * 2)
  )
  const height = clamp(
    state.height,
    CAPY_MIN_HEIGHT,
    Math.max(CAPY_MIN_HEIGHT, view.height - margin * 2)
  )
  return {
    ...state,
    width,
    height,
    x: clamp(state.x, margin, Math.max(margin, view.width - width - margin)),
    y: clamp(state.y, margin, Math.max(margin, view.height - height - margin))
  }
}

export function readCapyWindow(): CapyWindowState {
  try {
    const raw = localStorage.getItem(CAPY_UI_STORAGE_KEY)
    if (!raw) return { ...CAPY_WINDOW_DEFAULT }
    const parsed = JSON.parse(raw) as Partial<CapyWindowState>
    return clampCapyWindow({
      ...CAPY_WINDOW_DEFAULT,
      ...parsed,
      x: Number(parsed.x) || CAPY_WINDOW_DEFAULT.x,
      y: Number(parsed.y) || CAPY_WINDOW_DEFAULT.y,
      width: Number(parsed.width) || CAPY_WINDOW_DEFAULT.width,
      height: Number(parsed.height) || CAPY_WINDOW_DEFAULT.height
    })
  } catch {
    return { ...CAPY_WINDOW_DEFAULT }
  }
}

export function writeCapyWindow(state: CapyWindowState) {
  localStorage.setItem(CAPY_UI_STORAGE_KEY, JSON.stringify(state))
}

export const CAPY_OPEN_EVENT = 'sandwalk:capy-open'
export const CAPY_REVEAL_MINIMIZED_EVENT = 'sandwalk:capy-reveal-minimized'

export function requestOpenCapy() {
  window.dispatchEvent(new Event(CAPY_OPEN_EVENT))
}

export function shouldRevealCapyMinimized(state: Pick<CapyWindowState, 'open' | 'minimized'>) {
  return !state.open && !state.minimized
}

export function requestRevealCapyMinimized() {
  window.dispatchEvent(new Event(CAPY_REVEAL_MINIMIZED_EVENT))
}

export type CapyShortcut = {
  ctrl: boolean
  alt: boolean
  shift: boolean
  meta: boolean
  /** Set when the shortcut includes a non-modifier key. */
  key: string | null
}

export const DEFAULT_CAPY_SHORTCUT: CapyShortcut = {
  ctrl: true,
  alt: true,
  shift: false,
  meta: false,
  key: null
}

const CAPY_SHORTCUT_STORAGE_KEY = 'sandwalk:capy-shortcut'
export const CAPY_SHORTCUT_CHANGE_EVENT = 'sandwalk:capy-shortcut-change'

let recordingCapyShortcut = false

export function setCapyShortcutRecording(next: boolean) {
  recordingCapyShortcut = next
}

export function readCapyShortcut(): CapyShortcut {
  try {
    const raw = localStorage.getItem(CAPY_SHORTCUT_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_CAPY_SHORTCUT }
    const parsed = JSON.parse(raw) as Partial<CapyShortcut>
    const shortcut: CapyShortcut = {
      ctrl: Boolean(parsed.ctrl),
      alt: Boolean(parsed.alt),
      shift: Boolean(parsed.shift),
      meta: Boolean(parsed.meta),
      key: typeof parsed.key === 'string' && parsed.key.trim() ? parsed.key : null
    }
    const parts =
      Number(shortcut.ctrl) +
      Number(shortcut.alt) +
      Number(shortcut.shift) +
      Number(shortcut.meta) +
      (shortcut.key ? 1 : 0)
    if (parts < 2) return { ...DEFAULT_CAPY_SHORTCUT }
    return shortcut
  } catch {
    return { ...DEFAULT_CAPY_SHORTCUT }
  }
}

export function writeCapyShortcut(shortcut: CapyShortcut) {
  localStorage.setItem(CAPY_SHORTCUT_STORAGE_KEY, JSON.stringify(shortcut))
  window.dispatchEvent(
    new CustomEvent(CAPY_SHORTCUT_CHANGE_EVENT, { detail: shortcut })
  )
}

export function capyShortcutSymbols(shortcut: CapyShortcut = readCapyShortcut()): string[] {
  const symbols: string[] = []
  if (shortcut.ctrl) symbols.push('⌃')
  if (shortcut.alt) symbols.push('⌥')
  if (shortcut.shift) symbols.push('⇧')
  if (shortcut.meta) symbols.push('⌘')
  if (shortcut.key) {
    symbols.push(shortcut.key.length === 1 ? shortcut.key.toUpperCase() : shortcut.key)
  }
  return symbols
}

type ShortcutEvent = {
  key: string
  repeat?: boolean
  ctrlKey?: boolean
  altKey?: boolean
  shiftKey?: boolean
  metaKey?: boolean
}

function eventModifiers(event: ShortcutEvent) {
  return {
    ctrl: Boolean(event.ctrlKey) || event.key === 'Control',
    alt: Boolean(event.altKey) || event.key === 'Alt',
    shift: Boolean(event.shiftKey) || event.key === 'Shift',
    meta: Boolean(event.metaKey) || event.key === 'Meta'
  }
}

/** A finished shortcut from a keydown, or null while the user is still holding one modifier. */
export function shortcutFromEvent(event: ShortcutEvent): CapyShortcut | null {
  if (event.repeat || event.key === 'Escape') return null
  const mods = eventModifiers(event)
  const isModifier = ['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)
  const key = isModifier ? null : event.key
  const parts =
    Number(mods.ctrl) + Number(mods.alt) + Number(mods.shift) + Number(mods.meta) + (key ? 1 : 0)
  if (parts < 2 || (!mods.ctrl && !mods.alt && !mods.shift && !mods.meta)) return null
  return { ...mods, key }
}

export function matchesCapyShortcut(event: ShortcutEvent, shortcut: CapyShortcut) {
  if (event.repeat) return false
  const mods = eventModifiers(event)
  if (
    mods.ctrl !== shortcut.ctrl ||
    mods.alt !== shortcut.alt ||
    mods.shift !== shortcut.shift ||
    mods.meta !== shortcut.meta
  ) {
    return false
  }
  if (!shortcut.key) {
    return ['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)
  }
  return event.key.toLowerCase() === shortcut.key.toLowerCase()
}

export function isCapyHandsFreeKey(event: ShortcutEvent) {
  if (recordingCapyShortcut || event.repeat) return false
  return matchesCapyShortcut(event, readCapyShortcut())
}

export function formatCapyUnreadBadge(count: number): string | null {
  if (count <= 0) return null
  if (count > 99) return '99+'
  return String(count)
}

/** `{ rows, cols }` from an untrusted `ui.command` payload, or null. */
export function parseGridLayout(
  raw: unknown
): { rows: number; cols: number } | null {
  if (!raw || typeof raw !== 'object') return null
  const rows = Number((raw as { rows?: unknown }).rows)
  const cols = Number((raw as { cols?: unknown }).cols)
  if (!Number.isInteger(rows) || !Number.isInteger(cols)) return null
  if (rows < 1 || cols < 1 || rows > 16 || cols > 16) return null
  return { rows, cols }
}

export function applyCapyOpenSplit(
  sessionIds: string[],
  createSplitGroup: (ids: string[]) => string | null,
  navigate: (path: string) => void
): string | null {
  const ids = [...new Set(sessionIds.filter(id => id && !id.startsWith('grp_')))]
  if (ids.length < 2) return null
  const groupId = createSplitGroup(ids)
  if (groupId) navigate(`/agents/${groupId}`)
  return groupId
}
