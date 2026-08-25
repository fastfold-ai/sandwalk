import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const toastError = vi.fn()

vi.mock('sonner', () => ({
  toast: { error: (...args: unknown[]) => toastError(...args) }
}))

import { useCapySession } from './useCapySession'

function session(id = 'capy-1') {
  return { id, title: 'Capy', source: 'capy' }
}

describe('useCapySession', () => {
  beforeEach(() => {
    toastError.mockReset()
  })

  it('waits for the in-flight session before sending', async () => {
    let resolveSession: (value: ReturnType<typeof session>) => void = () =>
      undefined
    const getCapySession = vi.fn(
      () =>
        new Promise<ReturnType<typeof session>>(resolve => {
          resolveSession = resolve
        })
    )
    const sendMessage = vi.fn().mockResolvedValue({ runId: 'r1' })
    const client = {
      getCapySession,
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage,
      interrupt: vi.fn(),
      resetCapySession: vi.fn()
    }
    const { result } = renderHook(() =>
      useCapySession({ client: client as never, enabled: true })
    )

    let sent: Promise<void> = Promise.resolve()
    act(() => {
      sent = result.current.send('Hi')
    })
    expect(getCapySession).toHaveBeenCalledTimes(1)
    resolveSession(session())
    await act(async () => {
      await sent
    })
    expect(sendMessage).toHaveBeenCalledWith('capy-1', 'Hi')
    expect(result.current.chat.messages.at(-1)?.content).toBe('Hi')
    expect(result.current.chat.composer).toBe('')
  })

  it('toasts when the session cannot be created', async () => {
    const client = {
      getCapySession: vi.fn().mockRejectedValue(new Error('Capy unavailable')),
      listMessages: vi.fn(),
      sendMessage: vi.fn(),
      interrupt: vi.fn(),
      resetCapySession: vi.fn()
    }
    const { result } = renderHook(() =>
      useCapySession({ client: client as never, enabled: true })
    )
    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith('Capy unavailable')
    })
    await act(async () => {
      await result.current.send('Hi')
    })
    expect(client.sendMessage).not.toHaveBeenCalled()
  })

  it('keeps a draft typed before the session hydrates', async () => {
    let resolveSession: (value: ReturnType<typeof session>) => void = () =>
      undefined
    const client = {
      getCapySession: vi.fn(
        () =>
          new Promise<ReturnType<typeof session>>(resolve => {
            resolveSession = resolve
          })
      ),
      listMessages: vi.fn().mockResolvedValue([]),
      sendMessage: vi.fn(),
      interrupt: vi.fn(),
      resetCapySession: vi.fn()
    }
    const { result } = renderHook(() =>
      useCapySession({ client: client as never, enabled: true })
    )
    act(() => {
      result.current.setChat(prev => ({ ...prev, composer: 'Hi' }))
    })
    resolveSession(session())
    await waitFor(() => {
      expect(result.current.chat.messagesLoaded).toBe(true)
    })
    expect(result.current.chat.composer).toBe('Hi')
  })
})
