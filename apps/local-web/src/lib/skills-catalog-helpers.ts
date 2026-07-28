import type {
  AccountSummary,
  AgentSkill,
  AgentSkillSource,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'

export function isUserCreatedSkill(skill: AgentSkill): boolean {
  const category = String(skill.category || '').trim().toLowerCase()
  if (
    category === 'created by me' ||
    category === 'custom' ||
    category === 'user'
  ) {
    return true
  }
  const source = String(skill.source || '').trim().toLowerCase()
  if (source === 'custom' || source.startsWith('custom:')) return true
  if (
    source.startsWith('/') ||
    source.startsWith('~') ||
    source.includes('skill-drafts') ||
    source.includes('/workspaces/')
  ) {
    return true
  }
  return false
}

export function categorizeSkill(skill: AgentSkill) {
  if (isUserCreatedSkill(skill)) return 'Created by Me'
  const source = String(skill.source || '').trim().toLowerCase()
  const category = String(skill.category || '').trim().toLowerCase()
  if (source === 'bundled' || category === 'built-in') return 'Built-in'
  const name = skill.name.toLowerCase()
  if (name === 'fold' || name === 'boltz-structure-and-binding')
    return 'Structure Prediction'
  if (
    name.includes('md_') ||
    name.includes('openmm') ||
    name.includes('calvados')
  ) {
    return 'Molecular Dynamics'
  }
  if (
    name === 'boltz' ||
    name.includes('design') ||
    name.includes('boltzgen') ||
    name.startsWith('boltz-protein-')
  ) {
    return 'Protein Design'
  }
  if (name.startsWith('boltz-small-molecule-')) return 'Small Molecules'
  if (
    name.includes('setup') ||
    name.includes('integration') ||
    name.includes('slack') ||
    name.includes('report')
  ) {
    return 'Integrations'
  }
  return skill.tags[0] || 'Utilities'
}

export function isFeaturedIntegration(integration: IntegrationSummary) {
  const key = integration.key.toLowerCase()
  return (
    key === 'skills-sh' ||
    key === 'boltz' ||
    key === 'fastfold-cloud' ||
    key === 'slack'
  )
}

export function stripFrontmatter(content: string) {
  return content.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, '')
}

export function frontmatterValue(content: string, key: string): string | null {
  const match = content.match(new RegExp(`^${key}:\\s*(.+)$`, 'im'))
  if (!match?.[1]) return null
  return match[1].trim().replace(/^['"]|['"]$/g, '') || null
}

export function auditStatusBadgeClass(status: string): string {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'pass') {
    return 'border-emerald-300/70 bg-emerald-500/10 text-emerald-700 dark:border-emerald-600/60 dark:bg-emerald-500/15 dark:text-emerald-300'
  }
  if (normalized === 'warn') {
    return 'border-amber-300/70 bg-amber-500/10 text-amber-700 dark:border-amber-600/60 dark:bg-amber-500/15 dark:text-amber-300'
  }
  if (normalized === 'fail') {
    return 'border-red-300/70 bg-red-500/10 text-red-700 dark:border-red-600/60 dark:bg-red-500/15 dark:text-red-300'
  }
  return 'border-border/70 bg-muted/40 text-muted-foreground'
}

export function skillMetaText(skill: AgentSkill): string | null {
  const parts: string[] = []
  const author = skill.author.trim()
  if (author) parts.push(author)
  if (skill.version) parts.push(`v${skill.version.replace(/^v/i, '')}`)
  const source = String(skill.source || '').trim().toLowerCase()
  if (source === 'bundled') {
    parts.push('Built-in')
    return parts.join(' · ')
  }
  if (skill.updateAvailable && skill.latestVersion) {
    const latest = String(skill.latestVersion)
    const label =
      skill.updateChannel === 'commit' || /^[0-9a-f]{7,40}$/i.test(latest)
        ? latest.slice(0, 7)
        : latest
    parts.push(`→ ${label}`)
  }
  return parts.length > 0 ? parts.join(' · ') : null
}

export function skillAuthorLabel(skill: AgentSkill): string {
  const author = String(skill.author || '').trim()
  return author || 'Unknown'
}

export function suggestionSourceIcon(item: AgentSkillSource): string | null {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').toLowerCase()
  if (source.includes('fastfold-ai') || provider.includes('fastfold')) {
    return '/ff_simbol_color.svg'
  }
  if (source.includes('k-dense-ai') || provider.includes('k-dense')) {
    return '/suggestions/k-dense.png'
  }
  if (source.includes('google-deepmind') || provider.includes('deepmind')) {
    return '/suggestions/deepmind.png'
  }
  if (source.includes('anthropic') || provider.includes('anthropic')) {
    return '/suggestions/anthropic-claude.png'
  }
  if (
    source.includes('huggingface') ||
    provider.includes('hugging face') ||
    provider.includes('huggingface')
  ) {
    return '/suggestions/huggingface.png'
  }
  return null
}

export function suggestionSourceLabel(item: AgentSkillSource): string {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').trim()
  if (source.includes('fastfold-ai') || provider.toLowerCase().includes('fastfold')) {
    return 'Fastfold AI'
  }
  if (source.includes('anthropic') || provider.toLowerCase().includes('anthropic')) {
    return 'Anthropic Claude'
  }
  if (
    source.includes('huggingface') ||
    provider.toLowerCase().includes('hugging face')
  ) {
    return 'Hugging Face'
  }
  return provider || item.source
}

export type SkillsViewMode =
  | 'list'
  | 'detail'
  | 'catalog_detail'
  | 'import_github'
  | 'import_file'
  | 'trusted_sources'

/** Prefer username; fall back to linked Fastfold Cloud email. */
export function cloudAccountDisplayName(account: AccountSummary | null): string | null {
  if (!account?.configured) return null
  const username = account.user?.username?.trim()
  if (username) return username
  const email = account.user?.email?.trim()
  if (email) return email
  return null
}
