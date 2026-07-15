import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'

import { formatTokenCount } from '@/components/agents/composer/sandbox-utils'

export function ComposerTokenUsage({
  tokenUsage
}: {
  tokenUsage: { inputTokens: number; outputTokens: number }
}) {
  const usagePercent = Math.min(
    100,
    ((tokenUsage.inputTokens + tokenUsage.outputTokens) / 200_000) * 100
  )

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
                {Math.round(usagePercent)}%
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
                  {formatTokenCount(
                    tokenUsage.inputTokens + tokenUsage.outputTokens
                  )}{' '}
                  / 200k
                </span>
              </div>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
