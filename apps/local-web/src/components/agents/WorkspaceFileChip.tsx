import { Icon } from '@iconify/react'

import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

/** Clickable file chip matching composer / user `@` mention styling. */
export function WorkspaceFileChip({
  path,
  onOpenFile,
  className
}: {
  /** Workspace-relative path. */
  path: string
  onOpenFile: (path: string) => void
  className?: string
}) {
  const name = path.split('/').at(-1) || path
  return (
    <button
      type="button"
      className={cn(
        'bg-card border-border/70 hover:bg-muted/40 inline-flex max-w-full cursor-pointer items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs',
        className
      )}
      title={`Open @${path}`}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onOpenFile(path)
      }}
    >
      <Icon icon={getFileIcon(name)} className="size-3.5 shrink-0" />
      <span className="max-w-[220px] truncate">@{name}</span>
    </button>
  )
}
