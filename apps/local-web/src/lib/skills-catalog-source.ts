import type { AgentSkill } from '@sandwalk/agent-ui-core'

import {
  DEFAULT_SKILLS_REPO,
  OWNER_REPO_RE
} from './skills-catalog-install'

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
  const normalizedSkill = String(skill || '')
    .trim()
    .replace(/^\/+|\/+$/g, '')
  if (!normalizedSource || !normalizedSkill) return null
  return `https://skills.sh/${normalizedSource}/${normalizedSkill}`
}

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
