import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Plug, Sparkles } from 'lucide-react'

import { parseMessageParts } from '@/components/agents/composer-parts'
import {
  MessageFilePreview,
  messageFilePreviewKind
} from '@/components/agents/message-file-preview'
import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { getFileIcon } from '@/lib/file-icons'
import { splitTextWithWorkspacePaths } from '@/lib/workspace-file-paths'
import { cn } from '@/lib/utils'

export function UserMessageContent({
  content,
  className,
  onOpenFile,
  client,
  sessionId,
  workspacePath
}: {
  content: string
  className?: string
  onOpenFile?: (path: string) => void
  client?: LocalAgentClient | null
  sessionId?: string | null
  workspacePath?: string | null
}) {
  const parts = parseMessageParts(content)
  const canPreview = Boolean(client && sessionId)
  const previewPaths = canPreview
    ? parts
        .filter(
          (part): part is { type: 'file'; path: string } =>
            part.type === 'file' && messageFilePreviewKind(part.path) != null
        )
        .map(part => part.path)
        .filter((path, index, all) => all.indexOf(path) === index)
    : []
  const previewPathSet = new Set(previewPaths)
  const hasChips = parts.some(part => part.type !== 'text')
  const hasInlinePreviews = previewPaths.length > 0
  const hasWorkspacePaths =
    Boolean(onOpenFile) &&
    parts.some(
      part =>
        part.type === 'text' &&
        splitTextWithWorkspacePaths(part.text, workspacePath).some(
          segment => segment.type === 'file'
        )
    )

  if (!hasChips && !hasInlinePreviews && !hasWorkspacePaths) {
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

  const renderText = (text: string, key: string) => {
    if (!onOpenFile) {
      return (
        <span key={key} className="whitespace-pre-wrap">
          {text}
        </span>
      )
    }
    const segments = splitTextWithWorkspacePaths(text, workspacePath)
    return (
      <span key={key} className="whitespace-pre-wrap">
        {segments.map((segment, segmentIndex) => {
          if (segment.type === 'text') return segment.text
          return (
            <WorkspaceFileChip
              key={`${key}-ws-${segmentIndex}`}
              path={segment.relative}
              onOpenFile={onOpenFile}
            />
          )
        })}
      </span>
    )
  }

  const inlineParts = parts.map((part, index) => {
    if (part.type === 'text') {
      if (!part.text) return null
      return renderText(part.text, `text-${index}`)
    }
    if (part.type === 'file') {
      if (previewPathSet.has(part.path)) return null
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
    if (part.type === 'mcp') {
      return (
        <a
          key={`mcp-${index}-${part.id}`}
          href={`/dashboard/mcp/server/${encodeURIComponent(part.id)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="border-border/70 bg-muted/40 text-foreground inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs hover:underline"
        >
          <Plug className="text-muted-foreground size-3.5 shrink-0" />
          <span className="max-w-[200px] truncate">{part.name}</span>
        </a>
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
        <span className="max-w-[200px] truncate">{part.name}</span>
      </a>
    )
  })

  const hasInlineContent = inlineParts.some(Boolean)

  return (
    <div
      className={cn(
        'break-words text-[15px] leading-6',
        className
      )}
    >
      {hasInlinePreviews && client && sessionId ? (
        <div
          className={cn(
            'flex flex-wrap gap-2',
            hasInlineContent ? 'mb-2' : null
          )}
        >
          {previewPaths.map(path => (
            <MessageFilePreview
              key={path}
              client={client}
              sessionId={sessionId}
              path={path}
              onOpenFile={onOpenFile}
            />
          ))}
        </div>
      ) : null}
      {hasInlineContent ? (
        <p className="whitespace-pre-wrap break-words">{inlineParts}</p>
      ) : null}
    </div>
  )
}
