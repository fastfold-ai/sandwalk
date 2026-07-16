/** Host candidates for remote MCP favicon lookup (apex before mcp.*). */
export function faviconHostsForUrl(rawUrl: string): string[] {
  try {
    const withScheme = rawUrl.includes('://') ? rawUrl : `https://${rawUrl}`
    const host = new URL(withScheme).hostname.toLowerCase()
    if (!host) return []
    const hosts: string[] = []
    // mcp.betterstack.com → betterstack.com (Google often has no mcp.* favicon)
    if (host.startsWith('mcp.')) {
      hosts.push(host.slice(4))
    }
    hosts.push(host)
    const parts = host.split('.')
    if (parts.length > 2) {
      hosts.push(parts.slice(-2).join('.'))
    }
    return [...new Set(hosts.filter(Boolean))]
  } catch {
    return []
  }
}

/** Ordered favicon URLs to try for a remote MCP server URL. */
export function faviconCandidatesForUrl(rawUrl: string | null | undefined): string[] {
  const raw = rawUrl?.trim()
  if (!raw) return []
  const out: string[] = []
  for (const host of faviconHostsForUrl(raw)) {
    // DuckDuckGo first — Google often returns a tiny default that still HTTP 200s.
    out.push(`https://icons.duckduckgo.com/ip3/${encodeURIComponent(host)}.ico`)
    out.push(
      `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128`
    )
  }
  return out
}
