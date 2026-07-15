import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, WorkspaceFile } from '@sandwalk/agent-ui-core'
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  ARTIFACT_LIMIT,
  INDEX_SESSION_LIMIT,
  matchesQuery,
  SESSION_LIMIT,
  type IndexedArtifact,
  type SearchScope,
  uniqueSessionsByTitle
} from './global-search-utils'

export function useGlobalSearchState({
  open,
  onOpenChange,
  client,
  sessions,
  currentSessionId,
  currentSessionTitle,
  workspaceFiles
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  client: LocalAgentClient
  sessions: AgentSession[]
  currentSessionId: string | null
  currentSessionTitle?: string | null
  workspaceFiles: WorkspaceFile[]
}) {
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<SearchScope>('all')
  const [indexedArtifacts, setIndexedArtifacts] = useState<IndexedArtifact[]>(
    []
  )
  const [indexing, setIndexing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setScope('all')
      return
    }
    const timer = window.setTimeout(() => inputRef.current?.focus(), 20)
    return () => window.clearTimeout(timer)
  }, [open])

  useEffect(() => {
    if (!open) return
    const controller = new AbortController()
    setIndexing(true)

    const currentFiles: IndexedArtifact[] = workspaceFiles
      .filter(file => file.type === 'file')
      .map(file => ({
        path: file.path,
        name: file.name,
        sessionId: currentSessionId || '',
        sessionTitle: currentSessionTitle || 'Current session',
        mtime: file.mtime
      }))
      .filter(item => item.sessionId)

    setIndexedArtifacts(currentFiles)

    void (async () => {
      const otherSessions = sessions
        .filter(session => session.id !== currentSessionId)
        .slice(0, INDEX_SESSION_LIMIT)

      const batches = await Promise.all(
        otherSessions.map(async session => {
          try {
            const files = await client.listFiles(session.id, controller.signal)
            return files
              .filter(file => file.type === 'file')
              .map(file => ({
                path: file.path,
                name: file.name,
                sessionId: session.id,
                sessionTitle: session.title,
                mtime: file.mtime
              }))
          } catch {
            return [] as IndexedArtifact[]
          }
        })
      )

      if (controller.signal.aborted) return

      const byKey = new Map<string, IndexedArtifact>()
      for (const item of [...currentFiles, ...batches.flat()]) {
        byKey.set(`${item.sessionId}:${item.path}`, item)
      }
      const merged = [...byKey.values()].sort((a, b) => {
        const aTime = a.mtime ? new Date(a.mtime).getTime() : 0
        const bTime = b.mtime ? new Date(b.mtime).getTime() : 0
        return bTime - aTime
      })
      setIndexedArtifacts(merged)
      setIndexing(false)
    })()

    return () => {
      controller.abort()
    }
  }, [
    client,
    currentSessionId,
    currentSessionTitle,
    open,
    sessions,
    workspaceFiles
  ])

  const filteredArtifacts = useMemo(() => {
    const needle = query.trim()
    return indexedArtifacts
      .filter(
        item =>
          matchesQuery(item.name, needle) || matchesQuery(item.path, needle)
      )
      .slice(0, ARTIFACT_LIMIT)
  }, [indexedArtifacts, query])

  const filteredSessions = useMemo(() => {
    const needle = query.trim()
    return uniqueSessionsByTitle(sessions)
      .filter(session => matchesQuery(session.title, needle))
      .slice(0, SESSION_LIMIT)
  }, [query, sessions])

  const showArtifacts = scope === 'all' || scope === 'artifacts'
  const showSessions = scope === 'all' || scope === 'sessions'
  const showCommands = scope === 'all'

  const applyScopeFromKey = (next: SearchScope) => {
    setScope(next)
    setQuery('')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const clearScope = () => {
    setScope('all')
    window.setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleQueryChange = (value: string) => {
    if (scope === 'all') {
      if (value === '@' || value.startsWith('@')) {
        setScope('artifacts')
        setQuery(value.slice(1))
        return
      }
      if (value === '#' || value.startsWith('#')) {
        setScope('sessions')
        setQuery(value.slice(1))
        return
      }
    }
    setQuery(value)
  }

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (
      (event.key === 'Backspace' || event.key === 'Delete') &&
      !query &&
      scope !== 'all'
    ) {
      event.preventDefault()
      clearScope()
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      onOpenChange(false)
    }
  }

  const close = () => onOpenChange(false)

  return {
    query,
    scope,
    indexing,
    inputRef,
    filteredArtifacts,
    filteredSessions,
    showArtifacts,
    showSessions,
    showCommands,
    applyScopeFromKey,
    clearScope,
    handleQueryChange,
    handleInputKeyDown,
    close
  }
}
