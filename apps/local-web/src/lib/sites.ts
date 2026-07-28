import type { AgentProject, AgentSession, Site } from '@sandwalk/agent-ui-core'

export function filterSites(sites: Site[], query: string) {
  const needle = query.trim().toLowerCase()
  if (!needle) return sites
  return sites.filter(site =>
    [site.name, site.slug, site.deployment?.publicUrl, site.sourcePath].some(
      value => value?.toLowerCase().includes(needle)
    )
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
