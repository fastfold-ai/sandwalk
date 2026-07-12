import { Icon } from '@iconify/react'
import { Sparkles } from 'lucide-react'

import { parseMessageParts } from '@/components/agents/composer-parts'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'

export function UserMessageContent({
  content,
  className,
  onOpenFile
}: {
  content: string
  className?: string
  onOpenFile?: (path: string) => void
}) {
  const parts = parseMessageParts(content)
  const hasChips = parts.some(part => part.type !== 'text')

  if (!hasChips) {
    return (
      <p
        className={cn(
          'whitespace-pre-wrap break-words text-[15px] leading-6',
          className
        )}
      >
        {content}
      </p>
    )
  }

  return (
    <p
      className={cn(
        'whitespace-pre-wrap break-words text-[15px] leading-6',
        className
      )}
    >
      {parts.map((part, index) => {
        if (part.type === 'text') {
          if (!part.text) return null
          return (
            <span key={`text-${index}`} className="whitespace-pre-wrap">
              {part.text}
            </span>
          )
        }
        if (part.type === 'file') {
          const name = part.path.split('/').at(-1) || part.path
          const chipClass =
            'bg-card border-border/70 inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs'
          const chipBody = (
            <>
              <Icon icon={getFileIcon(name)} className="size-3.5 shrink-0" />
              <span className="max-w-[220px] truncate">@{name}</span>
            </>
          )
          if (onOpenFile) {
            return (
              <button
                key={`file-${index}-${part.path}`}
                type="button"
                className={cn(chipClass, 'hover:bg-muted/40 cursor-pointer')}
                title={`Open @${part.path}`}
                onClick={() => onOpenFile(part.path)}
              >
                {chipBody}
              </button>
            )
          }
          return (
            <span
              key={`file-${index}-${part.path}`}
              className={chipClass}
              title={`@${part.path}`}
            >
              {chipBody}
            </span>
          )
        }
        return (
          <a
            key={`skill-${index}-${part.name}`}
            href={`/dashboard/skills/${encodeURIComponent(part.name)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="border-primary/30 bg-primary/5 text-foreground inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs hover:underline"
          >
            <Sparkles className="text-primary/80 size-3.5 shrink-0" />
            <span className="max-w-[200px] truncate">/{part.name}</span>
          </a>
        )
      })}
    </p>
  )
}
