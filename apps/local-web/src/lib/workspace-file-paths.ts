/** Absolute / tilde paths under a sandwalk session workspace. */
const WORKSPACE_ABS_PATH_RE =
  /(?:~\/\.sandwalk\/workspaces\/|(?:\/[^/\s]+)+\/\.sandwalk\/workspaces\/)[^\s`"'<>)\]]+/g

const TRAILING_PUNCT_RE = /[.,;:!?)]+$/

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function stripPathTrailingPunctuation(value: string): string {
  return value.replace(TRAILING_PUNCT_RE, '')
}

/**
 * Convert an absolute / tilde / workspace-rooted path into a workspace-relative
 * posix path suitable for `onOpenFile` / the Files panel. Returns null when the
 * path is not under a sandwalk workspace (or the provided root).
 */
export function workspaceRelativeFromPath(
  raw: string,
  workspacePath?: string | null
): string | null {
  const cleaned = stripPathTrailingPunctuation(raw.trim().replace(/\\/g, '/'))
  if (!cleaned) return null

  const withoutFileScheme = cleaned.startsWith('file://')
    ? decodeURIComponent(cleaned.slice('file://'.length))
    : cleaned

  const tildeMarker = '~/.sandwalk/workspaces/'
  if (withoutFileScheme.startsWith(tildeMarker)) {
    const rest = withoutFileScheme.slice(tildeMarker.length)
    const slash = rest.indexOf('/')
    if (slash < 0) return null
    const relative = rest.slice(slash + 1)
    return relative || null
  }

  const marker = '/.sandwalk/workspaces/'
  const markerAt = withoutFileScheme.toLowerCase().indexOf(marker)
  if (markerAt >= 0) {
    const rest = withoutFileScheme.slice(markerAt + marker.length)
    const slash = rest.indexOf('/')
    if (slash < 0) return null
    const relative = rest.slice(slash + 1)
    return relative || null
  }

  if (workspacePath) {
    const root = workspacePath.replace(/\\/g, '/').replace(/\/$/, '')
    if (withoutFileScheme === root) return null
    if (withoutFileScheme.startsWith(`${root}/`)) {
      return withoutFileScheme.slice(root.length + 1) || null
    }
  }

  return null
}

export function matchWorkspacePaths(
  text: string,
  workspacePath?: string | null
): Array<{ start: number; end: number; absolute: string; relative: string }> {
  const matches: Array<{
    start: number
    end: number
    absolute: string
    relative: string
  }> = []
  const seen = new Set<string>()

  const pushMatch = (start: number, end: number, absolute: string) => {
    const relative = workspaceRelativeFromPath(absolute, workspacePath)
    if (!relative) return
    const key = `${start}:${end}`
    if (seen.has(key)) return
    seen.add(key)
    matches.push({ start, end, absolute, relative })
  }

  for (const match of text.matchAll(WORKSPACE_ABS_PATH_RE)) {
    const absolute = stripPathTrailingPunctuation(match[0])
    const start = match.index ?? 0
    pushMatch(start, start + absolute.length, absolute)
  }

  if (workspacePath) {
    const root = workspacePath.replace(/\\/g, '/').replace(/\/$/, '')
    if (root) {
      const rooted = new RegExp(
        `${escapeRegExp(root)}/[^\\s\`"'<>)\\]]+`,
        'g'
      )
      for (const match of text.matchAll(rooted)) {
        const absolute = stripPathTrailingPunctuation(match[0])
        const start = match.index ?? 0
        pushMatch(start, start + absolute.length, absolute)
      }
    }
  }

  return matches.sort((a, b) => a.start - b.start)
}

/** Split plain text into literal segments and workspace file hits. */
export function splitTextWithWorkspacePaths(
  text: string,
  workspacePath?: string | null
): Array<
  | { type: 'text'; text: string }
  | { type: 'file'; absolute: string; relative: string }
> {
  const matches = matchWorkspacePaths(text, workspacePath)
  if (matches.length === 0) return [{ type: 'text', text }]

  const parts: Array<
    | { type: 'text'; text: string }
    | { type: 'file'; absolute: string; relative: string }
  > = []
  let cursor = 0
  for (const match of matches) {
    if (match.start < cursor) continue
    if (match.start > cursor) {
      parts.push({ type: 'text', text: text.slice(cursor, match.start) })
    }
    parts.push({
      type: 'file',
      absolute: match.absolute,
      relative: match.relative
    })
    cursor = match.end
  }
  if (cursor < text.length) {
    parts.push({ type: 'text', text: text.slice(cursor) })
  }
  return parts
}
