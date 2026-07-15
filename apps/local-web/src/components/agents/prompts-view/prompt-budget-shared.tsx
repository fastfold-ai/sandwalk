import type {
  PromptBudgetBucket,
  PromptBudgetResponse,
  Specialist
} from '@sandwalk/agent-ui-core'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

export const BUCKET_COLORS = [
  'bg-sky-500',
  'bg-violet-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-indigo-500',
  'bg-teal-500'
]

/** Survive route unmount so switching dashboard tabs does not force a full re-estimate. */
export type PromptBudgetCache = {
  specialistId: string
  specialists: Specialist[]
  budget: PromptBudgetResponse
  at: number
}

export let promptBudgetCache: PromptBudgetCache | null = null
export const PROMPT_BUDGET_CACHE_TTL_MS = 5 * 60 * 1000

export function writePromptBudgetCache(cache: PromptBudgetCache) {
  promptBudgetCache = cache
}

export function patchPromptBudgetSpecialists(specialists: Specialist[]) {
  if (!promptBudgetCache) return
  promptBudgetCache = { ...promptBudgetCache, specialists }
}

export function formatTokens(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 10_000) return `${Math.round(value / 1000)}k`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
  return String(value)
}

export function PromptBucketRow({
  bucket,
  totalTokens,
  depth = 0,
  colorIndex = 0
}: {
  bucket: PromptBudgetBucket
  totalTokens: number
  depth?: number
  colorIndex?: number
}) {
  const [open, setOpen] = useState(depth === 0)
  const hasChildren = (bucket.children?.length || 0) > 0
  const share =
    totalTokens > 0 ? Math.max(0, (bucket.tokens / totalTokens) * 100) : 0
  const color = BUCKET_COLORS[colorIndex % BUCKET_COLORS.length]

  return (
    <div className="space-y-1">
      <button
        type="button"
        className={cn(
          'hover:bg-muted/40 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors',
          depth > 0 && 'opacity-90'
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => {
          if (hasChildren) setOpen(current => !current)
        }}
        disabled={!hasChildren}
      >
        {hasChildren ? (
          <ChevronDown
            className={cn(
              'text-muted-foreground size-3.5 shrink-0 transition-transform',
              !open && '-rotate-90'
            )}
          />
        ) : (
          <span className="size-3.5 shrink-0" />
        )}
        <span className={cn('size-2 shrink-0 rounded-full', color)} />
        <span className="min-w-0 flex-1 truncate text-sm">{bucket.label}</span>
        {bucket.count != null ? (
          <span className="text-muted-foreground shrink-0 text-xs">
            ×{bucket.count}
          </span>
        ) : null}
        <span className="text-muted-foreground shrink-0 font-mono text-xs">
          {formatTokens(bucket.tokens)}
        </span>
        <span className="text-muted-foreground/70 w-10 shrink-0 text-right text-xs">
          {share.toFixed(0)}%
        </span>
      </button>
      {hasChildren && open
        ? bucket.children.map(child => (
            <PromptBucketRow
              key={child.id}
              bucket={child}
              totalTokens={totalTokens}
              depth={depth + 1}
              colorIndex={colorIndex}
            />
          ))
        : null}
    </div>
  )
}
