import type { MessageSource } from '@sandwalk/agent-ui-core'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

/**
 * Rich card for a message that arrived through a connector.
 *
 * The stored `content` carries reply-handle framing the model needs; this
 * renders the sidecar instead so the transcript reads like the conversation
 * actually looked in Slack.
 */
export function ConnectorMessageCard({
  source,
  createdAt,
  className
}: {
  source: MessageSource
  createdAt: string
  className?: string
}) {
  const channel = source.channelName
    ? `#${source.channelName}`
    : source.channelId
  const sender = source.senderName || source.senderId
  const when = relativeTime(createdAt)
  const initial = sender.trim().charAt(0).toUpperCase() || '?'

  return (
    <div
      className={cn(
        'border-border/70 bg-background overflow-hidden rounded-xl border',
        className
      )}
    >
      <div className="bg-muted/40 flex items-center gap-2 px-3 py-1.5">
        <img
          src={INTEGRATION_ICONS.slack.src}
          alt=""
          className="size-3.5 shrink-0 object-contain"
        />
        <span
          className="truncate text-[12px] font-medium"
          title={source.channelId}
        >
          {channel}
        </span>
        <span className="text-muted-foreground">·</span>
        {source.senderAvatarUrl ? (
          <img
            src={source.senderAvatarUrl}
            alt=""
            className="size-4 shrink-0 rounded-full object-cover"
          />
        ) : (
          <span className="bg-muted text-muted-foreground flex size-4 shrink-0 items-center justify-center rounded-full text-[9px] font-medium">
            {initial}
          </span>
        )}
        <span className="truncate text-[12px]" title={`id ${source.senderId}`}>
          {sender}
        </span>
        <span className="text-muted-foreground text-[11px]">via Slack</span>
        {when ? (
          <span className="text-muted-foreground ml-auto shrink-0 text-[11px]">
            {when}
          </span>
        ) : null}
      </div>
      <p className="whitespace-pre-wrap break-words px-3 py-2 text-[13px]">
        {source.text}
      </p>
    </div>
  )
}
