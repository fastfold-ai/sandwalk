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

export const CAPY_HANDS_FREE_WINDOW_MS = 400

export function isCapyHandsFreeKey(event: {
  key: string
  repeat?: boolean
  metaKey?: boolean
  altKey?: boolean
}) {
  return (
    event.key === 'Control' &&
    !event.repeat &&
    !event.metaKey &&
    !event.altKey
  )
}

export function formatCapyUnreadBadge(count: number): string | null {
  if (count <= 0) return null
  if (count > 99) return '99+'
  return String(count)
}

export function createDoubleTap(windowMs = CAPY_HANDS_FREE_WINDOW_MS) {
  let last = 0
  return (now = Date.now()) => {
    const hit = last > 0 && now - last <= windowMs
    last = hit ? 0 : now
    return hit
  }
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
