/** Best-effort browser notifications for agent HITL / background alerts. */

let permissionRequested = false

async function ensurePermission(): Promise<NotificationPermission | 'unsupported'> {
  if (typeof window === 'undefined' || typeof Notification === 'undefined') {
    return 'unsupported'
  }
  if (Notification.permission === 'granted') return 'granted'
  if (Notification.permission === 'denied') return 'denied'
  if (permissionRequested) return Notification.permission
  permissionRequested = true
  try {
    return await Notification.requestPermission()
  } catch {
    return Notification.permission
  }
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
  const permission = await ensurePermission()
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

export function notifyApprovalRequired(input: {
  sessionTitle?: string | null
  toolName?: string | null
  sessionId?: string | null
}): void {
  const tool = (input.toolName || 'a tool').trim() || 'a tool'
  const title = 'Approval required'
  const session = (input.sessionTitle || '').trim()
  const body = session
    ? `${session}: ${tool} is waiting for your approval.`
    : `${tool} is waiting for your approval.`
  void notifyBrowser({
    title,
    body,
    tag: input.sessionId
      ? `sandwalk-approval-${input.sessionId}`
      : 'sandwalk-approval',
    // Always notify for approvals — user may be looking at another chat tab.
    onlyWhenHidden: false
  })
}
