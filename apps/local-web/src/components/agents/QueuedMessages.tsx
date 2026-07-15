import { ArrowUp, ChevronDown, Circle, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { QueuedMessage } from '@/lib/sessions'
import { cn } from '@/lib/utils'

type QueuedMessagesProps = {
  messages: QueuedMessage[]
  editingId?: string | null
  onEdit: (id: string) => void
  onSendNow: (id: string) => void
  onRemove: (id: string) => void
}

export function QueuedMessages({
  messages,
  editingId = null,
  onEdit,
  onSendNow,
  onRemove
}: QueuedMessagesProps) {
  const [expanded, setExpanded] = useState(true)

  if (messages.length === 0) return null

  return (
    <div className="border-border/60 mb-2 overflow-hidden rounded-lg border">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="text-muted-foreground hover:bg-muted/40 flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-[12px] transition-colors"
      >
        <ChevronDown
          className={cn(
            'size-3.5 shrink-0 transition-transform',
            !expanded && '-rotate-90'
          )}
        />
        <span>
          {messages.length} Queued
        </span>
      </button>
      {expanded ? (
        <ul className="border-border/50 divide-y divide-border/40 border-t">
          {messages.map(msg => {
            const isEditing = editingId === msg.id
            return (
              <li
                key={msg.id}
                className={cn(
                  'group flex items-start gap-2.5 px-3 py-2.5',
                  isEditing && 'bg-sky-500/10 ring-1 ring-inset ring-sky-500/30'
                )}
              >
                <Circle className="text-muted-foreground/70 mt-0.5 size-3.5 shrink-0 stroke-[1.5]" />
                <p className="text-foreground min-w-0 flex-1 whitespace-pre-wrap break-words text-[13px] leading-snug">
                  {msg.text}
                </p>
                <div className="flex shrink-0 items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
                  <button
                    type="button"
                    onClick={() => onEdit(msg.id)}
                    aria-label="Edit queued message"
                    title="Edit"
                    className="text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded-md p-1.5 transition-colors"
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onSendNow(msg.id)}
                    aria-label="Send queued message now"
                    title="Send now"
                    className="text-muted-foreground hover:text-foreground hover:bg-muted/60 rounded-md p-1.5 transition-colors"
                  >
                    <ArrowUp className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemove(msg.id)}
                    aria-label="Remove queued message"
                    title="Remove"
                    className="text-muted-foreground hover:text-destructive hover:bg-muted/60 rounded-md p-1.5 transition-colors"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
