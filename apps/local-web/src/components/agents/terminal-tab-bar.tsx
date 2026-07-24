import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { Plus, SquareTerminal, X } from 'lucide-react'
import type { RefObject } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function TerminalTabBar({
  tabs,
  activeId,
  tabColors,
  renameId,
  renameValue,
  renameInputRef,
  renameIgnoreBlurRef,
  onSelectTab,
  onCloseTab,
  onBeginRename,
  onRenameValueChange,
  onSubmitRename,
  onCancelRename,
  onCommitRenameFromBlur,
  onTabContextMenu,
  onCreateTab,
  onClose
}: {
  tabs: PtySessionInfo[]
  activeId: string | null
  tabColors: Record<string, string>
  renameId: string | null
  renameValue: string
  renameInputRef: RefObject<HTMLInputElement | null>
  renameIgnoreBlurRef: RefObject<boolean>
  onSelectTab: (id: string) => void
  onCloseTab: (id: string) => void
  onBeginRename: (tab: PtySessionInfo) => void
  onRenameValueChange: (value: string) => void
  onSubmitRename: () => void
  onCancelRename: () => void
  onCommitRenameFromBlur: () => void
  onTabContextMenu: (id: string, x: number, y: number) => void
  onCreateTab: () => void
  onClose?: () => void
}) {
  return (
    <div className="flex h-10 shrink-0 items-center gap-1 px-1.5">
      <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch gap-0.5 overflow-x-auto">
        {tabs.map(tab => {
          const color = tabColors[tab.id]
          const renaming = renameId === tab.id
          return (
            <div
              key={tab.id}
              className={cn(
                'group relative my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5',
                activeId === tab.id || renaming
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                renaming && 'max-w-[220px] pr-1.5'
              )}
              onContextMenu={event => {
                if (renaming) return
                event.preventDefault()
                onTabContextMenu(tab.id, event.clientX, event.clientY)
              }}
            >
              {renaming ? (
                <div className="inline-flex min-w-0 max-w-full flex-1 items-center gap-1.5">
                  <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full">
                    <SquareTerminal className="size-3.5 opacity-80" />
                  </span>
                  <input
                    ref={renameInputRef}
                    className="border-input bg-background text-foreground focus-visible:ring-ring h-6 w-full min-w-[6rem] rounded border px-1.5 text-xs font-medium outline-none focus-visible:ring-1"
                    value={renameValue}
                    onFocus={event => event.currentTarget.select()}
                    onChange={event => onRenameValueChange(event.target.value)}
                    onClick={event => event.stopPropagation()}
                    onKeyDown={event => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        event.stopPropagation()
                        renameIgnoreBlurRef.current = true
                        onSubmitRename()
                      } else if (event.key === 'Escape') {
                        event.preventDefault()
                        event.stopPropagation()
                        onCancelRename()
                      }
                    }}
                    onBlur={() => onCommitRenameFromBlur()}
                  />
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    className="inline-flex min-w-0 max-w-full items-center gap-1.5 truncate pr-0 text-left text-xs font-medium"
                    title={tab.title}
                    onClick={() => onSelectTab(tab.id)}
                    onDoubleClick={event => {
                      event.preventDefault()
                      onBeginRename(tab)
                    }}
                  >
                    <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full">
                      <SquareTerminal className="size-3.5 opacity-80" />
                    </span>
                    {color ? (
                      <span
                        className="size-2 shrink-0 rounded-full border border-black/10"
                        style={{ backgroundColor: color }}
                        aria-hidden
                      />
                    ) : null}
                    <span className="truncate">{tab.title}</span>
                  </button>
                  <button
                    type="button"
                    className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                    aria-label={`Close ${tab.title}`}
                    onClick={event => {
                      event.stopPropagation()
                      void onCloseTab(tab.id)
                    }}
                  >
                    <X className="size-3.5" />
                  </button>
                </>
              )}
            </div>
          )
        })}
      </div>
      <div className="ml-auto flex shrink-0 items-center">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="text-muted-foreground hover:text-foreground size-7"
          title="New terminal"
          aria-label="New terminal"
          onClick={onCreateTab}
        >
          <Plus className="size-3.5" />
        </Button>
        {onClose ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground size-7"
            title="Hide terminal"
            aria-label="Hide terminal"
            onClick={onClose}
          >
            <X className="size-3.5" />
          </Button>
        ) : null}
      </div>
    </div>
  )
}
