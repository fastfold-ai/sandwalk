/** Best-effort OS notifications for agent HITL / completion alerts. */

import { isTauri } from '@/lib/desktop'
import { openItem } from '@/lib/item-opener'
import {
  getStoredNotifyApproval,
  getStoredNotifyCompletion,
  shouldNotifyCompletion
} from '@/lib/notification-settings'

let webPermissionRequested = false
let clickHandlerRegistered = false
let focusListenersRegistered = false
// FAS-107 · Fase 1f · cache local del estado de foco de la ventana Tauri.
// `document.hasFocus()` en WKWebView macOS puede mentir (sigue en true
// aunque la ventana no sea key). Escuchamos los eventos nativos de
// Tauri (`tauri://focus` / `tauri://blur`) y mantenemos este flag
// sincronizado como fuente de verdad.
let tauriWindowFocused: boolean | null = null

/**
 * FAS-107 · Fase 1f · handler global del click en banner nativo de
 * macOS. Extrae el id del `tag` que ya usamos al enviar la notif y
 * llama `openItem(id)` — el resolver decide si es standalone o hijo
 * de split y navega + setea `activeChatId` según corresponda.
 *
 * Los tags que emitimos:
 *   sandwalk-complete-{sessionId}       → run.completed / failed
 *   sandwalk-approval-{sessionId}       → run.awaiting_approval
 *   sandwalk-term-{terminalId}          → command finished / failed
 *   sandwalk-term-notify-{terminalId}   → OSC 9 / OSC 777
 *
 * Se registra una sola vez, la primera vez que se dispara cualquier
 * notif. Tauri activa la ventana al click; nosotros llevamos al
 * pane exacto.
 */
function extractItemIdFromTag(tag: string | null | undefined): string | null {
  if (!tag) return null
  const prefixes = [
    'sandwalk-complete-',
    'sandwalk-approval-',
    'sandwalk-term-notify-', // check antes del más genérico
    'sandwalk-term-'
  ]
  for (const prefix of prefixes) {
    if (tag.startsWith(prefix)) {
      const id = tag.slice(prefix.length)
      return id.length > 0 ? id : null
    }
  }
  return null
}

async function ensureClickHandlerRegistered(): Promise<void> {
  if (clickHandlerRegistered || !isTauri()) return
  clickHandlerRegistered = true
  try {
    // FAS-107 · Fase 1g · el plugin oficial no expone `onAction` en
    // desktop macOS (solo mobile). Usamos un delegate nativo custom
    // registrado en `src-tauri/src/notification_click.rs` que emite el
    // evento `sandwalk://notification-click` con el `tag` como payload.
    const { listen } = await import('@tauri-apps/api/event')
    await listen<string>('sandwalk://notification-click', event => {
      // TEMP DEBUG FAS-107 (fase 1g/1h): trazar el flujo del click en
      // banner. Quitar tras validar el deep link end-to-end.
      // eslint-disable-next-line no-console
      console.log('[FAS-107 click event]', event.payload)
      const tag = typeof event.payload === 'string' ? event.payload : null
      const id = extractItemIdFromTag(tag)
      // eslint-disable-next-line no-console
      console.log(`[FAS-107 extracted id] tag=${tag} id=${id}`)
      if (id) openItem(id)
    })
    // eslint-disable-next-line no-console
    console.log('[FAS-107 click listener registered]')
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[FAS-107 notification click listen failed]', err)
    clickHandlerRegistered = false
  }
}

function isWindowFocused(): boolean {
  if (typeof document === 'undefined') return true
  if (document.hidden) return false
  // FAS-107 · Fase 1f · Tauri window focus manda sobre `document.hasFocus()`.
  // WKWebView macOS puede mantener `document.hasFocus() === true` incluso
  // cuando la ventana perdió estado key (típico al pasar a WhatsApp/Chrome
  // sin cambiar el DOM antes). El listener `tauri://focus/blur` da la
  // verdad. Antes de tener el listener registrado (null), fallback al DOM.
  if (tauriWindowFocused !== null) return tauriWindowFocused
  try {
    return document.hasFocus()
  } catch {
    return !document.hidden
  }
}

