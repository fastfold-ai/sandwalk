import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  WorkspaceFile,
  WorkspaceFileContent
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  groupArtifacts,
  isStructure,
  normalizeFileContent,
  readOpenFileTabs,
  type ViewMode,
  writeOpenFileTabs
} from '../workspace-utils'
import { useWorkspaceFileSave } from './use-workspace-file-save'

export type WorkspacePanelState = ReturnType<typeof useWorkspacePanelState>

const WORKSPACE_POLL_MS = 5000

export function useWorkspacePanelState({
  client,
  sessionId,
  workspaceVersion = 0,
  runActive = false,
  onFilesChange,
  onNewFiles
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion?: number
  /** When true, poll the artifacts list so files appear as the agent writes them. */
  runActive?: boolean
  onFilesChange?: (count: number) => void
  /** Called when new file paths appear since the last list (agent writes, uploads). */
  onNewFiles?: (files: WorkspaceFile[]) => void
}) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [tabs, setTabs] = useState<WorkspaceFileContent[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [reloading, setReloading] = useState(false)
  const draftRef = useRef(draft)
  const savingRef = useRef(false)
  const tabsRef = useRef(tabs)
  const activePathRef = useRef(activePath)
  draftRef.current = draft
  savingRef.current = saving
  tabsRef.current = tabs
  activePathRef.current = activePath
  const [pathDialog, setPathDialog] = useState<'file' | 'folder' | null>(null)
  const [pathValue, setPathValue] = useState('')
  const [pathBusy, setPathBusy] = useState(false)
  const [fileTabMenu, setFileTabMenu] = useState<{
    path: string
    x: number
    y: number
  } | null>(null)
  const [fileBrowserMenu, setFileBrowserMenu] = useState<{
    path: string
    x: number
    y: number
    type: 'file' | 'directory'
  } | null>(null)
  const [moveSourcePath, setMoveSourcePath] = useState<string | null>(null)
  const [moveBusy, setMoveBusy] = useState(false)
  const [renameDialogPath, setRenameDialogPath] = useState<string | null>(null)
  const [renameDialogValue, setRenameDialogValue] = useState('')
  const [renameDialogBusy, setRenameDialogBusy] = useState(false)
  const [renameFilePath, setRenameFilePath] = useState<string | null>(null)
  const [renameFileValue, setRenameFileValue] = useState('')
  const [renameFileBusy, setRenameFileBusy] = useState(false)
  const renameFileCancelRef = useRef(false)
  const renameFileIgnoreBlurRef = useRef(false)
  const renameFileBusyRef = useRef(false)
  const renameFilePathRef = useRef<string | null>(null)
  const renameFileValueRef = useRef('')
  const renameFileInputRef = useRef<HTMLInputElement | null>(null)
  const [deleteFilePath, setDeleteFilePath] = useState<string | null>(null)
  const [deleteFileBusy, setDeleteFileBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>(
    () => readOpenFileTabs(sessionId).viewMode ?? 'list'
  )
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(
    () => readOpenFileTabs(sessionId).expandedGroups || {}
  )
  const [expandedDirs, setExpandedDirs] = useState<Record<string, boolean>>(
    () => readOpenFileTabs(sessionId).expandedDirs || {}
  )
  const [modalOpen, setModalOpen] = useState(false)
  const [filesTabActive, setFilesTabActive] = useState(true)
  const [tabsReady, setTabsReady] = useState(false)
  const [editorDark, setEditorDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : true
  )
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const seenFilePathsRef = useRef<Set<string> | null>(null)
  /** Skip one tree persist after hydrating from storage for a session. */
  const skipTreePersistRef = useRef(true)
  const activeTab = tabs.find(tab => tab.path === activePath) || null
  const active = !filesTabActive ? activeTab : null
  const openingPath =
    !filesTabActive && activePath && !activeTab ? activePath : null

  renameFilePathRef.current = renameFilePath
  renameFileValueRef.current = renameFileValue
  renameFileBusyRef.current = renameFileBusy

  useEffect(() => {
    seenFilePathsRef.current = null
    skipTreePersistRef.current = true
    const persisted = readOpenFileTabs(sessionId)
    setViewMode(persisted.viewMode ?? 'list')
    setExpandedGroups(persisted.expandedGroups || {})
    setExpandedDirs(persisted.expandedDirs || {})
  }, [sessionId])

  useEffect(() => {
    const sync = () =>
      setEditorDark(document.documentElement.classList.contains('dark'))
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    })
    return () => observer.disconnect()
  }, [])

  const refresh = useCallback(async (options?: { silent?: boolean }) => {
    // S1: terminals no tienen filesystem propio (no son sesiones de chat).
    // Sin este guard el hook dispara `listFiles(term_...)` que 404 en el
    // backend y ensucia la consola con decenas de errores.
    if (sessionId.startsWith('term_')) return
    if (!options?.silent) setRefreshing(true)
    try {
      const next = await client.listFiles(sessionId)
      setFiles(next)
      const fileEntries = next.filter(file => file.type === 'file')
      onFilesChange?.(fileEntries.length)
      const paths = new Set(fileEntries.map(file => file.path))
      const previous = seenFilePathsRef.current
      if (previous) {
        const added = fileEntries.filter(file => !previous.has(file.path))
        if (added.length > 0) onNewFiles?.(added)
      }
      seenFilePathsRef.current = paths
    } finally {
      if (!options?.silent) setRefreshing(false)
    }
  }, [client, onFilesChange, onNewFiles, sessionId])

  /** Reload open tabs from disk, skipping the active tab when it has unsaved edits. */
  const softReloadOpenTabs = useCallback(async () => {
    const open = tabsRef.current
    if (open.length === 0) return
    const path = activePathRef.current
    const next: WorkspaceFileContent[] = []
    let changed = false
    for (const tab of open) {
      const isActive = tab.path === path
      if (
        isActive &&
        tab.encoding === 'text' &&
        !isStructure(tab.path) &&
        draftRef.current !== tab.content
      ) {
        next.push(tab)
        continue
      }
      try {
        const content = normalizeFileContent(
          await client.readFile(sessionId, tab.path)
        )
        if (
          content.content !== tab.content ||
          content.encoding !== tab.encoding
        ) {
          changed = true
          next.push(content)
          if (isActive && content.encoding === 'text') {
            setDraft(content.content)
          }
        } else {
          next.push(tab)
        }
      } catch {
        next.push(tab)
      }
    }
    if (!changed) return
    setTabs(next)
    tabsRef.current = next
  }, [client, sessionId])

  useEffect(() => {
    void refresh()
  }, [refresh, workspaceVersion])

  useEffect(() => {
    if (!runActive) return
    const timer = window.setInterval(() => {
      void (async () => {
        await refresh({ silent: true })
        await softReloadOpenTabs()
      })()
    }, WORKSPACE_POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh, runActive, softReloadOpenTabs])

  useEffect(() => {
    let cancelled = false
    setTabsReady(false)
    setTabs([])
    setActivePath(null)
    setDraft('')
    setFilesTabActive(true)

    const persisted = readOpenFileTabs(sessionId)
    void (async () => {
      if (persisted.paths.length === 0) {
        if (!cancelled) setTabsReady(true)
        return
      }
      const loaded: WorkspaceFileContent[] = []
      for (const path of persisted.paths) {
        try {
          const content = normalizeFileContent(
            await client.readFile(sessionId, path)
          )
          loaded.push(content)
        } catch {
          // Drop tabs for files that no longer exist.
        }
      }
      if (cancelled) return
      setTabs(loaded)
      if (loaded.length === 0) {
        setFilesTabActive(true)
        setActivePath(null)
        setDraft('')
      } else if (persisted.filesTabActive) {
        setFilesTabActive(true)
        setActivePath(persisted.activePath)
        setDraft('')
      } else {
        const restored =
          loaded.find(tab => tab.path === persisted.activePath) || loaded[0]
        setFilesTabActive(false)
        setActivePath(restored.path)
        setDraft(restored.encoding === 'text' ? restored.content : '')
      }
      setTabsReady(true)
    })()

    return () => {
      cancelled = true
    }
  }, [client, sessionId])

  useEffect(() => {
    if (!tabsReady) return
    const current = readOpenFileTabs(sessionId)
    writeOpenFileTabs(sessionId, {
      ...current,
      paths: tabs.map(tab => tab.path),
      activePath,
      filesTabActive,
      viewMode,
      expandedGroups,
      expandedDirs
    })
  }, [
    activePath,
    expandedDirs,
    expandedGroups,
    filesTabActive,
    sessionId,
    tabs,
    tabsReady,
    viewMode
  ])

  // Persist tree expand state even while file tabs are still restoring.
  useEffect(() => {
    if (skipTreePersistRef.current) {
      skipTreePersistRef.current = false
      return
    }
    const current = readOpenFileTabs(sessionId)
    writeOpenFileTabs(sessionId, {
      ...current,
      viewMode,
      expandedGroups,
      expandedDirs
    })
  }, [expandedDirs, expandedGroups, sessionId, viewMode])

  const artifactFiles = useMemo(
    () => files.filter(file => file.type === 'file'),
    [files]
  )
  const filteredEntries = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return files
    return files.filter(
      file =>
        file.name.toLowerCase().includes(needle) ||
        file.path.toLowerCase().includes(needle)
    )
  }, [files, query])
  const groups = useMemo(
    () => groupArtifacts(filteredEntries),
    [filteredEntries]
  )

  useEffect(() => {
    setExpandedGroups(current => {
      const next = { ...current }
      let changed = false
      for (const group of groups) {
        if (next[group.id] === undefined) {
          next[group.id] = true
          changed = true
        }
      }
      return changed ? next : current
    })
  }, [groups])

  const isDirty = Boolean(
    active &&
      active.encoding === 'text' &&
      !isStructure(active.path) &&
      draft !== active.content
  )

  const { flushActiveDraft, save } = useWorkspaceFileSave({
    client,
    sessionId,
    activePath,
    active,
    isDirty,
    draft,
    draftRef,
    savingRef,
    tabsRef,
    setTabs,
    setDraft,
    setStatus,
    setSaving,
    refresh
  })

  return {
    client,
    sessionId,
    files,
    tabs,
    setTabs,
    activePath,
    setActivePath,
    draft,
    setDraft,
    status,
    setStatus,
    saving,
    refreshing,
    reloading,
    setReloading,
    draftRef,
    tabsRef,
    pathDialog,
    setPathDialog,
    pathValue,
    setPathValue,
    pathBusy,
    setPathBusy,
    fileTabMenu,
    setFileTabMenu,
    fileBrowserMenu,
    setFileBrowserMenu,
    moveSourcePath,
    setMoveSourcePath,
    moveBusy,
    setMoveBusy,
    renameDialogPath,
    setRenameDialogPath,
    renameDialogValue,
    setRenameDialogValue,
    renameDialogBusy,
    setRenameDialogBusy,
    renameFilePath,
    setRenameFilePath,
    renameFileValue,
    setRenameFileValue,
    renameFileBusy,
    setRenameFileBusy,
    renameFileCancelRef,
    renameFileIgnoreBlurRef,
    renameFileBusyRef,
    renameFilePathRef,
    renameFileValueRef,
    renameFileInputRef,
    deleteFilePath,
    setDeleteFilePath,
    deleteFileBusy,
    setDeleteFileBusy,
    query,
    setQuery,
    viewMode,
    setViewMode,
    expandedGroups,
    setExpandedGroups,
    expandedDirs,
    setExpandedDirs,
    modalOpen,
    setModalOpen,
    filesTabActive,
    setFilesTabActive,
    editorDark,
    uploadRef,
    activeTab,
    active,
    openingPath,
    isDirty,
    artifactFiles,
    filteredFiles: filteredEntries,
    groups,
    refresh,
    save,
    flushActiveDraft
  }
}
