import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

export function IntegrationConfiguredToggle({
  configured,
  name
}: {
  configured: boolean
  name: string
}) {
  return (
    <span
      role="switch"
      aria-checked={configured}
      aria-label={`${name} ${configured ? 'configured' : 'not configured'}`}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        configured ? 'bg-black/75 dark:bg-zinc-300/50' : 'bg-zinc-200 dark:bg-zinc-700'
      )}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          configured ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </span>
  )
}

export function IntegrationCard({
  item,
  onSelect
}: {
  item: IntegrationSummary
  onSelect: (key: string) => void
}) {
  return (
    <div className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors">
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={() => onSelect(item.key)}
      >
        <div className="flex items-center gap-2">
          <IntegrationIcon integration={item} />
          <span className="truncate text-sm font-medium">{item.name}</span>
          <span className="text-muted-foreground text-xs">{item.category}</span>
        </div>
        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
          {item.description}
        </p>
      </button>
      <div className="flex items-center pt-0.5">
        <IntegrationConfiguredToggle
          configured={item.configured}
          name={item.name}
        />
      </div>
    </div>
  )
}

export const VERCEL_SETUP_RUN_COMMAND =
  'vercel login && vercel link && vercel env pull .env.local --environment=development'

export const VERCEL_SETUP_COMMANDS = [
  'cd "~/.sandwalk/vercel-integration"',
  'vercel login',
  'vercel link',
  'vercel env pull .env.local --environment=development'
]
