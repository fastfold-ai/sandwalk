import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { Pencil, Trash2 } from 'lucide-react'

import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

export function TerminalTabContextMenu({
  menu,
  tabs,
  tabColors,
  onClose,
  onRename,
  onSetTabColor,
  onTerminate
}: {
  menu: { id: string; x: number; y: number } | null
  tabs: PtySessionInfo[]
  tabColors: Record<string, string>
  onClose: () => void
  onRename: (tab: PtySessionInfo) => void
  onSetTabColor: (id: string, color: string | null) => void
  onTerminate: (id: string) => void
}) {
  if (!menu || !tabs.some(tab => tab.id === menu.id)) return null

  return (
    <TabContextMenuShell x={menu.x} y={menu.y} onClose={onClose}>
      <TabContextItem
        icon={<Pencil className="size-3.5" />}
        label="Rename terminal…"
        onClick={() => {
          const tab = tabs.find(item => item.id === menu.id)
          onClose()
          if (!tab) return
          onRename(tab)
        }}
      />
      <TabContextSeparator />
      <TabInlineColorRow
        value={tabColors[menu.id] || null}
        onSelect={color => {
          onSetTabColor(menu.id, color)
          onClose()
        }}
        onClear={() => {
          onSetTabColor(menu.id, null)
          onClose()
        }}
      />
      <TabContextSeparator />
      <TabContextItem
        icon={<Trash2 className="size-3.5" />}
        label="Terminate"
        destructive
        onClick={() => {
          const id = menu.id
          onClose()
          void onTerminate(id)
        }}
      />
    </TabContextMenuShell>
  )
}
