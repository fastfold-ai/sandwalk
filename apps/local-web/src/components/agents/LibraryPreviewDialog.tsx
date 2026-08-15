import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { LibraryItem, WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { Download, Loader, MessageSquarePlus, Pencil, RefreshCw, Save, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { FilePreview } from '@/components/agents/FilePreview'
import {
  AUTOSAVE_DELAY_MS,
  isStructure,
  normalizeFileContent
} from '@/components/agents/workspace-utils'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

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

export function LibraryPreviewDialog({
  item,
  client,
  busy,
  onClose,
  onRename,
  onChatAbout,
  onItemUpdated
}: {
  item: LibraryItem | null
  client: LocalAgentClient
  busy?: boolean
  onClose: () => void
  onRename: (item: LibraryItem) => void
  onChatAbout: (item: LibraryItem) => void
  onItemUpdated?: (item: LibraryItem) => void
}) {
  const editorDark = useEditorDark()
  const [active, setActive] = useState<WorkspaceFileContent | null>(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const draftRef = useRef(draft)
  const savingRef = useRef(false)
  const activeRef = useRef<WorkspaceFileContent | null>(null)
  draftRef.current = draft
  activeRef.current = active

  const canSave = Boolean(
    active && active.encoding === 'text' && !isStructure(active.path)
  )
  const isDirty = Boolean(canSave && active && draft !== active.content)

  const load = useCallback(
    async (target: LibraryItem, opts?: { reload?: boolean }) => {
      if (opts?.reload) setReloading(true)
      else setLoading(true)
      setError(null)
      try {
        const content = normalizeFileContent(
          await client.readLibraryFile(target.id)
        )
        setActive(content)
        setDraft(content.encoding === 'text' ? content.content : '')
        setStatus(null)
      } catch (cause) {
        setActive(null)
        setDraft('')
        setError(
          cause instanceof Error ? cause.message : 'Unable to open file'
        )
      } finally {
        setLoading(false)
        setReloading(false)
      }
    },
    [client]
  )

  useEffect(() => {
    if (!item) {
      setActive(null)
      setDraft('')
      setError(null)
      setStatus(null)
      return
    }
    void load(item)
  }, [item, load])

  const save = useCallback(
    async (opts?: { auto?: boolean }) => {
      if (!item || !activeRef.current) return
      const current = activeRef.current
      if (current.encoding !== 'text' || isStructure(current.path)) return
      const content = draftRef.current
      if (content === current.content) {
        if (!opts?.auto) {
          setStatus('Saved')
          window.setTimeout(() => {
            setStatus(value => (value === 'Saved' ? null : value))
          }, 1200)
        }
        return
      }
      if (savingRef.current) return
      savingRef.current = true
      setSaving(true)
      if (!opts?.auto) setStatus('Saving…')
      try {
        const saved = normalizeFileContent(
          await client.writeLibraryFile(item.id, { content })
        )
        setActive(saved)
        setDraft(value => (value === content ? saved.content : value))
        setStatus('Saved')
        window.setTimeout(() => {
          setStatus(value => (value === 'Saved' ? null : value))
        }, 1500)
        onItemUpdated?.({
          ...item,
          sha256: saved.version,
          bytes: saved.size,
          updatedAt: saved.mtime,
          mime: saved.mimeType
        })
      } catch (cause) {
        setStatus(cause instanceof Error ? cause.message : 'Save failed')
      } finally {
        savingRef.current = false
        setSaving(false)
      }
    },
    [client, item, onItemUpdated]
  )

  useEffect(() => {
    if (!isDirty || !canSave) return
    const timer = window.setTimeout(() => {
      void save({ auto: true })
    }, AUTOSAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [canSave, draft, isDirty, save])

  useEffect(() => {
    if (!isDirty) return
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [isDirty])

  const onDownload = async () => {
    if (!item) return
    try {
      const blob = await client.fetchLibraryContent(item.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = item.displayName || item.originalName
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (cause) {
      setStatus(cause instanceof Error ? cause.message : 'Download failed')
    }
  }

  return (
    <Dialog
      open={Boolean(item)}
      onOpenChange={open => {
        if (!open) onClose()
      }}
    >
      <DialogContent
        className="flex h-[min(92dvh,56rem)] w-[min(96vw,72rem)] max-w-none flex-col gap-0 overflow-hidden p-0 sm:rounded-xl"
        hideCloseButton
      >
        {item ? (
          <>
            <DialogHeader className="border-border space-y-0 border-b px-4 py-3 text-left">
              <div className="flex items-start justify-between gap-3 pr-8">
                <div className="min-w-0">
                  <DialogTitle className="truncate text-[15px]">
                    {item.displayName || item.originalName}
                  </DialogTitle>
                  <DialogDescription className="truncate text-[12px]">
                    {formatModified(item.updatedAt)}
                    {canSave && (saving || isDirty) ? (
                      <span className="text-muted-foreground">
                        {' · '}
                        {saving ? 'Saving…' : 'Unsaved'}
                      </span>
                    ) : status ? (
                      <span className="text-muted-foreground">
                        {' · '}
                        {status}
                      </span>
                    ) : null}
                  </DialogDescription>
                </div>
                <div className="absolute top-2.5 right-2.5 flex items-center gap-0.5">
                  {canSave ? (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8"
                      disabled={saving || !isDirty}
                      onClick={() => void save()}
                      title="Save"
                      aria-label="Save"
                    >
                      <Save className="size-4" />
                    </Button>
                  ) : null}
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8"
                    disabled={reloading || loading}
                    onClick={() => void load(item, { reload: true })}
                    title="Reload"
                    aria-label="Reload"
                  >
                    <RefreshCw
                      className={cn(
                        'size-4',
                        reloading && 'animate-spin'
                      )}
                    />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8"
                    onClick={() => void onDownload()}
                    title="Download"
                    aria-label="Download"
                  >
                    <Download className="size-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="size-8"
                    onClick={onClose}
                    aria-label="Close preview"
                  >
                    <X className="size-4" />
                  </Button>
                </div>
              </div>
            </DialogHeader>

            <div className="relative min-h-0 flex-1 overflow-hidden">
              {loading ? (
                <div className="text-muted-foreground flex h-full items-center justify-center gap-2 text-[13px]">
                  <Loader className="size-4 animate-spin" />
                  Loading…
                </div>
              ) : error ? (
                <div className="text-destructive grid h-full place-items-center px-6 text-center text-[13px]">
                  {error}
                </div>
              ) : active ? (
                <FilePreview
                  active={active}
                  draft={draft}
                  editorDark={editorDark}
                  onDraftChange={setDraft}
                  onSave={canSave ? () => void save() : undefined}
                />
              ) : null}
            </div>

            <div className="border-border flex flex-wrap items-center justify-end gap-2 border-t px-4 py-3">
              <Button
                size="sm"
                variant="outline"
                className="h-8 gap-1.5"
                onClick={() => onRename(item)}
              >
                <Pencil className="size-3.5" />
                Rename
              </Button>
              <Button
                size="sm"
                className="h-8 gap-1.5"
                disabled={busy}
                onClick={() => onChatAbout(item)}
              >
                <MessageSquarePlus className="size-3.5" />
                Chat about this
              </Button>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
