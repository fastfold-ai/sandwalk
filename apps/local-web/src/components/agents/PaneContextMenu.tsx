import { X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import type { PaneContextMenuDetail } from './ChatTilingContainer'
import { SplitMenuBlock } from './split-menu'
import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from './tab-context-menu'

/**
 * Global listener + floating menu triggered by a right-click on any
 * chat pane in the tiling container. Kept out of the tree so every pane
 * doesn't ship its own menu markup.
 *
 * Uses the tab-context primitives (not a Radix DropdownMenu): the Split
 * Down / Split Right flyouts must open on click, since WebKit in the
 * Tauri window drops the pointer-move Radix sub-menus rely on.
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

  const close = useCallback(() => setState(null), [])

  if (!state) return null

  return (
    <TabContextMenuShell x={state.x} y={state.y} onClose={close}>
      <SplitMenuBlock
        sourceId={state.chatId}
        onSplitPane={(id, direction, target) => {
          state.handlers.onSplitPane(id, direction, target)
          setState(null)
        }}
        trailingSeparator={false}
      />
      {state.handlers.onClose ? (
        <>
          <TabContextSeparator />
          <TabContextItem
            icon={<X />}
            label="Close pane"
            trailing={<span className="text-[11px] tabular-nums">⌘W</span>}
            onClick={() => {
              state.handlers.onClose?.()
              setState(null)
            }}
          />
        </>
      ) : null}
    </TabContextMenuShell>
  )
}
