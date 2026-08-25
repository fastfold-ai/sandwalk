import { startTransition } from 'react'

import {
  projectTabsKey,
  writeLastSessionByScope,
  writeRecentProjectIds
} from '@/lib/app-storage'
import { DRAFT_AGENT_SESSION_ID, sessionRoutePath } from '@/lib/draft-agent'
import { useTerminalsStore } from '@/lib/terminals-store'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type UseSessionActionsTabsArgs = Pick<
  UseSessionActionsArgs,
  | 'navigate'
  | 'activeProjectId'
  | 'tabsScopeKey'
  | 'sessionId'
  | 'stripSessionId'
  | 'sessions'
  | 'lastSessionByScope'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'openTabIds'
  | 'setOpenTabIds'
  | 'patchOpenTabs'
  | 'tabGroups'
>

export function useSessionActionsTabs({
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  stripSessionId,
  sessions,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  openTabIds,
  setOpenTabIds,
  patchOpenTabs,
  tabGroups
}: UseSessionActionsTabsArgs) {
  const closeSessionTab = (id: string) => {
    const scopeProjectId = activeProjectId
    const tabIsInScope = (tabId: string) => {
      // Los `grp_xxx` no son sesiones; se conservan siempre en el filtro
      // por-scope (el filtrado real por proyecto de un grupo se hace más
      // arriba en el `buildSessionSidebarModel`).
      if (tabId.startsWith('grp_')) return true
      // FAS-107 X4.4-hotfix: los `term_*` viven en el store Zustand,
      // no en `sessions`. Sin este chequeo, cerrar cualquier tab dentro
      // de un proyecto barría TODOS los terminales del strip.
      if (tabId.startsWith('term_')) {
        const term = useTerminalsStore
          .getState()
          .terminals.find(t => t.id === tabId)
        if (!term) return false
        if (!scopeProjectId) return true
        return (term.projectId ?? null) === scopeProjectId
      }
      const item = sessions.find(session => session.id === tabId)
      if (!item) return false
      if (!scopeProjectId) return true
      return item.projectId === scopeProjectId
    }

    // Neighbor picking + effective-tab compare use `stripSessionId`
    // (the id shown in the strip). Using `sessionId` (which resolves to
    // the child chat when the strip shows a grp_) misfires: closing the
    // group tab thinks "you're not on this tab", skips the navigate,
    // and a downstream effect re-opens the group on next render.
    const activeTabId = stripSessionId ?? sessionId

    // Compute EVERYTHING off the render-time snapshot of `openTabIds`,
    // then commit the next value with a plain `setOpenTabIds(next)`.
    // A previous version tried a functional updater and stashed `index`
    // and `neighbor` in outer variables via side effects inside the
    // updater. React 18 batching combined with the sibling `setMenu`
    // and `navigate` calls sometimes skipped the "eager computation"
    // optimization, leaving `index` at its initial `-1` and tripping
    // the early return before `navigate` fired — the observable
    // "first click deselects, second click closes" behavior.
    const index = openTabIds.indexOf(id)
    if (index === -1) return
    const withoutClosed = openTabIds.filter(tabId => tabId !== id)
    const next = scopeProjectId
      ? withoutClosed.filter(tabIsInScope)
      : withoutClosed
    let neighbor: string | null = null
    if (id === activeTabId && next.length > 0) {
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

    setOpenTabIds(next)

    if (id !== activeTabId) return

    if (!neighbor) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const nextMap = { ...current }
        delete nextMap[tabsScopeKey]
        writeLastSessionByScope(nextMap)
        return nextMap
      })
      // Closing the last tab lands on the empty draft-chat state — the
      // canonical "no chat open" surface. Sending the user to Project
      // Home (`/projects/<id>`) whenever a scope was active surprised
      // them: the chat sidebar disappears and coming back to /agents
      // re-hydrates whatever chat happened to be in `lastSessionByScope`,
      // which reads as "the app opened a random chat". The draft route
      // preserves the active project scope without opening any real
      // conversation.
      navigate(`/agents/${DRAFT_AGENT_SESSION_ID}`)
      return
    }

    // X4.4-hotfix: usar `sessionRoutePath` para elegir `/terminals/:id`
    // vs `/agents/:id` según el prefijo del neighbor. Antes se navegaba
    // siempre a `/agents/${neighbor}` — cuando el neighbor era un
    // terminal, la ruta era inválida (X3 Fase 6a bloquea `term_*` en
    // `/agents/`) → el active nunca cambiaba al vecino y el terminal
    // parecía "no cerrarse" del strip.
    navigate(sessionRoutePath(neighbor))
  }

  const closeOtherSessionTabs = (keepId: string) => {
    // Pinning promises "sticky" for both groups AND chats. Preserve any
    // id whose pinned state is true — group or session — instead of
    // sweeping them away with the rest.
    const activeTabId = stripSessionId ?? sessionId
    const pinnedGroupIds = new Set(
      tabGroups.filter(g => g.pinned).map(g => g.id)
    )
    const pinnedChatIds = new Set(
      sessions
        .filter(s => s.organizeLabel === 'pinned')
        .map(s => s.id)
    )
    setOpenTabIds(current =>
      current.filter(
        id =>
          id === keepId ||
          pinnedGroupIds.has(id) ||
          pinnedChatIds.has(id)
      )
    )
    if (activeTabId !== keepId) navigate(sessionRoutePath(keepId))
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
    // Always land on Project Home when picking a project from the selector.
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
    navigate(`/projects/${projectId}`)
  }

  return {
    closeSessionTab,
    closeOtherSessionTabs,
    reorderSessionTabs,
    selectAllProjects,
    selectProjectScope
  }
}
