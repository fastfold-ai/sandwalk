import { beforeEach, describe, expect, it, vi } from 'vitest'

import { planCardFromPath, startPlanBuild } from './plan-build'
import { emptySessionChatState } from './sessions'

describe('planCardFromPath', () => {
  it('titles from slug path', () => {
    expect(planCardFromPath('plans/boltz_screening_campaign.md')).toEqual({
      path: 'plans/boltz_screening_campaign.md',
      title: 'boltz screening campaign',
      summary: ''
    })
  })
})

describe('startPlanBuild', () => {
  const client = {
    updateRuntimeSettings: vi.fn()
  }
  const setRuntimeSettings = vi.fn()
  const handleComposerSend = vi.fn()
  const patchChat = vi.fn(
    (
      _id: string,
      updater: (prev: ReturnType<typeof emptySessionChatState>) => unknown
    ) => {
      updater(emptySessionChatState())
    }
  )

  beforeEach(() => {
    vi.clearAllMocks()
    client.updateRuntimeSettings.mockResolvedValue({ planMode: false })
  })

  it('disables plan mode and sends a file-chip execute message', async () => {
    await startPlanBuild({
      sessionId: 's1',
      plan: planCardFromPath('plans/demo.md'),
      patchChat,
      client: client as never,
      setRuntimeSettings,
      handleComposerSend
    })

    expect(client.updateRuntimeSettings).toHaveBeenCalledWith({
      planMode: false
    })
    expect(setRuntimeSettings).toHaveBeenCalledWith({ planMode: false })
    expect(handleComposerSend).toHaveBeenCalledWith(
      expect.stringContaining('⟦@:plans/demo.md⟧')
    )
    expect(patchChat).toHaveBeenCalled()
  })

  it('still sends when planMode update fails', async () => {
    client.updateRuntimeSettings.mockRejectedValue(new Error('offline'))
    await startPlanBuild({
      sessionId: 's1',
      plan: planCardFromPath('plans/demo.md'),
      patchChat,
      client: client as never,
      setRuntimeSettings,
      handleComposerSend
    })
    expect(setRuntimeSettings).not.toHaveBeenCalled()
    expect(handleComposerSend).toHaveBeenCalled()
  })

  it('does not duplicate builtPlanPaths', async () => {
    const prev = {
      ...emptySessionChatState(),
      builtPlanPaths: ['plans/demo.md']
    }
    const patch = vi.fn(
      (
        _id: string,
        updater: (state: typeof prev) => typeof prev
      ) => {
        const next = updater(prev)
        expect(next.builtPlanPaths).toEqual(['plans/demo.md'])
        expect(next.activeBuildPlan?.path).toBe('plans/demo.md')
      }
    )
    await startPlanBuild({
      sessionId: 's1',
      plan: planCardFromPath('plans/demo.md'),
      patchChat: patch,
      client: client as never,
      setRuntimeSettings,
      handleComposerSend
    })
  })
})
