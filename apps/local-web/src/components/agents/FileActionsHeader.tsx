import {
  Copy,
  Download,
  Eye,
  MessageSquarePlus,
  MoreHorizontal,
  RefreshCw,
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
  reloading,
  onDownload,
  onAddToChat,
  onSave,
  onReload,
  onExpand,
  onClose
}: {
  path: string
  canSave: boolean
  dirty?: boolean
  saving?: boolean
  reloading?: boolean
  onDownload: () => void
  onAddToChat: () => void
  onSave: () => void
  onReload?: () => void
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
            {onReload ? (
              <button
                type="button"
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm disabled:opacity-40"
                disabled={reloading}
                onClick={onReload}
              >
                <RefreshCw
                  className={`size-3.5 ${reloading ? 'animate-spin' : ''}`}
                />
                Reload
              </button>
            ) : null}
            <button
              type="button"
              className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm"
              onClick={onDownload}
            >
              <Download className="size-3.5" />
              Download
            </button>
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
        {onReload ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            title="Reload file"
            aria-label="Reload file"
            disabled={reloading}
            onClick={onReload}
          >
            <RefreshCw
              className={`size-3.5 ${reloading ? 'animate-spin' : ''}`}
            />
          </Button>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          title="Download"
          aria-label="Download"
          onClick={onDownload}
        >
          <Download className="size-3.5" />
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
