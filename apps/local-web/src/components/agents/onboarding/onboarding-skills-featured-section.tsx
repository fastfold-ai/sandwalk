import type { AgentSkill } from '@sandwalk/agent-ui-core'

import {
  featuredSkillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

import {
  FEATURED_SKILL_CATALOG,
  OnboardingFeaturedSkillCard,
  OnboardingSkillToggle
} from './onboarding-skills-shared'

export function OnboardingSkillsFeaturedSection({
  hasFeaturedInstalled,
  featuredInstalled,
  pendingEnabled,
  installedNames,
  selected,
  onSetEnabled,
  onToggleSelected
}: {
  hasFeaturedInstalled: boolean
  featuredInstalled: AgentSkill[]
  pendingEnabled: Record<string, boolean>
  installedNames: Set<string>
  selected: Record<string, boolean>
  onSetEnabled: (name: string, enabled: boolean) => void
  onToggleSelected: (name: string) => void
}) {
  return (
    <section className="space-y-3">
      <p className="text-muted-foreground text-sm">Featured</p>

      {hasFeaturedInstalled ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {featuredInstalled.map(skill => (
            <OnboardingFeaturedSkillCard
              key={skill.name}
              skill={skill}
              pending={pendingEnabled[skill.name]}
              onToggle={() => void onSetEnabled(skill.name, !skill.enabled)}
            />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {FEATURED_SKILL_CATALOG.map(item => {
            const on = Boolean(selected[item.name])
            const already = installedNames.has(item.name)
            const iconSource = featuredSkillIcon({
              name: item.name,
              iconSrc: null
            })
            return (
              <div
                key={item.name}
                className={cn(
                  'bg-background/60 flex items-start justify-between gap-3 rounded-lg border p-3',
                  !on && 'opacity-60'
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <img
                      src={iconSource}
                      alt=""
                      className={cn(
                        'size-7 rounded object-contain',
                        skillIconInvertInDark({
                          name: item.name,
                          iconSrc: null
                        }) && 'dark:invert'
                      )}
                    />
                    <span className="truncate text-sm font-medium">
                      {item.name}
                    </span>
                  </div>
                  <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
                    {item.description}
                  </p>
                  {already ? (
                    <p className="text-muted-foreground mt-1 text-[11px]">
                      Already installed
                    </p>
                  ) : null}
                </div>
                <OnboardingSkillToggle
                  enabled={on}
                  label={`${on ? 'Exclude' : 'Include'} ${item.name}`}
                  onToggle={() => onToggleSelected(item.name)}
                />
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
