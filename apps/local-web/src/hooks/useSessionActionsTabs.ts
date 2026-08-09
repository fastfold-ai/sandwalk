import { startTransition } from 'react'

import {
  projectTabsKey,
  writeLastSessionByScope,
  writeRecentProjectIds
} from '@/lib/app-storage'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type UseSessionActionsTabsArgs = Pick<
  UseSessionActionsArgs,
  | 'navigate'
  | 'activeProjectId'
  | 'tabsScopeKey'
  | 'sessionId'
  | 'sessions'
  | 'lastSessionByScope'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'setOpenTabIds'
  | 'patchOpenTabs'
>

export function useSessionActionsTabs({
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  sessions,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  setOpenTabIds,
  patchOpenTabs
}: UseSessionActionsTabsArgs) {
  const closeSessionTab = (id: string) => {
    const scopeProjectId = activeProjectId
    const tabIsInScope = (tabId: string) => {
      const item = sessions.find(session => session.id === tabId)
      if (!item) return false
      if (!scopeProjectId) return true
      return item.projectId === scopeProjectId
    }

    let neighbor: string | null | undefined
    setOpenTabIds(current => {
      const index = current.indexOf(id)
      if (index === -1) return current
      const withoutClosed = current.filter(tabId => tabId !== id)
      const next = scopeProjectId
        ? withoutClosed.filter(tabIsInScope)
        : withoutClosed

      if (id === sessionId) {
        if (next.length === 0) {
          neighbor = null
        } else {
          const preferred = withoutClosed
            .slice(Math.min(index, withoutClosed.length))
            .concat(
              withoutClosed
                .slice(0, Math.min(index, withoutClosed.length))
                .reverse()
            )
            .find(tabId => next.includes(tabId))
          neighbor = preferred || next[next.length - 1] || null
        }
      }
      return next
    })

    if (neighbor === undefined) return

    if (!neighbor) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
      navigate(scopeProjectId ? `/projects/${scopeProjectId}` : '/')
      return
    }

    navigate(`/agents/${neighbor}`)
  }

  const closeOtherSessionTabs = (keepId: string) => {
    setOpenTabIds(current => current.filter(id => id === keepId))
    if (sessionId !== keepId) navigate(`/agents/${keepId}`)
  }

  const reorderSessionTabs = (orderedIds: string[]) => {
    setOpenTabIds(orderedIds)
  }

  const retainActiveTabInScope = (scopeId: string | null) => {
    // Keep the current chat in the destination scope's tab strip so switching
    // projects does not blank the tab bar / remount the main panel.
    if (!sessionId) return
    const scopeKey = projectTabsKey(scopeId)
    patchOpenTabs(scopeKey, current =>
      current.includes(sessionId) ? current : [...current, sessionId]
    )
  }

  const selectAllProjects = () => {
    // Scope filter only — do not navigate to a project landing page.
    retainActiveTabInScope(null)
    startTransition(() => {
      setProjectScopeId(null)
    })
  }

  const selectProjectScope = (projectId: string) => {
    // Scope filter only — do not open `/projects/:id` when picking a project.
    retainActiveTabInScope(projectId)
    setRecentProjectIds(current => {
      const next = [
        projectId,
        ...current.filter(item => item !== projectId)
      ].slice(0, 10)
      writeRecentProjectIds(next)
      return next
    })
    startTransition(() => {
      setProjectScopeId(projectId)
    })
  }

  return {
    closeSessionTab,
    closeOtherSessionTabs,
    reorderSessionTabs,
    selectAllProjects,
    selectProjectScope
  }
}
