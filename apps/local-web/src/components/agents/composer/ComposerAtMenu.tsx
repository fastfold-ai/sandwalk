import { Icon } from '@iconify/react'
import type { WorkspaceFile } from '@sandwalk/agent-ui-core'
import { Folder } from 'lucide-react'
import {
  forwardRef,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState
} from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

export type ComposerAtMenuHandle = {
  handleKeyDown: (event: KeyboardEvent) => boolean
}

export const ComposerAtMenu = forwardRef<
  ComposerAtMenuHandle,
  {
    open: boolean
    results: WorkspaceFile[]
    workspaceFileCount: number
    onPick: (file: WorkspaceFile) => void
    onDismiss: () => void
    focusInput: () => void
  }
>(function ComposerAtMenu(
  { open, results, workspaceFileCount, onPick, onDismiss, focusInput },
  ref
) {
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null)
  const fileItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const listRootRef = useRef<HTMLDivElement | null>(null)

  const selectedFile =
    results.find(file => file.path === selectedFilePath) || results[0] || null

  const scrollFileIntoView = useCallback((filePath: string) => {
    const node = fileItemRefs.current.get(filePath)
    const viewport = listRootRef.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!node || !viewport) return
    const nodeRect = node.getBoundingClientRect()
    const viewRect = viewport.getBoundingClientRect()
    const pad = 6
    if (nodeRect.bottom > viewRect.bottom - pad) {
      viewport.scrollTop += nodeRect.bottom - viewRect.bottom + pad
    } else if (nodeRect.top < viewRect.top + pad) {
      viewport.scrollTop -= viewRect.top - nodeRect.top + pad
    }
  }, [])

  useEffect(() => {
    if (!open) {
      setSelectedFilePath(null)
      return
    }
    if (
      selectedFilePath &&
      results.some(file => file.path === selectedFilePath)
    ) {
      return
    }
    const nextPath = results[0]?.path || null
    setSelectedFilePath(current => (current === nextPath ? current : nextPath))
  }, [open, results, selectedFilePath])

  useEffect(() => {
    if (!open || !selectedFile) return
    scrollFileIntoView(selectedFile.path)
  }, [open, scrollFileIntoView, selectedFile?.path])

  useImperativeHandle(
    ref,
    () => ({
      handleKeyDown: event => {
        if (!open) return false
        if (event.key === 'Escape') {
          event.preventDefault()
          onDismiss()
          setSelectedFilePath(null)
          return true
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          event.stopPropagation()
          if (results.length === 0) return true
          const currentIndex = results.findIndex(
            file => file.path === selectedFile?.path
          )
          const safeIndex = currentIndex < 0 ? 0 : currentIndex
          const nextIndex =
            event.key === 'ArrowDown'
              ? Math.min(safeIndex + 1, results.length - 1)
              : Math.max(safeIndex - 1, 0)
          const nextPath = results[nextIndex]?.path
          if (!nextPath) return true
          setSelectedFilePath(nextPath)
          window.requestAnimationFrame(() => {
            focusInput()
            scrollFileIntoView(nextPath)
          })
          return true
        }
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault()
          if (selectedFile) onPick(selectedFile)
          return true
        }
        return false
      }
    }),
    [
      focusInput,
      onDismiss,
      onPick,
      open,
      results,
      scrollFileIntoView,
      selectedFile
    ]
  )

  if (!open) return null

  return (
    <div className="bg-popover border-border/70 absolute bottom-full left-0 right-0 z-40 mb-2 overflow-hidden rounded-lg border shadow-lg">
      <div ref={listRootRef} className="min-h-0">
        <ScrollArea className="h-64">
          <div
            className="p-1"
            role="listbox"
            aria-label="Workspace files and folders"
          >
            {results.length > 0 ? (
              results.map(file => {
                const selected = selectedFile?.path === file.path
                const isFolder = file.type === 'directory'
                return (
                  <button
                    key={file.path}
                    type="button"
                    tabIndex={-1}
                    role="option"
                    aria-selected={selected}
                    ref={node => {
                      if (node) fileItemRefs.current.set(file.path, node)
                      else fileItemRefs.current.delete(file.path)
                    }}
                    onMouseDown={event => event.preventDefault()}
                    onMouseEnter={() => setSelectedFilePath(file.path)}
                    onClick={() => {
                      onPick(file)
                    }}
                    className={cn(
                      'hover:bg-muted flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left',
                      selected && 'bg-muted'
                    )}
                  >
                    {isFolder ? (
                      <Folder className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                    ) : (
                      <Icon
                        icon={getFileIcon(file.name)}
                        className="mt-0.5 size-4 shrink-0"
                      />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        @{file.name}
                        {isFolder ? '/' : ''}
                      </span>
                      <span className="text-muted-foreground block truncate text-[11px]">
                        workspace/{file.path}
                        {isFolder ? '/' : ''}
                      </span>
                    </span>
                  </button>
                )
              })
            ) : (
              <div className="text-muted-foreground px-2 py-1.5 text-xs">
                {workspaceFileCount === 0
                  ? 'No workspace files yet'
                  : 'No matching files or folders'}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
})
