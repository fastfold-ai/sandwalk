/**
 * Thin bridge to the Tauri desktop shell. In the browser these are inert
 * (`isTauri() === false`). Uses injected `window.__TAURI__` (withGlobalTauri).
 */

export type DesktopServerStatus = {
  state: string
  label: string
  api_base?: string
  dashboard_url?: string
  dashboard_home_url?: string
  bind_host?: string
  port?: number
  dashboard_host?: string
  dashboard_port?: number
  dashboard_serve_mode?: string
  auto_start?: boolean
  menubar_running?: boolean
}

export type DesktopSettings = {
  bind_host: string
  port: number
  dashboard_host: string
  dashboard_port: number
  auto_start: boolean
  health_check_interval_seconds: number
  dashboard_serve_mode: string
  db_auto_heal: boolean
  keep_menubar_on_cmdq: boolean
}

export type DesktopAuth = {
  auth_enabled: boolean
  api_key_configured: boolean
  api_key: string
}

export type DesktopPrefs = {
  open_at_login: boolean
  open_at_login_status?: string
  auto_start: boolean
  keep_menubar_on_cmdq: boolean
}

export type DesktopLogs = {
  name: string
  text: string
  total_lines: number
  path?: string
}

type TauriGlobal = {
  core?: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> }
  event?: {
    listen: (
      event: string,
      handler: (event: { payload: unknown }) => void
    ) => Promise<() => void>
  }
}

export const isTauri = (): boolean => {
  const g = globalThis as {
    __TAURI__?: unknown
    __TAURI_INTERNALS__?: unknown
  }
  return typeof g.__TAURI__ !== 'undefined' || typeof g.__TAURI_INTERNALS__ !== 'undefined'
}

/** Tailwind classes: clear macOS traffic lights. */
export const MAC_OVERLAY_SIDEBAR_PAD = 'pl-[84px] pt-[12px]'
export const MAC_OVERLAY_MAIN_PAD = 'pt-[12px]'

/** "macos" | "windows" | "linux" — injected by the shell before SPA load. */
export const platformOS = (): string => {
  const injected = (globalThis as { __SANDWALK_PLATFORM__?: unknown })
    .__SANDWALK_PLATFORM__
  if (typeof injected === 'string' && injected) return injected
  if (/mac/i.test(navigator.userAgent)) return 'macos'
  if (/win/i.test(navigator.userAgent)) return 'windows'
  return 'linux'
}

/** Primary app window (`main`) vs spawned client windows. */
export const isMainDesktopWindow = (): boolean => {
  const kind = (globalThis as { __SANDWALK_WINDOW_KIND__?: unknown })
    .__SANDWALK_WINDOW_KIND__
  return kind !== 'client' && kind !== 'about'
}

/** Small About / update window opened from the Sandwalk menu. */
export const isAboutDesktopWindow = (): boolean => {
  const kind = (globalThis as { __SANDWALK_WINDOW_KIND__?: unknown })
    .__SANDWALK_WINDOW_KIND__
  return kind === 'about'
}

/** Overlay title bar (traffic lights over content) — macOS Tauri only. */
export const isMacDesktopOverlay = (): boolean => {
  // Our shell injects platform before SPA load — treat that as desktop even if
  // `__TAURI__` is briefly missing during HMR.
  const injected = (globalThis as { __SANDWALK_PLATFORM__?: unknown })
    .__SANDWALK_PLATFORM__
  if (injected === 'macos') return true
  return isTauri() && platformOS() === 'macos'
}

const tauri = (): TauriGlobal | null =>
  (globalThis as { __TAURI__?: TauriGlobal }).__TAURI__ ?? null

const invoke = async <T>(
  cmd: string,
  args?: Record<string, unknown>
): Promise<T | null> => {
  const api = tauri()
  if (!api?.core?.invoke) return null
  try {
    return (await api.core.invoke(cmd, args)) as T
  } catch {
    return null
  }
}

const invokeStrict = async <T>(
  cmd: string,
  args?: Record<string, unknown>
): Promise<T> => {
  const api = tauri()
  if (!api?.core?.invoke) {
    throw new Error('This feature is available in the Sandwalk desktop app.')
  }
  return (await api.core.invoke(cmd, args)) as T
}

export const desktopMenubarAvailable = () =>
  invoke<boolean>('desktop_menubar_available')

export const desktopServerStatus = () =>
  invoke<DesktopServerStatus>('desktop_server_status')

