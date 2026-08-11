import type { AgentPlanCard } from '@sandwalk/agent-ui-core'

import { planModeAccent } from '@/components/agents/composer/ComposerModeMenu'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function CreatedPlanCard({
  plan,
  onViewPlan,
  onBuild,
  className
}: {
  plan: AgentPlanCard
  onViewPlan: (path: string) => void
  onBuild: (plan: AgentPlanCard) => void
  className?: string
}) {
  return (
    <div
      className={cn(
        'border-border/70 bg-muted/15 space-y-3 rounded-xl border p-4',
        className
      )}
    >
      <div className="space-y-1">
        <p className="text-muted-foreground text-xs font-medium">Created Plan</p>
        <h3 className="text-foreground text-base font-semibold leading-snug">
          {plan.title || 'Plan'}
        </h3>
        {plan.summary ? (
          <p className="text-muted-foreground text-sm leading-6">{plan.summary}</p>
        ) : null}
      </div>
      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground text-sm font-medium"
          onClick={() => onViewPlan(plan.path)}
        >
          View Plan
        </button>
        <Button
          type="button"
          size="sm"
          className={cn(
            'h-7 rounded-full px-3 text-xs font-medium shadow-none',
            planModeAccent.send
          )}
          onClick={() => onBuild(plan)}
        >
          Build
        </Button>
      </div>
    </div>
  )
}
