import type { PromptBudgetResponse, Specialist } from '@sandwalk/agent-ui-core'
import { AlertTriangle, Loader } from 'lucide-react'

import { SpecialistAvatar } from '@/components/agents/SpecialistsView'
import { cn } from '@/lib/utils'

import {
  BUCKET_COLORS,
  formatTokens,
  PromptBucketRow,
  type TokenCountMethod
} from './prompt-budget-shared'

export function PromptBudgetResults({
  budget,
  selectedSpecialist,
  isEstimating,
  tokenCountMethod,
  onTokenCountMethodChange,
  countingDisabled = false
}: {
  budget: PromptBudgetResponse
  selectedSpecialist: Specialist | null
  isEstimating: boolean
  tokenCountMethod: TokenCountMethod
  onTokenCountMethodChange: (method: TokenCountMethod) => void
  countingDisabled?: boolean
}) {
  const toolCounts = budget.toolCounts
  const cap = toolCounts?.openaiCap || 128
  const totalTools = toolCounts?.total || 0
  const toolShare = Math.min(100, (totalTools / Math.max(cap, 1)) * 100)

  const stacked = (budget.buckets || []).map((bucket, index) => ({
    id: bucket.id,
    label: bucket.label,
    tokens: bucket.tokens,
    share:
      (bucket.tokens / Math.max(budget.totalTokens || 0, 1)) * 100,
    color: BUCKET_COLORS[index % BUCKET_COLORS.length]
  }))

  return (
    <div className="relative space-y-8">
      {isEstimating ? (
        <div className="bg-background/70 absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 rounded-xl backdrop-blur-[2px]">
          <Loader className="size-5 animate-spin" />
          <div className="text-center">
            <p className="text-sm font-medium">
              Recalculating input token estimate
            </p>
            <p className="text-muted-foreground mt-1 text-xs">
              {selectedSpecialist
                ? `Updating for ${selectedSpecialist.name}…`
                : 'Updating for default runtime…'}
            </p>
          </div>
        </div>
      ) : null}

      <div
        className={cn(
          'space-y-8 transition-opacity',
          isEstimating && 'pointer-events-none opacity-40'
        )}
        aria-busy={isEstimating}
      >
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-muted-foreground text-xs uppercase tracking-wide">
                Input token context
              </p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">
                {formatTokens(budget.totalTokens)}
              </p>
              <p className="text-muted-foreground mt-1 text-xs">
                {budget.totalChars.toLocaleString()} chars · {budget.tokenizer}
                {budget.toolMode ? ` · ${budget.toolMode}` : ''}
                {budget.model ? ` · ${budget.model}` : ''}
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div
                className="bg-muted/40 flex rounded-lg p-0.5"
                role="group"
                aria-label="Token counting method"
              >
                {(
                  [
                    { id: 'tiktoken', label: 'tiktoken' },
                    { id: 'provider', label: 'Provider' }
                  ] as const
                ).map(option => {
                  const active = tokenCountMethod === option.id
                  return (
                    <button
                      key={option.id}
                      type="button"
                      disabled={countingDisabled}
                      className={cn(
                        'rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
                        active
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      )}
                      onClick={() => onTokenCountMethodChange(option.id)}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>
              {selectedSpecialist ? (
                <div className="text-muted-foreground flex items-center gap-2 text-xs">
                  <SpecialistAvatar
                    color={selectedSpecialist.color}
                    icon={selectedSpecialist.icon}
                    className="size-6 rounded-md"
                  />
                  <span className="truncate">{selectedSpecialist.name}</span>
                </div>
              ) : null}
            </div>
          </div>

          <div className="bg-muted/15 flex h-3 overflow-hidden rounded-full">
            {stacked.map(slice => (
              <div
                key={slice.id}
                className={cn(slice.color, 'h-full')}
                style={{ width: `${Math.max(slice.share, 0.4)}%` }}
                title={`${slice.label}: ${formatTokens(slice.tokens)}`}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {stacked.map(slice => (
              <div
                key={slice.id}
                className="text-muted-foreground flex items-center gap-1.5 text-xs"
              >
                <span className={cn('size-2 rounded-full', slice.color)} />
                {slice.label}
              </div>
            ))}
          </div>
        </section>

        {toolCounts ? (
          <section className="space-y-3 rounded-xl border px-4 py-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">Tool counts</h3>
              <span
                className={cn(
                  'font-mono text-xs',
                  totalTools > cap
                    ? 'text-amber-600 dark:text-amber-300'
                    : 'text-muted-foreground'
                )}
              >
                {totalTools} / {cap}
              </span>
            </div>
            <div className="bg-muted/15 h-2 overflow-hidden rounded-full">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  totalTools > cap ? 'bg-amber-500/80' : 'bg-sky-500/80'
                )}
                style={{ width: `${toolShare}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {(
                [
                  ['Domain', toolCounts.domain],
                  ['MCP', toolCounts.mcp],
                  ['DeepAgents', toolCounts.deepagents],
                  ['Total', toolCounts.total]
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="bg-muted/15 rounded-lg px-3 py-2">
                  <p className="text-muted-foreground text-[11px]">{label}</p>
                  <p className="mt-0.5 font-mono text-sm font-medium">{value}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="space-y-2">
          <h3 className="text-sm font-semibold">Distribution</h3>
          <div className="divide-border/50 divide-y rounded-xl border">
            {(budget.buckets || []).map((bucket, index) => (
              <PromptBucketRow
                key={bucket.id}
                bucket={bucket}
                totalTokens={budget.totalTokens}
                colorIndex={index}
              />
            ))}
          </div>
        </section>

        {budget.warnings.length > 0 ? (
          <section className="border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-100 space-y-2 rounded-xl border px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className="size-4 shrink-0" />
              Warnings
            </div>
            <ul className="text-amber-800/90 dark:text-amber-200/90 list-disc space-y-1 pl-5 text-xs">
              {budget.warnings.map(warning => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  )
}
