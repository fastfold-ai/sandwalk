import type { AgentCatalogSkill } from '@sandwalk/agent-ui-core'

export const DEFAULT_SKILLS_REPO = 'fastfold-ai/skills'
export const OWNER_REPO_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/

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
