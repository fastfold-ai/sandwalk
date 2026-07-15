import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentEvent, AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction
} from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { formatSessionExportMarkdown } from '@/components/agents/transcript'
import {
  projectTabsKey,
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeRecentProjectIds
} from '@/lib/app-storage'
import type { SessionChatState } from '@/lib/sessions'

type UseSessionActionsArgs = {
  client: LocalAgentClient
  navigate: NavigateFunction
  activeProjectId: string | null
  tabsScopeKey: string
  sessionId: string | null
  session: AgentSession | null
  sessions: AgentSession[]
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
  activeProject: AgentProject | null
  openTabsByProject: Record<string, string[]>
  setOpenTabsByProject: Dispatch<SetStateAction<Record<string, string[]>>>
  lastSessionByScope: Record<string, string>
  setLastSessionByScope: Dispatch<SetStateAction<Record<string, string>>>
  setProjectScopeId: Dispatch<SetStateAction<string | null>>
  setRecentProjectIds: Dispatch<SetStateAction<string[]>>
  patchOpenTabs: (
    scopeKey: string,
    updater: (current: string[]) => string[]
  ) => void
  setOpenTabIds: (value: string[] | ((current: string[]) => string[])) => void
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
  loadSessions: () => Promise<void>
  loadProjects: () => Promise<void>
  setError: Dispatch<SetStateAction<string | null>>
  setCollapsedSidebarSections: Dispatch<
    SetStateAction<Record<string, boolean>>
  >
}

