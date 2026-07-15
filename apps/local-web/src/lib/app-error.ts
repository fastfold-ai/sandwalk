/** Normalized app error for reusable ErrorPage / ErrorBoundary UI. */

export type AppErrorInfo = {
  title: string
  detail: string
  hint: string | null
  status: number | null
  raw: string
  stack: string | null
  name: string | null
}

function extractJsonDetail(text: string): string | null {
  try {
    const jsonMatch = text.match(/\{[\s\S]*\}/)
    if (!jsonMatch) return null
    const parsed = JSON.parse(jsonMatch[0]) as { detail?: unknown }
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      return parsed.detail.trim()
    }
  } catch {
    // keep raw text
  }
  return null
}

function extractApiPath(text: string): string | null {
  const bracket = text.match(
    /\[(?:GET|POST|PUT|PATCH|DELETE)\s+(https?:\/\/[^\]]+|\/v1\/[^\]]+)\]/i
  )
  if (bracket?.[1]) {
    try {
      if (bracket[1].startsWith('/')) return bracket[1]
      const url = new URL(bracket[1])
      return `${url.pathname}${url.search}`
    } catch {
      return bracket[1]
    }
  }
  const match = text.match(/\/v1\/[a-zA-Z0-9_./?-]+/)
  return match ? match[0] : null
}

function extractStatus(text: string): number | null {
  const api = text.match(/FastFold Agent API (\d+)/i)
  if (api) return Number(api[1])
  const http = text.match(/\bHTTP\s*(\d{3})\b/i)
  if (http) return Number(http[1])
  const status = text.match(/\bstatus(?:Code)?[=:\s]+(\d{3})\b/i)
  if (status) return Number(status[1])
  return null
}

function asMessage(error: unknown): string {
  if (error == null) return ''
  if (typeof error === 'string') return error
  if (error instanceof Error) return error.message || error.name || String(error)
  if (typeof error === 'object' && 'message' in error) {
    const message = (error as { message?: unknown }).message
    if (typeof message === 'string') return message
  }
  try {
    return JSON.stringify(error)
  } catch {
    return String(error)
  }
}

function asStack(error: unknown): string | null {
  if (error instanceof Error && error.stack) return error.stack
  if (typeof error === 'object' && error && 'stack' in error) {
    const stack = (error as { stack?: unknown }).stack
    if (typeof stack === 'string' && stack.trim()) return stack.trim()
  }
  const message = asMessage(error)
  return message.includes('\n') ? message : null
}

function asName(error: unknown): string | null {
  if (error instanceof Error && error.name) return error.name
  if (typeof error === 'object' && error && 'name' in error) {
    const name = (error as { name?: unknown }).name
    if (typeof name === 'string' && name.trim()) return name.trim()
  }
  return null
}

/**
 * Turn any thrown value / API failure string into a stable UI model.
 * Safe to use from pages, fetch handlers, and Error Boundaries.
 */
export function normalizeAppError(
  error: unknown,
  options?: { fallbackTitle?: string }
): AppErrorInfo {
  const raw = asMessage(error).trim()
  const stack = asStack(error)
  const name = asName(error)
  const status = extractStatus(raw)
  const jsonDetail = extractJsonDetail(raw)
  const apiPath = extractApiPath(raw)
  const fallbackTitle = options?.fallbackTitle || 'Something went wrong'

  if (!raw) {
    return {
      title: fallbackTitle,
      detail: 'An unexpected error occurred.',
      hint: 'Try again. If it keeps happening, copy the technical details below.',
      status: null,
      raw: '',
      stack,
      name
    }
  }

  let detail = jsonDetail || raw
  if (apiPath && status === 404 && (!jsonDetail || /not found/i.test(detail))) {
    detail = `Request to ${apiPath} failed because the endpoint is missing on this backend.`
  } else if (detail.length > 280) {
    detail = `${detail.slice(0, 277)}…`
  }

  if (status === 404) {
    return {
      title: 'Not found',
      detail,
      hint: 'The UI may be newer than the running agent server. Restart sandwalk / the agent server after updating, then retry.',
      status,
      raw,
      stack: stack || raw,
      name
    }
  }

  if (status === 401 || status === 403) {
    return {
      title: 'Authentication failed',
      detail: jsonDetail || 'The backend rejected this request.',
      hint: 'Check your API key or sign in again.',
      status,
      raw,
      stack: stack || raw,
      name
    }
  }

  if (/failed to fetch|networkerror|load failed|network request failed|cors|access-control-allow-origin/i.test(raw)) {
    return {
      title: 'Backend unreachable',
      detail:
        /cors|access-control-allow-origin/i.test(raw)
          ? 'The browser blocked the response (often a crashing backend without CORS headers).'
          : 'The browser could not reach the backend, or a server crash hid the real HTTP status.',
      hint: 'Confirm the agent server is running on the expected port, check its logs for 500s, then retry. This is not an API-key problem.',
      status,
      raw,
      stack: stack || raw,
      name
    }
  }

  if (status != null && status >= 500) {
    return {
      title: 'Backend error',
      detail: jsonDetail || `The agent server returned HTTP ${status}.`,
      hint: 'Check agent server logs (and ~/.sandwalk if the store is corrupt), then retry. This is not an API-key problem.',
      status,
      raw,
      stack: stack || raw,
      name
    }
  }

  if (name === 'ChunkLoadError' || /loading chunk \d+ failed/i.test(raw)) {
    return {
      title: 'Failed to load UI',
      detail: 'A JavaScript chunk failed to load.',
      hint: 'Hard-refresh the page. If you just deployed, clear cache and retry.',
      status,
      raw,
      stack: stack || raw,
      name
    }
  }

  return {
    title: fallbackTitle,
    detail,
    hint: 'Try again. If it keeps happening, copy the technical details below.',
    status,
    raw,
    stack: stack || (jsonDetail && jsonDetail !== raw ? raw : null),
    name
  }
}

/** True only for credential / permission rejections — not network or 5xx. */
export function isAuthCredentialError(error: unknown): boolean {
  const info = normalizeAppError(error)
  return info.status === 401 || info.status === 403
}

/** True when the agent API is down, crashing, or blocked by CORS. */
export function isBackendUnavailableError(error: unknown): boolean {
  const info = normalizeAppError(error)
  if (info.status != null && info.status >= 500) return true
  return (
    info.title === 'Backend unreachable' ||
    /failed to fetch|networkerror|load failed|network request failed|cors|access-control-allow-origin/i.test(
      info.raw
    )
  )
}

/** @deprecated Prefer normalizeAppError — kept for connect-form call sites. */
export function formatConnectError(raw: string, stack?: string | null) {
  const info = normalizeAppError(
    stack ? Object.assign(new Error(raw), { stack }) : raw,
    { fallbackTitle: 'Unable to connect' }
  )
  return {
    title: info.title,
    detail: info.detail,
    hint: info.hint,
    status: info.status,
    raw: info.raw,
    technical: info.stack
  }
}
