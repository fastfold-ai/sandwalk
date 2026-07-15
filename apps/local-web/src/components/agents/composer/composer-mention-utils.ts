import type { AgentSkill, McpServer, Specialist } from '@sandwalk/agent-ui-core'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import {
  compareSkillsBySearchRank,
  skillMatchesSearch
} from '@/lib/skill-search'

export type SlashItem =
  | { kind: 'skill'; key: string; skill: AgentSkill }
  | { kind: 'mcp'; key: string; server: McpServer }

export function mcpSlashKey(server: McpServer): string {
  return `mcp:${server.id}`
}

export function mcpIconForServer(server: McpServer) {
  const key = String(server.catalogId || server.name || '')
    .trim()
    .toLowerCase()
  return INTEGRATION_ICONS[key] || null
}

export function mcpMatchesSearch(server: McpServer, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  const haystack = [
    server.name,
    server.description || '',
    server.catalogId || '',
    server.id,
    server.transport,
    server.url || ''
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(needle)
}

export function cleanSkillDescription(value: string | null | undefined) {
  const text = String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text || text === '>' || text === '-') return ''
  return text
}

export function buildSlashResults({
  slash,
  skills,
  mcpServers,
  selectedSpecialist
}: {
  slash: { query: string } | null
  skills: AgentSkill[]
  mcpServers: McpServer[]
  selectedSpecialist: Specialist | null
}): SlashItem[] {
  if (!slash) return []
  const query = slash.query.toLowerCase().trim()
  const specialistSkillSet = selectedSpecialist
    ? new Set(
        (selectedSpecialist.skillNames || [])
          .map(name => name.trim().toLowerCase())
          .filter(Boolean)
      )
    : null
  const specialistMcpIds = selectedSpecialist
    ? new Set(
        [
          ...(selectedSpecialist.mcpServerIds || []),
          ...(selectedSpecialist.mcpCatalogIds || [])
        ]
          .map(id => id.trim())
          .filter(Boolean)
      )
    : null

  const skillItems: SlashItem[] = []
  const seenSkills = new Set<string>()
  for (const skill of skills) {
    if (!skill.enabled) continue
    if (
      specialistSkillSet &&
      !specialistSkillSet.has(skill.name.trim().toLowerCase())
    ) {
      continue
    }
    const nameKey = skill.name.trim().toLowerCase()
    if (!nameKey || seenSkills.has(nameKey)) continue
    if (!skillMatchesSearch(skill, query)) continue
    seenSkills.add(nameKey)
    skillItems.push({
      kind: 'skill',
      key: `skill:${nameKey}`,
      skill
    })
  }
  skillItems.sort((a, b) =>
    a.kind === 'skill' && b.kind === 'skill'
      ? compareSkillsBySearchRank(a.skill, b.skill, query)
      : 0
  )

  const mcpItems: SlashItem[] = []
  const seenMcps = new Set<string>()
  for (const server of mcpServers) {
    if (!server.enabled) continue
    if (specialistMcpIds && specialistMcpIds.size > 0) {
      const catalogId = String(server.catalogId || '').trim()
      if (
        !specialistMcpIds.has(server.id) &&
        !(catalogId && specialistMcpIds.has(catalogId))
      ) {
        continue
      }
    }
    if (!mcpMatchesSearch(server, query)) continue
    const key = mcpSlashKey(server)
    if (seenMcps.has(key)) continue
    seenMcps.add(key)
    mcpItems.push({ kind: 'mcp', key, server })
  }
  mcpItems.sort((a, b) => {
    if (a.kind !== 'mcp' || b.kind !== 'mcp') return 0
    return a.server.name.localeCompare(b.server.name)
  })

  return [...skillItems, ...mcpItems]
}
