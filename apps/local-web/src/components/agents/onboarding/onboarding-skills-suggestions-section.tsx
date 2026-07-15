import type { AgentSkillSource } from '@sandwalk/agent-ui-core'
import { Check, GitBranch } from 'lucide-react'

import {
  suggestionSourceIcon,
  suggestionSourceLabel
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import { OnboardingSkillToggle } from './onboarding-skills-shared'

export function OnboardingSkillsSuggestionsSection({
  suggestions,
  installedSuggestionSources,
  suggestionSelected,
  installBusy,
  onToggleSuggestion
}: {
  suggestions: AgentSkillSource[]
  installedSuggestionSources: Set<string>
  suggestionSelected: Record<string, boolean>
  installBusy: boolean
  onToggleSuggestion: (source: string) => void
}) {
  if (suggestions.length === 0) return null

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold tracking-tight">
          Community Skills
        </h3>
        <p className="text-muted-foreground text-xs">
          Add any skills you love
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {suggestions.map(item => {
          const alreadyInstalled = installedSuggestionSources.has(item.source)
          const on =
            alreadyInstalled || Boolean(suggestionSelected[item.source])
          const icon = suggestionSourceIcon(item)
          const toggle = () => {
            if (alreadyInstalled || installBusy) return
            onToggleSuggestion(item.source)
          }
          return (
            <div
              key={item.source}
              className={cn(
                'bg-background/60 flex items-start gap-3 rounded-lg border p-3',
                on && !alreadyInstalled && 'border-foreground bg-muted/40',
                alreadyInstalled && 'border-emerald-500/40 bg-emerald-500/5',
                !on && 'opacity-60'
              )}
            >
              {icon ? (
                <img
                  src={icon}
                  alt=""
                  className="mt-0.5 size-8 shrink-0 rounded object-contain"
                />
              ) : (
                <span className="bg-muted/30 text-muted-foreground mt-0.5 grid size-8 shrink-0 place-items-center rounded">
                  <GitBranch className="size-4" />
                </span>
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {suggestionSourceLabel(item)}
                </p>
                <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
                  {item.description}
                </p>
                <span className="text-muted-foreground mt-1 block truncate font-mono text-[11px]">
                  {item.source}
                </span>
                {alreadyInstalled ? (
                  <p className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                    <Check className="size-3" />
                    Installed
                  </p>
                ) : null}
              </div>
              {alreadyInstalled ? (
                <span
                  className="text-emerald-700 dark:text-emerald-300 mt-0.5 grid size-8 shrink-0 place-items-center"
                  title="Installed"
                >
                  <Check className="size-4" />
                </span>
              ) : (
                <OnboardingSkillToggle
                  enabled={on}
                  pending={installBusy}
                  label={`${on ? 'Exclude' : 'Include'} ${suggestionSourceLabel(item)}`}
                  onToggle={toggle}
                />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
