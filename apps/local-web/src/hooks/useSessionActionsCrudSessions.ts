import type { AgentEvent, AgentSession } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

import { formatSessionExportMarkdown } from '@/components/agents/transcript'
import {
  projectTabsKey,
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeRecentProjectIds
} from '@/lib/app-storage'
import {
  DRAFT_AGENT_SESSION_ID,
  type DraftSessionSeed,
  isDraftAgentSessionId
} from '@/lib/draft-agent'
import { clearSessionAttention } from '@/lib/session-attention'
import { downloadMarkdown, emptySessionChatState } from '@/lib/sessions'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type SessionCrudArgs = Pick<
  UseSessionActionsArgs,
  | 'client'
  | 'navigate'
  | 'activeProjectId'
  | 'tabsScopeKey'
  | 'sessionId'
  | 'sessionIdRef'
  | 'setSessions'
  | 'setOpenTabsByProject'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'patchOpenTabs'
  | 'setChatBySessionId'
  | 'composerLiveRef'
  | 'loadSessions'
  | 'loadProjects'
  | 'setError'
  | 'setFilesPanelCollapsed'
  | 'setTerminalOpen'
>

function applyProjectScope(
  projectId: string | null,
  setProjectScopeId: SessionCrudArgs['setProjectScopeId'],
  setRecentProjectIds: SessionCrudArgs['setRecentProjectIds']
) {
  if (!projectId) return
  setProjectScopeId(projectId)
  setRecentProjectIds(current => {
    const next = [projectId, ...current.filter(item => item !== projectId)].slice(
      0,
      10
    )
    writeRecentProjectIds(next)
    return next
  })
}

