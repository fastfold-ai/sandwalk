import type { AgentEvent, AgentSession } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

import { formatSessionExportMarkdown } from '@/components/agents/transcript'
import {
  projectTabsKey,
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeRecentProjectIds
} from '@/lib/app-storage'
import { downloadMarkdown } from '@/lib/sessions'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type SessionCrudArgs = Pick<
  UseSessionActionsArgs,
  | 'client'
  | 'navigate'
  | 'activeProjectId'
  | 'tabsScopeKey'
  | 'sessionId'
  | 'session'
  | 'sessions'
  | 'setSessions'
  | 'setOpenTabsByProject'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'patchOpenTabs'
  | 'patchChat'
  | 'setChatBySessionId'
  | 'loadSessions'
  | 'loadProjects'
  | 'setError'
>

export function useSessionActionsCrudSessions({
  client,
  navigate,
  activeProjectId,
  tabsScopeKey,
  sessionId,
  session,
  sessions,
  setSessions,
  setOpenTabsByProject,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  patchOpenTabs,
  patchChat,
  setChatBySessionId,
  loadSessions,
  loadProjects,
  setError
}: SessionCrudArgs) {
  const createSessionInFlightRef = useRef(false)
  const [renameTarget, setRenameTarget] = useState<AgentSession | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<AgentSession | null>(null)

  const createSession = useCallback(
    async (projectId?: string | null) => {
      if (createSessionInFlightRef.current) return
      createSessionInFlightRef.current = true
      try {
        const id = projectId ?? activeProjectId ?? null
        const scopeKey = projectTabsKey(id)
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
    updateSession,
    selectSessionSpecialist,
    deleteSession,
    openRenameDialog,
    submitRename,
    confirmDelete,
    exportTranscript
  }
}
