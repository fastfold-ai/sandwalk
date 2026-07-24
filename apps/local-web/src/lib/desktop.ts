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

/** Tailwind classes: clear macOS traffic lights (OpenWorker-aligned). */
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

export const desktopAppVersion = () => invoke<string>('desktop_app_version')

/** Begin native window dragging from a custom title/header region. */
export const startWindowDrag = () => invoke<boolean>('start_window_drag')

/** Double-click title bar — toggle maximized (native macOS behavior). */
export const toggleMaximize = () => invoke<boolean>('toggle_maximize')

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
