import { Icon } from '@iconify/react'
import Editor from '@monaco-editor/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  WorkspaceFile,
  WorkspaceFileContent
} from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  CircleX,
  Copy,
  Download,
  Eye,
  FilePlus,
  Folder,
  FolderPlus,
  LayoutGrid,
  List,
  Maximize2,
  MessageSquarePlus,
  MoreHorizontal,
  Network,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  Trash2,
  Upload,
  X
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

import { ArtifactGridThumb } from './ArtifactGridThumb'
import { StructureViewer } from './StructureViewer'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from './tab-context-menu'
import { TerminalPanel } from './TerminalPanel'

type ViewMode = 'list' | 'grid'

/** Idle delay after the last keystroke before autosaving Monaco drafts. */
const AUTOSAVE_DELAY_MS = 1500

type ArtifactGroup = {
  id: string
  title: string
  files: WorkspaceFile[]
}

type PersistedFileTabs = {
  paths: string[]
  activePath: string | null
  filesTabActive: boolean
  viewMode?: ViewMode
}

const OPEN_FILE_TABS_STORAGE_KEY = 'fastfold.open-file-tabs'

function readOpenFileTabs(sessionId: string): PersistedFileTabs {
  try {
    const raw = localStorage.getItem(OPEN_FILE_TABS_STORAGE_KEY)
    if (!raw) return { paths: [], activePath: null, filesTabActive: true }
    const parsed = JSON.parse(raw) as Record<string, PersistedFileTabs>
    const entry = parsed?.[sessionId]
    if (!entry || !Array.isArray(entry.paths)) {
      return { paths: [], activePath: null, filesTabActive: true }
    }
    return {
      paths: entry.paths.filter(
        (path): path is string => typeof path === 'string' && path.length > 0
      ),
      activePath:
        typeof entry.activePath === 'string' ? entry.activePath : null,
      filesTabActive: entry.filesTabActive !== false,
      viewMode:
        entry.viewMode === 'grid' || entry.viewMode === 'list'
          ? entry.viewMode
          : undefined
    }
  } catch {
    return { paths: [], activePath: null, filesTabActive: true }
  }
}

function writeOpenFileTabs(sessionId: string, state: PersistedFileTabs) {
  try {
    const raw = localStorage.getItem(OPEN_FILE_TABS_STORAGE_KEY)
    const parsed = raw
      ? (JSON.parse(raw) as Record<string, PersistedFileTabs>)
      : {}
    parsed[sessionId] = state
    localStorage.setItem(OPEN_FILE_TABS_STORAGE_KEY, JSON.stringify(parsed))
  } catch {
    // ignore storage failures
  }
}

function normalizeFileContent(
  content: WorkspaceFileContent
): WorkspaceFileContent {
  if (
    content.encoding === 'base64' &&
    (isStructure(content.path) || isTextLike(content.path))
  ) {
    try {
      return {
        ...content,
        content: atob(content.content),
        encoding: 'text'
      }
    } catch {
      return content
    }
  }
  return content
}

function groupArtifacts(files: WorkspaceFile[]): ArtifactGroup[] {
  const onlyFiles = files.filter(file => file.type === 'file')
  const buckets = new Map<string, WorkspaceFile[]>()

  for (const file of onlyFiles) {
    const parts = file.path.split('/').filter(Boolean)
    let key = 'Artifacts'
    if (parts[0]?.toLowerCase() === 'uploads') key = 'Your uploads'
    else if (parts[0]?.toLowerCase() === 'outputs') key = 'Generated outputs'
    else if (parts.length > 1) key = parts[0]
    const bucket = buckets.get(key) || []
    bucket.push(file)
    buckets.set(key, bucket)
  }

  const preferred = ['Your uploads', 'Generated outputs', 'Artifacts']
  const keys = [
    ...preferred.filter(key => buckets.has(key)),
    ...[...buckets.keys()].filter(key => !preferred.includes(key)).sort()
  ]
  return keys.map(title => ({
    id: title,
    title,
    files: (buckets.get(title) || []).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  }))
}

