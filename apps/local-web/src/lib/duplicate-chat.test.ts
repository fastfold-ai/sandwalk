import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() }
}))

import { toast } from 'sonner'

import { duplicateChat } from './duplicate-chat'
import { useExternalAgentActions } from './external-agent-actions'

const source = { id: 's1', title: 'Binder design' } as AgentSession
const clone = { id: 's2', title: 'Binder design (copy)' } as AgentSession

describe('duplicateChat', () => {
  afterEach(() => {
    useExternalAgentActions.getState().bind(null)
    vi.clearAllMocks()
  })

  it('clones on the server, inserts the copy, opens it, and refreshes', async () => {
    const duplicateSession = vi.fn(async () => clone)
    const openItem = vi.fn()
    const upsertSession = vi.fn()
    const reloadSessions = vi.fn(async () => undefined)
    useExternalAgentActions.getState().bind({
      client: { duplicateSession } as unknown as LocalAgentClient,
      openItem,
      upsertSession,
      reloadSessions
    })
    const result = await duplicateChat(source)
    expect(result).toBe(clone)
    expect(duplicateSession).toHaveBeenCalledWith('s1')
    expect(upsertSession).toHaveBeenCalledWith(clone)
    expect(openItem).toHaveBeenCalledWith('s2')
    expect(reloadSessions).toHaveBeenCalled()
    expect(toast.success).toHaveBeenCalledWith('Duplicated as “Binder design (copy)”.')
  })

  it('reports a server error and does not navigate', async () => {
    const openItem = vi.fn()
    useExternalAgentActions.getState().bind({
      client: {
        duplicateSession: vi.fn(async () => {
          throw new Error('Session not found.')
        })
      } as unknown as LocalAgentClient,
      openItem,
      reloadSessions: vi.fn(async () => undefined)
    })
    expect(await duplicateChat(source)).toBeNull()
    expect(openItem).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalledWith('Session not found.')
  })

  it('does nothing useful when the server is not bound yet', async () => {
    expect(await duplicateChat(source)).toBeNull()
    expect(toast.error).toHaveBeenCalled()
  })
})
