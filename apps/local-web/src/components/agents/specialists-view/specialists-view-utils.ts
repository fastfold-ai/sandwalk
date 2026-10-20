import type {
  Specialist,
  SpecialistColor,
  SpecialistIcon
} from '@sandwalk/agent-ui-core'

const FASTFOLD_SKILL_INSTALL_SOURCES: Record<string, string> = {
  fold: 'fastfold-ai/skills@skills/fold',
  boltz: 'fastfold-ai/skills@skills/boltz',
  protein_design_boltzgen: 'fastfold-ai/skills@skills/protein_design_boltzgen',
  md_openmm_calvados: 'fastfold-ai/skills@skills/md_openmm_calvados',
  md_openmmdl: 'fastfold-ai/skills@skills/md_openmmdl',
  diagrams_mermaid: 'fastfold-ai/skills@skills/diagrams_mermaid',
  slack_report: 'fastfold-ai/skills@skills/slack_report'
}

export function resolveSkillInstallSource(skillName: string): string | null {
  const name = skillName.trim()
  if (!name) return null
  if (FASTFOLD_SKILL_INSTALL_SOURCES[name]) {
    return FASTFOLD_SKILL_INSTALL_SOURCES[name]
  }
  // Common third-party catalog layouts used by installed science skills.
  if (name.includes('_') || name.includes('-')) {
    return `K-Dense-AI/scientific-agent-skills@${name}`
  }
  return null
}

export function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export type SpecialistFormState = {
  name: string
  slug: string
  description: string
  instructions: string
  color: SpecialistColor
  icon: SpecialistIcon
  skillNames: string[]
  toolNames: string[]
  mcpServerIds: string[]
  mcpCatalogIds: string[]
  enabled: boolean
}

export function emptySpecialistForm(): SpecialistFormState {
  return {
    name: '',
    slug: '',
    description: '',
    instructions: '',
    color: 'ink',
    icon: 'capybara',
    skillNames: [],
    toolNames: [],
    mcpServerIds: [],
    mcpCatalogIds: [],
    enabled: true
  }
}

export function specialistFormFromRecord(specialist: Specialist): SpecialistFormState {
  return {
    name: specialist.name,
    slug: specialist.slug,
    description: specialist.description || '',
    instructions: specialist.instructions || '',
    color: (specialist.color as SpecialistColor) || 'ink',
    icon: (specialist.icon as SpecialistIcon) || 'git-branch',
    skillNames: [...(specialist.skillNames || [])],
    toolNames: [...(specialist.toolNames || [])],
    mcpServerIds: [...(specialist.mcpServerIds || [])],
    mcpCatalogIds: [...(specialist.mcpCatalogIds || [])],
    enabled: specialist.enabled !== false
  }
}

export type SpecialistCapabilityIssue = {
  kind: 'skill' | 'mcp'
  name: string
  detail: string
}

export function specialistFieldClassName() {
  return 'border-border/50 bg-muted/40 placeholder:text-muted-foreground focus-visible:ring-ring h-10 w-full rounded-xl border-0 px-3.5 text-sm outline-none focus-visible:ring-1'
}
