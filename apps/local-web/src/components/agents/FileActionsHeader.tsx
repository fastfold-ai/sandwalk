import {
  Copy,
  Download,
  Eye,
  MessageSquarePlus,
  MoreHorizontal,
  Save,
  X
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'

export function FileActionsHeader({
  path,
  canSave,
  dirty,
  saving,
  downloadUrl,
  onAddToChat,
  onSave,
  onExpand,
  onClose
}: {
  path: string
  canSave: boolean
  dirty?: boolean
  saving?: boolean
  downloadUrl: string
  onAddToChat: () => void
  onSave: () => void
  onExpand: () => void
  onClose: () => void
}) {
  const name = path.split('/').at(-1) || path
  return (
    <div className="flex h-9 shrink-0 items-center gap-2 px-2">
      <span className="text-foreground/90 min-w-0 flex-1 truncate text-xs">
        {name}
      </span>
      {canSave && (saving || dirty) ? (
        <span className="text-muted-foreground shrink-0 text-[10px]">
          {saving ? 'Saving…' : 'Unsaved'}
        </span>
      ) : null}
      <div className="flex shrink-0 items-center">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              title="File actions"
              aria-label="File actions"
            >
              <MoreHorizontal className="size-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-52 p-1.5">
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={onAddToChat}
            >
              <MessageSquarePlus className="size-3.5" />
              Add to chat
            </button>
            {canSave ? (
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                onClick={onSave}
              >
                <Save className="size-3.5" />
                Save
                <span className="text-muted-foreground ml-auto text-[10px]">
                  ⌘S
                </span>
              </button>
            ) : null}
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={() => void navigator.clipboard.writeText(path)}
            >
              <Copy className="size-3.5" />
              Copy path
            </button>
            <a
              href={downloadUrl}
              download
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
            >
              <Download className="size-3.5" />
              Download
            </a>
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={onExpand}
            >
              <Eye className="size-3.5" />
              Open full screen
            </button>
          </PopoverContent>
        </Popover>
        <Button variant="ghost" size="icon" className="size-7" asChild>
          <a href={downloadUrl} download title="Download">
            <Download className="size-3.5" />
          </a>
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          title="Close file"
          aria-label="Close file"
          onClick={onClose}
        >
          <X className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}