export const desktopServerStart = () =>
  invokeStrict<DesktopServerStatus>('desktop_server_start')

export const desktopServerStop = () =>
  invokeStrict<DesktopServerStatus>('desktop_server_stop')

export const desktopServerRestart = () =>
  invokeStrict<DesktopServerStatus>('desktop_server_restart')

export const desktopGetSettings = () =>
  invoke<DesktopSettings>('desktop_get_settings')

export const desktopPutSettings = (settings: Partial<DesktopSettings>) =>
  invokeStrict<DesktopSettings>('desktop_put_settings', { settings })

export const desktopGetAuth = () => invoke<DesktopAuth>('desktop_get_auth')

export const desktopPutAuth = (auth: Record<string, unknown>) =>
  invokeStrict<DesktopAuth>('desktop_put_auth', { auth })

export const desktopGetDesktop = () =>
  invoke<DesktopPrefs>('desktop_get_desktop')

export const desktopPutDesktop = (prefs: Partial<DesktopPrefs>) =>
  invokeStrict<DesktopPrefs>('desktop_put_desktop', { prefs })

export const desktopTailLogs = (name?: string, lines?: number) =>
  invoke<DesktopLogs>('desktop_tail_logs', { name, lines })

export const desktopRebuildDashboard = () =>
  invokeStrict<{ ok?: boolean }>('desktop_rebuild_dashboard')

export type DesktopCliPathStatus = {
  state: 'ready' | 'missing' | 'foreign' | 'unavailable' | string
  command?: string
  shim_path?: string
  shim_exists?: boolean
  managed?: boolean
  foreign?: boolean
  bundled_runtime?: boolean
  path_ready?: boolean
  message?: string
  version?: string
  python_path?: string
  outcome?: string
  error?: string
}

export const desktopCliPathStatus = () =>
  invoke<DesktopCliPathStatus>('desktop_cli_path_status')

export const desktopCliPathInstall = (force = false) =>
  invokeStrict<DesktopCliPathStatus>('desktop_cli_path_install', { force })

export const desktopAppVersion = () => invoke<string>('desktop_app_version')

/** Begin native window dragging from a custom title/header region. */
export const startWindowDrag = () => invoke<boolean>('start_window_drag')

/** Double-click title bar — toggle maximized (native macOS behavior). */
export const toggleMaximize = () => invoke<boolean>('toggle_maximize')

/** Native window fullscreen (not browser Fullscreen API). */
export const windowIsFullscreen = () => invoke<boolean>('window_is_fullscreen')

/** Listen for native fullscreen enter/exit (emitted on resize). */
export async function listenWindowFullscreen(
  handler: (fullscreen: boolean) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk-window-fullscreen', event => {
    handler(Boolean(event.payload))
  })
}

/** Listen for sidebar glass on/off (tied to window key focus). */
export async function listenWindowGlassActive(
  handler: (active: boolean) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk-window-glass-active', event => {
    handler(Boolean(event.payload))
  })
}

/** Sync native sidebar glass tint with light/dark theme (macOS desktop). */
export const syncSidebarGlassTheme = (dark: boolean) =>
  invoke<void>('set_sidebar_glass_dark', { dark })

/** Update native glass material + tint strength (macOS desktop). */
export const setSidebarGlassOptions = (variant: string, tintStrength: number) =>
  invoke<void>('set_sidebar_glass_options', {
    variant,
    tintStrength: Math.round(tintStrength),
    cornerRadius: 0
  })

/**
 * Swap the Dock tile (macOS desktop only). `variant` is "dark" | "light" |
 * "golden". Applied at runtime (and again on launch from the saved
 * preference); the installed bundle icon stays dark. No-op outside Tauri.
 */
export const setDockIcon = (variant: string) =>
  invoke<void>('set_dock_icon', { variant })

/**
 * Set / clear the macOS Dock badge (red notification indicator).
 * Pass a count/label string, or null/empty to clear. No-op outside Tauri.
 */
export const setDockBadge = (label: string | null) =>
  invoke<void>('set_dock_badge', { label })

/** Open a URL in the system browser. */
export const openExternalUrl = (url: string) =>
  invokeStrict<void>('open_external_url', { url })

/**
 * Copy via the native shell. Returns false when unavailable (browser) or when
 * the shell reports failure, so callers can fall back or surface an error.
 */
