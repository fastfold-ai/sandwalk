import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

import { OnboardingConfiguredToggle } from './onboarding-integrations-shared'

export function OnboardingIntegrationsFeaturedGrid({
  featured,
  selectedKey,
  onPick
}: {
  featured: IntegrationSummary[]
  selectedKey: string | null
  onPick: (item: IntegrationSummary) => void
}) {
  return (
    <section className="space-y-3">
      <p className="text-muted-foreground text-sm">Featured</p>
      {featured.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No featured integrations yet.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {featured.map(item => {
            const active = selectedKey === item.key
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onPick(item)}
                className={cn(
                  'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg border p-3 text-left transition-colors',
                  active
                    ? 'border-foreground bg-muted/40'
                    : 'border-transparent'
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <IntegrationIcon integration={item} />
                    <span className="truncate text-sm font-medium">
                      {item.name}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {item.category}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                    {item.description}
                  </p>
                </div>
                <div className="flex items-center pt-0.5">
                  <OnboardingConfiguredToggle
                    configured={item.configured}
                    name={item.name}
                  />
                </div>
              </button>
            )
          })}
        </div>
      )}
    </section>
  )
}
