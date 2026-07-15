import { CircleX, Download, Pencil, Trash2, X } from 'lucide-react'

import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from '../tab-context-menu'

export function WorkspaceFileTabContextMenu({
  menu,
  tabCount,
  onClose,
  onCloseTab,
  onCloseOtherTabs,
  onRename,
  onDownload,
  onDelete
}: {
  menu: { path: string; x: number; y: number } | null
  tabCount: number
  onClose: () => void
  onCloseTab: (path: string) => void
  onCloseOtherTabs: (path: string) => void
  onRename: (path: string) => void
  onDownload: (path: string) => void
  onDelete: (path: string) => void
}) {
  if (!menu) return null

  return (
    <TabContextMenuShell x={menu.x} y={menu.y} onClose={onClose}>
      <TabContextItem
        icon={<X className="size-3.5" />}
        label="Close"
        onClick={() => {
          const path = menu.path
          onClose()
          onCloseTab(path)
        }}
      />
      <TabContextItem
        icon={<CircleX className="size-3.5" />}
        label="Close others"
        disabled={tabCount <= 1}
        onClick={() => {
          const path = menu.path
          onClose()
          onCloseOtherTabs(path)
        }}
      />
      <TabContextSeparator />
      <TabContextItem
        icon={<Pencil className="size-3.5" />}
        label="Rename…"
        onClick={() => {
          const path = menu.path
          onClose()
          onRename(path)
        }}
      />
      <TabContextItem
        icon={<Download className="size-3.5" />}
        label="Download"
        onClick={() => {
          const path = menu.path
          onClose()
          onDownload(path)
        }}
      />
      <TabContextSeparator />
      <TabContextItem
        icon={<Trash2 className="size-3.5" />}
        label="Delete"
        destructive
        onClick={() => {
          const path = menu.path
          onClose()
          onDelete(path)
        }}
      />
    </TabContextMenuShell>
  )
}
