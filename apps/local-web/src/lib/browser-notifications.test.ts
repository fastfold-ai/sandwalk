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
  notifyTerminalCommandFinished,
  notifyTerminalCustom,
  requestNotificationPermission
} from './browser-notifications'

const tauri = vi.hoisted(() => ({
  granted: vi.fn(async () => true),
  request: vi.fn(async () => 'granted' as const),
  invoke: vi.fn(async () => undefined),
  listen: vi.fn(async () => () => undefined)
}))

vi.mock('@tauri-apps/plugin-notification', () => ({
  isPermissionGranted: () => tauri.granted(),
  requestPermission: () => tauri.request()
}))

vi.mock('@tauri-apps/api/core', () => ({
  invoke: (...args: unknown[]) => tauri.invoke(...args)
}))

vi.mock('@tauri-apps/api/event', () => ({
  listen: (...args: unknown[]) => tauri.listen(...args)
}))

vi.mock('@tauri-apps/api/window', () => ({
  getCurrentWindow: () => ({
    isFocused: async () => false,
    listen: async () => () => undefined
  })
}))
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

  it('notifies a finished terminal command and a custom banner', async () => {
    notifyTerminalCommandFinished({
      terminalTitle: 'Build',
      terminalId: 'term_1',
      exitCode: 0,
      durationMs: 1500
    })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Command finished',
          body: 'Build: command finished (2s).',
          tag: 'sandwalk-term-term_1'
        })
      )
    })
    notify.mockReset()
    notifyTerminalCommandFinished({
      exitCode: 2,
      durationMs: 90_000,
      viewingTerminal: false
    })
    await vi.waitFor(() => {
      expect(notify.mock.calls[0]?.[0].body).toContain('exit 2')
      expect(notify.mock.calls[0]?.[0].body).toContain('1m 30s')
    })
    notify.mockReset()
    notifyTerminalCustom({
      terminalId: 'term_2',
      title: 'Done',
      body: 'tests passed'
    })
    await vi.waitFor(() => {
      expect(notify).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Done',
          tag: 'sandwalk-term-notify-term_2'
        })
      )
    })
  })

  it('sends a native notification and opens the clicked item', async () => {
    isTauri.mockReturnValue(true)
    tauri.granted.mockResolvedValue(true)
    const { openItem } = await import('./item-opener')
    const opener = vi.fn()
    const { setItemOpener } = await import('./item-opener')
    setItemOpener(opener)
    await expect(
      notifyBrowser({ title: 'Native', tag: 'sandwalk-complete-chat-9', onlyWhenHidden: false })
    ).resolves.toBe(true)
    expect(tauri.invoke).toHaveBeenCalled()
    const handler = tauri.listen.mock.calls[0]?.[1] as (event: { payload: string }) => void
    handler({ payload: 'sandwalk-complete-chat-9' })
    expect(opener).toHaveBeenCalledWith('chat-9')
    handler({ payload: 'nope' })
    expect(opener).toHaveBeenCalledTimes(1)
    void openItem
    setItemOpener(null)
    await expect(requestNotificationPermission()).resolves.toBe('granted')
    await expect(getNotificationPermission()).resolves.toBe('granted')
  })
})
