import type { AgentSession } from '@sandwalk/agent-ui-core'
import { MessageSquare } from 'lucide-react'
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
import { cn } from '@/lib/utils'

export type ComposerHashMenuHandle = {
  handleKeyDown: (event: KeyboardEvent) => boolean
}

export const ComposerHashMenu = forwardRef<
  ComposerHashMenuHandle,
  {
    open: boolean
    results: AgentSession[]
    chatCount: number
    onPick: (session: AgentSession) => void
    onDismiss: () => void
    focusInput: () => void
  }
>(function ComposerHashMenu(
  { open, results, chatCount, onPick, onDismiss, focusInput },
  ref
) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const listRootRef = useRef<HTMLDivElement | null>(null)

  const selected =
    results.find(chat => chat.id === selectedId) || results[0] || null

  const scrollIntoView = useCallback((id: string) => {
    const node = itemRefs.current.get(id)
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
      setSelectedId(null)
      return
    }
    if (selectedId && results.some(chat => chat.id === selectedId)) return
    const nextId = results[0]?.id || null
    setSelectedId(current => (current === nextId ? current : nextId))
  }, [open, results, selectedId])

  useEffect(() => {
    if (!open || !selected) return
    scrollIntoView(selected.id)
  }, [open, scrollIntoView, selected?.id])

  useImperativeHandle(
    ref,
    () => ({
      handleKeyDown(event) {
        if (!open) return false
        if (event.key === 'Escape') {
          event.preventDefault()
          onDismiss()
          setSelectedId(null)
          return true
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          event.stopPropagation()
          if (results.length === 0) return true
          const currentIndex = results.findIndex(chat => chat.id === selected?.id)
          const safeIndex = currentIndex < 0 ? 0 : currentIndex
          const nextIndex =
            event.key === 'ArrowDown'
              ? Math.min(safeIndex + 1, results.length - 1)
              : Math.max(safeIndex - 1, 0)
          const nextId = results[nextIndex]?.id
          if (!nextId) return true
          setSelectedId(nextId)
          window.requestAnimationFrame(() => {
            focusInput()
            scrollIntoView(nextId)
          })
          return true
        }
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault()
          if (selected) onPick(selected)
          return true
        }
        return false
      }
    }),
    [focusInput, onDismiss, onPick, open, results, scrollIntoView, selected]
  )

  if (!open) return null

  return (
    <div className="border-border bg-popover absolute bottom-full left-0 z-20 mb-2 w-full overflow-hidden rounded-xl border shadow-lg">
      <div ref={listRootRef}>
        <ScrollArea className="max-h-56">
          <div className="p-1" role="listbox">
            {results.length > 0 ? (
              results.map(session => {
                const isSelected = selected?.id === session.id
                const title = session.title.trim() || 'Untitled'
                return (
                  <button
                    key={session.id}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    ref={node => {
                      if (node) itemRefs.current.set(session.id, node)
                      else itemRefs.current.delete(session.id)
                    }}
                    onMouseDown={event => event.preventDefault()}
                    onMouseEnter={() => setSelectedId(session.id)}
                    onClick={() => onPick(session)}
                    className={cn(
                      'hover:bg-muted flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left',
                      isSelected && 'bg-muted'
                    )}
                  >
                    <MessageSquare className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        #{title}
                      </span>
                    </span>
                  </button>
                )
              })
            ) : (
              <div className="text-muted-foreground px-2 py-1.5 text-xs">
                {chatCount === 0
                  ? 'No agent sessions yet'
                  : 'No matching sessions'}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
})