export function useSessionActionsCrudSessions({
  client,
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  sessionIdRef,
  setSessions,
  setOpenTabsByProject,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  patchOpenTabs,
  setChatBySessionId,
  composerLiveRef,
  loadSessions,
  loadProjects,
  setError,
  setFilesPanelCollapsed,
  setTerminalOpen
}: SessionCrudArgs) {
  const createSessionInFlightRef = useRef(false)
  const ensureInFlightRef = useRef<Promise<string | null> | null>(null)
  // Real session created under /agents/new (upload/sandbox) before navigate.
  // Kept separate from sessionIdRef so the draft route cannot stick to an old
  // session and mix uploads / history across chats.
  const materializedDraftSessionRef = useRef<string | null>(null)
  const [renameTarget, setRenameTarget] = useState<AgentSession | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentSession | null>(null)

  /** Open the local draft composer — no API session until first real action.
   * Pass `null` for All projects; omit to keep the current project scope.
   */
  const createSession = useCallback(
    async (projectId?: string | null, seed?: DraftSessionSeed) => {
      const id = projectId === undefined ? (activeProjectId ?? null) : projectId
      const composer = seed?.composer ?? ''
      if (id) {
        applyProjectScope(id, setProjectScopeId, setRecentProjectIds)
      } else {
        setProjectScopeId(null)
      }
      materializedDraftSessionRef.current = null
      // Match All-scope New Agent: draft only, no side panels forcing a session.
      setFilesPanelCollapsed(true)
      setTerminalOpen(false)
      setChatBySessionId(current => ({
        ...current,
        [DRAFT_AGENT_SESSION_ID]: {
          ...emptySessionChatState(),
          composer,
          composerSkills: seed?.composerSkills ?? [],
          messagesLoaded: true
        }
      }))
      composerLiveRef.current = composer
      sessionIdRef.current = DRAFT_AGENT_SESSION_ID
      // Always bump state so remounting /agents/new clears any silently
      // materialized draft workspace from a prior New Agent in this scope.
      navigate(`/agents/${DRAFT_AGENT_SESSION_ID}`, {
        state: { draftReset: Date.now() }
      })
    },
    [
      activeProjectId,
      composerLiveRef,
      navigate,
      sessionIdRef,
      setChatBySessionId,
      setFilesPanelCollapsed,
      setProjectScopeId,
      setRecentProjectIds,
      setTerminalOpen
    ]
  )

  /** Copy draft composer fields onto a real session id — never messages/tools. */
  const adoptDraftChat = useCallback(
    (realId: string) => {
      const liveComposer = composerLiveRef.current
      setChatBySessionId(current => {
        const draft = current[DRAFT_AGENT_SESSION_ID]
        const existing = current[realId] ?? emptySessionChatState()
        const next = { ...current }
        delete next[DRAFT_AGENT_SESSION_ID]
        next[realId] = {
          ...existing,
          messagesLoaded: true,
          composer: liveComposer || draft?.composer || '',
          composerSkills: draft?.composerSkills ?? [],
          composerFiles: draft?.composerFiles ?? []
        }
        return next
      })
      composerLiveRef.current = liveComposer
    },
    [composerLiveRef, setChatBySessionId]
  )

  const bindMaterializedSession = useCallback(
    (createdId: string, projectId: string | null, shouldNavigate: boolean) => {
      const scopeKey = projectTabsKey(projectId)
      if (shouldNavigate) {
        patchOpenTabs(scopeKey, current =>
          current.includes(createdId) ? current : [...current, createdId]
        )
        setLastSessionByScope(current => {
          const next = { ...current, [scopeKey]: createdId }
          writeLastSessionByScope(next)
          return next
        })
        adoptDraftChat(createdId)
        materializedDraftSessionRef.current = null
        sessionIdRef.current = createdId
        navigate(`/agents/${createdId}`, { replace: true })
        return
      }
      // Stay on /agents/new — composer keeps the draft chat key.
      materializedDraftSessionRef.current = createdId
      setChatBySessionId(current => {
        const draft =
          current[DRAFT_AGENT_SESSION_ID] ?? emptySessionChatState()
        return {
          ...current,
          [DRAFT_AGENT_SESSION_ID]: {
            ...draft,
            messagesLoaded: true
          }
        }
      })
    },
    [
      adoptDraftChat,
      navigate,
      patchOpenTabs,
      sessionIdRef,
      setChatBySessionId,
      setLastSessionByScope
    ]
  )

  /**
   * Materialize a real session if the UI is on the draft route (or has no id).
   * Returns the real session id, or null on failure.
   * Pass `{ navigate: false }` to create the session without leaving /agents/new
   * (keeps the composer mounted — used for uploads).
   */
  const ensureAgentSession = useCallback(
    async (
      projectId?: string | null,
      options?: { navigate?: boolean }
    ): Promise<string | null> => {
      const shouldNavigate = options?.navigate !== false

      // Already on a real session route — use it.
      if (sessionId && !isDraftAgentSessionId(sessionId)) {
        materializedDraftSessionRef.current = null
        return sessionId
      }

      const finishDraft = (id: string | null) => {
        if (
          !id ||
          !shouldNavigate ||
          !materializedDraftSessionRef.current ||
          materializedDraftSessionRef.current !== id
        ) {
          return id
        }
        bindMaterializedSession(
          id,
          projectId ?? activeProjectId ?? null,
          true
        )
        return id
      }

      // Draft route with a session created earlier in this draft (e.g. upload).
      const existingDraft = materializedDraftSessionRef.current
      if (existingDraft) {
        return finishDraft(existingDraft)
      }

      if (ensureInFlightRef.current) {
        return ensureInFlightRef.current.then(finishDraft)
      }

      const scopeId = projectId ?? activeProjectId ?? null
      const run = (async () => {
        if (createSessionInFlightRef.current) return null
        createSessionInFlightRef.current = true
        try {
          const created = await client.createSession({
            // Omit title so the server keeps title_source=pending and auto-titles
            // after the second agent response.
            projectId: scopeId || undefined,
            sandboxBackend: 'builtin'
          })
          applyProjectScope(scopeId, setProjectScopeId, setRecentProjectIds)
          setSessions(current => {
            if (current.some(item => item.id === created.id)) return current
            return [created, ...current]
          })
          // Always park as silent materialization first; navigate callers
          // finish via finishDraft so concurrent upload+send share one session.
          bindMaterializedSession(created.id, scopeId, false)
          await loadSessions()
          if (scopeId) await loadProjects()
          return created.id
        } catch (cause) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to create agent'
          )
          return null
        } finally {
          createSessionInFlightRef.current = false
        }
      })()

      ensureInFlightRef.current = run
      try {
        return await run.then(finishDraft)
      } finally {
        if (ensureInFlightRef.current === run) {
          ensureInFlightRef.current = null
        }
      }
    },
    [
      activeProjectId,
      bindMaterializedSession,
      client,
      loadProjects,
      loadSessions,
      sessionId,
      setError,
      setProjectScopeId,
      setRecentProjectIds,
      setSessions
    ]
  )

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.key.toLowerCase() !== 'n') return
      if (!(event.metaKey || event.ctrlKey)) return
      if (event.altKey || event.shiftKey) return
      event.preventDefault()
      void createSession(activeProjectId)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeProjectId, createSession])

  const updateSession = async (
    target: AgentSession,
    changes: Parameters<typeof client.updateSession>[1]
  ) => {
    // Optimistic patch so project-scope / tab filtering does not flicker while
    // the API + reload round-trip completes.
    setSessions(current =>
      current.map(item =>
        item.id === target.id
          ? {
              ...item,
              ...changes,
              updatedAt: new Date().toISOString()
            }
          : item
      )
    )
    try {
      await client.updateSession(target.id, changes)
      await Promise.all([loadSessions(), loadProjects()])
    } catch (cause) {
      setSessions(current =>
        current.map(item => (item.id === target.id ? target : item))
      )
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const selectSessionSpecialist = async (specialistId: string | null) => {
    const targetId = await ensureAgentSession()
    if (!targetId) return
    try {
      const updated = await client.updateSession(targetId, { specialistId })
      setSessions(current =>
        current.map(item => (item.id === updated.id ? updated : item))
      )
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const deleteSession = async (target: AgentSession) => {
    await client.deleteSession(target.id)
    clearSessionAttention(target.id)
    // Drop the row now. The list refresh that follows preserves chats it
    // hydrated for split groups, and it decides that from the cache.
    setSessions(current => current.filter(item => item.id !== target.id))
    let neighbor: string | null = null
    let scopeEmpty = false
    // FAS-107 X4.4-hotfix: SOLO quitar el target.id de cada scope.
    // Antes había un filtro por proyecto que asumía que TODOS los ids
    // en `openTabsByProject[scope]` eran chats — y descartaba cualquier
    // id que `sessions.find(...)` no reconociera. Eso barría todos los
    // `grp_*` (grupos) y `term_*` (terminales) del strip cuando borrabas
    // un chat estando dentro de un proyecto.
    //
    // El barrido por proyecto ya lo hace `useAppSessionEffects` de forma
    // correcta usando las 3 listas (sessions + terminals + tabGroups).
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        if (!ids.includes(target.id)) {
          next[key] = ids
          if (key === tabsScopeKey) {
            neighbor = ids.find(id => id !== target.id) || null
            scopeEmpty = ids.length === 0
          }
          continue
        }
        const filtered = ids.filter(id => id !== target.id)
        changed = true
        if (key === tabsScopeKey) {
          neighbor = filtered[0] || null
          scopeEmpty = filtered.length === 0
        }
        if (filtered.length > 0) next[key] = filtered
      }
      if (!changed) return current
      writeOpenTabsByProject(next)
      return next
    })
    if (scopeEmpty) {
      setLastSessionByScope(current => {
        if (!(tabsScopeKey in current)) return current
        const next = { ...current }
        delete next[tabsScopeKey]
        writeLastSessionByScope(next)
        return next
      })
    }
    setChatBySessionId(current => {
      if (!current[target.id]) return current
      const next = { ...current }
      delete next[target.id]
      return next
    })
    await loadSessions()
    if (target.id === sessionId) {
      navigate(
        neighbor
          ? `/agents/${neighbor}`
          : activeProjectId
            ? `/projects/${activeProjectId}`
            : '/'
      )
    }
  }

  const openRenameDialog = (target: AgentSession) => {
    setRenameTarget(target)
    setRenameValue(target.title || '')
  }

  const submitRename = async () => {
    const title = renameValue.trim()
    if (!renameTarget || !title) return
    await updateSession(renameTarget, { title })
    setRenameTarget(null)
    setRenameValue('')
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const target = deleteTarget
    setDeleteTarget(null)
    await deleteSession(target)
  }

  const exportTranscript = async (target: AgentSession) => {
    try {
      const [messages, events] = await Promise.all([
        client.listMessages(target.id),
        client.listEventHistory(target.id).catch(() => [] as AgentEvent[])
      ])
      const markdown = formatSessionExportMarkdown({
        title: target.title,
        messages,
        events
      })
      const filename = `${target.title
        .replace(/[^a-z0-9]+/gi, '-')
        .replace(/^-+|-+$/g, '')
        .toLowerCase() || 'session'}.md`
      await downloadMarkdown(filename, markdown)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to export session'
      )
    }
  }

  return {
    renameTarget,
    renameValue,
    setRenameTarget,
    setRenameValue,
    deleteTarget,
    setDeleteTarget,
    createSession,
    ensureAgentSession,
    updateSession,
    selectSessionSpecialist,
    deleteSession,
    openRenameDialog,
    submitRename,
    confirmDelete,
    exportTranscript
  }
}
