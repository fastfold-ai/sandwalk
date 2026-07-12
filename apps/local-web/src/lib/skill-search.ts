import type { AgentSkill } from '@sandwalk/agent-ui-core'

function cleanSkillDescription(value: string | null | undefined) {
  const text = String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text || text === '>' || text === '-') return ''
  return text
}

/** Lower is better. 5+ means no match. */
export function skillSearchMatchRank(
  skill: Pick<AgentSkill, 'name' | 'description'>,
  query: string
): number {
  const normalizedQuery = String(query || '')
    .trim()
    .toLowerCase()
  if (!normalizedQuery) return 3
  const name = String(skill.name || '')
    .trim()
    .toLowerCase()
  const description = cleanSkillDescription(skill.description).toLowerCase()
  if (name === normalizedQuery) return 0
  if (name.startsWith(normalizedQuery)) return 1
  if (name.includes(normalizedQuery)) return 2
  if (description.startsWith(normalizedQuery)) return 3
  if (description.includes(normalizedQuery)) return 4
  return 5
}

export function skillMatchesSearch(
  skill: Pick<AgentSkill, 'name' | 'description'>,
  query: string
): boolean {
  const normalizedQuery = String(query || '')
    .trim()
    .toLowerCase()
  if (!normalizedQuery) return true
  return skillSearchMatchRank(skill, normalizedQuery) < 5
}

export function compareSkillsBySearchRank(
  a: Pick<AgentSkill, 'name' | 'description'>,
  b: Pick<AgentSkill, 'name' | 'description'>,
  query: string
): number {
  const rankDiff =
    skillSearchMatchRank(a, query) - skillSearchMatchRank(b, query)
  if (rankDiff !== 0) return rankDiff
  return String(a.name || '').localeCompare(String(b.name || ''))
}
