import { renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  SANDBOX_STREAM_SESSION_GONE,
  useSessionSandboxStream
} from './use-session-sandbox-stream'

class FakeSocket {
  static instances: FakeSocket[] = []
  onopen: (() => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(public url: string) {
    FakeSocket.instances.push(this)
  }
  close() {
    this.closed = true
  }
  /** Server accepted, then closed with `code` after `upMs` of being open. */
  openThenClose(code: number, upMs: number) {
    this.onopen?.()
    vi.advanceTimersByTime(upMs)
    this.onclose?.({ code })
  }
}

function mount(sessionId = 's1') {
  const client = {
    getSessionSandbox: vi.fn().mockRejectedValue(new Error('404')),
    sandboxStreamUrl: (id: string) => `ws://api/v1/sessions/${id}/sandbox/stream`
  }
  const setStatus = vi.fn()
  const setPhase = vi.fn()
  const hook = renderHook(() =>
    useSessionSandboxStream({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      client: client as any,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      health: { ok: true } as any,
      sessionId,
      sandboxActionSessionRef: { current: null },
      setSessionSandboxStatus: setStatus,
      setSessionSandboxPhase: setPhase
    })
  )
  // connect() is deferred with setTimeout(0)
  vi.advanceTimersByTime(0)
  return { hook, client, setStatus }
}

describe('useSessionSandboxStream reconnects', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeSocket.instances = []
    vi.stubGlobal('WebSocket', FakeSocket)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('stops reconnecting once the server says the session is gone (4404)', () => {
    const { hook, setStatus } = mount()
    expect(FakeSocket.instances).toHaveLength(1)

    FakeSocket.instances[0].openThenClose(SANDBOX_STREAM_SESSION_GONE, 10)
    vi.advanceTimersByTime(60_000)

    expect(FakeSocket.instances).toHaveLength(1)
    expect(setStatus).toHaveBeenLastCalledWith(null)
    hook.unmount()
  })

  it('keeps backing off when the stream opens but drops immediately', () => {
    const { hook } = mount()
    // Accepted-then-closed (e.g. 1011 while the API restarts) must not reset
    // the delay to 1 s on every open, or panes reconnect at 1 Hz forever.
    FakeSocket.instances[0].openThenClose(1011, 10)
    vi.advanceTimersByTime(3_999)
    expect(FakeSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(2)

    FakeSocket.instances[1].openThenClose(1011, 10)
    vi.advanceTimersByTime(7_999)
    expect(FakeSocket.instances).toHaveLength(2)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(3)
    hook.unmount()
  })

  it('resets the backoff after a stream that stayed healthy', () => {
    const { hook } = mount()
    FakeSocket.instances[0].openThenClose(1011, 10)
    vi.advanceTimersByTime(4_000)
    expect(FakeSocket.instances).toHaveLength(2)

    // This one stays up well past the healthy threshold before a normal close.
    FakeSocket.instances[1].openThenClose(1000, 5_000)
    vi.advanceTimersByTime(1_000)
    expect(FakeSocket.instances).toHaveLength(3)
    hook.unmount()
  })
})
