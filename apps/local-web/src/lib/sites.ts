import type { AgentProject, AgentSession, Site } from '@sandwalk/agent-ui-core'

/**
 * Interactive site preview sandbox. Includes `allow-same-origin` so Chart.js,
 * canvas heatmaps, and relative asset fetches work in the panel iframe.
 * Thumbnails intentionally use a stricter empty sandbox (no scripts).
 */
export const SITE_PREVIEW_SANDBOX =
  'allow-forms allow-modals allow-popups allow-same-origin allow-scripts'

export function filterSites(sites: Site[], query: string) {
  const needle = query.trim().toLowerCase()
  if (!needle) return sites
  return sites.filter(site =>
    [site.name, site.slug, site.deployment?.publicUrl, site.sourcePath].some(
      value => value?.toLowerCase().includes(needle)
    )
  )
}

/** When a project is selected, only sites from chats in that project. */
export function filterSitesByProject(
  sites: Site[],
  projectId: string | null | undefined,
  sessions: AgentSession[]
) {
  const scoped = (projectId || '').trim()
  if (!scoped) return sites
  const sessionIds = new Set(
    sessions.filter(session => session.projectId === scoped).map(s => s.id)
  )
  return sites.filter(
    site =>
      site.sourceProjectId === scoped ||
      (site.sourceSessionId != null && sessionIds.has(site.sourceSessionId))
  )
}

export function formatSiteBytes(bytes: number | null) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

export function siteSourceLabel(
  site: Site,
  sessions: AgentSession[],
  projects: AgentProject[]
) {
  if (site.sourceSessionId) {
    const session = sessions.find(item => item.id === site.sourceSessionId)
    return session?.title || 'Chat'
  }
  if (site.sourceProjectId) {
    const project = projects.find(item => item.id === site.sourceProjectId)
    return project?.name || 'Project'
  }
  return site.sourcePath || 'Local draft'
}

export function sitePublicUrl(site: Site) {
  return site.deployment?.publicUrl || null
}

export function isPublishedSite(site: Site) {
  return Boolean(sitePublicUrl(site))
}

export function siteChatPath(site: Site) {
  if (!site.sourceSessionId) return null
  const query = new URLSearchParams({ site: site.id })
  return `/agents/${encodeURIComponent(site.sourceSessionId)}?${query}`
}
