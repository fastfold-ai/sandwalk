import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { LibraryItem, LibraryKind } from '@sandwalk/agent-ui-core'
import {
  Check,
  LayoutGrid,
  LibraryBig,
  List,
  Loader2,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Upload,
  X
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { structureFormat } from '@/components/agents/artifact-grid-thumb-utils'
import { LibraryPreviewDialog } from '@/components/agents/LibraryPreviewDialog'
import { PdfFirstPagePreview } from '@/components/agents/PdfFirstPagePreview'
import { Py2dMolMiniPreview } from '@/components/agents/py2dmol/Py2dMolMiniPreview'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from '@/components/agents/tab-context-menu'
import { VideoPlayPreview } from '@/components/agents/VideoPlayPreview'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

const FILTERS: { id: LibraryKind | 'all'; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'image', label: 'Images' },
  { id: 'document', label: 'Documents' },
  { id: 'structure', label: 'Structures' },
  { id: 'code', label: 'Code' },
  { id: 'other', label: 'Other' }
]

const LAYOUT_KEY = 'sandwalk.library.layout'
const PAGE_SIZE = 48

function findScrollRoot(node: HTMLElement | null) {
  return node?.closest(
    '[data-radix-scroll-area-viewport]'
  ) as HTMLElement | null
}

function formatFileCount(total: number) {
  const label = total === 1 ? 'file' : 'files'
  return `${total.toLocaleString()} ${label}`
}

function formatModified(iso: string) {
  try {
    const date = new Date(iso)
    return `Modified ${date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    })}`
  } catch {
    return 'Modified recently'
  }
}

function isImageItem(item: LibraryItem) {
  return item.kind === 'image' || Boolean(item.mime?.startsWith('image/'))
}

function isPdfItem(item: LibraryItem) {
  const name = (item.displayName || item.originalName).toLowerCase()
  return name.endsWith('.pdf') || item.mime === 'application/pdf'
}

function isVideoItem(item: LibraryItem) {
  const name = (item.displayName || item.originalName).toLowerCase()
  return (
    Boolean(item.mime?.startsWith('video/')) ||
    /\.(mp4|webm|mov|avi|mpeg|mpg|wmv|flv|3gpp)$/i.test(name)
  )
}

function structurePreviewFormat(
  name: string
): 'pdb' | 'cif' | null {
  const kind = structureFormat(name)
  if (kind === 'pdb') return 'pdb'
  if (kind === 'sdf') return null
  return 'cif'
}

