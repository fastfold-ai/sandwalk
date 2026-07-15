import { useCallback } from 'react'

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
  | 'openTabsByProject'
  | 'lastSessionByScope'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'setOpenTabIds'
>

export function useSessionActionsTabs({
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  sessions,
  openTabsByProject,
  lastSessionByScope,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  setOpenTabIds
}: UseSessionActionsTabsArgs) {
  const landingPathForScope = useCallback(
    (scopeId: string | null) => {
      const key = projectTabsKey(scopeId)
      const tabs = (openTabsByProject[key] || []).filter(id => {
        const item = sessions.find(session => session.id === id)
        if (!item) return false
        if (!scopeId) return true
        return item.projectId === scopeId
      })
      if (tabs.length === 0) {
        return scopeId ? `/projects/${scopeId}` : '/'
      }
      const last = lastSessionByScope[key]
      const target =
        last && tabs.includes(last) ? last : tabs[tabs.length - 1]
      return `/agents/${target}`
    },
    [lastSessionByScope, openTabsByProject, sessions]
  )

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

  const selectAllProjects = () => {
    setProjectScopeId(null)
    navigate(landingPathForScope(null))
  }

  const selectProjectScope = (projectId: string) => {
    setProjectScopeId(projectId)
    setRecentProjectIds(current => {
      const next = [
        projectId,
        ...current.filter(item => item !== projectId)
      ].slice(0, 10)
      writeRecentProjectIds(next)
      return next
    })
    navigate(landingPathForScope(projectId))
  }

  return {
    landingPathForScope,
    closeSessionTab,
    closeOtherSessionTabs,
    selectAllProjects,
    selectProjectScope
  }
}
