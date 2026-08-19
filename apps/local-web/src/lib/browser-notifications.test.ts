import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { isTauri } = vi.hoisted(() => ({
  isTauri: vi.fn(() => false)
}))

vi.mock('@/lib/desktop', () => ({ isTauri }))

import {
  getNotificationPermission,
  notifyApprovalRequired,
  notifyBrowser,
  notifyMissedCompletions,
  notifyRunCompleted,
  requestNotificationPermission
} from './browser-notifications'
import {
  applyNotifyApproval,
  applyNotifyCompletion
} from './notification-settings'

function installMemoryLocalStorage() {
  const store = new Map<string, string>()
  const memory: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return [...store.keys()][index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    }
  }
  vi.stubGlobal('localStorage', memory)
}

function stubNotification(
  permission: NotificationPermission,
  notify: ReturnType<typeof vi.fn>
) {
  vi.stubGlobal(
    'Notification',
    class FakeNotification {
      static permission = permission
      static requestPermission = vi.fn(async () => permission)
      onclick: (() => void) | null = null
      constructor(
        public title: string,
        public options?: { body?: string; tag?: string }
      ) {
        notify({ title, ...options })
      }
      close() {
        return undefined
      }
    }
  )
}

describe('browser-notifications', () => {
  const notify = vi.fn()

  beforeEach(() => {
    installMemoryLocalStorage()
    isTauri.mockReturnValue(false)
    notify.mockReset()
    stubNotification('granted', notify)
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => true
    })
    vi.spyOn(document, 'hasFocus').mockReturnValue(false)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('skips missed completions when count is zero or mode is never', () => {
    notifyMissedCompletions(0)
    expect(notify).not.toHaveBeenCalled()
    applyNotifyCompletion('never')
    notifyMissedCompletions(2)
    expect(notify).not.toHaveBeenCalled()
  })

  it('notifies missed completions while away', async () => {
    notifyMissedCompletions(1)
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Sandwalk',
          body: '1 chat finished while you were away.'
        })
      )
    })
    notify.mockReset()
    notifyMissedCompletions(3)
    await vi.waitFor(() => {
      expect(notify.mock.calls[0]?.[0].body).toContain('3 chats finished')
    })
  })

  it('notifies a finished run when the user is not in that chat', async () => {
    notifyRunCompleted({
      sessionTitle: 'Slack chat',
      sessionId: 's1',
      ok: true,
      viewingSession: false
    })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Agent finished',
          body: 'Slack chat finished responding.',
          tag: 'sandwalk-complete-s1'
        })
      )
    })
  })

  it('notifies untitled success and named failure', async () => {
    notifyRunCompleted({ ok: true, viewingSession: false })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Agent finished',
          body: 'Your agent finished responding.',
          tag: 'sandwalk-complete'
        })
      )
    })
    notify.mockReset()
    notifyRunCompleted({
      sessionTitle: 'Job',
      ok: false,
      viewingSession: false
    })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Agent failed',
          body: 'Job failed.'
        })
      )
    })
    notify.mockReset()
    notifyRunCompleted({ ok: false, viewingSession: false })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({ body: 'Your agent run failed.' })
      )
    })
  })

  it('skips completion when viewing that chat in a focused window', () => {
    vi.spyOn(document, 'hasFocus').mockReturnValue(true)
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => false
    })
    notifyRunCompleted({
      sessionTitle: 'Open',
      ok: true,
      viewingSession: true
    })
    expect(notify).not.toHaveBeenCalled()
  })

  it('notifies approval and skips when disabled', async () => {
    notifyApprovalRequired({
      sessionTitle: 'Chat',
      toolName: 'bash',
      sessionId: 's1'
    })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Approval required',
          body: 'Chat: bash is waiting for your approval.',
          tag: 'sandwalk-approval-s1'
        })
      )
    })
    notify.mockReset()
    applyNotifyApproval(false)
    notifyApprovalRequired({ toolName: 'bash' })
    expect(notify).not.toHaveBeenCalled()
  })

  it('notifyBrowser respects onlyWhenHidden', async () => {
    Object.defineProperty(document, 'hidden', {
      configurable: true,
      get: () => false
    })
    await expect(notifyBrowser({ title: 'Hi' })).resolves.toBe(false)
    await expect(
      notifyBrowser({ title: 'Hi', onlyWhenHidden: false })
    ).resolves.toBe(true)
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ title: 'Hi' }))
  })

  it('reads web notification permission', async () => {
    await expect(getNotificationPermission()).resolves.toBe('granted')
    await expect(requestNotificationPermission()).resolves.toBe('granted')
  })

  it('returns unsupported when Notification is missing', async () => {
    vi.stubGlobal('Notification', undefined)
    await expect(getNotificationPermission()).resolves.toBe('unsupported')
    await expect(requestNotificationPermission()).resolves.toBe('unsupported')
  })
})