function LibraryThumb({
  item,
  client,
  className,
  fit = 'cover'
}: {
  item: LibraryItem
  client: LocalAgentClient
  className?: string
  fit?: 'cover' | 'contain'
}) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [structureText, setStructureText] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const name = item.displayName || item.originalName
  const structureFormatKind = structurePreviewFormat(name)
  const isStructurePreview =
    item.kind === 'structure' && structureFormatKind !== null
  const isVideoPreview = isVideoItem(item)
  const needsMediaPreview =
    isImageItem(item) || isPdfItem(item) || isVideoPreview
  const viewerId = useMemo(
    () => `library-thumb-${item.id.replace(/[^a-zA-Z0-9_-]+/g, '_')}`,
    [item.id]
  )

  useEffect(() => {
    if (!needsMediaPreview && !isStructurePreview) return
    const controller = new AbortController()
    let url: string | null = null
    setFailed(false)
    setObjectUrl(null)
    setStructureText(null)
    void client
      .fetchLibraryContent(item.id, controller.signal)
      .then(async blob => {
        if (controller.signal.aborted) return
        if (isStructurePreview) {
          setStructureText(await blob.text())
          return
        }
        url = URL.createObjectURL(blob)
        setObjectUrl(url)
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [client, isStructurePreview, item.id, needsMediaPreview])

  if (!failed && isStructurePreview) {
    if (!structureText) {
      return (
        <div
          className={cn(
            'bg-muted/30 h-full w-full animate-pulse',
            className
          )}
        />
      )
    }
    return (
      <div className={cn('h-full w-full overflow-hidden', className)}>
        <Py2dMolMiniPreview
          text={structureText}
          format={structureFormatKind}
          viewerId={viewerId}
        />
      </div>
    )
  }

  if (!failed && isImageItem(item) && objectUrl) {
    return (
      <img
        src={objectUrl}
        alt=""
        className={cn(
          'h-full w-full',
          fit === 'contain' ? 'object-contain' : 'object-cover',
          className
        )}
        onError={() => setFailed(true)}
      />
    )
  }

  if (!failed && isPdfItem(item) && objectUrl) {
    return (
      <PdfFirstPagePreview
        url={objectUrl}
        title={name}
        className={cn('h-full w-full', className)}
        onError={() => setFailed(true)}
      />
    )
  }

  if (!failed && isVideoPreview && objectUrl) {
    return (
      <div className={cn('h-full w-full overflow-hidden', className)}>
        <VideoPlayPreview
          src={objectUrl}
          mode="thumb"
          muted
          interactive={false}
          onError={() => setFailed(true)}
        />
      </div>
    )
  }

  return (
    <div
      className={cn(
        'bg-muted/40 flex h-full w-full items-center justify-center',
        className
      )}
    >
      <Icon icon={getFileIcon(name)} className="size-10 opacity-80" />
    </div>
  )
}

export function LibraryView({
  client,
  navigate,
  projectId,
  pendingAttachmentsRef,
  openSessionTab,
  loadSessions
}: {
  client: LocalAgentClient
  navigate: NavigateFunction
  projectId: string | null
  pendingAttachmentsRef: {
    current: { sessionId: string; paths: string[] } | null
  }
  openSessionTab: (sessionId: string) => void
  loadSessions: () => void | Promise<void>
}) {
  const [items, setItems] = useState<LibraryItem[]>([])
  const [total, setTotal] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<LibraryKind | 'all'>('all')
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [layout, setLayout] = useState<'grid' | 'list'>(() => {
    try {
      return localStorage.getItem(LAYOUT_KEY) === 'list' ? 'list' : 'grid'
    } catch {
      return 'grid'
    }
  })
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [selectMode, setSelectMode] = useState(false)
  const [previewItem, setPreviewItem] = useState<LibraryItem | null>(null)
  const [contextMenu, setContextMenu] = useState<{
    item: LibraryItem
    x: number
    y: number
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [renameId, setRenameId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const listSectionRef = useRef<HTMLDivElement>(null)
  const loadMoreInFlight = useRef(false)
  const pageRef = useRef(0)
  const hasMoreRef = useRef(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [query])

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    setItems([])
    pageRef.current = 0
    loadMoreInFlight.current = false
    try {
      const result = await client.listLibrary({
        kind: filter === 'all' ? null : filter,
        q: debouncedQuery || null,
        page: 0,
        perPage: PAGE_SIZE
      })
      setItems(result.data)
      setTotal(result.pagination.total)
      setHasMore(result.pagination.hasMore)
      hasMoreRef.current = result.pagination.hasMore
      pageRef.current = result.pagination.page
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load library')
      setTotal(0)
      setHasMore(false)
      hasMoreRef.current = false
    } finally {
      setLoading(false)
    }
  }, [client, debouncedQuery, filter])

  const loadMore = useCallback(async () => {
    if (
      loading ||
      loadingMore ||
      loadMoreInFlight.current ||
      !hasMoreRef.current
    ) {
      return
    }
    loadMoreInFlight.current = true
    setLoadingMore(true)
    const nextPage = pageRef.current + 1
    try {
      const result = await client.listLibrary({
        kind: filter === 'all' ? null : filter,
        q: debouncedQuery || null,
        page: nextPage,
        perPage: PAGE_SIZE
      })
      setItems(current => {
        const seen = new Set(current.map(item => item.id))
        const appended = result.data.filter(item => !seen.has(item.id))
        return [...current, ...appended]
      })
      setTotal(result.pagination.total)
      setHasMore(result.pagination.hasMore)
      hasMoreRef.current = result.pagination.hasMore
      pageRef.current = result.pagination.page
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load more')
    } finally {
      loadMoreInFlight.current = false
      setLoadingMore(false)
    }
  }, [client, debouncedQuery, filter, loading, loadingMore])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    try {
      localStorage.setItem(LAYOUT_KEY, layout)
    } catch {
      /* ignore */
    }
  }, [layout])

  useEffect(() => {
    if (loading || loadingMore || !hasMore) return
    const root = findScrollRoot(listSectionRef.current)
    if (!root) return
    const maybeLoad = () => {
      const remaining = root.scrollHeight - root.scrollTop - root.clientHeight
      if (remaining <= 360) void loadMore()
    }
    maybeLoad()
    root.addEventListener('scroll', maybeLoad, { passive: true })
    return () => root.removeEventListener('scroll', maybeLoad)
  }, [hasMore, items.length, loadMore, loading, loadingMore])

  const selectedItems = useMemo(
    () => items.filter(item => selected.has(item.id)),
    [items, selected]
  )

  const toggleSelected = (id: string) => {
    setSelected(current => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const exitSelectMode = () => {
    setSelectMode(false)
    setSelected(new Set())
  }

  const openItemMenu = (
    item: LibraryItem,
    event: { clientX: number; clientY: number; preventDefault: () => void }
  ) => {
    event.preventDefault()
    setContextMenu({ item, x: event.clientX, y: event.clientY })
  }

  const onItemActivate = (item: LibraryItem) => {
    if (selectMode) {
      toggleSelected(item.id)
      return
    }
    setPreviewItem(item)
  }

  const startRename = (item: LibraryItem) => {
    setRenameId(item.id)
    setRenameValue(item.displayName || item.originalName)
    setContextMenu(null)
    setPreviewItem(null)
  }

  const useInNewChat = async (itemIds: string[]) => {
    if (!itemIds.length || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await client.useLibraryInChat({
        itemIds,
        projectId,
        title: 'Library chat'
      })
      pendingAttachmentsRef.current = {
        sessionId: result.sessionId,
        paths: result.paths
      }
      openSessionTab(result.sessionId)
      await loadSessions()
      navigate(`/agents/${result.sessionId}`)
      setSelected(new Set())
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to start chat from library'
      )
    } finally {
      setBusy(false)
    }
  }

  const onUpload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        await client.uploadLibraryFile(file)
      }
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Upload failed')
    } finally {
      setBusy(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const onRename = async (item: LibraryItem) => {
    const name = renameValue.trim()
    if (!name || name === item.displayName) {
      setRenameId(null)
      return
    }
    setBusy(true)
    try {
      await client.updateLibraryItem(item.id, { displayName: name })
      setRenameId(null)
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Rename failed')
    } finally {
      setBusy(false)
    }
  }

  const onDelete = async (itemIds: string[]) => {
    if (!itemIds.length) return
    const label =
      itemIds.length === 1
        ? 'Delete this file from Library?'
        : `Delete ${itemIds.length} files from Library?`
    if (!window.confirm(label)) return
    setBusy(true)
    try {
      for (const id of itemIds) {
        await client.deleteLibraryItem(id)
      }
      setSelected(current => {
        const next = new Set(current)
        for (const id of itemIds) next.delete(id)
        return next
      })
      await reload()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Delete failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-6 py-6 md:px-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-baseline gap-2.5">
            <div className="flex items-center gap-2">
              <LibraryBig className="text-muted-foreground size-5" />
              <h1 className="text-lg font-semibold tracking-tight">Library</h1>
            </div>
            {!loading ? (
              <span className="text-muted-foreground text-[12px] tabular-nums">
                {formatFileCount(total)}
              </span>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            <Input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search files"
              className="h-8 w-44 md:w-56"
            />
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              onChange={event => void onUpload(event.target.files)}
            />
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="size-3.5" />
              Upload
            </Button>
            <Button
              size="sm"
              variant={selectMode ? 'secondary' : 'outline'}
              className="h-8 gap-1.5"
              onClick={() => {
                if (selectMode) exitSelectMode()
                else setSelectMode(true)
              }}
            >
              {selectMode ? (
                <>
                  <X className="size-3.5" />
                  Done
                </>
              ) : (
                <>
                  <Check className="size-3.5" />
                  Select
                </>
              )}
            </Button>
            <div className="border-border flex overflow-hidden rounded-md border">
              <Button
                size="icon"
                variant="ghost"
                className={cn(
                  'size-8 rounded-none',
                  layout === 'grid' && 'bg-muted'
                )}
                onClick={() => setLayout('grid')}
                aria-label="Grid view"
              >
                <LayoutGrid className="size-3.5" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className={cn(
                  'size-8 rounded-none',
                  layout === 'list' && 'bg-muted'
                )}
                onClick={() => setLayout('list')}
                aria-label="List view"
              >
                <List className="size-3.5" />
              </Button>
            </div>
          </div>
        </div>

        <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          {FILTERS.map(pill => (
            <button
              key={pill.id}
              type="button"
              className={cn(
                'shrink-0 rounded-full px-3 py-1 text-[12px] font-medium transition-colors',
                filter === pill.id
                  ? 'bg-foreground text-background'
                  : 'bg-muted/70 text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setFilter(pill.id)}
            >
              {pill.label}
            </button>
          ))}
        </div>

        {selectMode && selected.size > 0 ? (
          <div className="bg-muted/50 flex flex-wrap items-center gap-2 rounded-lg px-3 py-2">
            <span className="text-muted-foreground text-[12px]">
              {selected.size} selected
            </span>
            <Button
              size="sm"
              className="h-7 gap-1.5"
              disabled={busy}
              onClick={() => void useInNewChat([...selected])}
            >
              <MessageSquarePlus className="size-3.5" />
              Use in new chat
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive h-7 gap-1.5"
              disabled={busy}
              onClick={() => void onDelete([...selected])}
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7"
              onClick={() => setSelected(new Set())}
            >
              Clear
            </Button>
          </div>
        ) : null}

        {error ? (
          <p className="text-destructive text-[13px]">{error}</p>
        ) : null}
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <div
          ref={listSectionRef}
          className="mx-auto w-full max-w-6xl px-6 pb-10 md:px-10"
        >
          {loading ? (
            <div className="text-muted-foreground flex items-center gap-2 py-16 text-[13px]">
              <Loader2 className="size-4 animate-spin" />
              Loading library…
            </div>
          ) : items.length === 0 ? (
            <div className="text-muted-foreground flex flex-col items-center gap-3 py-20 text-center">
              <LibraryBig className="size-10 opacity-40" />
              <div>
                <p className="text-foreground text-[14px] font-medium">
                  No files yet
                </p>
                <p className="mt-1 max-w-sm text-[13px]">
                  Library indexes files from every chat (uploads, outputs,
                  artifacts). Upload here or attach something in a session.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="gap-1.5"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="size-3.5" />
                Upload files
              </Button>
            </div>
          ) : layout === 'grid' ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {items.map(item => {
                const name = item.displayName || item.originalName
                const isSelected = selected.has(item.id)
                return (
                  <div
                    key={item.id}
                    className={cn(
                      'group border-border/70 relative overflow-hidden rounded-xl border bg-background',
                      isSelected && 'ring-foreground/30 ring-2'
                    )}
                    onContextMenu={event => openItemMenu(item, event)}
                  >
                    {selectMode ? (
                      <button
                        type="button"
                        className={cn(
                          'absolute top-1.5 left-1.5 z-10 flex size-4 items-center justify-center rounded-full border text-white backdrop-blur-sm transition-opacity',
                          isSelected
                            ? 'border-white/50 bg-black/55 opacity-100'
                            : 'border-white/35 bg-black/35 opacity-100'
                        )}
                        onClick={event => {
                          event.stopPropagation()
                          toggleSelected(item.id)
                        }}
                        aria-label={isSelected ? 'Deselect' : 'Select'}
                      >
                        {isSelected ? <Check className="size-2.5" /> : null}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="aspect-[4/3] w-full overflow-hidden"
                      onClick={() => onItemActivate(item)}
                    >
                      <LibraryThumb item={item} client={client} />
                    </button>
                    <div className="flex items-start gap-1 px-2.5 py-2">
                      <div className="min-w-0 flex-1">
                        {renameId === item.id ? (
                          <Input
                            autoFocus
                            value={renameValue}
                            className="h-7 text-[12px]"
                            onChange={event => setRenameValue(event.target.value)}
                            onBlur={() => void onRename(item)}
                            onKeyDown={event => {
                              if (event.key === 'Enter') void onRename(item)
                              if (event.key === 'Escape') setRenameId(null)
                            }}
                          />
                        ) : (
                          <button
                            type="button"
                            className="w-full text-left"
                            onClick={() => onItemActivate(item)}
                          >
                            <p className="truncate text-[12px] font-medium">
                              {name}
                            </p>
                            <p className="text-muted-foreground truncate text-[10px]">
                              {formatModified(item.updatedAt)}
                            </p>
                          </button>
                        )}
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-7 shrink-0 opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100"
                            onClick={event => event.stopPropagation()}
                          >
                            <MoreHorizontal className="size-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => void useInNewChat([item.id])}
                          >
                            Chat about this
                          </DropdownMenuItem>
                          {item.originSessionId ? (
                            <DropdownMenuItem
                              onClick={() => {
                                openSessionTab(item.originSessionId!)
                                navigate(`/agents/${item.originSessionId}`)
                              }}
                            >
                              Open origin chat
                            </DropdownMenuItem>
                          ) : null}
                          <DropdownMenuItem onClick={() => startRename(item)}>
                            Rename
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            className="text-destructive"
                            onClick={() => void onDelete([item.id])}
                          >
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="divide-border/70 border-border/70 divide-y rounded-xl border">
              {items.map(item => {
                const name = item.displayName || item.originalName
                const isSelected = selected.has(item.id)
                return (
                  <div
                    key={item.id}
                    className={cn(
                      'group hover:bg-muted/40 flex items-center gap-3 px-3 py-2.5',
                      isSelected && 'bg-muted/50'
                    )}
                    onContextMenu={event => openItemMenu(item, event)}
                  >
                    {selectMode ? (
                      <button
                        type="button"
                        className={cn(
                          'border-border flex size-3.5 shrink-0 items-center justify-center rounded border',
                          isSelected
                            ? 'bg-foreground text-background'
                            : 'bg-background'
                        )}
                        onClick={() => toggleSelected(item.id)}
                        aria-label={isSelected ? 'Deselect' : 'Select'}
                      >
                        {isSelected ? <Check className="size-2.5" /> : null}
                      </button>
                    ) : null}
                    <div className="bg-muted/40 size-10 shrink-0 overflow-hidden rounded-md">
                      <button
                        type="button"
                        className="size-full"
                        onClick={() => onItemActivate(item)}
                      >
                        <LibraryThumb item={item} client={client} />
                      </button>
                    </div>
                    <div className="min-w-0 flex-1">
                      {renameId === item.id ? (
                        <Input
                          autoFocus
                          value={renameValue}
                          className="h-7 text-[13px]"
                          onChange={event => setRenameValue(event.target.value)}
                          onBlur={() => void onRename(item)}
                          onKeyDown={event => {
                            if (event.key === 'Enter') void onRename(item)
                            if (event.key === 'Escape') setRenameId(null)
                          }}
                        />
                      ) : (
                        <button
                          type="button"
                          className="w-full text-left"
                          onClick={() => onItemActivate(item)}
                        >
                          <p className="truncate text-[13px] font-medium">
                            {name}
                          </p>
                          <p className="text-muted-foreground text-[11px]">
                            {formatModified(item.updatedAt)}
                          </p>
                        </button>
                      )}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="icon" variant="ghost" className="size-8">
                          <MoreHorizontal className="size-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => void useInNewChat([item.id])}
                        >
                          Chat about this
                        </DropdownMenuItem>
                        {item.originSessionId ? (
                          <DropdownMenuItem
                            onClick={() => {
                              openSessionTab(item.originSessionId!)
                              navigate(`/agents/${item.originSessionId}`)
                            }}
                          >
                            Open origin chat
                          </DropdownMenuItem>
                        ) : null}
                        <DropdownMenuItem onClick={() => startRename(item)}>
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => void onDelete([item.id])}
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )
              })}
            </div>
          )}
          {selectMode && selectedItems.length > 0 ? (
            <p className="sr-only">{selectedItems.length} items selected</p>
          ) : null}
          {loadingMore ? (
            <div className="text-muted-foreground flex items-center justify-center gap-2 py-6 text-[12px]">
              <Loader2 className="size-3.5 animate-spin" />
              Loading more…
            </div>
          ) : null}
        </div>
      </ScrollArea>

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
              const id = contextMenu.item.id
              setContextMenu(null)
              void useInNewChat([id])
            }}
          />
          {contextMenu.item.originSessionId ? (
            <TabContextItem
              icon={<LibraryBig className="size-3.5" />}
              label="Open origin chat"
              onClick={() => {
                const sessionId = contextMenu.item.originSessionId!
                setContextMenu(null)
                openSessionTab(sessionId)
                navigate(`/agents/${sessionId}`)
              }}
            />
          ) : null}
          <TabContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename"
            onClick={() => startRename(contextMenu.item)}
          />
          <TabContextSeparator />
          <TabContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Delete"
            destructive
            onClick={() => {
              const id = contextMenu.item.id
              setContextMenu(null)
              void onDelete([id])
            }}
          />
        </TabContextMenuShell>
      ) : null}

      <LibraryPreviewDialog
        item={previewItem}
        client={client}
        busy={busy}
        onClose={() => setPreviewItem(null)}
        onRename={startRename}
        onChatAbout={target => void useInNewChat([target.id])}
        onItemUpdated={updated => {
          setPreviewItem(updated)
          setItems(current =>
            current.map(entry => (entry.id === updated.id ? updated : entry))
          )
        }}
      />
    </div>
  )
}
