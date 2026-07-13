export function sanitizeAuthReturnTo(path: string | null | undefined): string | null {
  if (!path) return null
  const trimmed = path.trim()
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) return null
  if (trimmed === '/' || trimmed === '/login' || trimmed.startsWith('/login?')) {
    return null
  }
  return trimmed
}

export function loginPathWithNext(returnTo: string | null): string {
  const safe = sanitizeAuthReturnTo(returnTo)
  if (!safe) return '/'
  return `/?next=${encodeURIComponent(safe)}`
}

export function nextFromSearch(search: string): string | null {
  const raw = new URLSearchParams(search).get('next')
  return sanitizeAuthReturnTo(raw)
}

export function formatConnectError(raw: string): { title: string; detail: string } {
  const text = String(raw || '').trim()
  if (!text) {
    return {
      title: 'Unable to connect',
      detail: 'Check that the agent backend is running, then try again.'
    }
  }
  const statusMatch = text.match(/FastFold Agent API (\d+)/i)
  const status = statusMatch ? Number(statusMatch[1]) : null
  let detail = text
  try {
    const jsonMatch = text.match(/\{.*\}/s)
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]) as { detail?: unknown }
      if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
        detail = parsed.detail.trim()
      }
    }
  } catch {
    // keep raw text
  }
  if (status === 404) {
    return {
      title: 'Backend endpoint missing',
      detail:
        detail === 'Not Found'
          ? 'The UI called an API the running backend does not have yet. Restart Sandwalk / the agent server after updating, then connect again.'
          : detail
    }
  }
  if (status === 401 || status === 403) {
    return {
      title: 'Authentication failed',
      detail: 'Check the API key and try again.'
    }
  }
  if (/failed to fetch|networkerror|load failed/i.test(text)) {
    return {
      title: 'Backend unreachable',
      detail: 'Confirm the URL is correct and the agent server is running.'
    }
  }
  return {
    title: 'Unable to connect',
    detail: detail.length > 180 ? `${detail.slice(0, 177)}…` : detail
  }
}