async function ensureFocusListenersRegistered(): Promise<void> {
  if (focusListenersRegistered || !isTauri()) return
  focusListenersRegistered = true
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    const win = getCurrentWindow()
    tauriWindowFocused = await win.isFocused()
    await win.listen('tauri://focus', () => {
      tauriWindowFocused = true
    })
    await win.listen('tauri://blur', () => {
      tauriWindowFocused = false
    })
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[FAS-107 focus listener failed]', err)
    focusListenersRegistered = false
  }
}

function completionNotifyAllowed(viewingSession: boolean): boolean {
  return shouldNotifyCompletion(getStoredNotifyCompletion(), {
    windowFocused: isWindowFocused(),
    viewingSession
  })
}

async function ensureWebPermission(): Promise<
  NotificationPermission | 'unsupported'
> {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    return 'unsupported'
  }
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  if (webPermissionRequested) return Notification.permission
  webPermissionRequested = true
  try {
    return await Notification.requestPermission()
  } catch {
    return Notification.permission
  }
}

async function ensureNativePermission(): Promise<boolean> {
  try {
    const {
      isPermissionGranted,
      requestPermission
    } = await import('@tauri-apps/plugin-notification')
    if (await isPermissionGranted()) return true
    return (await requestPermission()) === 'granted'
  } catch {
    return false
  }
}

async function sendOsNotification(input: {
  title: string
  body?: string
  tag?: string
}): Promise<boolean> {
  if (isTauri()) {
    try {
      if (!(await ensureNativePermission())) return false
      // FAS-107 · Fase 1g · registrar handler del click (una sola vez)
      // que escucha el evento del delegate nativo custom para navegar
      // al pane exacto. También registramos los listeners de foco de
      // la ventana Tauri (fuente de verdad de macOS) para no depender
      // de `document.hasFocus()` que en WKWebView puede mentir.
      void ensureClickHandlerRegistered()
      void ensureFocusListenersRegistered()
      // FAS-107 · Fase 1g · comando Rust custom que mete el `tag` en
      // el `userInfo` de UNMutableNotificationContent — el delegate
      // Objective-C nuestro lo lee de vuelta al click y emite el
      // evento a JS. El plugin oficial descarta el tag silenciosamente
      // en desktop, por eso no lo usamos aquí.
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('sandwalk_notify', {
        title: input.title,
        body: input.body ?? null,
        tag: input.tag ?? null
      })
      return true
    } catch {
      // Fall through to Web Notification API.
    }
  }

  const permission = await ensureWebPermission()
  if (permission !== 'granted') return false
  try {
    const note = new Notification(input.title, {
      body: input.body,
      tag: input.tag
    })
    note.onclick = () => {
      window.focus()
      note.close()
    }
    return true
  } catch {
    return false
  }
}

/** Request native (or web) notification permission — used by settings UI. */
export async function requestNotificationPermission(): Promise<
  'granted' | 'denied' | 'default' | 'unsupported'
> {
  if (isTauri()) {
    try {
      const {
        isPermissionGranted,
        requestPermission
      } = await import('@tauri-apps/plugin-notification')
      if (await isPermissionGranted()) return 'granted'
      const result = await requestPermission()
      if (result === 'granted' || result === 'denied') return result
      return 'default'
    } catch {
      return 'unsupported'
    }
  }
  const permission = await ensureWebPermission()
  if (permission === 'unsupported') return 'unsupported'
  return permission
}

/** Current OS notification permission for settings UI. */
export async function getNotificationPermission(): Promise<
  'granted' | 'denied' | 'default' | 'unsupported'
> {
  if (isTauri()) {
    try {
      const { isPermissionGranted } = await import(
        '@tauri-apps/plugin-notification'
      )
      if (await isPermissionGranted()) return 'granted'
      if (typeof Notification !== 'undefined') {
        if (Notification.permission === 'denied') return 'denied'
        if (Notification.permission === 'granted') return 'granted'
      }
      return 'default'
    } catch {
      return 'unsupported'
    }
  }
  if (typeof Notification === 'undefined') return 'unsupported'
  return Notification.permission
}

export async function notifyBrowser(input: {
  title: string
  body?: string
  tag?: string
  /** When true, only notify if the document is hidden (default). */
  onlyWhenHidden?: boolean
}): Promise<boolean> {
  const onlyWhenHidden = input.onlyWhenHidden !== false
  if (onlyWhenHidden && typeof document !== 'undefined' && !document.hidden) {
    return false
  }
  return sendOsNotification(input)
}