export function useSessionActions({
  client,
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  session,
  sessions,
  setSessions,
  activeProject,
  openTabsByProject,
  setOpenTabsByProject,
  lastSessionByScope,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  patchOpenTabs,
  setOpenTabIds,
  patchChat,
  setChatBySessionId,
  loadSessions,
  loadProjects,
  setError,
  setCollapsedSidebarSections
}: UseSessionActionsArgs) {
  const createSessionInFlightRef = useRef(false)
  const [renameTarget, setRenameTarget] = useState<AgentSession | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentSession | null>(null)
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(
    () => new Set()
  )
  const [selectionAnchorId, setSelectionAnchorId] = useState<string | null>(
    null
  )
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchDeletePending, setBatchDeletePending] = useState(false)

  const createSession = useCallback(
    async (projectId?: string | null) => {
      if (createSessionInFlightRef.current) return
      createSessionInFlightRef.current = true
      try {
        const id = projectId ?? activeProjectId ?? null
        const scopeKey = projectTabsKey(id)
        // New chats always start on Built-in. Modal starts only when the user
        // turns on the per-session Modal toggle in the composer.
        const created = await client.createSession({
          title: 'Untitled session',
          projectId: id || undefined,
          sandboxBackend: 'builtin'
        })
        if (id) {
          setProjectScopeId(id)
          setRecentProjectIds(current => {
            const next = [id, ...current.filter(item => item !== id)].slice(
              0,
              10
            )
            writeRecentProjectIds(next)
            return next
          })
        }
        patchOpenTabs(scopeKey, current =>
          current.includes(created.id) ? current : [...current, created.id]
        )
        // Skip chat skeleton flash — new sessions start empty.
        patchChat(created.id, {
          messages: [],
          messagesLoaded: true
        })
        setLastSessionByScope(current => {
          const next = { ...current, [scopeKey]: created.id }
          writeLastSessionByScope(next)
          return next
        })
        await loadSessions()
        if (id) await loadProjects()
        navigate(`/agents/${created.id}`)
      } catch (cause) {
        setError(
          cause instanceof Error ? cause.message : 'Unable to create agent'
        )
      } finally {
        createSessionInFlightRef.current = false
      }
    },
    [
      activeProjectId,
      client,
      loadProjects,
      loadSessions,
      navigate,
      patchChat,
      patchOpenTabs,
      setLastSessionByScope,
      setProjectScopeId,
      setRecentProjectIds,
      setError
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
      // Drop tabs that don't belong in this project scope (e.g. leftover global tabs).
      const next = scopeProjectId
        ? withoutClosed.filter(tabIsInScope)
        : withoutClosed

      if (id === sessionId) {
        if (next.length === 0) {
          neighbor = null
        } else {
          const preferred = withoutClosed
            .slice(Math.min(index, withoutClosed.length))
            .concat(withoutClosed.slice(0, Math.min(index, withoutClosed.length)).reverse())
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

  const updateSession = async (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => {
    try {
      await client.updateSession(target.id, changes)
      await Promise.all([loadSessions(), loadProjects()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const selectSessionSpecialist = async (specialistId: string | null) => {
    if (!session) return
    try {
      const updated = await client.updateSession(session.id, { specialistId })
      setSessions(current =>
        current.map(item => (item.id === updated.id ? updated : item))
      )
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update agent'
      )
    }
  }

  const createProject = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    try {
      const project = await client.createProject(input)
      await loadProjects()
      setProjectScopeId(project.id)
      setRecentProjectIds(current => {
        const next = [
          project.id,
          ...current.filter(item => item !== project.id)
        ].slice(0, 10)
        writeRecentProjectIds(next)
        return next
      })
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to create project'
      )
      throw cause
    }
  }

  const saveProjectSettings = async (input: {
    name: string
    description: string
    agentContext: string
  }) => {
    if (!activeProject) return
    try {
      await client.updateProject(activeProject.id, {
        name: input.name,
        description: input.description || null,
        agentContext: input.agentContext || null
      })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
      throw cause
    }
  }

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

  const togglePinProject = async (project: AgentProject) => {
    try {
      await client.updateProject(project.id, { pinned: !project.pinned })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
    }
  }

  const deleteProject = async (project: AgentProject) => {
    try {
      await client.deleteProject(project.id)
      setOpenTabsByProject(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeOpenTabsByProject(next)
        return next
      })
      setLastSessionByScope(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeLastSessionByScope(next)
        return next
      })
      if (activeProjectId === project.id) {
        setProjectScopeId(null)
        navigate('/')
      }
      await Promise.all([loadProjects(), loadSessions()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete project'
      )
    }
  }

  const deleteSession = async (target: AgentSession) => {
    await client.deleteSession(target.id)
    let neighbor: string | null = null
    let scopeEmpty = false
    const scopeProjectId = activeProjectId
    setOpenTabsByProject(current => {
      let changed = false
      const next: Record<string, string[]> = {}
      for (const [key, ids] of Object.entries(current)) {
        if (!ids.includes(target.id) && key !== tabsScopeKey) {
          next[key] = ids
          continue
        }
        const withoutTarget = ids.filter(id => id !== target.id)
        const filtered =
          key === tabsScopeKey && scopeProjectId
            ? withoutTarget.filter(id => {
                const item = sessions.find(session => session.id === id)
                return Boolean(item && item.projectId === scopeProjectId)
              })
            : withoutTarget
        if (filtered.length !== ids.length) changed = true
        if (key === tabsScopeKey) {
          neighbor = filtered[0] || null
          scopeEmpty = filtered.length === 0
        }
        if (filtered.length > 0) next[key] = filtered
        else if (ids.length > 0) changed = true
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
          : scopeProjectId
            ? `/projects/${scopeProjectId}`
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
    const [messages, events] = await Promise.all([
      client.listMessages(target.id),
      client.listEventHistory(target.id).catch(() => [] as AgentEvent[])
    ])
    const markdown = formatSessionExportMarkdown({
      title: target.title,
      messages,
      events
    })
    const url = URL.createObjectURL(
      new Blob([markdown], { type: 'text/markdown' })
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${target.title
      .replace(/[^a-z0-9]+/gi, '-')
      .toLowerCase()}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const clearSessionSelection = useCallback(() => {
    setSelectedSessionIds(new Set())
    setSelectionAnchorId(null)
  }, [])

  const selectedSessions = useMemo(
    () => sessions.filter(item => selectedSessionIds.has(item.id)),
    [sessions, selectedSessionIds]
  )

  useEffect(() => {
    setSelectedSessionIds(current => {
      if (current.size === 0) return current
      const valid = new Set(sessions.map(item => item.id))
      let changed = false
      const next = new Set<string>()
      for (const id of current) {
        if (valid.has(id)) next.add(id)
        else changed = true
      }
      return changed ? next : current
    })
  }, [sessions])

  useEffect(() => {
    if (selectedSessionIds.size === 0) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        clearSessionSelection()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [clearSessionSelection, selectedSessionIds.size])

  const selectSessionRange = (orderedIds: string[], targetId: string) => {
    const anchor = selectionAnchorId
    if (!anchor) {
      setSelectedSessionIds(new Set([targetId]))
      setSelectionAnchorId(targetId)
      return
    }
    const start = orderedIds.indexOf(anchor)
    const end = orderedIds.indexOf(targetId)
    if (start < 0 || end < 0) {
      setSelectedSessionIds(new Set([targetId]))
      setSelectionAnchorId(targetId)
      return
    }
    const [lo, hi] = start < end ? [start, end] : [end, start]
    setSelectedSessionIds(new Set(orderedIds.slice(lo, hi + 1)))
  }

  const toggleSessionSelected = (targetId: string) => {
    setSelectedSessionIds(current => {
      const next = new Set(current)
      if (next.has(targetId)) next.delete(targetId)
      else next.add(targetId)
      return next
    })
    setSelectionAnchorId(targetId)
  }

  const batchArchiveSelected = async () => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      await Promise.all(
        selectedSessions.map(item =>
          client.updateSession(item.id, { organizeLabel: 'archive' })
        )
      )
      setCollapsedSidebarSections(current => ({
        ...current,
        archive: false
      }))
      clearSessionSelection()
      await loadSessions()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to archive sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const batchMoveSelected = async (projectId: string | null) => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      await Promise.all(
        selectedSessions.map(item =>
          client.updateSession(item.id, { projectId })
        )
      )
      clearSessionSelection()
      await loadSessions()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to move sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const batchExportSelected = async () => {
    if (selectedSessions.length === 0 || batchBusy) return
    setBatchBusy(true)
    setError(null)
    try {
      for (const item of selectedSessions) {
        await exportTranscript(item)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to export sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  const confirmBatchDelete = async () => {
    if (selectedSessions.length === 0) return
    setBatchDeletePending(false)
    setBatchBusy(true)
    setError(null)
    const targets = [...selectedSessions]
    clearSessionSelection()
    try {
      for (const target of targets) {
        await deleteSession(target)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete sessions'
      )
    } finally {
      setBatchBusy(false)
    }
  }

  return {
    renameTarget,
    renameValue,
    setRenameTarget,
    setRenameValue,
    deleteTarget,
    setDeleteTarget,
    selectedSessionIds,
    setSelectionAnchorId,
    batchBusy,
    batchDeletePending,
    setBatchDeletePending,
    createSession,
    closeSessionTab,
    closeOtherSessionTabs,
    updateSession,
    selectSessionSpecialist,
    createProject,
    saveProjectSettings,
    selectAllProjects,
    selectProjectScope,
    togglePinProject,
    deleteProject,
    openRenameDialog,
    submitRename,
    confirmDelete,
    exportTranscript,
    clearSessionSelection,
    selectSessionRange,
    toggleSessionSelected,
    batchArchiveSelected,
    batchMoveSelected,
    batchExportSelected,
    confirmBatchDelete
  }
}
