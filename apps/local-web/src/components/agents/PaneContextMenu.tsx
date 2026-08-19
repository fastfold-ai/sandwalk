import { useEffect, useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'

import type { PaneContextMenuDetail } from './ChatTilingContainer'

/**
 * Global listener + floating menu triggered by a right-click on any
 * chat pane in the tiling container. The menu is a plain shadcn
 * DropdownMenu anchored at the click coordinates via a hidden 1×1
 * trigger element. Kept out of the tree so every pane doesn't ship its
 * own menu markup.
 */
export function PaneContextMenu() {
  const [state, setState] = useState<PaneContextMenuDetail | null>(null)

  useEffect(() => {
    const handler = (ev: Event) => {
      const detail = (ev as CustomEvent<PaneContextMenuDetail>).detail
      setState(detail)
    }
    window.addEventListener(
      'sandwalk:pane-context-menu',
      handler as EventListener
    )
    return () =>
      window.removeEventListener(
        'sandwalk:pane-context-menu',
        handler as EventListener
      )
  }, [])

  if (!state) return null

  return (
    <DropdownMenu open onOpenChange={o => !o && setState(null)}>
      {/* Anchor: an invisible trigger sitting exactly at the click. */}
      <DropdownMenuTrigger asChild>
        <div
          style={{
            position: 'fixed',
            left: `${state.x}px`,
            top: `${state.y}px`,
            width: 1,
            height: 1,
            pointerEvents: 'none'
          }}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="bottom" className="w-52">
        <DropdownMenuItem
          onSelect={() => {
            state.handlers.onSplitLeft()
            setState(null)
          }}
        >
          Split left
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => {
            state.handlers.onSplitRight()
            setState(null)
          }}
        >
          Split right
          <DropdownMenuShortcut>⌘D</DropdownMenuShortcut>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => {
            state.handlers.onSplitUp()
            setState(null)
          }}
        >
          Split up
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => {
            state.handlers.onSplitDown()
            setState(null)
          }}
        >
          Split down
          <DropdownMenuShortcut>⇧⌘D</DropdownMenuShortcut>
        </DropdownMenuItem>
        {state.handlers.onClose ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                state.handlers.onClose?.()
                setState(null)
              }}
            >
              Close pane
              <DropdownMenuShortcut>⌘W</DropdownMenuShortcut>
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
