import type { AgentSkill } from '@fastfold/agent-ui-core'

const SKILL_ICON_BY_NAME: Record<string, string> = {
  boltz: '/pipelines/boltzgen.svg',
  diagrams_mermaid: '/mermaid-logo.png',
  slack_report: '/integrations/slack.png',
  md_openmm_calvados: '/models/openmm-seeklogo.svg',
  md_openmmdl: '/models/openmmdl.png'
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
  return SKILL_ICON_BY_NAME[skill.name] || null
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
