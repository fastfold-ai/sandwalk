import type { AgentSession } from '@fastfold/agent-ui-core'
import {
  Archive,
  CircleX,
  Download,
  Pencil,
  Pin,
  Search,
  Trash2,
  X
} from 'lucide-react'
import { type ReactNode,useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

type TabContextMenuState = {
  sessionId: string
  x: number
  y: number
}

export function SessionTabs({
  tabs,
  activeId,
  onSelect,
  onClose,
  onCloseOthers,
  onRename,
  onTogglePin,
  onExport,
  onInspect,
  onArchive,
  onDelete
}: {
  tabs: AgentSession[]
  activeId: string | null
  onSelect: (id: string) => void
  onClose: (id: string) => void
  onCloseOthers: (id: string) => void
  onRename: (session: AgentSession) => void
  onTogglePin: (session: AgentSession) => void
  onExport: (session: AgentSession) => void
  onInspect: (session: AgentSession) => void
  onArchive: (session: AgentSession) => void
  onDelete: (session: AgentSession) => void
}) {
  const [menu, setMenu] = useState<TabContextMenuState | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!menu) return
    const close = (event: MouseEvent) => {
      if (menuRef.current?.contains(event.target as Node)) return
      setMenu(null)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(null)
    }
    const onScroll = () => setMenu(null)
    // Use click (not mousedown) so menu item handlers run first.
    window.addEventListener('click', close, true)
    window.addEventListener('keydown', onKey)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('click', close, true)
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [menu])

  const menuSession = menu
    ? tabs.find(tab => tab.id === menu.sessionId) || null
    : null

  const runAction = (action: () => void) => {
    setMenu(null)
    action()
  }

  return (
    <div className="flex min-w-0 flex-1 items-center gap-1">
      <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch gap-0.5 overflow-x-auto">
        {tabs.map(tab => {
          const active = tab.id === activeId
          return (
            <div
              key={tab.id}
              className={cn(
                'group relative my-auto flex h-8 w-40 shrink-0 items-center rounded-md px-2.5',
                active
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
              )}
              onContextMenu={event => {
                event.preventDefault()
                setMenu({
                  sessionId: tab.id,
                  x: event.clientX,
                  y: event.clientY
                })
              }}
            >
              <button
                type="button"
                className="min-w-0 flex-1 truncate pr-5 text-left text-xs font-medium"
                onClick={() => onSelect(tab.id)}
                title={tab.title || 'Untitled'}
              >
                {tab.title || 'Untitled'}
              </button>
              <button
                type="button"
                className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                aria-label={`Close ${tab.title || 'Untitled'}`}
                onClick={event => {
                  event.stopPropagation()
                  onClose(tab.id)
                }}
              >
                <X className="size-3.5" />
              </button>
            </div>
          )
        })}
      </div>

      {menu && menuSession ? (
        <div
          ref={menuRef}
          className="bg-popover text-popover-foreground fixed z-50 min-w-[11.5rem] rounded-md border p-1 shadow-md"
          style={{ left: menu.x, top: menu.y }}
          role="menu"
          onClick={event => event.stopPropagation()}
        >
          <ContextItem
            icon={<X className="size-3.5" />}
            label="Close"
            onClick={() => runAction(() => onClose(menuSession.id))}
          />
          <ContextItem
            icon={<CircleX className="size-3.5" />}
            label="Close others"
            disabled={tabs.length <= 1}
            onClick={() => runAction(() => onCloseOthers(menuSession.id))}
          />
          <div className="bg-border my-1 h-px" />
          <ContextItem
            icon={<Pencil className="size-3.5" />}
            label="Rename…"
            onClick={() => runAction(() => onRename(menuSession))}
          />
          <ContextItem
            icon={<Pin className="size-3.5" />}
            label={menuSession.organizeLabel === 'pinned' ? 'Unpin' : 'Pin'}
            onClick={() => runAction(() => onTogglePin(menuSession))}
          />
          <div className="bg-border my-1 h-px" />
          <ContextItem
            icon={<Download className="size-3.5" />}
            label="Export session"
            onClick={() => runAction(() => onExport(menuSession))}
          />
          <ContextItem
            icon={<Search className="size-3.5" />}
            label="Inspect chat"
            onClick={() => runAction(() => onInspect(menuSession))}
          />
          <ContextItem
            icon={<Archive className="size-3.5" />}
            label={
              menuSession.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'
            }
            onClick={() => runAction(() => onArchive(menuSession))}
          />
          <div className="bg-border my-1 h-px" />
          <ContextItem
            icon={<Trash2 className="size-3.5" />}
            label="Delete"
            destructive
            onClick={() => runAction(() => onDelete(menuSession))}
          />
        </div>
      ) : null}
    </div>
  )
}

function ContextItem({
  icon,
  label,
  onClick,
  disabled,
  destructive
}: {
  icon: ReactNode
  label: string
  onClick: () => void
  disabled?: boolean
  destructive?: boolean
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      className={cn(
        'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm',
        destructive
          ? 'text-red-600 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-red-950/20'
          : 'hover:bg-muted disabled:opacity-40',
        disabled && 'pointer-events-none'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onClick()
      }}
    >
      {icon}
      {label}
    </button>
  )
}
