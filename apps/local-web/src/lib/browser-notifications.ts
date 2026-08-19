/** Best-effort OS notifications for agent HITL / completion alerts. */

import { isTauri } from '@/lib/desktop'
import {
  getStoredNotifyApproval,
  getStoredNotifyCompletion,
  shouldNotifyCompletion
} from '@/lib/notification-settings'

let webPermissionRequested = false

function isWindowFocused(): boolean {
  if (typeof document === 'undefined') return true
  if (document.hidden) return false
  try {
    return document.hasFocus()
  } catch {
    return !document.hidden
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
      const { sendNotification } = await import(
        '@tauri-apps/plugin-notification'
      )
      sendNotification({
        title: input.title,
        body: input.body
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