export const copyViaDesktop = async (text: string): Promise<boolean> => {
  const api = tauri()
  if (!api?.core?.invoke) return false
  try {
    await api.core.invoke('copy_to_clipboard', { text })
    return true
  } catch {
    return false
  }
}

/**
 * Save text via the native shell (Downloads + reveal). WebView `<a download>`
 * does not write files in Tauri.
 */
export const saveTextFile = (defaultFilename: string, contents: string) =>
  invokeStrict<string>('save_text_file', {
    defaultFilename,
    contents
  })

/**
 * Save binary bytes (base64) to Downloads and reveal in Finder / file manager.
 * Returns the absolute path written.
 */
export const saveBytesFile = (defaultFilename: string, contentsBase64: string) =>
  invokeStrict<string>('save_bytes_file', {
    defaultFilename,
    contentsBase64
  })

/** Open any http(s) URL in the system browser (Tauri) or a new tab (web). */
export async function openInSystemBrowser(url: string): Promise<void> {
  const trimmed = url.trim()
  if (!trimmed) return
  if (isTauri()) {
    await openExternalUrl(trimmed)
    return
  }
  window.open(trimmed, '_blank', 'noopener,noreferrer')
}

/**
 * Resolve the supervised web dashboard URL (browser UI), then open it externally
 * when running in Tauri; otherwise open a new tab.
 */
export async function openWebUiInBrowser(backendUrl?: string | null): Promise<void> {
  let url: string | null = null
  if (isTauri()) {
    const status = await desktopServerStatus()
    url =
      status?.dashboard_home_url?.trim() ||
      status?.dashboard_url?.trim() ||
      null
  }
  if (!url) {
    url = fallbackWebUiUrl(backendUrl)
  }
  await openInSystemBrowser(url)
}

function fallbackWebUiUrl(backendUrl?: string | null): string {
  const raw = (backendUrl || 'http://127.0.0.1:8787').trim()
  try {
    const parsed = new URL(raw)
    if (!parsed.port || parsed.port === '8787') {
      parsed.port = '8969'
    }
    parsed.pathname = '/dashboard'
    parsed.search = ''
    parsed.hash = ''
    return parsed.toString()
  } catch {
    return 'http://127.0.0.1:8969/dashboard'
  }
}

/** Listen for menubar deep-link navigation into this window. */
export async function listenDesktopNavigate(
  handler: (path: string) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk://navigate', event => {
    const payload = event.payload as { path?: string } | null
    if (payload?.path) handler(payload.path)
  })
}

export type DesktopMenuAction = {
  action: string
  url?: string | null
  route?: string | null
  title?: string | null
  snapshotId?: string | null
  hostname?: string | null
  platform?: string | null
}

/** File menu actions that need SPA UI (Remote dialog / Open Recent with key). */
export async function listenDesktopMenu(
  handler: (payload: DesktopMenuAction) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk-menu', event => {
    const payload = event.payload as DesktopMenuAction | null
    if (payload?.action) handler(payload)
  })
}

export type DesktopApplyAuth = {
  url: string
  apiKey: string
}

/** Re-apply a remembered API key into an already-open remote WebView. */
export async function listenDesktopApplyAuth(
  handler: (payload: DesktopApplyAuth) => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk-apply-auth', event => {
    const payload = event.payload as {
      url?: string
      apiKey?: string
      api_key?: string
    } | null
    const url = payload?.url?.trim()
    const apiKey = (payload?.apiKey || payload?.api_key || '').trim()
    if (url && apiKey) handler({ url, apiKey })
  })
}

/** Open Recent list changed (`window-recents.json` rewritten). */
export async function listenDesktopWindowRecentsChanged(
  handler: () => void
): Promise<() => void> {
  const listen = tauri()?.event?.listen
  if (!listen) return () => {}
  return listen('sandwalk-window-recents-changed', () => {
    handler()
  })
}

export type OpenDesktopWindowArgs = {
  backendUrl?: string | null
  apiKey?: string | null
  title?: string | null
  route?: string | null
  snapshotId?: string | null
  hostname?: string | null
  platform?: string | null
  focusExisting?: boolean
}

/** Spawn or focus a desktop WebView bound to a backend URL / snapshot. */
export const openDesktopWindow = (args: OpenDesktopWindowArgs = {}) =>
  invokeStrict<string>('desktop_open_window', {
    // Single `payload` arg — avoids flat-arg drops that left remotes on localhost.
    payload: {
      backendUrl: args.backendUrl ?? null,
      apiKey: args.apiKey ?? null,
      title: args.title ?? null,
      route: args.route ?? null,
      snapshotId: args.snapshotId ?? null,
      hostname: args.hostname ?? null,
      platform: args.platform ?? null,
      focusExisting: Boolean(args.focusExisting)
    }
  })

