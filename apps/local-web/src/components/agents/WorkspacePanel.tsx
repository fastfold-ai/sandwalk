import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  WorkspaceFile,
  WorkspaceFileContent
} from '@sandwalk/agent-ui-core'
import {
  CircleX,
  Download,
  Pencil,
  Trash2,
  X
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { cn } from '@/lib/utils'

import { ArtifactsBrowser } from './ArtifactsBrowser'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from './tab-context-menu'
import { TerminalPanel } from './TerminalPanel'
import { WorkspaceArtifactsModal } from './WorkspaceArtifactsModal'
import { WorkspaceFileTabsColumn } from './WorkspaceFileTabsColumn'
import {
  AUTOSAVE_DELAY_MS,
  groupArtifacts,
  isStructure,
  normalizeFileContent,
  readOpenFileTabs,
  writeOpenFileTabs,
  type ViewMode
} from './workspace-utils'

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
    <WorkspaceFileTabsColumn
      tabs={tabs}
      filesTabActive={filesTabActive}
      activePath={activePath}
      active={active}
      openingPath={openingPath}
      renameFilePath={renameFilePath}
      renameFileValue={renameFileValue}
      draft={draft}
      editorDark={editorDark}
      isDirty={isDirty}
      saving={saving}
      status={status}
      uploadRef={uploadRef}
      renameFileInputRef={renameFileInputRef}
      renameFileIgnoreBlurRef={renameFileIgnoreBlurRef}
      browser={browser}
      client={client}
      sessionId={sessionId}
      onTogglePanel={onTogglePanel}
      onSelectFilesTab={selectFilesTab}
      onSelectFileTab={selectFileTab}
      onCloseTab={closeTab}
      onOpenModal={() => setModalOpen(true)}
      onFileTabContextMenu={(path, x, y) => setFileTabMenu({ path, x, y })}
      onRenameFileValueChange={setRenameFileValue}
      onSubmitRenameFile={() => void submitRenameFile()}
      onCancelRenameFile={cancelRenameFile}
      onCommitRenameFileFromBlur={commitRenameFileFromBlur}
      onBeginRenameFile={beginRenameFile}
      onDraftChange={setDraft}
      onSave={() => void save()}
      onAddToChat={onAddToChat}
      onUploadChange={files => {
        const uploads = Array.from(files || [])
        void Promise.all(
          uploads.map(file => client.uploadFile(sessionId, file, 'uploads'))
        ).then(refresh)
      }}
    />
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

      <WorkspaceArtifactsModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        browser={browser}
        activeTab={activeTab}
        openingPath={openingPath}
        activePath={activePath}
        draft={draft}
        editorDark={editorDark}
        client={client}
        sessionId={sessionId}
        onUpload={() => uploadRef.current?.click()}
        onRefresh={() => void refresh()}
        onAddToChat={onAddToChat}
        onDraftChange={setDraft}
        onSave={() => void save()}
      />

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
