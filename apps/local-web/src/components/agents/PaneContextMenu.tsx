import { X } from 'lucide-react'
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
import { SplitMenuDropdown } from './split-menu'

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
      <DropdownMenuContent
        align="start"
        side="bottom"
        // Keeps the menu inside the viewport when the click lands near
        // the bottom-right of a pane (small splits especially). Radix's
        // Popper flip handles the axis, this padding prevents flush-cut
        // edges once flipped.
        collisionPadding={{ bottom: 8, right: 8, top: 8, left: 8 }}
        className="w-56"
      >
        <SplitMenuDropdown
          sourceId={state.chatId}
          onSplitPane={(id, direction, target) => {
            state.handlers.onSplitPane(id, direction, target)
            setState(null)
          }}
        />
        {state.handlers.onClose ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="gap-2 text-[13px]"
              onSelect={() => {
                state.handlers.onClose?.()
                setState(null)
              }}
            >
              <X className="size-3.5" />
              Close pane
              <DropdownMenuShortcut>⌘W</DropdownMenuShortcut>
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
