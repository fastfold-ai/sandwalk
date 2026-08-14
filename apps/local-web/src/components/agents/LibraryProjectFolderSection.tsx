import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  LibraryKind,
  ProjectFolderFile,
  ProjectFolderListing,
  WorkspaceFileContent
} from '@sandwalk/agent-ui-core'
import {
  Folder,
  Loader2,
  MessageSquarePlus,
  Pencil,
  Trash2,
  X
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { FilePreview } from '@/components/agents/FilePreview'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from '@/components/agents/tab-context-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { getFileIcon } from '@/lib/file-icons'
import { cn, relativeTime } from '@/lib/utils'

function useEditorDark() {
  const [editorDark, setEditorDark] = useState(() =>
    typeof document !== 'undefined'
      ? document.documentElement.classList.contains('dark')
      : true
  )
  useEffect(() => {
    const root = document.documentElement
    const sync = () => setEditorDark(root.classList.contains('dark'))
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return editorDark
}

export function LibraryProjectFolderSection({
  client,
  projectId,
  filter,
  query,
  navigate,
  pendingAttachmentsRef,
  openSessionTab,
  loadSessions
}: {
  client: LocalAgentClient
  projectId: string
  filter: LibraryKind | 'all'
  query: string
  navigate: NavigateFunction
  pendingAttachmentsRef: {
    current: { sessionId: string; paths: string[] } | null
  }
  openSessionTab: (sessionId: string) => void
  loadSessions: () => void | Promise<void>
}) {
  const editorDark = useEditorDark()
  const [listing, setListing] = useState<ProjectFolderListing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previewPath, setPreviewPath] = useState<string | null>(null)
  const [preview, setPreview] = useState<WorkspaceFileContent | null>(null)
  const [draft, setDraft] = useState('')
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{
    file: ProjectFolderFile
    x: number
    y: number
  } | null>(null)
  const [renamePath, setRenamePath] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<ProjectFolderFile | null>(
    null
  )
  const [busy, setBusy] = useState(false)

  const reload = async () => {
    const result = await client.listProjectFolderFiles(projectId)
    setListing(result)
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void client
      .listProjectFolderFiles(projectId)
      .then(result => {
        if (cancelled) return
        setListing(result)
      })
      .catch(cause => {
        if (cancelled) return
        const message =
          cause instanceof Error ? cause.message : 'Unable to load project folder'
        if (/no linked folder/i.test(message) || /404/i.test(message)) {
          setListing(null)
          setError(null)
        } else {
          setListing(null)
          setError(message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client, projectId])

  const files = useMemo(() => {
    if (!listing) return [] as ProjectFolderFile[]
    const needle = query.trim().toLowerCase()
    return listing.data.filter(file => {
      if (filter !== 'all' && file.kind !== filter) return false
      if (!needle) return true
      return (
        file.name.toLowerCase().includes(needle) ||
        file.path.toLowerCase().includes(needle)
      )
    })
  }, [filter, listing, query])

  useEffect(() => {
    if (!previewPath) {
      setPreview(null)
      setDraft('')
      setPreviewError(null)
      return
    }
    let cancelled = false
    setPreviewBusy(true)
    setPreviewError(null)
    void client
      .readProjectFolderFile(projectId, previewPath)
      .then(content => {
        if (cancelled) return
        setPreview(content)
        setDraft(content.encoding === 'text' ? content.content : '')
      })
      .catch(cause => {
        if (!cancelled) {
          setPreview(null)
          setDraft('')
          setPreviewError(
            cause instanceof Error ? cause.message : 'Unable to open file'
          )
        }
      })
      .finally(() => {
        if (!cancelled) setPreviewBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [client, previewPath, projectId])

  const chatAbout = async (file: ProjectFolderFile) => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await client.useProjectFolderInChat(projectId, {
        paths: [file.path],
        title: file.name
      })
      pendingAttachmentsRef.current = {
        sessionId: result.sessionId,
        paths: result.paths
      }
      openSessionTab(result.sessionId)
      await loadSessions()
      navigate(`/agents/${result.sessionId}`)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to start chat'
      )
    } finally {
      setBusy(false)
    }
  }

  const commitRename = async (file: ProjectFolderFile) => {
    const next = renameValue.trim()
    setRenamePath(null)
    if (!next || next === file.name || busy) return
    setBusy(true)
    setError(null)
    try {
      const updated = await client.renameProjectFolderFile(
        projectId,
        file.path,
        next
      )
      setListing(current => {
        if (!current) return current
        return {
          ...current,
          data: current.data.map(entry =>
            entry.path === file.path ? updated : entry
          )
        }
      })
      if (previewPath === file.path) setPreviewPath(updated.path)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Rename failed')
      await reload().catch(() => undefined)
    } finally {
      setBusy(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget || busy) return
    const target = deleteTarget
    setDeleteTarget(null)
    setBusy(true)
    setError(null)
    try {
      await client.deleteProjectFolderFile(projectId, target.path)
      setListing(current => {
        if (!current) return current
        return {
          ...current,
          data: current.data.filter(entry => entry.path !== target.path)
        }
      })
      if (previewPath === target.path) setPreviewPath(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Delete failed')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="text-muted-foreground mb-6 flex items-center gap-2 text-[13px]">
        <Loader2 className="size-3.5 animate-spin" />
        Loading project folder…
      </div>
    )
  }

  if (error && !listing) {
    return <p className="text-destructive mb-6 text-[13px]">{error}</p>
  }

  if (!listing) return null

  return (
    <>
      <section className="border-border/70 bg-muted/15 mb-8 overflow-hidden rounded-xl border">
        <div className="flex min-w-0 items-center gap-2 px-3.5 py-2.5">
          <Folder className="text-muted-foreground size-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="text-foreground text-[13px] font-medium">
                Project folder
              </span>
              <span className="text-muted-foreground shrink-0 text-[11px] tabular-nums">
                {listing.data.length}
                {listing.truncated ? '+' : ''} files
                {files.length !== listing.data.length
                  ? ` · ${files.length} shown`
                  : ''}
              </span>
            </div>
            <div
              className="text-muted-foreground mt-0.5 truncate font-mono text-[11px]"
              title={listing.folderPath}
            >
              {listing.folderPath}
            </div>
          </div>
        </div>

        {error ? (
          <p className="text-destructive border-border/60 border-t px-3.5 py-2 text-[12px]">
            {error}
          </p>
        ) : null}

        {files.length === 0 ? (
          <div className="text-muted-foreground border-border/60 border-t px-3.5 py-6 text-center text-[12px]">
            {listing.data.length === 0
              ? 'No files in this project folder yet.'
              : 'No project files match this filter.'}
          </div>
        ) : (
          <ul className="border-border/60 divide-y border-t">
            {files.map(file => (
              <li key={file.path}>
                <button
                  type="button"
                  className={cn(
                    'hover:bg-muted/50 flex w-full items-center gap-2.5 px-3.5 py-2 text-left transition-colors'
                  )}
                  onClick={() => setPreviewPath(file.path)}
                  onContextMenu={event => {
                    event.preventDefault()
                    setContextMenu({
                      file,
                      x: event.clientX,
                      y: event.clientY
                    })
                  }}
                >
                  <Icon
                    icon={getFileIcon(file.name)}
                    className="text-muted-foreground size-4 shrink-0 opacity-80"
                  />
                  <div className="min-w-0 flex-1">
                    {renamePath === file.path ? (
                      <Input
                        autoFocus
                        value={renameValue}
                        className="h-7 text-[12px]"
                        onClick={event => event.stopPropagation()}
                        onChange={event => setRenameValue(event.target.value)}
                        onBlur={() => void commitRename(file)}
                        onKeyDown={event => {
                          if (event.key === 'Enter') {
                            event.preventDefault()
                            void commitRename(file)
                          }
                          if (event.key === 'Escape') {
                            event.preventDefault()
                            setRenamePath(null)
                          }
                        }}
                      />
                    ) : (
                      <>
                        <div className="text-foreground truncate text-[13px]">
                          {file.name}
                        </div>
                        {file.path !== file.name ? (
                          <div className="text-muted-foreground truncate font-mono text-[11px]">
                            {file.path}
                          </div>
                        ) : null}
                      </>
                    )}
                  </div>
                  <span className="text-muted-foreground shrink-0 text-[11px] tabular-nums">
                    {relativeTime(file.mtime)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {contextMenu ? (
        <TabContextMenuShell
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
        >
          <TabContextItem
            icon={<MessageSquarePlus className="size-3.5" />}
            label="Chat about this"
            onClick={() => {
              const file = contextMenu.file
              setContextMenu(null)
              void chatAbout(file)
            }}
          />
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename"
            onClick={() => {
              setRenamePath(contextMenu.file.path)
              setRenameValue(contextMenu.file.name)
              setContextMenu(null)
            }}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Delete"
            destructive
            onClick={() => {
              setDeleteTarget(contextMenu.file)
              setContextMenu(null)
            }}
          />
        </TabContextMenuShell>
      ) : null}

      <AlertDialog
        open={Boolean(deleteTarget)}
        onOpenChange={open => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete from project folder?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes{' '}
              <span className="text-foreground font-medium">
                {deleteTarget?.name}
              </span>{' '}
              from the linked folder on disk. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={busy}
              onClick={event => {
                event.preventDefault()
                void confirmDelete()
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={Boolean(previewPath)}
        onOpenChange={open => {
          if (!open) setPreviewPath(null)
        }}
      >
        <DialogContent
          hideCloseButton
          className="flex h-[min(92dvh,56rem)] w-[min(96vw,72rem)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:rounded-xl"
        >
          <DialogHeader className="border-border shrink-0 space-y-0 border-b px-4 py-3 text-left">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <DialogTitle className="truncate text-[15px]">
                  {previewPath?.split('/').pop() || 'Project file'}
                </DialogTitle>
                <DialogDescription className="truncate font-mono text-[11px]">
                  {previewPath || ''}
                </DialogDescription>
              </div>
              <div className="flex shrink-0 items-center gap-0.5">
                {previewPath ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-8 gap-1.5"
                    disabled={busy}
                    onClick={() => {
                      const file = listing.data.find(
                        entry => entry.path === previewPath
                      )
                      if (file) void chatAbout(file)
                    }}
                  >
                    <MessageSquarePlus className="size-3.5" />
                    Chat
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="size-8"
                  onClick={() => setPreviewPath(null)}
                  aria-label="Close preview"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </div>
          </DialogHeader>
          <div className="relative min-h-0 flex-1 overflow-hidden">
            {previewBusy ? (
              <div className="text-muted-foreground flex h-full items-center justify-center gap-2 text-[13px]">
                <Loader2 className="size-4 animate-spin" />
                Opening…
              </div>
            ) : previewError ? (
              <div className="text-destructive flex h-full items-center justify-center px-6 text-center text-[13px]">
                {previewError}
              </div>
            ) : preview ? (
              <FilePreview
                active={preview}
                draft={draft}
                editorDark={editorDark}
                onDraftChange={setDraft}
              />
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
