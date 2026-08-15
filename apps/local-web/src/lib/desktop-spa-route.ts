import { isTauri } from '@/lib/desktop'

type Loc = {
  pathname: string
  search: string
  hash: string
}

/** Custom-protocol shells have no history fallback — keep the SPA in the hash. */
export function usesDesktopHashRouter(): boolean {
  if (typeof window === 'undefined') return false
  if (isTauri()) return true
  const { protocol, hostname } = window.location
  return (
    protocol === 'tauri:' ||
    protocol === 'asset:' ||
    hostname === 'tauri.localhost' ||
    hostname === 'asset.localhost'
  )
}

/**
 * In-app path for Open Recent / titles. HashRouter keeps the document at
 * `index.html`, so `window.location.pathname` is not the SPA route.
 */
export function desktopSpaRoute(loc: Loc): string {
  const hash = loc.hash || ''
  if (hash.startsWith('#')) {
    const inner = hash.slice(1)
    if (!inner || inner === '/') return '/'
    return inner.startsWith('/') ? inner : `/${inner}`
  }
  const path = loc.pathname || '/'
  if (path === '/' || /(?:^|\/)index\.html$/i.test(path)) {
    return loc.search || '/'
  }
  return `${path}${loc.search || ''}`
}

/**
 * Native Reload / Cmd+R on a history URL like `/dashboard/models` 404s the
 * asset protocol. Stay on `index.html` and put the SPA path in the hash.
 */
export function desktopReloadTarget(loc: Loc): 'reload' | { replace: string } {
  const path = loc.pathname || '/'
  const isIndex = path === '/' || /(?:^|\/)index\.html$/i.test(path)
  if (isIndex || loc.hash) return 'reload'
  const last = path.split('/').pop() || ''
  if (last.includes('.')) return 'reload'
  return { replace: `/index.html#${path}${loc.search || ''}` }
}

export function reloadDesktopSpa(): void {
  const target = desktopReloadTarget({
    pathname: window.location.pathname,
    search: window.location.search,
    hash: window.location.hash
  })
  if (target === 'reload') {
    window.location.reload()
    return
  }
  window.location.replace(target.replace)
}
