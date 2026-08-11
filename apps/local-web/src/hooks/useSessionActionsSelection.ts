import type { AgentSession } from '@sandwalk/agent-ui-core'
import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from 'react'

import { clearSessionAttention } from '@/lib/session-attention'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type UseSessionActionsSelectionArgs = Pick<
  UseSessionActionsArgs,
  'client' | 'sessions' | 'loadSessions' | 'setError' | 'setCollapsedSidebarSections'
> & {
  deleteSession: (target: AgentSession) => Promise<void>
  exportTranscript: (target: AgentSession) => Promise<void>
}

export function useSessionActionsSelection({
  client,
  sessions,
  loadSessions,
  setError,
  setCollapsedSidebarSections,
  deleteSession,
  exportTranscript
}: UseSessionActionsSelectionArgs) {
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(
    () => new Set()
  )
  const [selectionAnchorId, setSelectionAnchorId] = useState<string | null>(
    null
  )
  const [batchBusy, setBatchBusy] = useState(false)
  const [batchDeletePending, setBatchDeletePending] = useState(false)

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

  const batchMarkReadSelected = () => {
    if (selectedSessions.length === 0) return
    for (const item of selectedSessions) {
      clearSessionAttention(item.id)
    }
    clearSessionSelection()
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
    selectedSessionIds,
    setSelectionAnchorId,
    batchBusy,
    batchDeletePending,
    setBatchDeletePending,
    clearSessionSelection,
    selectSessionRange,
    toggleSessionSelected,
    batchMarkReadSelected,
    batchArchiveSelected,
    batchMoveSelected,
    batchExportSelected,
    confirmBatchDelete
  }
}
