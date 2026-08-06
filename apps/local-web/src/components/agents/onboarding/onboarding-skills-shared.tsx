import type { AgentSkill } from '@sandwalk/agent-ui-core'

import {
  featuredSkillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

export const DEFAULT_SKILLS_REPO = 'fastfold-ai/skills'

/** Featured FastFold skills shown before install (matches catalog names). */
export const FEATURED_SKILL_CATALOG: Array<{
  name: string
  description: string
  source: string
}> = [
  {
    name: 'fold',
    description: 'Protein structure prediction with FastFold Cloud jobs.',
    source: 'fastfold-ai/skills@skills/fold'
  },
  {
    name: 'boltz',
    description: 'Boltz structure prediction workflows.',
    source: 'fastfold-ai/skills@skills/boltz'
  },
  {
    name: 'protein_design_boltzgen',
    description: 'Protein design with BoltzGen.',
    source: 'fastfold-ai/skills@skills/protein_design_boltzgen'
  },
  {
    name: 'md_openmm_calvados',
    description: 'Molecular dynamics with OpenMM / CALVADOS.',
    source: 'fastfold-ai/skills@skills/md_openmm_calvados'
  },
  {
    name: 'md_openmmdl',
    description: 'MD analysis with OpenMMDL.',
    source: 'fastfold-ai/skills@skills/md_openmmdl'
  },
  {
    name: 'diagrams_mermaid',
    description: 'Diagrams and flowcharts with Mermaid.',
    source: 'fastfold-ai/skills@skills/diagrams_mermaid'
  },
  {
    name: 'slack_report',
    description: 'Share research updates to Slack.',
    source: 'fastfold-ai/skills@skills/slack_report'
  },
  {
    name: 'convert-documents-to-markdown',
    description:
      'Convert Word, PowerPoint, Excel, PDF, and more to Markdown (anydoc).',
    source: 'firecrawl/anydoc'
  }
]

export function OnboardingSkillToggle({
  enabled,
  pending,
  label,
  onToggle
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

export function OnboardingFeaturedSkillCard({
  skill,
  pending,
  onToggle
}: {
  skill: AgentSkill
  pending?: boolean
  onToggle: () => void
}) {
  const iconSource = featuredSkillIcon(skill)
  return (
    <div
      className={cn(
        'bg-background/60 flex items-start justify-between gap-3 rounded-lg border p-3',
        !skill.enabled && 'opacity-60'
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <img
            src={iconSource}
            alt=""
            className={cn(
              'size-7 rounded object-contain',
              skillIconInvertInDark(skill) && 'dark:invert'
            )}
          />
          <span className="truncate text-sm font-medium">{skill.name}</span>
        </div>
        {skill.description ? (
          <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
            {skill.description}
          </p>
        ) : null}
      </div>
      <OnboardingSkillToggle
        enabled={skill.enabled}
        pending={pending}
        label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.name}`}
        onToggle={onToggle}
      />
    </div>
  )
}
