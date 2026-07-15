import { Icon } from '@iconify/react'
import { Plug, Sparkles, X } from 'lucide-react'

import { getFileIcon } from '@/lib/file-icons'

export function ComposerFileChip({
  path,
  onOpenFile,
  onRemove
}: {
  path: string
  onOpenFile?: (path: string) => void
  onRemove: () => void
}) {
  const name = path.split('/').at(-1) || path
  return (
    <span className="bg-muted/50 border-border/70 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs">
      <Icon
        icon={getFileIcon(name)}
        className="text-muted-foreground size-3.5 shrink-0"
      />
      <button
        type="button"
        className="text-foreground max-w-[180px] truncate hover:underline"
        title={`Open @${path}`}
        onClick={() => onOpenFile?.(path)}
      >
        @{name}
      </button>
      <button
        type="button"
        className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
        onClick={onRemove}
        aria-label={`Remove @${name}`}
      >
        <X className="size-3" />
      </button>
    </span>
  )
}

export function ComposerSkillChip({
  name,
  onRemove
}: {
  name: string
  onRemove: () => void
}) {
  return (
    <span className="border-primary/30 bg-primary/5 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs">
      <Sparkles className="text-primary/80 size-3.5 shrink-0" />
      <button
        type="button"
        className="text-foreground max-w-[200px] truncate hover:underline"
        onClick={() =>
          window.open(
            `/dashboard/skills/${encodeURIComponent(name)}`,
            '_blank',
            'noopener,noreferrer'
          )
        }
      >
        {name}
      </button>
      <button
        type="button"
        className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
        onClick={onRemove}
        aria-label={`Remove skill ${name}`}
      >
        <X className="size-3" />
      </button>
    </span>
  )
}

export function ComposerMcpChip({
  id,
  name,
  onRemove
}: {
  id: string
  name: string
  onRemove: () => void
}) {
  const href = `/dashboard/mcp/server/${encodeURIComponent(id)}`
  return (
    <span className="border-border/70 bg-muted/40 inline-flex max-w-full select-none items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs">
      <Plug className="text-muted-foreground size-3.5 shrink-0" />
      <button
        type="button"
        className="text-foreground max-w-[200px] truncate hover:underline"
        onClick={() => window.open(href, '_blank', 'noopener,noreferrer')}
      >
        {name}
      </button>
      <button
        type="button"
        className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
        onClick={onRemove}
        aria-label={`Remove MCP ${name}`}
      >
        <X className="size-3" />
      </button>
    </span>
  )
}
