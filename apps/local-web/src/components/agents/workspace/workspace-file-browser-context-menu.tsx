import {
  Download,
  FolderInput,
  MessageSquarePlus,
  Pencil,
  Trash2
} from 'lucide-react'

import {
  TabContextItem,
  TabContextMenuShell,
  TabContextSeparator
} from '../tab-context-menu'

export function WorkspaceFileBrowserContextMenu({
  menu,
  onClose,
  onAddToChat,
  onRename,
  onMove,
  onDownload,
  onDelete
}: {
  menu: {
    path: string
    x: number
    y: number
    type: 'file' | 'directory'
  } | null
  onClose: () => void
  onAddToChat: (path: string, kind?: 'file' | 'directory') => void
  onRename: (path: string) => void
  onMove: (path: string) => void
  onDownload: (path: string) => void
  onDelete: (path: string) => void
}) {
  if (!menu) return null

  return (
    <TabContextMenuShell x={menu.x} y={menu.y} onClose={onClose}>
      <TabContextItem
        icon={<MessageSquarePlus className="size-3.5" />}
        label="Add to chat"
        onClick={() => {
          const path = menu.path
          const kind = menu.type
          onClose()
          onAddToChat(path, kind)
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
        icon={<FolderInput className="size-3.5" />}
        label="Move to folder…"
        onClick={() => {
          const path = menu.path
          onClose()
          onMove(path)
        }}
      />
      {menu.type === 'file' ? (
        <TabContextItem
          icon={<Download className="size-3.5" />}
          label="Download"
          onClick={() => {
            const path = menu.path
            onClose()
            onDownload(path)
          }}
        />
      ) : null}
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
