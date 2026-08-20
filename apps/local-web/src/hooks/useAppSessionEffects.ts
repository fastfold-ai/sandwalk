import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  AgentSkillDetail,
  IntegrationSummary,
  TerminalSession,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { type MutableRefObject,useEffect } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { fileChipToken } from '@/components/agents/composer-parts'
import {
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeProjectScopeId
} from '@/lib/app-storage'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { clearSessionAttention } from '@/lib/session-attention'

type UseAppSessionEffectsArgs = {
  setIntegrationValues: Dispatch<SetStateAction<Record<string, string>>>
  selectedIntegrationKey: string | null
  isIntegrations: boolean
  integrations: IntegrationSummary[]
  navigate: NavigateFunction
  sessionId: string | null
  sessions: AgentSession[]
  activeProjectId: string | null
  openSessionTab: (id: string, scopeKey?: string) => void
  setOpenTabsByProject: Dispatch<SetStateAction<Record<string, string[]>>>
  setLastSessionByScope: Dispatch<SetStateAction<Record<string, string>>>
  tabsScopeKey: string
  projectScopeId: string | null
  client: LocalAgentClient
  workspaceVersion: number
  /** When the route is a draft, list Files/@ mentions from this materialized session. */
  draftWorkspaceSessionId: string | null
  setWorkspaceFiles: Dispatch<SetStateAction<WorkspaceFile[]>>
  skillRouteName: string | null | undefined
  setSkillDetail: Dispatch<SetStateAction<AgentSkillDetail | null>>
  setError: Dispatch<SetStateAction<string | null>>
  pendingMentionRef: MutableRefObject<string | string[] | null>
  setComposer: Dispatch<SetStateAction<string>>
  setComposerFiles: Dispatch<SetStateAction<string[]>>
  /** Returns true if the chat lives inside a split-view group in this scope. */
  chatIsInsideAnyGroup?: (chatId: string) => boolean
  /**
   * Todos los grupos activos (union de todos los scopes) — el effect que
   * limpia `openTabsByProject` los consulta para no borrar los `grp_xxx`
   * como si fueran "chats desconocidos". Un grupo se conserva en la lista
   * si al menos uno de sus chats pertenece al proyecto activo.
   */
  tabGroups?: import('@sandwalk/agent-ui-core').SessionGroup[]
  /**
   * FAS-107 P1: todos los terminales conocidos. El cleanup de
   * `openTabsByProject` los usa como tercera fuente de verdad (además de
   * `sessions` y `tabGroups`) — sin esto, un `term_*` id en el strip se
   * caía al primer render porque no matcheaba ninguna sesión existente.
   */
  terminals?: TerminalSession[]
}