export function notifyApprovalRequired(input: {
  sessionTitle?: string | null
  toolName?: string | null
  sessionId?: string | null
}): void {
  if (!getStoredNotifyApproval()) return

  const tool = (input.toolName || 'a tool').trim() || 'a tool'
  const title = 'Approval required'
  const session = (input.sessionTitle || '').trim()
  const body = session
    ? `${session}: ${tool} is waiting for your approval.`
    : `${tool} is waiting for your approval.`

  void sendOsNotification({
    title,
    body,
    tag: input.sessionId
      ? `sandwalk-approval-${input.sessionId}`
      : 'sandwalk-approval'
  })
}

export function notifyMissedCompletions(count: number): void {
  if (count <= 0) return
  if (getStoredNotifyCompletion() === 'never') return
  const n = count === 1 ? '1 chat finished' : `${count} chats finished`
  void sendOsNotification({
    title: 'Sandwalk',
    body: `${n} while you were away.`,
    tag: 'sandwalk-missed-complete'
  })
}

/**
 * FAS-107 · Fase 1c · notificación nativa cuando un comando de terminal
 * termina. Respeta el mismo `completionNotifyAllowed` que los agentes —
 * el modo `never/unfocused/always` aplica igual. El umbral (duración
 * mínima del comando) lo decide el caller antes de invocar esta función.
 */
export function notifyTerminalCommandFinished(input: {
  terminalTitle?: string | null
  terminalId?: string | null
  exitCode: number | null
  durationMs: number | null
  viewingTerminal?: boolean
}): void {
  if (!completionNotifyAllowed(Boolean(input.viewingTerminal))) return

  const label = (input.terminalTitle || 'Terminal').trim() || 'Terminal'
  const ok = input.exitCode === 0 || input.exitCode === null
  const title = ok ? 'Command finished' : 'Command failed'
  const durationLabel =
    typeof input.durationMs === 'number' && input.durationMs > 0
      ? ` (${formatDuration(input.durationMs)})`
      : ''
  const body = ok
    ? `${label}: command finished${durationLabel}.`
    : `${label}: command failed with exit ${input.exitCode}${durationLabel}.`

  void sendOsNotification({
    title,
    body,
    tag: input.terminalId
      ? `sandwalk-term-${input.terminalId}`
      : 'sandwalk-term'
  })
}

/**
 * FAS-107 · Fase 1c · notificación custom disparada por OSC 9 / OSC 777
 * en el stream del PTY (el usuario/script escribe `printf '\\e]777;notify;...'`).
 * A diferencia de `notifyTerminalCommandFinished`, siempre se envía
 * (no aplica umbral ni focus gate — es intención explícita del usuario).
 */
export function notifyTerminalCustom(input: {
  terminalTitle?: string | null
  terminalId?: string | null
  title?: string | null
  body?: string | null
}): void {
  const fallbackTitle = (input.terminalTitle || 'Terminal').trim() || 'Terminal'
  const title = (input.title || '').trim() || fallbackTitle
  const body = (input.body || '').trim() || undefined
  void sendOsNotification({
    title,
    body,
    tag: input.terminalId
      ? `sandwalk-term-notify-${input.terminalId}`
      : 'sandwalk-term-notify'
  })
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remSeconds = seconds % 60
  return remSeconds > 0 ? `${minutes}m ${remSeconds}s` : `${minutes}m`
}

export function notifyRunCompleted(input: {
  sessionTitle?: string | null
  sessionId?: string | null
  ok: boolean
  viewingSession?: boolean
}): void {
  if (!completionNotifyAllowed(Boolean(input.viewingSession))) return

  const session = (input.sessionTitle || '').trim()
  const title = input.ok ? 'Agent finished' : 'Agent failed'
  const body = session
    ? input.ok
      ? `${session} finished responding.`
      : `${session} failed.`
    : input.ok
      ? 'Your agent finished responding.'
      : 'Your agent run failed.'

  void sendOsNotification({
    title,
    body,
    tag: input.sessionId
      ? `sandwalk-complete-${input.sessionId}`
      : 'sandwalk-complete'
  })
}
