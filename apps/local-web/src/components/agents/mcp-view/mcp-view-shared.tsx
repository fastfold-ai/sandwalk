import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import { Plug } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

import { faviconCandidatesForUrl } from './mcp-favicon'

export type HeaderRow = { id: string; name: string; value: string }
export type CustomMode = 'remote' | 'local'

export function newHeaderRow(): HeaderRow {
  return { id: crypto.randomUUID(), name: '', value: '' }
}

export function headersFromRows(rows: HeaderRow[]): Record<string, string> | null {
  const out: Record<string, string> = {}
  for (const row of rows) {
    const name = row.name.trim()
    const value = row.value
    if (!name || !value) continue
    out[name] = value
  }
  return Object.keys(out).length > 0 ? out : null
}

export const MCP_ICONS: Record<string, { src: string; invertInDark?: boolean }> = {
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  paperclip: { src: '/integrations/paperclip.png' },
  huggingface: { src: '/integrations/huggingface.png' },
  linear: { src: '/integrations/linear.png' },
}

export function McpToggle({
  enabled,
  pending,
  label,
  onToggle,
}: {
  enabled: boolean
  pending?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60',
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

export function McpIcon({
  id,
  name,
  url,
  size = 'sm',
}: {
  id: string
  name: string
  /** When set and no bundled icon exists, resolve favicon from this MCP URL. */
  url?: string | null
  size?: 'sm' | 'lg'
}) {
  const icon = MCP_ICONS[id]
  const box = size === 'lg' ? 'size-9' : 'size-6'
  const candidates = icon ? [] : faviconCandidatesForUrl(url)
  const [faviconIndex, setFaviconIndex] = useState(0)

  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          box,
          'bg-muted shrink-0 rounded object-contain p-0.5',
          icon.invertInDark && 'dark:invert',
        )}
      />
    )
  }

  if (candidates.length > 0 && faviconIndex < candidates.length) {
    return (
      <span
        className={cn(
          box,
          'bg-muted shrink-0 overflow-hidden rounded grid place-items-center',
        )}
      >
        <img
          key={candidates[faviconIndex]}
          src={candidates[faviconIndex]}
          alt=""
          className="block size-full max-h-full max-w-full object-contain p-0.5"
          onError={() => setFaviconIndex(prev => prev + 1)}
        />
      </span>
    )
  }

  return (
    <span
      className={cn(
        'bg-muted text-muted-foreground grid shrink-0 place-items-center rounded',
        box,
      )}
    >
      <Plug className={size === 'lg' ? 'size-5' : 'size-3.5'} />
      <span className="sr-only">{name}</span>
    </span>
  )
}

export function formatConnectError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err)
  const jsonStart = raw.indexOf('{')
  if (jsonStart >= 0) {
    try {
      const parsed = JSON.parse(raw.slice(jsonStart)) as { detail?: unknown }
      if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
        return parsed.detail
      }
    } catch {
      // fall through
    }
  }
  return raw.replace(/^FastFold Agent API \d+:\s*/, '').trim() || raw
}

export function authMeta(entry: McpCatalogEntry) {
  const keysHref = entry.integrationKey
    ? `/dashboard/integrations/${entry.integrationKey}`
    : null
  const apiKeyLabel = keysHref ? (
    <a
      href={keysHref}
      className="text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
    >
      API key
    </a>
  ) : (
    <span>API key</span>
  )

  if (entry.preferredAuth === 'oauth') {
    if (entry.authMode === 'api_key_or_oauth') {
      return (
        <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
          OAuth · {apiKeyLabel}
        </span>
      )
    }
    return <span className="text-muted-foreground text-xs">OAuth</span>
  }
  return (
    <span className="text-muted-foreground inline-flex items-center text-xs">
      {apiKeyLabel}
    </span>
  )
}

export function statusBadge(
  entry: McpCatalogEntry,
  onOpen?: (entry: McpCatalogEntry) => void,
) {
  const showConnected =
    entry.connected ||
    (entry.enabled && typeof entry.toolCount === 'number')
  if (showConnected) {
    const count =
      typeof entry.toolCount === 'number' ? ` (${entry.toolCount})` : ''
    if (onOpen) {
      return (
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-xs underline-offset-2 hover:underline"
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            onOpen(entry)
          }}
        >
          <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
          Connected{count}
        </button>
      )
    }
    return (
      <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
        <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
        Connected{count}
      </span>
    )
  }
  if (entry.statusMessage) {
    const needsReconnect = /expired|reconnect|invalid_token|unauthorized/i.test(
      entry.statusMessage,
    )
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-xs',
          needsReconnect
            ? 'text-amber-700 dark:text-amber-300'
            : 'text-red-600 dark:text-red-400',
        )}
        title={entry.statusMessage}
      >
        <span
          className={cn(
            'size-1.5 shrink-0 rounded-full',
            needsReconnect ? 'bg-amber-500' : 'bg-red-500',
          )}
        />
        {needsReconnect ? 'Needs reconnect' : 'Error'}
      </span>
    )
  }
  return null
}

export type CatalogStatusPatch = {
  connected?: boolean
  enabled?: boolean
  toolCount?: number | null
  statusMessage?: string | null
}

export function withStatusPatch(
  entry: McpCatalogEntry,
  patch?: CatalogStatusPatch,
): McpCatalogEntry {
  if (!patch) return entry
  return {
    ...entry,
    connected: patch.connected ?? entry.connected,
    enabled: patch.enabled ?? entry.enabled,
    toolCount:
      patch.toolCount !== undefined ? patch.toolCount : entry.toolCount,
    statusMessage:
      patch.statusMessage !== undefined
        ? patch.statusMessage
        : entry.statusMessage,
  }
}