/** Sync native window title + Open Recent after in-app Change server. */
export const bindDesktopWindowBackend = (url: string) =>
  invoke<void>('desktop_bind_window_backend', { url })

/** Dock / Mission Control window label (chat or page title). */
export const setDesktopWindowTitle = (title: string) =>
  invoke<void>('desktop_set_window_title', { title })

/** Close the current desktop WebView (remote windows quit; main may hide). */
export const closeDesktopWindow = () =>
  invokeStrict<void>('desktop_close_current_window')

/** Hide the current desktop WebView (launcher after opening a remote window). */
export const hideDesktopWindow = () =>
  invokeStrict<void>('desktop_hide_current_window')

/** Persist / update Open Recent for this window (route + title snapshot). */
export const upsertDesktopWindowSnapshot = (args: {
  snapshotId?: string | null
  url: string
  route: string
  title: string
  hostname?: string | null
  platform?: string | null
}) =>
  invokeStrict<string>('desktop_upsert_window_snapshot', {
    snapshotId: args.snapshotId ?? null,
    url: args.url,
    route: args.route,
    title: args.title,
    hostname: args.hostname ?? null,
    platform: args.platform ?? null
  })

/** Snapshot id injected when the native window was created. */
export function readDesktopSnapshotId(): string | null {
  const injected = (globalThis as { __SANDWALK_SNAPSHOT_ID__?: unknown })
    .__SANDWALK_SNAPSHOT_ID__
  if (typeof injected === 'string' && injected.trim()) return injected.trim()
  try {
    const stored = sessionStorage.getItem('sandwalk.snapshotId')
    if (stored?.trim()) return stored.trim()
  } catch {
    // ignore
  }
  return null
}

export function persistDesktopSnapshotId(id: string) {
  const trimmed = id.trim()
  if (!trimmed) return
  ;(globalThis as { __SANDWALK_SNAPSHOT_ID__?: string }).__SANDWALK_SNAPSHOT_ID__ =
    trimmed
  try {
    sessionStorage.setItem('sandwalk.snapshotId', trimmed)
  } catch {
    // ignore
  }
}

/** Open the Sandwalk Server helper Settings window. */
export const openDesktopServerSettings = () =>
  invokeStrict<void>('desktop_open_server_settings')

export const rememberDesktopWindowRecent = (url: string) =>
  invoke<void>('desktop_remember_window_recent', { url })

export const clearDesktopWindowRecents = () =>
  invokeStrict<void>('desktop_clear_window_recents')

export const removeDesktopWindowRecent = (id: string) =>
  invokeStrict<void>('desktop_remove_window_recent', { id })

export type DesktopWindowRecent = {
  id: string
  url: string
  route?: string
  title?: string
  /** Remote machine hostname from discover / LAN scan. */
  hostname?: string
  /** OS from LAN scan / discover (`Linux`, `Darwin`, …) — no live probe needed. */
  platform?: string
  label?: string | null
  lastOpenedAt: number
}

export const listDesktopWindowRecents = () =>
  invoke<DesktopWindowRecent[]>('desktop_list_window_recents')

export type LanDesktopServer = {
  url: string
  hostname: string
  platform: string
  arch: string
  deviceLabel: string
  authRequired: boolean
  version: string
}

/** Probe local /24 (+ localhost) for Sandwalk servers on :8787/:8789/:8790. */
export const scanLanDesktopServers = () =>
  invokeStrict<LanDesktopServer[]>('desktop_scan_lan_servers')

/** This machine’s short hostname (e.g. `Julios-MacBook-Pro`), or null. */
export const desktopLocalHostname = () =>
  invoke<string>('desktop_local_hostname').then(name => {
    const trimmed = (name || '').trim()
    return trimmed || null
  })

/** Native directory picker (desktop). Returns null when canceled or unavailable. */
export async function pickDirectory(): Promise<string | null> {
  if (!isTauri()) return null
  try {
    const dialog = await import('@tauri-apps/plugin-dialog')
    const selected = await dialog.open({
      directory: true,
      multiple: false,
      title: 'Choose project folder'
    })
    if (typeof selected === 'string' && selected.trim()) return selected
    return null
  } catch {
    return null
  }
}
