import { Loader2, Monitor, Network, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { OsPlatformIcon } from '@/components/agents/os-platform-icon'
import { SandwalkMark } from '@/components/SandwalkMark'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import {
  DEFAULT_BACKEND_URL,
  isLocalBackendUrl,
  normalizeBackendUrl
} from '@/lib/backend-url'
import {
  clearDesktopWindowRecents,
  type DesktopWindowRecent,
  isTauri,
  listDesktopWindowRecents,
  platformOS
} from '@/lib/desktop'
import { openDesktopRecent } from '@/lib/open-desktop-recent'
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

async function resolveRecentPlatform(
  url: string,
  hostname?: string
): Promise<string> {
  if (isLocalBackendUrl(url)) return localPlatformHint()
  const hint = hostnamePlatformHint(hostname)
  try {
    const res = await fetch(`${normalizeBackendUrl(url)}/v1/discover`, {
      method: 'GET',
      headers: { Accept: 'application/json' }
    })
    if (!res.ok) return hint
    const body = (await res.json()) as { platform?: string }
    return (body.platform || '').trim() || hint
  } catch {
    return hint
  }
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
  const [platforms, setPlatforms] = useState<Record<string, string>>({})
  const [loadingRecents, setLoadingRecents] = useState(isTauri())
  const [openingId, setOpeningId] = useState<string | null>(null)

  const refreshRecents = useCallback(async () => {
    if (!isTauri()) {
      setRecents([])
      setPlatforms({})
      setLoadingRecents(false)
      return
    }
    setLoadingRecents(true)
    try {
      const rows = await listDesktopWindowRecents()
      setRecents(rows)
      // Seed local / hostname hints immediately; refine via /v1/discover.
      const seeded: Record<string, string> = {}
      for (const row of rows) {
        const key = row.id || row.url
        const hint = isLocalBackendUrl(row.url)
          ? localPlatformHint()
          : hostnamePlatformHint(row.hostname)
        if (hint) seeded[key] = hint
      }
      setPlatforms(seeded)
      void Promise.all(
        rows.map(async row => {
          const key = row.id || row.url
          const platform = await resolveRecentPlatform(row.url, row.hostname)
          if (platform) {
            setPlatforms(prev =>
              prev[key] === platform ? prev : { ...prev, [key]: platform }
            )
          }
        })
      )
    } catch {
      setRecents([])
      setPlatforms({})
    } finally {
      setLoadingRecents(false)
    }
  }, [])

  useEffect(() => {
    void refreshRecents()
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
        hostname: row.hostname
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
                        platform={
                          platforms[key] ||
                          (isLocalBackendUrl(row.url)
                            ? localPlatformHint()
                            : row.hostname)
                        }
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
