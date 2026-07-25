import type { SlackParkedMessage } from '@sandwalk/agent-ui-core'

import { Button } from '@/components/ui/button'

export function SlackParkedQueue({
  parked,
  busy,
  onAllow,
  onDismiss
}: {
  parked: SlackParkedMessage[]
  busy: boolean
  onAllow: (messageId: string) => void
  onDismiss: (messageId: string) => void
}) {
  if (parked.length === 0) return null

  return (
    <section className="rounded-xl border border-amber-500/30 bg-amber-500/5">
      <div className="px-4 py-3">
        <p className="text-[13px] font-medium">
          Waiting for your OK · {parked.length}
        </p>
        <p className="text-muted-foreground mt-0.5 text-[12px]">
          These people mentioned the agent but are not on the People list yet.
        </p>
      </div>
      <div className="divide-border/70 divide-y">
        {parked.map(item => (
          <div
            key={item.id}
            className="flex flex-wrap items-center gap-2 px-4 py-2.5"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-[12px]">
                <span
                  className="font-medium"
                  title={`id ${item.slackUserId}`}
                >
                  {item.userName || item.slackUserId}
                </span>
                <span className="text-muted-foreground"> — {item.text}</span>
              </p>
            </div>
            <Button
              size="sm"
              className="h-7 text-[12px]"
              disabled={busy}
              onClick={() => onAllow(item.id)}
            >
              Allow &amp; deliver
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-[12px]"
              disabled={busy}
              onClick={() => onDismiss(item.id)}
            >
              Dismiss
            </Button>
          </div>
        ))}
      </div>
    </section>
  )
}
