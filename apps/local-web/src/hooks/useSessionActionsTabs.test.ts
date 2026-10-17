import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DRAFT_AGENT_SESSION_ID } from '@/lib/draft-agent'

import { useSessionActionsTabs } from './useSessionActionsTabs'

describe('useSessionActionsTabs', () => {
  it('closes the active tab, keeps pinned tabs, and switches project scope', () => {
    const navigate = vi.fn()
    const setOpenTabIds = vi.fn()
    const patchOpenTabs = vi.fn()
    const setProjectScopeId = vi.fn()
    const setRecentProjectIds = vi.fn((updater: (current: string[]) => string[]) =>
      updater(['old'])
    )
    const setLastSessionByScope = vi.fn(
      (updater: (current: Record<string, string>) => Record<string, string>) =>
        updater({ all: 'a' })
    )
    const { result } = renderHook(() =>
      useSessionActionsTabs({
        navigate,
        activeProjectId: null,
        tabsScopeKey: 'all',
        sessionId: 'a',
        stripSessionId: 'a',
        sessionsRef: {
          current: [
            { id: 'a', projectId: null, organizeLabel: null },
            { id: 'b', projectId: null, organizeLabel: 'pinned' }
          ] as never
        },
        setLastSessionByScope,
        setProjectScopeId,
        setRecentProjectIds,
        openTabIds: ['a', 'b'],
        setOpenTabIds,
        patchOpenTabs,
        tabGroupsRef: { current: [{ id: 'grp_1', pinned: true }] as never }
      })
    )
    act(() => result.current.closeSessionTab('missing'))
    expect(navigate).not.toHaveBeenCalled()
    act(() => result.current.closeSessionTab('a'))
    expect(setOpenTabIds).toHaveBeenCalledWith(['b'])
    expect(navigate).toHaveBeenCalledWith('/agents/b')
    act(() => result.current.closeOtherSessionTabs('a'))
    expect(navigate).not.toHaveBeenCalledWith('/agents/a')
    act(() => result.current.reorderSessionTabs(['b', 'a']))
    expect(setOpenTabIds).toHaveBeenCalledWith(['b', 'a'])
    act(() => result.current.selectProjectScope('p1'))
    expect(navigate).toHaveBeenCalledWith('/projects/p1')
    act(() => result.current.selectAllProjects())
    expect(setProjectScopeId).toHaveBeenCalledWith(null)
    act(() => result.current.closeSessionTab(DRAFT_AGENT_SESSION_ID))
  })
})
