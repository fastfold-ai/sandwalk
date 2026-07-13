import type { AgentSkill } from '@sandwalk/agent-ui-core'

const SKILL_ICON_BY_NAME: Record<
  string,
  { src: string; invertInDark?: boolean }
> = {
  boltz: { src: '/pipelines/boltzgen.svg', invertInDark: true },
  diagrams_mermaid: { src: '/mermaid-logo.png' },
  slack_report: { src: '/integrations/slack.png' },
  md_openmm_calvados: { src: '/models/openmm-seeklogo.svg' },
  md_openmmdl: { src: '/models/openmmdl.png' }
}

export function isFeaturedSkill(
  skill: Pick<AgentSkill, 'name' | 'author' | 'source'>
): boolean {
  const author = String(skill.author || '').toLowerCase()
  const source = String(skill.source || '').toLowerCase()
  return (
    author.includes('fastfold') ||
    source === 'bundled' ||
    source.includes('fastfold-ai')
  )
}

export function skillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'>
): string | null {
  const custom = String(skill.iconSrc || '').trim()
  if (custom) return custom
  return SKILL_ICON_BY_NAME[skill.name]?.src || null
}

/** Match Integrations: invert dark logos (e.g. Boltz) in dark mode. */
export function skillIconInvertInDark(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'>
): boolean {
  if (String(skill.iconSrc || '').trim()) return false
  return Boolean(SKILL_ICON_BY_NAME[skill.name]?.invertInDark)
}

export function featuredSkillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc'>
): string {
  return skillIcon(skill) || '/ff_simbol_color.svg'
}

export function composerSkillIcon(
  skill: Pick<AgentSkill, 'name' | 'iconSrc' | 'author' | 'source'>
): string | null {
  return skillIcon(skill) || (isFeaturedSkill(skill) ? '/ff_simbol_color.svg' : null)
}
