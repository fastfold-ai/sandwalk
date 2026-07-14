import type {
  AccountSummary,
  AgentCatalogSkill,
  AgentSkill,
  AgentSkillSource,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'

export function categorizeSkill(skill: AgentSkill) {
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
    key === 'openai'
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
  return parts.length > 0 ? parts.join(' · ') : null
}

export function skillAuthorLabel(skill: AgentSkill): string {
  const author = String(skill.author || '').trim()
  return author || 'Unknown'
}

export function suggestionSourceIcon(item: AgentSkillSource): string | null {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').toLowerCase()
  if (source.includes('k-dense-ai') || provider.includes('k-dense')) {
    return '/suggestions/k-dense.png'
  }
  if (source.includes('google-deepmind') || provider.includes('deepmind')) {
    return '/suggestions/deepmind.png'
  }
  if (source.includes('anthropic') || provider.includes('anthropic')) {
    return '/suggestions/anthropic-claude.png'
  }
  return null
}

export function suggestionSourceLabel(item: AgentSkillSource): string {
  const source = String(item.source || '').toLowerCase()
  const provider = String(item.provider || '').trim()
  if (source.includes('anthropic') || provider.toLowerCase().includes('anthropic')) {
    return 'Anthropic Claude'
  }
  return provider || item.source
}

export function catalogSkillInstallSource(skill: AgentCatalogSkill): string {
  const installUrl = String(skill.installUrl || '').trim()
  if (installUrl) return installUrl
  const source = String(skill.source || '').trim()
  if (/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(source)) {
    return `https://github.com/${source}`
  }
  return source
}

export function parseCatalogSkillId(raw: string | null | undefined): {
  id: string
  source: string
  skill: string
} | null {
  const decoded = String(raw || '')
    .trim()
    .replaceAll('~', '/')
  if (!decoded) return null
  const parts = decoded.split('/').filter(Boolean)
  if (parts.length < 2) return null
  const skill = parts.pop() || ''
  const source = parts.join('/')
  if (!source || !skill) return null
  return { id: `${source}/${skill}`, source, skill }
}

export function catalogSkillInstallCommand(
  source: string,
  skill: string,
  files?: Array<{ path: string }> | null
): string {
  // Match `sandwalk skills add <source>` — CLI has no --skill flag; use @subpath.
  const target = catalogSkillInstallTarget(source, skill, files)
  return target ? `sandwalk skills add ${target}` : ''
}

export function catalogSkillInstallTarget(
  source: string,
  skill: string,
  files?: Array<{ path: string }> | null
): string {
  const normalizedSource = String(source || '').trim()
  const normalizedSkill = String(skill || '').trim()
  if (!normalizedSource) return ''
  if (!OWNER_REPO_RE.test(normalizedSource)) {
    return normalizedSource
  }
  // Skills.sh file paths are often skill-relative (just "SKILL.md"), not repo-rooted.
  // Only use them when they include a real directory (e.g. skills/.curated/linear/SKILL.md).
  const skillMdPath = (files || [])
    .map(file => String(file.path || '').trim().replace(/^\/+/, ''))
    .find(path => /(^|\/)skill\.md$/i.test(path))
  if (skillMdPath && skillMdPath.includes('/')) {
    const dir = skillMdPath.replace(/\/[^/]+$/u, '').replace(/^\/+/, '')
    if (dir && !/^skill\.md$/i.test(dir)) {
      return `${normalizedSource}@${dir}`
    }
  }
  if (!normalizedSkill) return normalizedSource
  // CLI-compatible shorthand; nested layouts resolve by skill folder name.
  return `${normalizedSource}@skills/${normalizedSkill}`
}

export function formatSkillInstallError(error: unknown): string {
  const raw =
    error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : 'Unable to install this skill.'
  const detailMatch = raw.match(/\{.*"detail"\s*:\s*"((?:\\.|[^"\\])*)"/s)
  const detail = (detailMatch?.[1] || raw)
    .replace(/\\"/g, '"')
    .replace(/^FastFold Agent API \d+:\s*/i, '')
    .replace(/^"|"$/g, '')
    .trim()
  const lower = detail.toLowerCase()
  if (
    lower.includes('removed or moved') ||
    lower.includes('skills.sh listing') ||
    lower.includes('unavailable')
  ) {
    return detail
  }
  if (
    lower.includes('no skill.md') ||
    lower.includes('not found') ||
    lower.includes('could not find')
  ) {
    return (
      `${detail} ` +
      'Skills.sh may still list it, but the skill is unavailable or was removed/moved in the source repository.'
    )
  }
  return detail || 'Unable to install this skill from Skills.sh.'
}

export function normalizeSkillMatchKey(raw: string | null | undefined): string {
  return String(raw || '')
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export const DEFAULT_SKILLS_REPO = 'fastfold-ai/skills'
export const OWNER_REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/

export function splitSkillSourceSpec(
  rawSource: string | null | undefined
): { ownerRepo: string; skillsPath: string } | null {
  const source = String(rawSource || '').trim()
  if (!source || source === 'bundled') {
    return { ownerRepo: DEFAULT_SKILLS_REPO, skillsPath: 'skills' }
  }
  if (source.startsWith('https://github.com/')) {
    try {
      const url = new URL(source)
      const parts = url.pathname.replace(/^\/+/, '').split('/').filter(Boolean)
      if (parts.length < 2) return null
      const ownerRepo = `${parts[0]}/${parts[1].replace(/\.git$/i, '')}`
      let skillsPath = 'skills'
      const treeIndex = parts.indexOf('tree')
      if (treeIndex >= 0 && parts.length > treeIndex + 3) {
        const pathFromTree = parts.slice(treeIndex + 3).join('/').trim()
        if (pathFromTree) skillsPath = pathFromTree
      }
      return { ownerRepo, skillsPath }
    } catch {
      return null
    }
  }
  const [ownerRepoRaw, pathRaw] = source.split('@', 2)
  const ownerRepo = ownerRepoRaw.trim()
  if (!OWNER_REPO_RE.test(ownerRepo)) return null
  const skillsPath =
    String(pathRaw || 'skills').trim().replace(/^\/+|\/+$/g, '') || 'skills'
  return { ownerRepo, skillsPath }
}

export function pathPointsToSkill(skillsPath: string, skillName: string): boolean {
  const normalizedPath = String(skillsPath || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
    .toLowerCase()
  const normalizedName = String(skillName || '').trim().toLowerCase()
  if (!normalizedPath || !normalizedName) return false
  return (
    normalizedPath === normalizedName ||
    normalizedPath.endsWith(`/${normalizedName}`)
  )
}

export function skillInstallSource(
  skillName: string,
  rawSource: string | null | undefined
): string {
  const source = String(rawSource || '').trim()
  const spec = splitSkillSourceSpec(source)
  if (spec) {
    if (pathPointsToSkill(spec.skillsPath, skillName)) {
      const parentPath = spec.skillsPath
        .split('/')
        .filter(Boolean)
        .slice(0, -1)
        .join('/')
      if (!parentPath || parentPath === 'skills') return spec.ownerRepo
      return `${spec.ownerRepo}@${parentPath}`
    }
    return spec.skillsPath === 'skills'
      ? spec.ownerRepo
      : `${spec.ownerRepo}@${spec.skillsPath}`
  }
  return source || DEFAULT_SKILLS_REPO
}

export function skillGithubUrl(
  name: string,
  rawSource: string | null | undefined
): string | null {
  const spec = splitSkillSourceSpec(rawSource)
  if (!spec) return null
  const ownerRepo = spec.ownerRepo
  const skillPath = pathPointsToSkill(spec.skillsPath, name)
    ? spec.skillsPath
    : `${spec.skillsPath}/${encodeURIComponent(name)}`
  return `https://github.com/${ownerRepo}/tree/main/${skillPath}`
}

export function catalogCoordsFromInstalledSkill(
  skill: Pick<AgentSkill, 'name' | 'source'>
): { source: string; skill: string } | null {
  const name = String(skill.name || '').trim()
  if (!name) return null
  const spec = splitSkillSourceSpec(skill.source)
  if (!spec?.ownerRepo) return null
  return { source: spec.ownerRepo, skill: name }
}

export function skillsShSkillUrl(source: string, skill: string): string | null {
  const normalizedSource = String(source || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  // Keep underscores — skills.sh canonical paths use the skill folder name
  // (e.g. md_openmm_calvados), not a hyphenated slug.
  const normalizedSkill = String(skill || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  if (!normalizedSource || !normalizedSkill) return null
  return `https://skills.sh/${normalizedSource}/${normalizedSkill}`
}

/** Prefer skills.sh / install name (underscores) over hyphenated API slugs. */
export function catalogSkillPreferredName(skill: {
  name?: string | null
  slug?: string | null
  id?: string | null
}): string {
  const name = String(skill.name || '').trim()
  if (name) return name
  const slug = String(skill.slug || '').trim()
  if (slug) return slug
  const id = String(skill.id || '').trim()
  return id.split('/').filter(Boolean).pop() || ''
}

export function catalogSkillDetailPath(skill: {
  id?: string | null
  source?: string | null
  name?: string | null
  slug?: string | null
}): string {
  const source = String(skill.source || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  const name = catalogSkillPreferredName(skill)
  if (source && name) return `/dashboard/skills/catalog/${source}/${name}`
  const id = String(skill.id || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  return id ? `/dashboard/skills/catalog/${id}` : '/dashboard/skills'
}

export function skillAuthorUrl(rawSource: string | null | undefined): string | null {
  const spec = splitSkillSourceSpec(rawSource)
  if (!spec) return null
  return `https://github.com/${spec.ownerRepo}`
}

export function displaySkillVersion(version: string | null | undefined): string {
  const value = String(version || '').trim()
  if (!value) return 'Unknown'
  return /^v/i.test(value) ? value : `v${value}`
}

export function formatSkillUpdatedLabel(updatedAt: string | null | undefined): string {
  const raw = String(updatedAt || '').trim()
  if (!raw) return 'Unknown'
  const parsed = new Date(raw)
  if (Number.isNaN(parsed.getTime())) return raw
  const diffMs = Date.now() - parsed.getTime()
  if (diffMs < 0) return raw
  const minute = 60 * 1000
  const hour = 60 * minute
  const day = 24 * hour
  if (diffMs < minute) return 'just now'
  if (diffMs < hour) return `${Math.floor(diffMs / minute)}m ago`
  if (diffMs < day) return `${Math.floor(diffMs / hour)}h ago`
  return `${Math.floor(diffMs / day)}d ago`
}

export type SkillsViewMode =
  | 'list'
  | 'detail'
  | 'catalog_detail'
  | 'import_github'
  | 'import_file'
  | 'trusted_sources'

/** Prefer linked Fastfold Cloud email; otherwise username. */
export function cloudAccountDisplayName(account: AccountSummary | null): string | null {
  if (!account?.configured) return null
  const email = account.user?.email?.trim()
  if (email) return email
  const username = account.user?.username?.trim()
  if (username) return username
  return null
}
