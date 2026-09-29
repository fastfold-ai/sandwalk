import type { AgentSession, SessionGroup } from '@sandwalk/agent-ui-core'
import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useSessionActionsTabs } from './useSessionActionsTabs'

const session = (id: string, extra: Partial<AgentSession> = {}) =>
  ({ id, title: id, projectId: 'p1', status: 'idle', ...extra }) as AgentSession

const group = (id: string, pinned: boolean) =>
  ({ id, pinned, chatIds: [], activeChatId: null }) as unknown as SessionGroup

function setup(openTabIds: string[]) {
  const sessionsRef = { current: [session('s1'), session('s2')] }
  const tabGroupsRef = { current: [group('grp_a', false)] }
  const setOpenTabIds = vi.fn()
  const navigate = vi.fn()
  const hook = renderHook(() =>
    useSessionActionsTabs({
      navigate,
      activeProjectId: 'p1',
      tabsScopeKey: 'p1',
      sessionId: 's1',
      stripSessionId: 's1',
      sessionsRef,
      setLastSessionByScope: vi.fn(),
      setProjectScopeId: vi.fn(),
      setRecentProjectIds: vi.fn(),
      openTabIds,
      setOpenTabIds,
      patchOpenTabs: vi.fn(),
      tabGroupsRef
    })
  )
  return { hook, sessionsRef, tabGroupsRef, setOpenTabIds, navigate }
}

describe('useSessionActionsTabs (ref-fed sessions/groups)', () => {
  it('closeOtherSessionTabs keeps pinned chats and groups from the latest refs without a re-render', () => {
    const { hook, sessionsRef, tabGroupsRef, setOpenTabIds } = setup([
      's1',
      's2',
      'grp_a',
      'grp_b'
    ])
    // Mutate the refs after render — the handler must see these values.
    sessionsRef.current = [
      session('s1'),
      session('s2', { organizeLabel: 'pinned' } as Partial<AgentSession>)
    ]
    tabGroupsRef.current = [group('grp_a', false), group('grp_b', true)]

    hook.result.current.closeOtherSessionTabs('s1')

    expect(setOpenTabIds).toHaveBeenCalledTimes(1)
    const updater = setOpenTabIds.mock.calls[0][0] as (
      current: string[]
    ) => string[]
    expect(updater(['s1', 's2', 'grp_a', 'grp_b'])).toEqual(['s1', 's2', 'grp_b'])
  })

  it('closeSessionTab scopes the remaining tabs using the latest sessions ref', () => {
    const { hook, sessionsRef, setOpenTabIds, navigate } = setup(['s1', 's2', 's3'])
    // s3 belongs to another project → dropped from the p1 strip on close.
    sessionsRef.current = [
      session('s1'),
      session('s2'),
      session('s3', { projectId: 'other' })
    ]

    hook.result.current.closeSessionTab('s1')

    expect(setOpenTabIds).toHaveBeenCalledWith(['s2'])
    expect(navigate).toHaveBeenCalledWith('/agents/s2')
  })
})
