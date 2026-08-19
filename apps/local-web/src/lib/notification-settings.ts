/** User preferences for completion + permission (HITL) notifications. */

export type NotifyCompletionMode = 'never' | 'unfocused' | 'always'

const COMPLETION_STORAGE_KEY = 'sandwalk.notify-completion'
const APPROVAL_STORAGE_KEY = 'sandwalk.notify-approval'

export const NOTIFY_COMPLETION_CHANGE_EVENT = 'sandwalk:notify-completion-change'
export const NOTIFY_APPROVAL_CHANGE_EVENT = 'sandwalk:notify-approval-change'

export const NOTIFY_COMPLETION_OPTIONS: {
  id: NotifyCompletionMode
  label: string
}[] = [
  { id: 'never', label: 'Never' },
  { id: 'unfocused', label: "When you're not in that chat" },
  { id: 'always', label: 'Always' }
]

export function shouldNotifyCompletion(
  mode: NotifyCompletionMode,
  opts: { windowFocused: boolean; viewingSession: boolean }
): boolean {
  if (mode === 'never') return false
  if (mode === 'always') return true
  return !opts.viewingSession || !opts.windowFocused
}

export function getStoredNotifyCompletion(): NotifyCompletionMode {
  try {
    const value = localStorage.getItem(COMPLETION_STORAGE_KEY)
    if (value === 'never' || value === 'unfocused' || value === 'always') {
      return value
    }
  } catch {
    // ignore
  }
  return 'unfocused'
}

export function applyNotifyCompletion(mode: NotifyCompletionMode) {
  try {
    localStorage.setItem(COMPLETION_STORAGE_KEY, mode)
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<NotifyCompletionMode>(NOTIFY_COMPLETION_CHANGE_EVENT, {
      detail: mode
    })
  )
}

export function getStoredNotifyApproval(): boolean {
  try {
    const value = localStorage.getItem(APPROVAL_STORAGE_KEY)
    if (value === 'off' || value === '0' || value === 'false') return false
  } catch {
    // ignore
  }
  return true
}

export function applyNotifyApproval(enabled: boolean) {
  try {
    localStorage.setItem(APPROVAL_STORAGE_KEY, enabled ? 'on' : 'off')
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent<boolean>(NOTIFY_APPROVAL_CHANGE_EVENT, {
      detail: enabled
    })
  )
}
