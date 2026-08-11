import { Icon } from '@iconify/react'
import { Folder } from 'lucide-react'

import {
  mentionDisplayName,
  mentionPathIsDirectory
} from '@/components/agents/composer-parts'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

/** Clickable file/folder chip matching composer / user `@` mention styling. */
export function WorkspaceFileChip({
  path,
  kind,
  onOpenFile,
  className
}: {
  /** Workspace-relative path. */
  path: string
  kind?: 'file' | 'directory'
  onOpenFile: (path: string) => void
  className?: string
}) {
  const isFolder =
    kind === 'directory' || mentionPathIsDirectory(path)
  const name = mentionDisplayName(path)
  const openPath = path.replace(/\/+$/u, '') || path
  return (
    <button
      type="button"
      className={cn(
        'bg-card border-border/70 hover:bg-muted/40 inline-flex max-w-full cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs',
        className
      )}
      title={`Open @${openPath}`}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onOpenFile(openPath)
      }}
    >
      {isFolder ? (
        <Folder className="text-muted-foreground size-3.5 shrink-0" />
      ) : (
        <Icon icon={getFileIcon(name)} className="size-3.5 shrink-0" />
      )}
      <span className="max-w-[220px] truncate">
        @{name}
        {isFolder ? '/' : ''}
      </span>
    </button>
  )
}
