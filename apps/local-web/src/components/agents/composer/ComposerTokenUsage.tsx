import { formatTokenCount } from '@/components/agents/composer/sandbox-utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { formatContextWindow } from '@/lib/composer-models'

export function ComposerTokenUsage({
  tokenUsage,
  contextWindow
}: {
  tokenUsage: { inputTokens: number; outputTokens: number }
  contextWindow?: number | null
}) {
  const maxTokens =
    typeof contextWindow === 'number' && contextWindow > 0
      ? contextWindow
      : null
  const totalTokens = tokenUsage.inputTokens + tokenUsage.outputTokens
  const usagePercent =
    maxTokens != null ? Math.min(100, (totalTokens / maxTokens) * 100) : null

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="relative grid size-7 place-items-center rounded-full"
            aria-label="Context usage"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-5 -rotate-90"
              aria-hidden
            >
              <circle
                cx="12"
                cy="12"
                r="9"
                fill="none"
                stroke="hsl(var(--muted))"
                strokeWidth="2.5"
              />
              {usagePercent != null ? (
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  fill="none"
                  stroke="hsl(var(--foreground) / 0.7)"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeDasharray={`${usagePercent * 0.565} 56.5`}
                />
              ) : null}
            </svg>
          </button>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          sideOffset={10}
          className="rounded-lg px-3 py-2"
        >
          <div className="grid min-w-44 gap-1.5 text-xs">
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">Usage</span>
              <span className="font-mono tabular-nums">
                {usagePercent != null ? `${Math.round(usagePercent)}%` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">↑ Input</span>
              <span className="font-mono tabular-nums">
                {formatTokenCount(tokenUsage.inputTokens)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">↓ Output</span>
              <span className="font-mono tabular-nums">
                {formatTokenCount(tokenUsage.outputTokens)}
              </span>
            </div>
            <div className="border-border/60 mt-0.5 border-t pt-1.5">
              <div className="flex items-center justify-between gap-4">
                <span className="text-muted-foreground">Total</span>
                <span className="font-mono tabular-nums">
                  {formatTokenCount(totalTokens)}
                  {maxTokens != null
                    ? ` / ${formatContextWindow(maxTokens)}`
                    : ''}
                </span>
              </div>
              {maxTokens == null ? (
                <div className="text-muted-foreground/80 mt-1 text-[10px]">
                  Context limit unknown for this model
                </div>
              ) : null}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
