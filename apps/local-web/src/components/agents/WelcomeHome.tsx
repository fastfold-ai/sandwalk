import { Loader2, Monitor, Network, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { OsPlatformIcon } from '@/components/agents/os-platform-icon'
import { SandwalkMark } from '@/components/SandwalkMark'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { DEFAULT_BACKEND_URL, isLocalBackendUrl } from '@/lib/backend-url'
import {
  clearDesktopWindowRecents,
  type DesktopWindowRecent,
  isTauri,
  listDesktopWindowRecents,
  listenDesktopWindowRecentsChanged,
  platformOS
} from '@/lib/desktop'
import { openDesktopRecent } from '@/lib/open-desktop-recent'
import { readCachedRemotePlatform } from '@/lib/remote-hostname'
import { cn } from '@/lib/utils'

function hostport(url: string): string {
  try {
    const parsed = new URL(url)
    return parsed.port ? `${parsed.hostname}:${parsed.port}` : parsed.hostname
  } catch {
    return url
  }
}

function shortHostname(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return ''
  const noLocal = trimmed.endsWith('.local')
    ? trimmed.slice(0, -'.local'.length)
    : trimmed
  return noLocal.split('.')[0] || noLocal
}

function formatRecent(row: DesktopWindowRecent): { title: string; detail: string } {
  const rawTitle = (row.title || row.label || 'Sandwalk').trim() || 'Sandwalk'
  if (isLocalBackendUrl(row.url)) {
    return {
      title:
        rawTitle === 'Sandwalk' || rawTitle === 'Local' ? 'Local' : rawTitle,
      detail: hostport(row.url)
    }
  }
  const short = shortHostname(row.hostname || '')
  const port = hostport(row.url)
  const ip = port.split(':')[0] || port
  const detail =
    short && short.toLowerCase() !== ip.toLowerCase()
      ? `${short} · ${port}`
      : port
  return { title: rawTitle, detail }
}

function localPlatformHint(): string {
  const os = platformOS()
  if (os === 'windows') return 'windows'
  if (os === 'linux') return 'linux'
  return 'darwin'
}

function hostnamePlatformHint(hostname: string | undefined): string {
  const h = (hostname || '').toLowerCase()
  if (!h) return ''
  if (h.includes('mac') || h.includes('iphone') || h.includes('ipad')) {
    return 'darwin'
  }
  if (h.includes('win')) return 'windows'
  if (h.includes('linux') || h.includes('ubuntu')) return 'linux'
  return ''
}

/** Icon OS from stored recent / cache only — never probes the network. */
function recentPlatform(row: DesktopWindowRecent): string {
  if (isLocalBackendUrl(row.url)) return localPlatformHint()
  const stored = (row.platform || '').trim()
  if (stored) return stored
  const cached = readCachedRemotePlatform(row.url)
  if (cached) return cached
  return hostnamePlatformHint(row.hostname)
}

export function WelcomeHome({
  connecting,
  onConnectLocal,
  onOpenRemote
}: {
  connecting: boolean
  onConnectLocal: () => void | Promise<void>
  onOpenRemote: (prefillUrl?: string | null) => void
}) {
  const [recents, setRecents] = useState<DesktopWindowRecent[]>([])
  const [loadingRecents, setLoadingRecents] = useState(isTauri())
  const [openingId, setOpeningId] = useState<string | null>(null)

  const refreshRecents = useCallback(async (options?: { silent?: boolean }) => {
    if (!isTauri()) {
      setRecents([])
      setLoadingRecents(false)
      return
    }
    if (!options?.silent) setLoadingRecents(true)
    try {
      const rows = (await listDesktopWindowRecents()) ?? []
      setRecents(rows)
    } catch {
      setRecents([])
    } finally {
      setLoadingRecents(false)
    }
  }, [])

  useEffect(() => {
    void refreshRecents()
  }, [refreshRecents])

  // Other windows append Open Recent when they connect — refresh this list live.
  useEffect(() => {
    if (!isTauri()) return
    let cancelled = false
    let unlisten: (() => void) | undefined
    void listenDesktopWindowRecentsChanged(() => {
      if (!cancelled) void refreshRecents({ silent: true })
    }).then(fn => {
      if (cancelled) fn()
      else unlisten = fn
    })
    const onFocus = () => {
      if (document.visibilityState === 'visible') {
        void refreshRecents({ silent: true })
      }
    }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onFocus)
    return () => {
      cancelled = true
      unlisten?.()
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onFocus)
    }
  }, [refreshRecents])

  const openRecent = async (row: DesktopWindowRecent) => {
    if (openingId || connecting) return
    setOpeningId(row.id || row.url)
    try {
      const result = await openDesktopRecent({
        url: row.url,
        route: row.route,
        title: row.title,
        id: row.id,
        hostname: row.hostname,
        platform: row.platform
      })
      if (!result.opened) onOpenRemote(result.url)
    } catch {
      onOpenRemote(row.url)
    } finally {
      setOpeningId(null)
    }
  }

  const clearRecents = async () => {
    if (!isTauri()) return
    try {
      await clearDesktopWindowRecents()
    } catch {
      // ignore
    }
    setRecents([])
  }

  return (
    <main className="bg-background relative grid h-full place-items-center overflow-auto p-8">
      <ThemeToggle placement="top-right" />
      <div className="flex w-full max-w-xl flex-col items-stretch gap-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <SandwalkMark className="text-foreground h-12 w-12" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">sandwalk</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Choose a local or remote agent workspace
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            type="button"
            disabled={connecting}
            onClick={() => void onConnectLocal()}
            className={cn(
              'border-border hover:bg-muted/40 flex items-center gap-3 rounded-xl border px-4 py-4 text-left transition-colors',
              'disabled:pointer-events-none disabled:opacity-50'
            )}
          >
            <span className="bg-muted text-foreground grid size-10 place-items-center rounded-lg">
              {connecting ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Monitor className="size-5" />
              )}
            </span>
            <span>
              <span className="block text-sm font-medium">Connect locally</span>
              <span className="text-muted-foreground block text-xs">
                {DEFAULT_BACKEND_URL.replace(/^https?:\/\//, '')}
              </span>
            </span>
          </button>
          <button
            type="button"
            disabled={connecting}
            onClick={() => onOpenRemote(null)}
            className={cn(
              'border-border hover:bg-muted/40 flex items-center gap-3 rounded-xl border px-4 py-4 text-left transition-colors',
              'disabled:pointer-events-none disabled:opacity-50'
            )}
          >
            <span className="bg-muted text-foreground grid size-10 place-items-center rounded-lg">
              <Network className="size-5" />
            </span>
            <span>
              <span className="block text-sm font-medium">Open remote…</span>
              <span className="text-muted-foreground block text-xs">
                LAN scan or paste a URL
              </span>
            </span>
          </button>
        </div>

        <section className="min-h-[8rem]">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Recent
            </h2>
            {recents.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-muted-foreground h-7 px-2 text-xs"
                onClick={() => void clearRecents()}
              >
                <Trash2 className="size-3.5" />
                Clear
              </Button>
            ) : null}
          </div>

          {loadingRecents ? (
            <div className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader2 className="size-4 animate-spin" />
              Loading…
            </div>
          ) : recents.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No recent workspaces yet. Connect locally or open a remote server.
            </p>
          ) : (
            <ul className="divide-border divide-y">
              {recents.map(row => {
                const { title, detail } = formatRecent(row)
                const key = row.id || row.url
                const busy = openingId === key
                return (
                  <li key={row.id || `${row.url}:${row.route}:${row.lastOpenedAt}`}>
                    <button
                      type="button"
                      disabled={connecting || Boolean(openingId)}
                      onClick={() => void openRecent(row)}
                      className="hover:bg-muted/40 flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors disabled:opacity-50"
                    >
                      <OsPlatformIcon
                        platform={recentPlatform(row)}
                        className="size-7"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">
                          {title}
                        </span>
                      </span>
                      <span className="text-muted-foreground shrink-0 text-xs">
                        {busy ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          detail
                        )}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  )
}
