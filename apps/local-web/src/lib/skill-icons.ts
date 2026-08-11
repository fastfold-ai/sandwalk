import type { AgentSkill } from '@sandwalk/agent-ui-core'

const SANDWALK_MARK = '/sandwalk-mark.svg'

/** Explicit featured names (includes non-FastFold sources like Firecrawl anydoc). */
const FEATURED_SKILL_NAMES = new Set([
  'fold',
  'boltz',
  'protein_design_boltzgen',
  'md_openmm_calvados',
  'md_openmmdl',
  'diagrams_mermaid',
  'slack_report',
  'convert-documents-to-markdown',
  'modal-basic-skills',
  'modal-gpu-dev',
  'modal-gpu-experiment',
  'sub-agents'
])

const SKILL_ICON_BY_NAME: Record<
  string,
  { src: string; invertInDark?: boolean }
> = {
  boltz: { src: '/pipelines/boltzgen.svg', invertInDark: true },
  diagrams_mermaid: { src: '/mermaid-logo.png' },
  slack_report: { src: '/integrations/slack.png' },
  md_openmm_calvados: { src: '/models/openmm-seeklogo.svg' },
  md_openmmdl: { src: '/models/openmmdl.png' },
  'convert-documents-to-markdown': {
    src: '/integrations/firecrawl.png'
  },
  'modal-basic-skills': { src: '/modal-logo-icon.png' },
  'modal-gpu-dev': { src: '/modal-logo-icon.png' },
  'modal-gpu-experiment': { src: '/modal-logo-icon.png' },
  'sub-agents': { src: '/modal-logo-icon.png' },
  'skill-creator': { src: SANDWALK_MARK, invertInDark: true },
  'skill-find': { src: SANDWALK_MARK, invertInDark: true }
}

function isBundledSkill(
  skill: Partial<Pick<AgentSkill, 'author' | 'source'>>
): boolean {
  const author = String(skill.author || '').toLowerCase()
  const source = String(skill.source || '').toLowerCase()
  return source === 'bundled' || author === 'sandwalk'
}

export function isFeaturedSkill(
  skill: Pick<AgentSkill, 'name' | 'author' | 'source'>
): boolean {
  const name = String(skill.name || '').trim()
  if (FEATURED_SKILL_NAMES.has(name)) return true
  const author = String(skill.author || '').toLowerCase()
  const source = String(skill.source || '').toLowerCase()
  return (
    author.includes('fastfold') ||
    author === 'sandwalk' ||
    author.includes('firecrawl') ||
    source === 'bundled' ||
    source.includes('fastfold-ai') ||
    source.includes('firecrawl/anydoc') ||
    source.includes('modal-projects/modal-auto-research-skills')
  )
}

function inferredSkillIcon(
  skill: Pick<AgentSkill, 'name'> &
    Partial<Pick<AgentSkill, 'author' | 'source'>>
): string | null {
  const name = String(skill.name || '').trim().toLowerCase()
  const author = String(skill.author || '').trim().toLowerCase()
  const source = String(skill.source || '').trim().toLowerCase()
  if (
    name.startsWith('hf-') ||
    name.includes('huggingface') ||
    author.includes('hugging face') ||
    author.includes('huggingface') ||
    source.includes('huggingface')
  ) {
    return '/integrations/huggingface.png'
  }
  if (isBundledSkill(skill)) return SANDWALK_MARK
  return null
}

export function skillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'> &
    Partial<Pick<AgentSkill, 'author' | 'source'>>
): string | null {
  const custom = String(skill.iconSrc || '').trim()
  if (custom) return custom
  return SKILL_ICON_BY_NAME[skill.name]?.src || inferredSkillIcon(skill)
}

/** Match Integrations: invert dark logos (e.g. Boltz) in dark mode. */
export function skillIconInvertInDark(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'> &
    Partial<Pick<AgentSkill, 'author' | 'source'>>
): boolean {
  if (String(skill.iconSrc || '').trim()) return false
  if (SKILL_ICON_BY_NAME[skill.name]?.invertInDark) return true
  return isBundledSkill(skill)
}

export function featuredSkillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'> &
    Partial<Pick<AgentSkill, 'author' | 'source'>>
): string {
  return skillIcon(skill) || '/ff_simbol_color.svg'
}

export function composerSkillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc' | 'author' | 'source'>
): string | null {
  return skillIcon(skill) || (isFeaturedSkill(skill) ? '/ff_simbol_color.svg' : null)
}

/** Resolve a chip/message icon when only the skill name is available. */
export function skillIconForName(
  name: string,
  skills?: Array<Pick<AgentSkill, 'name' | 'iconSrc' | 'author' | 'source'>>
): string | null {
  const needle = name.trim().toLowerCase()
  const match = skills?.find(
    skill => skill.name.trim().toLowerCase() === needle
  )
  if (match) return composerSkillIcon(match)
  return skillIcon({ name, iconSrc: null })
}
