import type { McpCatalogEntry, McpServer } from '@sandwalk/agent-ui-core'
import { useState } from 'react'

import { McpMark } from '@/components/McpMark'
import { cn } from '@/lib/utils'

import { faviconCandidatesForUrl } from './mcp-favicon'
import { MCP_ICONS } from './mcp-view-shared'

export function transportLabel(server: McpServer): string {
  if (server.transport === 'streamable_http') return 'HTTP'
  if (server.transport === 'sse') return 'SSE'
  return 'stdio'
}

export function subtitle(server: McpServer): string {
  if (server.command) {
    return `${server.command} ${server.args.join(' ')}`.trim()
  }
  return server.url || server.description || transportLabel(server)
}

/** Remote custom MCP with no credentials yet — needs Connect before enable. */
export function customServerNeedsAuth(server: McpServer): boolean {
  if (server.transport === 'stdio') return false
  if (server.headersConfigured) return false
  if (server.headersHelperCommand?.trim()) return false
  return true
}

export function serverNeedsAuth(
  server: McpServer,
  catalogEntry: McpCatalogEntry | undefined
): boolean {
  if (server.catalogId) {
    return !(catalogEntry?.configured)
  }
  return customServerNeedsAuth(server)
}

export function isAuthReconnectMessage(
  message: string | null | undefined
): boolean {
  if (!message) return false
  return /expired|reconnect|invalid_token|unauthorized|401/i.test(message)
}

export function authStatusLabel(
  server: McpServer,
  catalogEntry: McpCatalogEntry | undefined,
  options: { waiting: boolean; needsAuth: boolean }
): { text: string; tone: 'muted' | 'amber' | 'waiting' } {
  if (options.waiting) {
    return { text: 'Waiting for callback…', tone: 'waiting' }
  }
  const statusMessage = catalogEntry?.statusMessage?.trim()
  if (statusMessage && isAuthReconnectMessage(statusMessage)) {
    return { text: 'Needs reconnect', tone: 'amber' }
  }
  if (options.needsAuth) {
    return { text: 'Needs authentication', tone: 'amber' }
  }
  return { text: subtitle(server), tone: 'muted' }
}

/**
 * Featured catalog MCPs use bundled first-party icons.
 * Everything else (custom remotes) uses favicon in the fixed layout box.
 */
export function CustomServerIcon({ server }: { server: McpServer }) {
  const catalogKey = server.catalogId?.trim().toLowerCase() || ''
  const bundled = catalogKey ? MCP_ICONS[catalogKey] : undefined
  const candidates = bundled ? [] : faviconCandidatesForUrl(server.url)
  const [index, setIndex] = useState(0)

  if (bundled) {
    return (
      <img
        src={bundled.src}
        alt=""
        className={cn(
          'block size-full max-h-full max-w-full object-contain p-px',
          bundled.invertInDark && 'dark:invert'
        )}
      />
    )
  }

  if (candidates.length > 0 && index < candidates.length) {
    return (
      <img
        key={candidates[index]}
        src={candidates[index]}
        alt=""
        className="block size-full max-h-full max-w-full object-contain p-px"
        onError={() => setIndex(prev => prev + 1)}
      />
    )
  }
  return <McpMark className="size-3.5" />
}
