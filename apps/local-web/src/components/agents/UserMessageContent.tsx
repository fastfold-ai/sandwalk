import { Icon } from '@iconify/react'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { McpServer } from '@sandwalk/agent-ui-core'
import { Plug } from 'lucide-react'
import { Fragment, type ReactNode } from 'react'

import {
  mcpIconForChip,
  mcpIconForServer
} from '@/components/agents/composer/composer-mention-utils'
import { parseMessageParts } from '@/components/agents/composer-parts'
import { ExternalUrlLink } from '@/components/agents/ExternalUrlLink'
import {
  MessageFilePreview,
  messageFilePreviewKind
} from '@/components/agents/message-file-preview'
import {
  type SkillIconSkill,
  SkillMentionChip} from '@/components/agents/SkillMentionChip'
import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { splitTextWithUrls } from '@/lib/chat-urls'
import { getFileIcon } from '@/lib/file-icons'
import { cn } from '@/lib/utils'
import { splitTextWithWorkspacePaths } from '@/lib/workspace-file-paths'

function linkifyUrlsInText(text: string): ReactNode {
  const segments = splitTextWithUrls(text)
  if (segments.length === 1 && segments[0]?.type === 'text') {
    return text
  }
  return segments.map((segment, index) => {
    if (segment.type === 'text') {
      return <Fragment key={`t-${index}`}>{segment.text}</Fragment>
    }
    return (
      <ExternalUrlLink key={`u-${index}-${segment.href}`} href={segment.href}>
        {segment.text}
      </ExternalUrlLink>
    )
  })
}

export function UserMessageContent({
  content,
  className,
  onOpenFile,
  client,
  sessionId,
  workspacePath,
  skills,
  mcpServers
}: {
  content: string
  className?: string
  onOpenFile?: (path: string) => void
  client?: LocalAgentClient | null
  sessionId?: string | null
  workspacePath?: string | null
  skills?: SkillIconSkill[]
  mcpServers?: McpServer[]
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
  const hasUrls = parts.some(
    part =>
      part.type === 'text' &&
      splitTextWithUrls(part.text).some(segment => segment.type === 'url')
  )

  if (!hasChips && !hasInlinePreviews && !hasWorkspacePaths && !hasUrls) {
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
          {linkifyUrlsInText(text)}
        </span>
      )
    }
    const segments = splitTextWithWorkspacePaths(text, workspacePath)
    return (
      <span key={key} className="whitespace-pre-wrap">
        {segments.map((segment, segmentIndex) => {
          if (segment.type === 'text') {
            return (
              <Fragment key={`${key}-t-${segmentIndex}`}>
                {linkifyUrlsInText(segment.text)}
              </Fragment>
            )
          }
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
      const server = mcpServers?.find(
        item => item.id === part.id || item.name === part.name
      )
      const icon = server
        ? mcpIconForServer(server)
        : mcpIconForChip(part.id, part.name)
      return (
        <a
          key={`mcp-${index}-${part.id}`}
          href={`/dashboard/mcp/server/${encodeURIComponent(part.id)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="border-border/70 bg-muted/40 text-foreground inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs hover:underline"
        >
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
          <span className="max-w-[200px] truncate">{part.name}</span>
        </a>
      )
    }
    return (
      <SkillMentionChip
        key={`skill-${index}-${part.name}`}
        name={part.name}
        skills={skills}
      />
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
