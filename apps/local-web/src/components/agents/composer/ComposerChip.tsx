import { Icon } from '@iconify/react'
import { Folder, MessageSquare, Plug, Sparkles, X } from 'lucide-react'

import { mcpIconForChip } from '@/components/agents/composer/composer-mention-utils'
import {
  mentionDisplayName,
  mentionPathIsDirectory
} from '@/components/agents/composer-parts'
import { getFileIcon } from '@/lib/file-icons'
import { skillIconForName, skillIconInvertInDark } from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

export function ComposerFileChip({
  path,
  kind = 'file',
  onOpenFile,
  onRemove
}: {
  path: string
  kind?: 'file' | 'directory'
  onOpenFile?: (path: string) => void
  onRemove: () => void
}) {
  const isFolder = kind === 'directory' || mentionPathIsDirectory(path)
  const name = mentionDisplayName(path)
  const openPath = path.replace(/\/+$/u, '') || path
  return (
    <span className="bg-muted/50 border-border/70 inline-flex max-w-full select-none items-center gap-0.5 rounded-full border px-1.5 py-0 align-middle text-xs leading-5">
      {isFolder ? (
        <Folder className="text-muted-foreground size-3.5 shrink-0" />
      ) : (
        <Icon
          icon={getFileIcon(name)}
          className="text-muted-foreground size-3.5 shrink-0"
        />
      )}
      <button
        type="button"
        className="text-foreground max-w-[180px] truncate hover:underline"
        title={`Open @${openPath}`}
        onClick={() => onOpenFile?.(openPath)}
      >
        @{name}
        {isFolder ? '/' : ''}
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
  iconSrc,
  author,
  source,
  onRemove
}: {
  name: string
  iconSrc?: string | null
  author?: string | null
  source?: string | null
  onRemove: () => void
}) {
  const skill = {
    name,
    iconSrc: iconSrc || null,
    author: author || '',
    source: source || ''
  }
  const resolved = skillIconForName(name, [skill])
  const invert = skillIconInvertInDark(skill)
  return (
    <span className="border-primary/30 bg-primary/5 inline-flex max-w-full select-none items-center gap-0.5 rounded-full border px-1.5 py-0 align-middle text-xs leading-5">
      {resolved ? (
        <img
          src={resolved}
          alt=""
          className={cn(
            'size-3.5 shrink-0 rounded-sm object-contain',
            invert && 'dark:invert'
          )}
        />
      ) : (
        <Sparkles className="text-primary/80 size-3.5 shrink-0" />
      )}
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
  catalogId,
  onRemove
}: {
  id: string
  name: string
  catalogId?: string | null
  onRemove: () => void
}) {
  const href = `/dashboard/mcp/server/${encodeURIComponent(id)}`
  const icon =
    mcpIconForChip(id, name) ||
    (catalogId ? mcpIconForChip(catalogId, name) : null)
  return (
    <span className="border-border/70 bg-muted/40 inline-flex max-w-full select-none items-center gap-0.5 rounded-full border px-1.5 py-0 align-middle text-xs leading-5">
      {icon ? (
        <img
          src={icon.src}
          alt=""
          className={cn(
            'size-3.5 shrink-0 rounded-sm object-contain',
            icon.invertInDark && 'dark:invert'
          )}
        />
      ) : (
        <Plug className="text-muted-foreground size-3.5 shrink-0" />
      )}
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

export function ComposerChatChip({
  sessionId,
  title,
  onRemove
}: {
  sessionId: string
  title?: string
  onRemove?: () => void
}) {
  const label = title?.trim() || sessionId.slice(0, 8)
  return (
    <span className="bg-muted/50 border-border/70 inline-flex max-w-full select-none items-center gap-0.5 rounded-full border px-1.5 py-0 align-middle text-xs leading-5">
      <MessageSquare className="text-muted-foreground size-3.5 shrink-0" />
      <span className="text-foreground max-w-[180px] truncate" title={sessionId}>
        #{label}
      </span>
      {onRemove ? (
        <button
          type="button"
          className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-4 items-center justify-center rounded-full"
          onClick={onRemove}
          aria-label={`Remove #${label}`}
        >
          <X className="size-3" />
        </button>
      ) : null}
    </span>
  )
}