export function useAppSessionEffects({
  setIntegrationValues,
  selectedIntegrationKey,
  isIntegrations,
  integrations,
  navigate,
  sessionId,
  sessions,
  activeProjectId,
  openSessionTab,
  setOpenTabsByProject,
  setLastSessionByScope,
  tabsScopeKey,
  projectScopeId,
  client,
  workspaceVersion,
  draftWorkspaceSessionId,
  setWorkspaceFiles,
  skillRouteName,
  setSkillDetail,
  setError,
  pendingMentionRef,
  setComposer,
  setComposerFiles,
  chatIsInsideAnyGroup,
  tabGroups = [],
  terminals = []
}: UseAppSessionEffectsArgs) {
  useEffect(() => {
    setIntegrationValues({})
  }, [selectedIntegrationKey])

  useEffect(() => {
    if (!isIntegrations || !selectedIntegrationKey) return
    if (integrations.length === 0) return
    if (!integrations.some(item => item.key === selectedIntegrationKey)) {
      navigate('/dashboard/integrations', { replace: true })
    }
  }, [integrations, isIntegrations, navigate, selectedIntegrationKey])

  useEffect(() => {
    if (!sessionId || isDraftAgentSessionId(sessionId)) return
    const item = sessions.find(session => session.id === sessionId)
    // Keep project tab strips clean: only pin sessions that belong to the scope.
    if (activeProjectId && item && item.projectId !== activeProjectId) return
    // Chats que viven dentro de un grupo no se auto-abren como tabs sueltas:
    // el grupo ya está en la strip como pestaña virtual y agregarlos volvería
    // a duplicar el chat en el strip.
    if (chatIsInsideAnyGroup?.(sessionId)) {
      clearSessionAttention(sessionId)
      return
    }
    openSessionTab(sessionId)
    clearSessionAttention(sessionId)
  }, [activeProjectId, openSessionTab, sessionId, sessions, chatIsInsideAnyGroup])

  // Clear Dock badge for the open session when the window is focused again.
  useEffect(() => {
    if (!sessionId || isDraftAgentSessionId(sessionId)) return
    const onFocus = () => clearSessionAttention(sessionId)
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [sessionId])

  useEffect(() => {
    // Wait until sessions are loaded — otherwise every persisted tab looks
    // "unknown" and gets wiped on reload.
    if (!activeProjectId || sessions.length === 0) return
    setOpenTabsByProject(current => {
      const ids = current[activeProjectId]
      if (!ids || ids.length === 0) return current
      const filtered = ids.filter(id => {
        // Grupos: se conservan si al menos un chat interno pertenece al
        // proyecto activo. Antes este filtro borraba TODOS los `grp_xxx`
        // (no aparecen en `sessions`), y el chip del grupo desaparecía
        // de la strip después del primer click aunque el user lo tuviera
        // marcado como abierto.
        if (id.startsWith('grp_')) {
          const group = tabGroups.find(g => g.id === id)
          if (!group) return false
          return group.chatIds.some(chatId => {
            const chat = sessions.find(s => s.id === chatId)
            return Boolean(chat && chat.projectId === activeProjectId)
          })
        }
        // FAS-107 P1: terminales viven en su propio store (`terminals`),
        // no en `sessions`. Sin este chequeo un `term_*` id caería al
        // primer render porque `sessions.find(...)` devolvería undefined.
        if (id.startsWith('term_')) {
          const term = terminals.find(t => t.id === id)
          return Boolean(term && (term.projectId ?? null) === activeProjectId)
        }
        const item = sessions.find(session => session.id === id)
        return Boolean(item && item.projectId === activeProjectId)
      })
      if (filtered.length === ids.length) return current
      const next = { ...current }
      if (filtered.length > 0) next[activeProjectId] = filtered
      else delete next[activeProjectId]
      writeOpenTabsByProject(next)
      return next
    })
  }, [activeProjectId, sessions, tabGroups, terminals])

  useEffect(() => {
    if (!sessionId || isDraftAgentSessionId(sessionId)) return
    setLastSessionByScope(current => {
      if (current[tabsScopeKey] === sessionId) return current
      const next = { ...current, [tabsScopeKey]: sessionId }
      writeLastSessionByScope(next)
      return next
    })
  }, [sessionId, tabsScopeKey])

  useEffect(() => {
    writeProjectScopeId(projectScopeId)
  }, [projectScopeId])

  useEffect(() => {
    if (sessions.length === 0) return
    const existing = new Set(sessions.map(item => item.id))
    const validGroupIds = new Set(tabGroups.map(g => g.id))
    // FAS-107 P1: terminales son first-class; sus ids también son válidos
    // en `openTabsByProject`.
    const validTerminalIds = new Set(terminals.map(t => t.id))
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        // Un id se conserva si es un chat válido O un grp_ conocido O un
        // terminal. Antes este cleanup borraba TODOS los `grp_xxx` y los
        // `term_*` (ninguno vive en `sessions`).
        const filtered = ids.filter(
          id =>
            existing.has(id) ||
            validGroupIds.has(id) ||
            validTerminalIds.has(id)
        )
        if (filtered.length !== ids.length) changed = true
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    setLastSessionByScope(current => {
      let changed = false
      const next: Record<string, string> = {}
      for (const [key, id] of Object.entries(current)) {
        if (!existing.has(id)) {
          changed = true
          continue
        }
        next[key] = id
      }
      if (!changed) return current
      writeLastSessionByScope(next)
      return next
    })
  }, [sessions, tabGroups, terminals])

  useEffect(() => {
    const listId =
      sessionId && isDraftAgentSessionId(sessionId)
        ? draftWorkspaceSessionId
        : sessionId
    if (!listId) {
      setWorkspaceFiles([])
      return
    }
    // S1: si el id activo es un terminal, no hay filesystem que listar
    // (terminales viven en su propio endpoint). El request devolvería 404
    // y ensuciaría la consola.
    if (listId.startsWith('term_')) {
      setWorkspaceFiles([])
      return
    }
    let cancelled = false
    void client
      .listFiles(listId)
      .then(files => {
        if (!cancelled) setWorkspaceFiles(files)
      })
      .catch(() => {
        if (!cancelled) setWorkspaceFiles([])
      })
    return () => {
      cancelled = true
    }
  }, [client, draftWorkspaceSessionId, sessionId, workspaceVersion])

  useEffect(() => {
    const name = skillRouteName
    if (!name) {
      setSkillDetail(null)
      return
    }
    const controller = new AbortController()
    void client
      .getSkill(decodeURIComponent(name), controller.signal)
      .then(setSkillDetail)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load skill'
          )
        }
      })
    return () => controller.abort()
  }, [client, skillRouteName])

  useEffect(() => {
    const pending = pendingMentionRef.current
    if (!sessionId || !pending) return
    pendingMentionRef.current = null
    const paths = Array.isArray(pending) ? pending : [pending]
    if (!paths.length) return
    setComposer(
      current => `${current}${paths.map(path => fileChipToken(path)).join('')}`
    )
    setComposerFiles(paths)
  }, [sessionId, setComposer, setComposerFiles, pendingMentionRef])
}
