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

/** @deprecated Prefer normalizeAppError / ErrorPage from @/lib/app-error */
export { formatConnectError, type AppErrorInfo as ConnectErrorInfo } from '@/lib/app-error'
