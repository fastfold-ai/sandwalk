import type { WidgetSize } from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import { heroShellClass, widgetShellClass } from '../grid'

export function ProjectTextWidget({
  label,
  text,
  size,
  empty = '—'
}: {
  label: string
  text: string | null | undefined
  size: WidgetSize
  empty?: string
}) {
  const body = (text || '').trim()
  // LG matches Usage hero height; SM/MD keep the metric-card shell.
  const shell =
    size === 'lg' ? heroShellClass(size) : widgetShellClass(size)
  return (
    <div className={shell}>
      <p className="text-muted-foreground shrink-0 truncate text-xs font-light tracking-wide">
        {label}
      </p>
      <ScrollArea className="min-h-0 flex-1">
        <div
          className={cn(
            'text-foreground pr-2 text-sm leading-relaxed whitespace-pre-wrap',
            size === 'sm' && 'text-[12px] leading-snug',
            !body && 'text-muted-foreground'
          )}
        >
          {body || empty}
        </div>
      </ScrollArea>
    </div>
  )
}
