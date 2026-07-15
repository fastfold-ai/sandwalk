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

export function useWorkspacePanelState({
  client,
  sessionId,
  workspaceVersion = 0,
  onFilesChange
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion?: number
  onFilesChange?: (count: number) => void
}) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [tabs, setTabs] = useState<WorkspaceFileContent[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const draftRef = useRef(draft)
  const savingRef = useRef(false)
  const tabsRef = useRef(tabs)
  draftRef.current = draft
  savingRef.current = saving
  tabsRef.current = tabs
  const [pathDialog, setPathDialog] = useState<'file' | 'folder' | null>(null)
  const [pathValue, setPathValue] = useState('')
  const [pathBusy, setPathBusy] = useState(false)
  const [fileTabMenu, setFileTabMenu] = useState<{
    path: string
    x: number
    y: number
  } | null>(null)
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
    {}
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
  const activeTab = tabs.find(tab => tab.path === activePath) || null
  const active = !filesTabActive ? activeTab : null
  const openingPath =
    !filesTabActive && activePath && !activeTab ? activePath : null

  renameFilePathRef.current = renameFilePath
  renameFileValueRef.current = renameFileValue
  renameFileBusyRef.current = renameFileBusy

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

  const refresh = useCallback(async () => {
    const next = await client.listFiles(sessionId)
    setFiles(next)
    onFilesChange?.(next.filter(file => file.type === 'file').length)
  }, [client, onFilesChange, sessionId])

  useEffect(() => {
    void refresh()
  }, [refresh, workspaceVersion])

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
    writeOpenFileTabs(sessionId, {
      paths: tabs.map(tab => tab.path),
      activePath,
      filesTabActive,
      viewMode
    })
  }, [activePath, filesTabActive, sessionId, tabs, tabsReady, viewMode])

  useEffect(() => {
    const current = readOpenFileTabs(sessionId)
    writeOpenFileTabs(sessionId, { ...current, viewMode })
  }, [sessionId, viewMode])

  const artifactFiles = useMemo(
    () => files.filter(file => file.type === 'file'),
    [files]
  )
  const filteredFiles = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return artifactFiles
    return artifactFiles.filter(
      file =>
        file.name.toLowerCase().includes(needle) ||
        file.path.toLowerCase().includes(needle)
    )
  }, [artifactFiles, query])
  const groups = useMemo(() => groupArtifacts(filteredFiles), [filteredFiles])

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
    filteredFiles,
    groups,
    refresh,
    save,
    flushActiveDraft
  }
}