export function WorkspacePanel({
  client,
  sessionId,
  workspaceVersion = 0,
  openPathRequest = null,
  onOpenPathRequestHandled,
  onAddToChat,
  onFilesChange,
  onTogglePanel,
  terminalOpen = false,
  onCloseTerminal,
  onOpenTerminal
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion?: number
  /** When set, open this workspace path in a preview tab. */
  openPathRequest?: string | null
  onOpenPathRequestHandled?: () => void
  onAddToChat: (path: string) => void
  onFilesChange?: (count: number) => void
  onTogglePanel?: () => void
  terminalOpen?: boolean
  onCloseTerminal?: () => void
  onOpenTerminal?: () => void
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
  /** Keep terminal mounted after first open so toggle doesn't drop the PTY socket. */
  const [terminalMounted, setTerminalMounted] = useState(terminalOpen)
  const terminalPanelRef = useRef<ImperativePanelHandle>(null)
  /** When true, the dedicated Files tree tab is selected (not a file preview). */
  const [filesTabActive, setFilesTabActive] = useState(true)
  const [tabsReady, setTabsReady] = useState(false)
  const [editorDark, setEditorDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : true
  )
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const activeTab = tabs.find(tab => tab.path === activePath) || null
  /** Preview tab content — null while browsing the Files tree. */
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

  useEffect(() => {
    if (terminalOpen) setTerminalMounted(true)
  }, [terminalOpen])

  useEffect(() => {
    const panel = terminalPanelRef.current
    if (!panel || !terminalMounted) return
    if (terminalOpen) {
      if (panel.isCollapsed()) panel.expand(50)
    } else if (!panel.isCollapsed()) {
      panel.collapse()
    }
  }, [terminalOpen, terminalMounted])

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
        const activeTab =
          loaded.find(tab => tab.path === persisted.activePath) || loaded[0]
        setFilesTabActive(false)
        setActivePath(activeTab.path)
        setDraft(activeTab.encoding === 'text' ? activeTab.content : '')
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

  const saveFile = useCallback(
    async (
      path: string,
      content: string,
      baseVersion: string | null | undefined,
      opts?: { auto?: boolean }
    ) => {
      if (savingRef.current) return false
      savingRef.current = true
      setSaving(true)
      if (!opts?.auto) setStatus('Saving…')
      try {
        const result = await client.writeFile(sessionId, {
          path,
          content,
          baseVersion
        })
        if (!result.ok) {
          setTabs(current => {
            const next = current.map(tab =>
              tab.path === result.current.path ? result.current : tab
            )
            tabsRef.current = next
            return next
          })
          setDraft(result.current.content)
          setStatus('File changed on disk; latest version loaded.')
          return false
        }
        setTabs(current => {
          const next = current.map(tab =>
            tab.path === result.content.path ? result.content : tab
          )
          tabsRef.current = next
          return next
        })
        // Keep newer keystrokes that landed while the save was in flight.
        setDraft(current =>
          current === content ? result.content.content : current
        )
        setStatus('Saved')
        window.setTimeout(() => {
          setStatus(current => (current === 'Saved' ? null : current))
        }, 1500)
        void refresh()
        return true
      } catch (cause) {
        setStatus(cause instanceof Error ? cause.message : 'Save failed')
        return false
      } finally {
        savingRef.current = false
        setSaving(false)
      }
    },
    [client, refresh, sessionId]
  )

  const flushActiveDraft = useCallback(async () => {
    if (!activePath) return
    const tab = tabsRef.current.find(item => item.path === activePath)
    if (!tab || tab.encoding !== 'text' || isStructure(tab.path)) return
    const content = draftRef.current
    if (content === tab.content) return
    await saveFile(tab.path, content, tab.version, { auto: true })
  }, [activePath, saveFile])

  const save = useCallback(async () => {
    if (!activePath) return
    const tab = tabsRef.current.find(item => item.path === activePath)
    if (!tab || tab.encoding !== 'text' || isStructure(tab.path)) return
    const content = draftRef.current
    if (content === tab.content) {
      setStatus('Saved')
      window.setTimeout(() => {
        setStatus(current => (current === 'Saved' ? null : current))
      }, 1200)
      return
    }
    await saveFile(tab.path, content, tab.version)
  }, [activePath, saveFile])

  // Debounced autosave after idle keystrokes (same pattern as cloud Agent IDE).
  useEffect(() => {
    if (!isDirty || !active) return
    const path = active.path
    const version = active.version
    const timer = window.setTimeout(() => {
      void saveFile(path, draftRef.current, version, { auto: true })
    }, AUTOSAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [active, isDirty, draft, saveFile])

  useEffect(() => {
    if (!isDirty) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [isDirty])

  const openFile = async (file: WorkspaceFile) => {
    if (file.type !== 'file') return

    await flushActiveDraft()

    // Already loaded — switch to its tab immediately (no re-fetch).
    const existing = tabsRef.current.find(tab => tab.path === file.path)
    if (existing) {
      const sameFile = existing.path === activePath && !filesTabActive
      setActivePath(existing.path)
      setFilesTabActive(false)
      if (!sameFile) {
        setDraft(existing.encoding === 'text' ? existing.content : '')
      }
      setStatus(null)
      return
    }

    // Switch to the file tab right away; load content in the background.
    setActivePath(file.path)
    setFilesTabActive(false)
    setDraft('')
    setStatus(`Opening ${file.name}…`)
    try {
      const normalized = normalizeFileContent(
        await client.readFile(sessionId, file.path)
      )
      setTabs(current => [
        ...current.filter(
          tab => tab.path !== normalized.path && tab.path !== file.path
        ),
        normalized
      ])
      setActivePath(normalized.path)
      setDraft(normalized.encoding === 'text' ? normalized.content : '')
      setStatus(null)
    } catch (cause) {
      setFilesTabActive(true)
      setStatus(cause instanceof Error ? cause.message : 'Unable to open file')
    }
  }

  useEffect(() => {
    if (!openPathRequest) return
    let cancelled = false
    void (async () => {
      try {
        const list =
          files.length > 0 ? files : await client.listFiles(sessionId)
        if (cancelled) return
        const match =
          list.find(
            file => file.type === 'file' && file.path === openPathRequest
          ) ||
          list.find(
            file =>
              file.type === 'file' &&
              (file.name === openPathRequest ||
                file.path.endsWith(`/${openPathRequest}`))
          )
        if (match) await openFile(match)
        else {
          const normalized = normalizeFileContent(
            await client.readFile(sessionId, openPathRequest)
          )
          if (cancelled) return
          setTabs(current => [
            ...current.filter(tab => tab.path !== normalized.path),
            normalized
          ])
          setActivePath(normalized.path)
          setDraft(normalized.encoding === 'text' ? normalized.content : '')
          setFilesTabActive(false)
        }
      } catch (cause) {
        if (!cancelled) {
          setStatus(
            cause instanceof Error ? cause.message : 'Unable to open file'
          )
        }
      } finally {
        if (!cancelled) onOpenPathRequestHandled?.()
      }
    })()
    return () => {
      cancelled = true
    }
  }, [openPathRequest])

  const openPathDialog = (kind: 'file' | 'folder') => {
    setPathDialog(kind)
    setPathValue('')
  }

  const submitPathDialog = async () => {
    const path = pathValue.trim()
    if (!path || !pathDialog) return
    setPathBusy(true)
    try {
      if (pathDialog === 'file') {
        await client.writeFile(sessionId, { path, content: '' })
        await refresh()
        const file = (await client.listFiles(sessionId)).find(
          item => item.path === path
        )
        if (file) await openFile(file)
      } else {
        await client.createFolder(sessionId, path)
        await refresh()
      }
      setPathDialog(null)
      setPathValue('')
    } catch (cause) {
      setStatus(
        cause instanceof Error ? cause.message : 'Unable to create path'
      )
    } finally {
      setPathBusy(false)
    }
  }

  const closeTab = (path: string) => {
    void (async () => {
      if (path === activePath) await flushActiveDraft()
      const index = tabs.findIndex(tab => tab.path === path)
      const next = tabs.filter(tab => tab.path !== path)
      setTabs(next)
      if (activePath === path) {
        if (!filesTabActive) {
          const replacement = next[Math.max(0, index - 1)] || null
          if (replacement) {
            setActivePath(replacement.path)
            setDraft(
              replacement.encoding === 'text' ? replacement.content : ''
            )
          } else {
            setActivePath(null)
            setDraft('')
            setFilesTabActive(true)
          }
        } else if (!next.some(tab => tab.path === path)) {
          // Closed while browsing Files — clear highlight if nothing left.
          if (next.length === 0) setActivePath(null)
        }
      }
    })()
  }

  const closeOtherTabs = (keepPath: string) => {
    void (async () => {
      if (activePath !== keepPath) await flushActiveDraft()
      const keep = tabsRef.current.find(tab => tab.path === keepPath)
      if (!keep) return
      setTabs([keep])
      tabsRef.current = [keep]
      setFilesTabActive(false)
      setActivePath(keep.path)
      setDraft(keep.encoding === 'text' ? keep.content : '')
    })()
  }

  const downloadFileTab = (path: string) => {
    const name = path.split('/').at(-1) || path
    const anchor = document.createElement('a')
    anchor.href = client.downloadUrl(sessionId, path)
    anchor.download = name
    anchor.click()
  }

  const submitRenameFile = async () => {
    const previousPath = renameFilePathRef.current
    const nextName = renameFileValueRef.current.trim()
    if (!previousPath || !nextName || renameFileBusyRef.current) return
    if (nextName.includes('/') || nextName.includes('\\')) {
      setStatus('Enter a file name without path separators.')
      return
    }
    const slash = previousPath.lastIndexOf('/')
    const dir = slash >= 0 ? previousPath.slice(0, slash) : ''
    const targetPath = dir ? `${dir}/${nextName}` : nextName
    const previousName = previousPath.split('/').at(-1) || previousPath
    if (targetPath === previousPath || nextName === previousName) {
      setRenameFilePath(null)
      setRenameFileValue('')
      return
    }
    renameFileBusyRef.current = true
    setRenameFileBusy(true)
    setStatus(null)
    // Close the editor immediately; finish the move in the background.
    setTabs(current =>
      current.map(tab =>
        tab.path === previousPath ? { ...tab, path: targetPath } : tab
      )
    )
    if (activePath === previousPath) setActivePath(targetPath)
    setRenameFilePath(null)
    setRenameFileValue('')
    try {
      await client.moveFile(sessionId, previousPath, targetPath)
      await refresh()
      try {
        const content = await client.readFile(sessionId, targetPath)
        const normalized = normalizeFileContent(content)
        setTabs(current =>
          current.map(tab => (tab.path === targetPath ? normalized : tab))
        )
        if (activePath === targetPath || activePath === previousPath) {
          setActivePath(targetPath)
          setDraft(
            normalized.encoding === 'text' ? normalized.content : ''
          )
        }
      } catch {
        // Tab path already updated; content refresh can wait.
      }
    } catch (error) {
      setTabs(current =>
        current.map(tab =>
          tab.path === targetPath ? { ...tab, path: previousPath } : tab
        )
      )
      if (activePath === targetPath) setActivePath(previousPath)
      setStatus(
        error instanceof Error ? error.message : 'Failed to rename file'
      )
    } finally {
      renameFileBusyRef.current = false
      setRenameFileBusy(false)
    }
  }

  const beginRenameFile = (path: string) => {
    const name = path.split('/').at(-1) || path
    renameFileCancelRef.current = false
    renameFileIgnoreBlurRef.current = true
    const tab = tabs.find(item => item.path === path)
    if (tab) {
      setFilesTabActive(false)
      setActivePath(tab.path)
      setDraft(tab.encoding === 'text' ? tab.content : '')
    }
    setRenameFilePath(path)
    setRenameFileValue(name)
    requestAnimationFrame(() => {
      renameFileInputRef.current?.focus()
      renameFileInputRef.current?.select()
      window.setTimeout(() => {
        renameFileIgnoreBlurRef.current = false
      }, 150)
    })
  }

  const cancelRenameFile = () => {
    renameFileCancelRef.current = true
    setRenameFilePath(null)
    setRenameFileValue('')
  }

  const commitRenameFileFromBlur = () => {
    if (renameFileBusyRef.current || renameFileIgnoreBlurRef.current) return
    if (renameFileCancelRef.current) {
      renameFileCancelRef.current = false
      return
    }
    const path = renameFilePathRef.current
    const nextName = renameFileValueRef.current.trim()
    const currentName = path?.split('/').at(-1) || path
    if (nextName && currentName && nextName !== currentName) {
      void submitRenameFile()
    } else {
      setRenameFilePath(null)
      setRenameFileValue('')
    }
  }

  const submitDeleteFile = async () => {
    if (!deleteFilePath) return
    setDeleteFileBusy(true)
    setStatus(null)
    try {
      await client.deleteFile(sessionId, deleteFilePath)
      closeTab(deleteFilePath)
      setDeleteFilePath(null)
      await refresh()
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : 'Failed to delete file'
      )
    } finally {
      setDeleteFileBusy(false)
    }
  }

  const selectFilesTab = () => {
    void (async () => {
      await flushActiveDraft()
      setFilesTabActive(true)
    })()
  }

  const selectFileTab = (path: string) => {
    void (async () => {
      if (path !== activePath) await flushActiveDraft()
      const tab = tabsRef.current.find(item => item.path === path)
      if (!tab) return
      setFilesTabActive(false)
      setActivePath(tab.path)
      setDraft(tab.encoding === 'text' ? tab.content : '')
    })()
  }

  const downloadAll = () => {
    for (const file of artifactFiles) {
      const anchor = document.createElement('a')
      anchor.href = client.downloadUrl(sessionId, file.path)
      anchor.download = file.name
      anchor.click()
    }
  }

  const browser = (
    <ArtifactsBrowser
      client={client}
      sessionId={sessionId}
      groups={groups}
      totalCount={filteredFiles.length}
      query={query}
      viewMode={viewMode}
      expandedGroups={expandedGroups}
      activePath={activePath}
      empty={artifactFiles.length === 0}
      onQueryChange={setQuery}
      onViewModeChange={setViewMode}
      onToggleGroup={id =>
        setExpandedGroups(current => ({
          ...current,
          [id]: !(current[id] ?? true)
        }))
      }
      onOpenFile={file => void openFile(file)}
      onDownloadFile={path => {
        const anchor = document.createElement('a')
        anchor.href = client.downloadUrl(sessionId, path)
        anchor.download = path.split('/').at(-1) || path
        anchor.click()
      }}
      onDownloadAll={downloadAll}
      onUpload={() => uploadRef.current?.click()}
      onNewFile={() => openPathDialog('file')}
      onNewFolder={() => openPathDialog('folder')}
      onRefresh={() => void refresh()}
    />
  )

  const filesColumn = (
    <>
        <div className="flex h-10 shrink-0 items-center gap-1 px-1.5">
          <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch gap-0.5 overflow-x-auto">
            <div
              className={cn(
                'group relative my-auto flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5',
                filesTabActive
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
              )}
            >
              <button
                type="button"
                className="inline-flex items-center gap-1.5 text-xs font-medium"
                onClick={selectFilesTab}
              >
                <Folder className="size-3.5 shrink-0" />
                Files
              </button>
              {onTogglePanel ? (
                <button
                  type="button"
                  className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                  aria-label="Close files panel"
                  onClick={event => {
                    event.stopPropagation()
                    onTogglePanel()
                  }}
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </div>
            {tabs.map(tab => {
              const name = tab.path.split('/').at(-1) || tab.path
              const selected = !filesTabActive && activePath === tab.path
              const renaming = renameFilePath === tab.path
              return (
                <div
                  key={tab.path}
                  className={cn(
                    'group relative my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5',
                    selected || renaming
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                    renaming && 'max-w-[220px] pr-1.5'
                  )}
                  onContextMenu={event => {
                    if (renaming) return
                    event.preventDefault()
                    setFileTabMenu({
                      path: tab.path,
                      x: event.clientX,
                      y: event.clientY
                    })
                  }}
                >
                  {renaming ? (
                    <input
                      ref={renameFileInputRef}
                      className="bg-background text-foreground h-6 w-full min-w-[6rem] rounded border px-1.5 text-xs font-medium outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={renameFileValue}
                      onFocus={event => event.currentTarget.select()}
                      onChange={event => setRenameFileValue(event.target.value)}
                      onClick={event => event.stopPropagation()}
                      onKeyDown={event => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          event.stopPropagation()
                          renameFileIgnoreBlurRef.current = true
                          void submitRenameFile()
                        } else if (event.key === 'Escape') {
                          event.preventDefault()
                          event.stopPropagation()
                          cancelRenameFile()
                        }
                      }}
                      onBlur={() => commitRenameFileFromBlur()}
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        className="max-w-full truncate pr-0 text-left text-xs font-medium"
                        title={tab.path}
                        onClick={() => selectFileTab(tab.path)}
                        onDoubleClick={event => {
                          event.preventDefault()
                          beginRenameFile(tab.path)
                        }}
                      >
                        {name}
                      </button>
                      <button
                        type="button"
                        className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                        aria-label={`Close ${name}`}
                        onClick={event => {
                          event.stopPropagation()
                          closeTab(tab.path)
                        }}
                      >
                        <X className="size-3.5" />
                      </button>
                    </>
                  )}
                </div>
              )
            })}
            {openingPath &&
            !tabs.some(tab => tab.path === openingPath) ? (
              <div className="bg-muted text-foreground my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5">
                <span
                  className="max-w-full truncate text-xs font-medium"
                  title={openingPath}
                >
                  {openingPath.split('/').at(-1) || openingPath}
                </span>
              </div>
            ) : null}
          </div>
          <div className="ml-auto flex shrink-0 items-center">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              title="Open full screen"
              onClick={() => setModalOpen(true)}
            >
              <Maximize2 className="size-3.5" />
            </Button>
            {onTogglePanel ? (
              <Button
                variant="ghost"
                size="icon"
                className="size-7"
                title="Hide files panel"
                aria-label="Hide files panel"
                onClick={onTogglePanel}
              >
                <X className="size-3.5" />
              </Button>
            ) : null}
          </div>
          <input
            ref={uploadRef}
            hidden
            type="file"
            multiple
            onChange={event => {
              const uploads = Array.from(event.target.files || [])
              void Promise.all(
                uploads.map(file =>
                  client.uploadFile(sessionId, file, 'uploads')
                )
              ).then(refresh)
              event.target.value = ''
            }}
          />
        </div>

        {filesTabActive ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">{browser}</div>
            {status ? (
              <div className="text-muted-foreground border-t px-2 py-1 text-[10px]">
                {status}
              </div>
            ) : null}
          </div>
        ) : active ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <FileActionsHeader
              path={active.path}
              canSave={active.encoding === 'text' && !isStructure(active.path)}
              dirty={isDirty}
              saving={saving}
              downloadUrl={client.downloadUrl(sessionId, active.path)}
              onAddToChat={() => onAddToChat(active.path)}
              onSave={() => void save()}
              onExpand={() => setModalOpen(true)}
              onClose={() => closeTab(active.path)}
            />
            <div className="min-h-0 flex-1">
              <FilePreview
                active={active}
                draft={draft}
                editorDark={editorDark}
                onDraftChange={setDraft}
                onSave={() => void save()}
              />
            </div>
            {status ? (
              <div className="text-muted-foreground border-t px-2 py-1 text-[10px]">
                {status}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            <FileActionsHeader
              path={openingPath || activePath || 'file'}
              canSave={false}
              dirty={false}
              saving={false}
              downloadUrl={
                openingPath || activePath
                  ? client.downloadUrl(sessionId, openingPath || activePath!)
                  : '#'
              }
              onAddToChat={() => {
                if (activePath) onAddToChat(activePath)
              }}
              onSave={() => undefined}
              onExpand={() => setModalOpen(true)}
              onClose={() => {
                if (activePath) closeTab(activePath)
                else setFilesTabActive(true)
              }}
            />
            <div className="grid min-h-0 flex-1 place-items-center px-6" aria-busy="true">
              <div className="w-full max-w-md space-y-3">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
                <Skeleton className="h-3 w-2/3" />
              </div>
            </div>
          </div>
        )}
    </>
  )

  return (
    <>
      <aside className="bg-card flex h-full w-full min-w-0 flex-col">
        {terminalMounted ? (
          <ResizablePanelGroup
            direction="vertical"
            autoSaveId="fastfold.files-terminal-panels"
            className="h-full"
          >
            <ResizablePanel
              id="files"
              order={1}
              defaultSize={50}
              minSize={20}
              className="min-h-0"
            >
              <div className="flex h-full min-h-0 flex-col overflow-hidden">
                {filesColumn}
              </div>
            </ResizablePanel>
            <ResizableHandle
              className={cn(
                'bg-transparent after:bg-transparent',
                !terminalOpen && 'pointer-events-none opacity-0'
              )}
            />
            <ResizablePanel
              id="terminal"
              order={2}
              ref={terminalPanelRef}
              collapsible
              collapsedSize={0}
              defaultSize={terminalOpen ? 50 : 0}
              minSize={15}
              className="min-h-0"
              onCollapse={() => onCloseTerminal?.()}
              onExpand={() => onOpenTerminal?.()}
            >
              <TerminalPanel
                client={client}
                sessionId={sessionId}
                visible={terminalOpen}
                onClose={onCloseTerminal}
              />
            </ResizablePanel>
          </ResizablePanelGroup>
        ) : (
          filesColumn
        )}
      </aside>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent
          hideCloseButton
          className="flex h-[min(90vh,52rem)] w-[min(96vw,72rem)] max-w-none flex-col gap-0 overflow-hidden p-0"
        >
          <div className="flex h-12 shrink-0 items-center justify-between border-b px-4">
            <div className="flex items-center gap-2">
              <Folder className="text-muted-foreground size-4" />
              <DialogTitle className="text-sm font-medium">
                Artifacts
              </DialogTitle>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                title="Upload"
                onClick={() => uploadRef.current?.click()}
              >
                <Upload className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                title="Refresh"
                onClick={() => void refresh()}
              >
                <RefreshCw className="size-4" />
              </Button>
              <DialogClose asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8"
                  title="Close"
                  aria-label="Close"
                >
                  <X className="size-4" />
                </Button>
              </DialogClose>
            </div>
          </div>
          <div className="flex min-h-0 flex-1">
            <div className="flex w-[22rem] shrink-0 flex-col border-r">
              {browser}
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              {activeTab ? (
                <>
                  <div className="flex h-10 shrink-0 items-center justify-between border-b px-3">
                    <span className="text-muted-foreground truncate text-xs">
                      {activeTab.path}
                    </span>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-[11px]"
                        onClick={() => onAddToChat(activeTab.path)}
                      >
                        Add to chat
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        asChild
                      >
                        <a
                          href={client.downloadUrl(sessionId, activeTab.path)}
                          download
                        >
                          <Download className="size-3.5" />
                        </a>
                      </Button>
                    </div>
                  </div>
                  <div className="min-h-0 flex-1">
                    <FilePreview
                      active={activeTab}
                      draft={draft}
                      editorDark={editorDark}
                      onDraftChange={setDraft}
                      onSave={
                        activeTab.encoding === 'text' &&
                        !isStructure(activeTab.path)
                          ? () => void save()
                          : undefined
                      }
                    />
                  </div>
                </>
              ) : openingPath || activePath ? (
                <div className="grid flex-1 place-items-center px-6" aria-busy="true">
                  <div className="w-full max-w-md space-y-3">
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-5/6" />
                    <Skeleton className="h-3 w-2/3" />
                  </div>
                </div>
              ) : (
                <div className="text-muted-foreground/70 grid flex-1 place-items-center text-xs">
                  Select a file to preview
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(pathDialog)}
        onOpenChange={open => {
          if (!open) {
            setPathDialog(null)
            setPathValue('')
          }
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>
              {pathDialog === 'folder' ? 'New folder' : 'New file'}
            </DialogTitle>
            <DialogDescription>
              {pathDialog === 'folder'
                ? 'Enter a relative folder path in this session workspace.'
                : 'Enter a relative file path in this session workspace.'}
            </DialogDescription>
          </DialogHeader>
          <Input
            value={pathValue}
            onChange={event => setPathValue(event.target.value)}
            placeholder={
              pathDialog === 'folder' ? 'results/run-1' : 'notes/summary.md'
            }
            autoFocus
            onKeyDown={event => {
              if (event.key === 'Enter' && pathValue.trim() && !pathBusy) {
                event.preventDefault()
                void submitPathDialog()
              }
            }}
          />
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setPathDialog(null)
                setPathValue('')
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!pathValue.trim() || pathBusy}
              onClick={() => void submitPathDialog()}
            >
              {pathBusy ? 'Creating…' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(deleteFilePath)}
        onOpenChange={open => {
          if (!open) setDeleteFilePath(null)
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete file</DialogTitle>
            <DialogDescription>
              Permanently delete{' '}
              <span className="text-foreground font-medium">
                {deleteFilePath?.split('/').at(-1) || deleteFilePath}
              </span>{' '}
              from this session workspace? This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeleteFilePath(null)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={deleteFileBusy}
              onClick={() => void submitDeleteFile()}
            >
              {deleteFileBusy ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {fileTabMenu && tabs.some(tab => tab.path === fileTabMenu.path) ? (
        <TabContextMenuShell
          x={fileTabMenu.x}
          y={fileTabMenu.y}
          onClose={() => setFileTabMenu(null)}
        >
          <TabContextItem
            icon={<X className="size-3.5" />}
            label="Close"
            onClick={() => {
              const path = fileTabMenu.path
              setFileTabMenu(null)
              closeTab(path)
            }}
          />
          <TabContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close others"
            disabled={tabs.length <= 1}
            onClick={() => {
              const path = fileTabMenu.path
              setFileTabMenu(null)
              closeOtherTabs(path)
            }}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename…"
            onClick={() => {
              const path = fileTabMenu.path
              setFileTabMenu(null)
              beginRenameFile(path)
            }}
          />
          <TabContextItem
            icon={<Download className="size-3.5" />}
            label="Download"
            onClick={() => {
              const path = fileTabMenu.path
              setFileTabMenu(null)
              downloadFileTab(path)
            }}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Delete"
            destructive
            onClick={() => {
              const path = fileTabMenu.path
              setFileTabMenu(null)
              setDeleteFilePath(path)
            }}
          />
        </TabContextMenuShell>
      ) : null}
    </>
  )
}

function ArtifactsBrowser({
  client,
  sessionId,
  groups,
  totalCount,
  query,
  viewMode,
  expandedGroups,
  activePath,
  empty,
  onQueryChange,
  onViewModeChange,
  onToggleGroup,
  onOpenFile,
  onDownloadFile,
  onDownloadAll,
  onUpload,
  onNewFile,
  onNewFolder,
  onRefresh
}: {
  client: LocalAgentClient
  sessionId: string
  groups: ArtifactGroup[]
  totalCount: number
  query: string
  viewMode: ViewMode
  expandedGroups: Record<string, boolean>
  activePath: string | null
  empty: boolean
  onQueryChange: (value: string) => void
  onViewModeChange: (mode: ViewMode) => void
  onToggleGroup: (id: string) => void
  onOpenFile: (file: WorkspaceFile) => void
  onDownloadFile: (path: string) => void
  onDownloadAll: () => void
  onUpload: () => void
  onNewFile: () => void
  onNewFolder: () => void
  onRefresh: () => void
}) {
  const [scope, setScope] = useState<string>('all')
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (scope === 'all') return
    if (!groups.some(group => group.id === scope)) setScope('all')
  }, [groups, scope])

  const visibleGroups = useMemo(() => {
    if (scope === 'all') return groups
    return groups.filter(group => group.id === scope)
  }, [groups, scope])

  const visibleCount = useMemo(
    () => visibleGroups.reduce((sum, group) => sum + group.files.length, 0),
    [visibleGroups]
  )

  const scopeLabel =
    scope === 'all'
      ? 'Artifacts'
      : groups.find(group => group.id === scope)?.title || 'Artifacts'

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 px-2 py-2">
        <Popover open={menuOpen} onOpenChange={setMenuOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="hover:bg-muted inline-flex h-8 max-w-full items-center gap-1.5 rounded-md px-2 text-xs font-medium"
            >
              <Network className="size-3.5 shrink-0" />
              <span className="truncate">{scopeLabel}</span>
              <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-64 p-1.5">
            <div className="text-muted-foreground px-2 py-1 text-[10px] font-medium uppercase tracking-wide">
              Artifacts
            </div>
            <button
              type="button"
              className={cn(
                'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                scope === 'all' && 'bg-muted'
              )}
              onClick={() => {
                setScope('all')
                setMenuOpen(false)
              }}
            >
              <Network className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">All artifacts</span>
              {scope === 'all' ? (
                <Check className="size-3.5 shrink-0 text-sky-500" />
              ) : null}
              <span className="text-muted-foreground shrink-0 text-xs">
                {totalCount}
              </span>
            </button>
            {groups.map(group => {
              const icon =
                group.id === 'Your uploads' ? (
                  <Paperclip className="size-3.5 shrink-0" />
                ) : (
                  <Folder className="size-3.5 shrink-0" />
                )
              return (
                <button
                  key={group.id}
                  type="button"
                  className={cn(
                    'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                    scope === group.id && 'bg-muted'
                  )}
                  onClick={() => {
                    setScope(group.id)
                    setMenuOpen(false)
                  }}
                >
                  {icon}
                  <span className="min-w-0 flex-1 truncate">{group.title}</span>
                  {scope === group.id ? (
                    <Check className="size-3.5 shrink-0 text-sky-500" />
                  ) : null}
                  <span className="text-muted-foreground shrink-0 text-xs">
                    {group.files.length}
                  </span>
                </button>
              )
            })}
            <div className="bg-border my-1.5 h-px" />
            <div className="text-muted-foreground px-2 py-1 text-[10px] font-medium uppercase tracking-wide">
              This computer
            </div>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onUpload()
              }}
            >
              <Upload className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Upload files…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onNewFile()
              }}
            >
              <FilePlus className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">New file…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onNewFolder()
              }}
            >
              <Plus className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Add folder…</span>
            </button>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              onClick={() => {
                setMenuOpen(false)
                onRefresh()
              }}
            >
              <RefreshCw className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1 truncate">Refresh</span>
            </button>
          </PopoverContent>
        </Popover>

        <div className="bg-muted/40 border-border/60 flex h-8 w-full items-center gap-1 rounded-md border px-1.5">
          <Search className="text-muted-foreground size-3.5 shrink-0" />
          <input
            value={query}
            onChange={event => onQueryChange(event.target.value)}
            placeholder="Search artifacts..."
            className="text-foreground placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-xs outline-none"
          />
          <span className="text-muted-foreground shrink-0 whitespace-nowrap pr-0.5 text-[11px]">
            {visibleCount} artifact{visibleCount === 1 ? '' : 's'}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn('size-6', viewMode === 'grid' && 'bg-muted')}
            title="Grid view"
            onClick={() => onViewModeChange('grid')}
          >
            <LayoutGrid className="size-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn('size-6', viewMode === 'list' && 'bg-muted')}
            title="List view"
            onClick={() => onViewModeChange('list')}
          >
            <List className="size-3.5" />
          </Button>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-6"
                title="More actions"
              >
                <MoreHorizontal className="size-3.5" />
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-48 p-1.5">
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm disabled:opacity-40"
                disabled={visibleCount === 0}
                onClick={onDownloadAll}
              >
                <Download className="size-3.5" />
                Download artifacts…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onUpload}
              >
                <Upload className="size-3.5" />
                Upload files…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onNewFile}
              >
                <FilePlus className="size-3.5" />
                New file…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onNewFolder}
              >
                <FolderPlus className="size-3.5" />
                New folder…
              </button>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onRefresh}
              >
                <RefreshCw className="size-3.5" />
                Refresh
              </button>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {empty ? (
        <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
          <Folder className="size-9 opacity-70" />
          <p className="text-xs">No files yet</p>
        </div>
      ) : visibleGroups.length === 0 ? (
        <div className="text-muted-foreground/70 flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-3 text-center">
          <Folder className="size-9 opacity-70" />
          <p className="text-xs">No artifacts in this scope</p>
        </div>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-2 p-2">
            {visibleGroups.map(group => {
              const open = expandedGroups[group.id] ?? true
              return (
                <div key={group.id} className="space-y-1">
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground flex w-full items-center justify-between rounded px-1 py-1 text-left text-[11px]"
                    onClick={() => onToggleGroup(group.id)}
                  >
                    <span className="inline-flex min-w-0 items-center gap-1 font-medium">
                      <ChevronDown
                        className={cn(
                          'size-3.5 shrink-0 transition-transform',
                          !open && '-rotate-90'
                        )}
                      />
                      <span className="truncate">{group.title}</span>
                    </span>
                    <span>
                      {group.files.length}
                      {group.files[0]?.mtime
                        ? ` · ${relativeTime(group.files[0].mtime)}`
                        : ''}
                    </span>
                  </button>
                  {open ? (
                    viewMode === 'grid' ? (
                      <div className="grid grid-cols-2 gap-2">
                        {group.files.map(file => (
                          <button
                            key={file.path}
                            type="button"
                            className={cn(
                              'hover:bg-muted/60 group/file flex flex-col items-stretch gap-1.5 rounded-md border border-transparent p-1.5 text-left transition-colors',
                              activePath === file.path &&
                                'bg-muted border-border'
                            )}
                            onClick={() => onOpenFile(file)}
                          >
                            <ArtifactGridThumb
                              client={client}
                              sessionId={sessionId}
                              file={file}
                            />
                            <span className="line-clamp-2 w-full px-0.5 text-[11px] leading-tight">
                              {file.name}
                            </span>
                            <span className="text-muted-foreground px-0.5 text-[10px]">
                              {relativeTime(file.mtime)}
                            </span>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="space-y-0.5">
                        {group.files.map(file => (
                          <div
                            key={file.path}
                            role="button"
                            tabIndex={0}
                            className={cn(
                              'hover:bg-muted group/file flex w-full cursor-pointer items-center gap-1.5 rounded px-1.5 py-1.5',
                              activePath === file.path && 'bg-muted'
                            )}
                            onClick={() => onOpenFile(file)}
                            onKeyDown={event => {
                              if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault()
                                onOpenFile(file)
                              }
                            }}
                          >
                            <Icon
                              icon={getFileIcon(file.name)}
                              className="size-3.5 shrink-0"
                            />
                            <span className="min-w-0 flex-1 truncate text-left text-[11px]">
                              {file.name}
                            </span>
                            <div className="relative h-6 w-11 shrink-0">
                              <span className="text-muted-foreground pointer-events-none absolute inset-0 flex items-center justify-end pr-0.5 text-[10px] transition-opacity group-hover/file:opacity-0">
                                {relativeTime(file.mtime)}
                              </span>
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 inline-flex size-6 items-center justify-center rounded opacity-0 transition-opacity group-hover/file:opacity-100"
                                title="Download"
                                onClick={event => {
                                  event.stopPropagation()
                                  onDownloadFile(file.path)
                                }}
                              >
                                <Download className="size-3.5" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  ) : null}
                </div>
              )
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  )
}

function FileActionsHeader({
  path,
  canSave,
  dirty,
  saving,
  downloadUrl,
  onAddToChat,
  onSave,
  onExpand,
  onClose
}: {
  path: string
  canSave: boolean
  dirty?: boolean
  saving?: boolean
  downloadUrl: string
  onAddToChat: () => void
  onSave: () => void
  onExpand: () => void
  onClose: () => void
}) {
  const name = path.split('/').at(-1) || path
  return (
    <div className="flex h-9 shrink-0 items-center gap-2 px-2">
      <span className="text-foreground/90 min-w-0 flex-1 truncate text-xs">
        {name}
      </span>
      {canSave && (saving || dirty) ? (
        <span className="text-muted-foreground shrink-0 text-[10px]">
          {saving ? 'Saving…' : 'Unsaved'}
        </span>
      ) : null}
      <div className="flex shrink-0 items-center">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              title="File actions"
              aria-label="File actions"
            >
              <MoreHorizontal className="size-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-52 p-1.5">
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={onAddToChat}
            >
              <MessageSquarePlus className="size-3.5" />
              Add to chat
            </button>
            {canSave ? (
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onSave}
              >
                <Save className="size-3.5" />
                Save
                <span className="text-muted-foreground ml-auto text-[10px]">
                  ⌘S
                </span>
              </button>
            ) : null}
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={() => void navigator.clipboard.writeText(path)}
            >
              <Copy className="size-3.5" />
              Copy path
            </button>
            <a
              href={downloadUrl}
              download
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
            >
              <Download className="size-3.5" />
              Download
            </a>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={onExpand}
            >
              <Eye className="size-3.5" />
              Open full screen
            </button>
          </PopoverContent>
        </Popover>
        <Button variant="ghost" size="icon" className="size-7" asChild>
          <a href={downloadUrl} download title="Download">
            <Download className="size-3.5" />
          </a>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          title="Close file"
          aria-label="Close file"
          onClick={onClose}
        >
          <X className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}

function fileTextContent(active: WorkspaceFileContent, draft: string): string {
  if (active.encoding === 'text') return draft || active.content
  if (isStructure(active.path) || isTextLike(active.path)) {
    try {
      return atob(active.content)
    } catch {
      return active.content
    }
  }
  return draft || active.content
}

function FilePreview({
  active,
  draft,
  editorDark,
  onDraftChange,
  onSave
}: {
  active: WorkspaceFileContent
  draft: string
  editorDark: boolean
  onDraftChange: (value: string) => void
  onSave?: () => void
}) {
  const text = fileTextContent(active, draft)
  const editable = active.encoding === 'text'
  const onSaveRef = useRef(onSave)
  onSaveRef.current = onSave

  if (isStructure(active.path)) {
    return (
      <StructureViewer
        data={text}
        format={
          active.path.toLowerCase().endsWith('.pdb')
            ? 'pdb'
            : active.path.toLowerCase().endsWith('.sdf')
            ? 'sdf'
            : 'cif'
        }
      />
    )
  }
  if (isSvg(active.path) || active.mimeType === 'image/svg+xml') {
    const src =
      active.encoding === 'base64'
        ? `data:image/svg+xml;base64,${active.content}`
        : `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text)}`
    return (
      <div className="bg-muted/10 grid h-full place-items-center overflow-auto p-4">
        <img
          src={src}
          alt={active.path}
          className="max-h-full max-w-full object-contain"
        />
      </div>
    )
  }
  if (isSpreadsheet(active.path)) {
    return <TablePreview content={text} path={active.path} />
  }
  if (editable || isTextLike(active.path)) {
    return (
      <div className="h-full min-h-0 w-full">
        <Editor
          height="100%"
          value={editable ? draft : text}
          onChange={editable ? value => onDraftChange(value || '') : undefined}
          language={languageFor(active.path)}
          theme={editorDark ? 'vs-dark' : 'vs'}
          onMount={(editor, monaco) => {
            if (!editable) return
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
              onSaveRef.current?.()
            })
          }}
          options={{
            readOnly: !editable,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'on',
            lineNumbersMinChars: 3,
            wordWrap: 'on',
            padding: { top: 12 },
            scrollBeyondLastLine: false,
            automaticLayout: true
          }}
        />
      </div>
    )
  }
  if (active.mimeType === 'application/pdf') {
    return (
      <iframe
        title={active.path}
        src={`data:application/pdf;base64,${active.content}`}
        className="h-full w-full border-0"
      />
    )
  }
  if (active.mimeType.startsWith('image/')) {
    return (
      <div className="bg-muted/10 grid h-full place-items-center p-4">
        <img
          src={`data:${active.mimeType};base64,${active.content}`}
          alt={active.path}
          className="max-h-full max-w-full object-contain"
        />
      </div>
    )
  }
  return (
    <div className="text-muted-foreground grid h-full place-items-center text-sm">
      Binary preview unavailable
    </div>
  )
}

function isStructure(path: string) {
  return /\.(pdb|cif|mmcif|sdf)$/i.test(path)
}

function isSvg(path: string) {
  return /\.svg$/i.test(path)
}

function isSpreadsheet(path: string) {
  return /\.(csv|tsv)$/i.test(path)
}

function isTextLike(path: string) {
  return /\.(json|md|txt|ya?ml|py|ts|tsx|js|jsx|css|html?|xml|cif|mmcif|pdb|sdf)$/i.test(
    path
  )
}

function TablePreview({ content, path }: { content: string; path: string }) {
  const separator = path.toLowerCase().endsWith('.tsv') ? '\t' : ','
  const rows = content
    .split(/\r?\n/)
    .filter(Boolean)
    .map(line => line.split(separator))
  if (rows.length === 0) {
    return (
      <div className="text-muted-foreground grid h-full place-items-center text-sm">
        Empty file
      </div>
    )
  }
  return (
    <div className="h-full overflow-auto">
      <table className="min-w-full border-collapse text-[11px]">
        <thead className="bg-muted sticky top-0">
          <tr>
            {rows[0].map((cell, index) => (
              <th
                key={`${cell}-${index}`}
                className="border px-2 py-1.5 text-left font-medium"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(1, 1000).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className="whitespace-nowrap border px-2 py-1.5"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function languageFor(path: string) {
  const extension = path.split('.').at(-1)?.toLowerCase()
  return (
    {
      py: 'python',
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      json: 'json',
      md: 'markdown',
      yaml: 'yaml',
      yml: 'yaml',
      css: 'css',
      html: 'html',
      htm: 'html',
      xml: 'xml',
      svg: 'xml',
      csv: 'plaintext',
      pdb: 'plaintext',
      cif: 'plaintext',
      mmcif: 'plaintext',
      sdf: 'plaintext'
    }[extension || ''] || 'plaintext'
  )
}
