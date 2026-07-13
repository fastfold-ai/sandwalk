import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer,
} from '@sandwalk/agent-ui-core'
import {
  ArrowRight,
  ChevronDown,
  ExternalLink,
  KeyRound,
  Loader2,
  Plus,
  Plug,
  Trash2,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type HeaderRow = { id: string; name: string; value: string }
type CustomMode = 'remote' | 'local'

function newHeaderRow(): HeaderRow {
  return { id: crypto.randomUUID(), name: '', value: '' }
}

function headersFromRows(rows: HeaderRow[]): Record<string, string> | null {
  const out: Record<string, string> = {}
  for (const row of rows) {
    const name = row.name.trim()
    const value = row.value
    if (!name || !value) continue
    out[name] = value
  }
  return Object.keys(out).length > 0 ? out : null
}

const MCP_ICONS: Record<string, { src: string; invertInDark?: boolean }> = {
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  linear: { src: '/integrations/linear.png' },
}

function McpToggle({
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

function McpIcon({
  id,
  name,
  size = 'sm',
}: {
  id: string
  name: string
  size?: 'sm' | 'lg'
}) {
  const icon = MCP_ICONS[id]
  const box = size === 'lg' ? 'size-9' : 'size-6'
  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          box,
          'shrink-0 rounded object-contain',
          icon.invertInDark && 'dark:invert',
        )}
      />
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

function formatConnectError(err: unknown): string {
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

function authMeta(entry: McpCatalogEntry) {
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

function statusBadge(entry: McpCatalogEntry) {
  if (entry.connected) {
    const count =
      typeof entry.toolCount === 'number' ? ` (${entry.toolCount})` : ''
    return (
      <span className="text-muted-foreground inline-flex items-center gap-1.5 text-xs">
        <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
        Connected{count}
      </span>
    )
  }
  // Only show live errors while enabled; disable/reconnect clears prior failures.
  if (entry.enabled && entry.statusMessage) {
    return (
      <span
        className="inline-flex max-w-[14rem] items-center gap-1.5 text-xs text-red-600 dark:text-red-400"
        title={entry.statusMessage}
      >
        <span className="size-1.5 shrink-0 rounded-full bg-red-500" />
        <span className="truncate">{entry.statusMessage}</span>
      </span>
    )
  }
  return null
}

type CatalogStatusPatch = {
  connected?: boolean
  enabled?: boolean
  toolCount?: number | null
  statusMessage?: string | null
}

function withStatusPatch(
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

export function McpView({
  mcpServers,
  catalog,
  catalogLoading,
  featuredOnly = false,
  onShowAll,
  onRefresh,
  onConnectCatalog,
  onToggleCatalog,
  onCreateMcp,
  onDeleteMcp,
  onToggleCustom,
}: {
  mcpServers: McpServer[]
  catalog: McpCatalogEntry[]
  catalogLoading?: boolean
  /** Overview: only the Featured catalog grid (same cards as MCP page). */
  featuredOnly?: boolean
  onShowAll?: () => void
  onRefresh: () => Promise<void>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string },
  ) => Promise<ConnectMcpResult>
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onCreateMcp: (
    input: Omit<McpServer, 'id' | 'createdAt' | 'updatedAt'>,
  ) => Promise<void>
  onDeleteMcp: (id: string) => Promise<void>
  onToggleCustom: (id: string, enabled: boolean) => Promise<void>
}) {
  const [mcpMode, setMcpMode] = useState<CustomMode>('remote')
  const [mcpName, setMcpName] = useState('')
  const [mcpTransport, setMcpTransport] = useState<'sse' | 'streamable_http'>(
    'streamable_http',
  )
  const [mcpTarget, setMcpTarget] = useState('')
  const [mcpDescription, setMcpDescription] = useState('')
  const [mcpAdvancedOpen, setMcpAdvancedOpen] = useState(false)
  const [mcpOauthClientId, setMcpOauthClientId] = useState('')
  const [mcpOauthServerUrl, setMcpOauthServerUrl] = useState('')
  const [mcpOauthScopes, setMcpOauthScopes] = useState('')
  const [mcpHeadersHelper, setMcpHeadersHelper] = useState('')
  const [mcpHeaderRows, setMcpHeaderRows] = useState<HeaderRow[]>([newHeaderRow()])
  const [creatingCustom, setCreatingCustom] = useState(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState<Record<string, string>>({})
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({})
  const [statusPatch, setStatusPatch] = useState<
    Record<string, CatalogStatusPatch>
  >({})

  const resetCustomForm = useCallback(() => {
    setMcpName('')
    setMcpTarget('')
    setMcpDescription('')
    setMcpOauthClientId('')
    setMcpOauthServerUrl('')
    setMcpOauthScopes('')
    setMcpHeadersHelper('')
    setMcpHeaderRows([newHeaderRow()])
    setMcpTransport('streamable_http')
    setMcpAdvancedOpen(false)
  }, [])

  const submitCustomMcp = useCallback(async () => {
    const name = mcpName.trim()
    const target = mcpTarget.trim()
    if (!name || !target) return
    setCreatingCustom(true)
    try {
      const isLocal = mcpMode === 'local'
      const parts = isLocal ? target.split(/\s+/).filter(Boolean) : []
      const headers = isLocal ? null : headersFromRows(mcpHeaderRows)
      await onCreateMcp({
        name,
        transport: isLocal ? 'stdio' : mcpTransport,
        command: isLocal ? parts[0] || null : null,
        args: isLocal ? parts.slice(1) : [],
        url: isLocal ? null : target,
        enabled: true,
        description: mcpDescription.trim() || null,
        oauthClientId: mcpOauthClientId.trim() || null,
        oauthServerUrl: mcpOauthServerUrl.trim() || null,
        oauthScopes: mcpOauthScopes.trim() || null,
        headersHelperCommand: mcpHeadersHelper.trim() || null,
        headers,
      })
      resetCustomForm()
      toast.success(`Added ${name}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add MCP server')
    } finally {
      setCreatingCustom(false)
    }
  }, [
    mcpDescription,
    mcpHeaderRows,
    mcpHeadersHelper,
    mcpMode,
    mcpName,
    mcpOauthClientId,
    mcpOauthScopes,
    mcpOauthServerUrl,
    mcpTarget,
    mcpTransport,
    onCreateMcp,
    resetCustomForm,
  ])

  const customServers = useMemo(
    () => mcpServers.filter(server => !server.catalogId),
    [mcpServers],
  )

  useEffect(() => {
    // Drop optimistic patches once the catalog reflects the latest server state.
    setStatusPatch(prev => {
      if (Object.keys(prev).length === 0) return prev
      const next = { ...prev }
      for (const entry of catalog) {
        const patch = next[entry.id]
        if (!patch) continue
        const connectedMatches =
          patch.connected === undefined || patch.connected === entry.connected
        const enabledMatches =
          patch.enabled === undefined || patch.enabled === entry.enabled
        const messageMatches =
          patch.statusMessage === undefined ||
          (patch.statusMessage ?? null) === (entry.statusMessage ?? null)
        const countMatches =
          patch.toolCount === undefined ||
          patch.toolCount === (entry.toolCount ?? null)
        if (
          connectedMatches &&
          enabledMatches &&
          messageMatches &&
          countMatches
        ) {
          delete next[entry.id]
        }
      }
      return next
    })
  }, [catalog])

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      const catalogId = String(data.catalogId || '')
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth', {
          description: catalogId || undefined,
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: true,
              enabled: true,
              statusMessage: null,
              toolCount: null,
            },
          }))
        }
      } else {
        toast.error(data.error || 'OAuth failed', {
          description: catalogId || undefined,
        })
        if (catalogId) {
          setStatusPatch(prev => ({
            ...prev,
            [catalogId]: {
              connected: false,
              enabled: true,
              statusMessage: data.error || 'OAuth failed',
            },
          }))
        }
      }
      void onRefresh()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [onRefresh])

  const connectOAuth = useCallback(
    async (entry: McpCatalogEntry) => {
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, { method: 'oauth' })
        if (result.authorizeUrl) {
          window.open(
            result.authorizeUrl,
            'fastfold-mcp-oauth',
            'width=560,height=720',
          )
          toast.message('Complete sign-in in the browser window…', {
            description: entry.name,
          })
        } else if (!result.ok) {
          toast.error(result.message || 'OAuth connect failed', {
            description: entry.name,
          })
          if (entry.authMode !== 'oauth') {
            setShowApiKey(prev => ({ ...prev, [entry.id]: true }))
          }
        }
      } catch (err) {
        const message = formatConnectError(err)
        const oauthUnavailable =
          /no oauth registration|use api key connect/i.test(message)
        toast.error(
          oauthUnavailable
            ? `${entry.name} OAuth needs a registered client here — use API key instead.`
            : message,
          { description: entry.name },
        )
        if (entry.authMode !== 'oauth') {
          setShowApiKey(prev => ({ ...prev, [entry.id]: true }))
        }
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [onConnectCatalog, onRefresh],
  )

  const connectApiKey = useCallback(
    async (entry: McpCatalogEntry) => {
      const apiKey = (apiKeyDraft[entry.id] || '').trim()
      if (!apiKey) {
        toast.error('API key is required', { description: entry.name })
        return
      }
      setPendingId(entry.id)
      try {
        const result = await onConnectCatalog(entry.id, {
          method: 'api_key',
          apiKey,
        })
        if (result.ok) {
          toast.dismiss()
          toast.success(
            result.message || `Connected · ${result.toolCount ?? 0} tools`,
            { description: entry.name },
          )
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: true,
              enabled: true,
              statusMessage: null,
              toolCount:
                typeof result.toolCount === 'number' ? result.toolCount : 0,
            },
          }))
          setApiKeyDraft(prev => {
            const next = { ...prev }
            delete next[entry.id]
            return next
          })
          setShowApiKey(prev => ({ ...prev, [entry.id]: false }))
        } else {
          toast.error(result.message || 'Connect failed', {
            description: entry.name,
          })
          setStatusPatch(prev => ({
            ...prev,
            [entry.id]: {
              connected: false,
              enabled: false,
              statusMessage: result.message || 'Connect failed',
              toolCount: null,
            },
          }))
        }
      } catch (err) {
        toast.error(formatConnectError(err), { description: entry.name })
      } finally {
        setPendingId(null)
        await onRefresh()
      }
    },
    [apiKeyDraft, onConnectCatalog, onRefresh],
  )

  const renderCatalogCard = (entry: McpCatalogEntry) => {
    const view = withStatusPatch(entry, statusPatch[entry.id])
    const pending = pendingId === view.id
    const supportsApiKey = view.authMode !== 'oauth'
    const supportsOAuth = view.authMode !== 'api_key'
    const hasBoth = supportsApiKey && supportsOAuth
    const isSetup = view.configured || view.connected || view.enabled
    const label = isSetup ? 'Reconnect' : 'Connect'

    const primaryConnect = () => {
      if (supportsOAuth && view.preferredAuth === 'oauth') {
        void connectOAuth(view)
        return
      }
      if (supportsApiKey && !supportsOAuth) {
        setShowApiKey(prev => ({ ...prev, [view.id]: true }))
        return
      }
      if (supportsOAuth) {
        void connectOAuth(view)
        return
      }
      setShowApiKey(prev => ({ ...prev, [view.id]: true }))
    }

    return (
      <div
        key={view.id}
        className="bg-background/60 hover:bg-muted/40 flex h-full flex-col rounded-lg p-3 transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <McpIcon id={view.id} name={view.name} />
              <span className="truncate text-sm font-medium">{view.name}</span>
              {authMeta(view)}
              {statusBadge(view)}
            </div>
            <p className="text-muted-foreground mt-1 line-clamp-2 min-h-10 text-sm">
              {view.description}
            </p>
          </div>
          {isSetup ? (
            <McpToggle
              enabled={view.enabled}
              pending={pending}
              label={
                view.enabled
                  ? `Disable ${view.name}`
                  : `Enable ${view.name}`
              }
              onToggle={() => {
                if (!view.configured && !view.enabled) {
                  toast.error(
                    'Connect with OAuth or API key first, then enable.',
                    { description: view.name },
                  )
                  return
                }
                const nextEnabled = !view.enabled
                setPendingId(view.id)
                setStatusPatch(prev => ({
                  ...prev,
                  [view.id]: {
                    enabled: nextEnabled,
                    connected: nextEnabled ? view.connected : false,
                    statusMessage: nextEnabled ? view.statusMessage : null,
                    toolCount: nextEnabled ? view.toolCount : view.toolCount,
                  },
                }))
                void onToggleCatalog(view, nextEnabled)
                  .then(() =>
                    toast.success(nextEnabled ? 'Enabled' : 'Disabled', {
                      description: view.name,
                    }),
                  )
                  .catch((err: unknown) => {
                    setStatusPatch(prev => {
                      const next = { ...prev }
                      delete next[view.id]
                      return next
                    })
                    toast.error(formatConnectError(err), {
                      description: view.name,
                    })
                  })
                  .finally(() => setPendingId(null))
              }}
            />
          ) : null}
        </div>

        <div className="mt-auto flex w-full items-center gap-2 pt-2">
          {hasBoth ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs"
                  disabled={pending}
                >
                  {pending ? (
                    <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  ) : null}
                  {label}
                  <ChevronDown className="ml-1 size-3.5 opacity-70" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-44">
                <DropdownMenuItem
                  disabled={pending}
                  onSelect={() => void connectOAuth(view)}
                >
                  With OAuth
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={pending}
                  onSelect={() =>
                    setShowApiKey(prev => ({ ...prev, [view.id]: true }))
                  }
                >
                  <KeyRound className="mr-2 size-3.5" />
                  With API key
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              disabled={pending}
              onClick={() => primaryConnect()}
            >
              {pending ? (
                <Loader2 className="mr-1.5 size-3.5 animate-spin" />
              ) : null}
              {label}
            </Button>
          )}
          {view.docsUrl ? (
            <a
              href={view.docsUrl}
              target="_blank"
              rel="noreferrer"
              className="text-muted-foreground hover:text-foreground ml-auto inline-flex shrink-0 items-center gap-1 text-xs"
            >
              Docs <ExternalLink className="size-3" />
            </a>
          ) : null}
        </div>

        {showApiKey[view.id] && supportsApiKey ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border/50 pt-3">
            <Input
              type="password"
              className="max-w-md"
              placeholder={view.apiKeyEnvVar || 'API key'}
              autoFocus
              value={apiKeyDraft[view.id] || ''}
              onChange={event =>
                setApiKeyDraft(prev => ({
                  ...prev,
                  [view.id]: event.target.value,
                }))
              }
              onKeyDown={event => {
                if (event.key === 'Enter') void connectApiKey(view)
              }}
            />
            <Button
              size="sm"
              disabled={pending || !(apiKeyDraft[view.id] || '').trim()}
              onClick={() => void connectApiKey(view)}
            >
              Save & enable
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                setShowApiKey(prev => ({ ...prev, [view.id]: false }))
              }
            >
              Cancel
            </Button>
          </div>
        ) : null}
      </div>
    )
  }

  const featuredSection = (
    <section className={featuredOnly ? 'space-y-3' : 'space-y-2'}>
      <div
        className={cn(
          'flex gap-2',
          featuredOnly ? 'items-end justify-between' : 'items-center justify-between',
        )}
      >
        {featuredOnly ? (
          <div>
            <h3 className="text-base font-semibold tracking-tight">MCPs</h3>
            <p className="text-muted-foreground text-xs font-medium">
              Featured ({catalog.length})
            </p>
          </div>
        ) : (
          <p className="text-muted-foreground text-xs font-medium">
            Featured ({catalog.length})
          </p>
        )}
        {featuredOnly && onShowAll ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-medium transition-colors"
            onClick={onShowAll}
          >
            Show all
            <ArrowRight className="size-3.5" />
          </button>
        ) : null}
      </div>
      {catalogLoading && catalog.length === 0 ? (
        <CardGridSkeleton cards={featuredOnly ? 2 : 4} columns={2} />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {(featuredOnly ? catalog.slice(0, 2) : catalog).map(entry =>
            renderCatalogCard(entry),
          )}
        </div>
      )}
    </section>
  )

  if (featuredOnly) {
    return featuredSection
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-6">
        <div>
          <h2 className="text-2xl font-semibold">MCP servers</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Connect featured cloud MCPs (off by default). Credentials save under
            Integrations / keys. Add custom stdio, SSE, or HTTP servers below.
          </p>
        </div>

        <div className="space-y-6 pb-4">
          {featuredSection}

          <section className="space-y-2">
            <p className="text-muted-foreground text-xs font-medium">
              Custom ({customServers.length})
            </p>
            <p className="text-muted-foreground text-sm">
              Add a remote HTTP/SSE MCP or a local stdio command. Custom headers
              and a headers helper cover API keys and other auth schemes.
            </p>

            <div className="bg-background/60 space-y-3 rounded-lg border p-4">
              <div className="inline-flex rounded-md border p-0.5">
                <button
                  type="button"
                  className={cn(
                    'rounded px-3 py-1.5 text-sm transition-colors',
                    mcpMode === 'remote'
                      ? 'bg-muted font-medium'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  onClick={() => setMcpMode('remote')}
                >
                  Remote
                </button>
                <button
                  type="button"
                  className={cn(
                    'rounded px-3 py-1.5 text-sm transition-colors',
                    mcpMode === 'local'
                      ? 'bg-muted font-medium'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                  onClick={() => setMcpMode('local')}
                >
                  Local command
                </button>
              </div>

              <div className="space-y-2">
                <label className="text-muted-foreground text-xs font-medium">
                  Name
                </label>
                <Input
                  value={mcpName}
                  onChange={event => setMcpName(event.target.value)}
                  placeholder="My MCP server"
                />
              </div>

              <div className="space-y-2">
                <label className="text-muted-foreground text-xs font-medium">
                  {mcpMode === 'local'
                    ? 'Command'
                    : 'Remote MCP server URL'}
                </label>
                <Input
                  value={mcpTarget}
                  onChange={event => setMcpTarget(event.target.value)}
                  placeholder={
                    mcpMode === 'local'
                      ? 'npx -y @example/mcp-server'
                      : 'https://mcp.example.com/mcp'
                  }
                  className="font-mono text-sm"
                />
              </div>

              {mcpMode === 'remote' ? (
                <div className="space-y-2">
                  <label className="text-muted-foreground text-xs font-medium">
                    Transport
                  </label>
                  <select
                    value={mcpTransport}
                    onChange={event =>
                      setMcpTransport(
                        event.target.value as 'sse' | 'streamable_http',
                      )
                    }
                    className="bg-background h-9 w-full rounded-md border px-3 text-sm"
                  >
                    <option value="streamable_http">Streamable HTTP</option>
                    <option value="sse">SSE (legacy)</option>
                  </select>
                </div>
              ) : null}

              <div className="space-y-2">
                <label className="text-muted-foreground text-xs font-medium">
                  Description (optional)
                </label>
                <Input
                  value={mcpDescription}
                  onChange={event => setMcpDescription(event.target.value)}
                  placeholder="What this server is for"
                />
              </div>

              <div className="rounded-md border">
                <button
                  type="button"
                  className="hover:bg-muted/40 flex w-full items-center justify-between px-3 py-2 text-left text-sm"
                  onClick={() => setMcpAdvancedOpen(open => !open)}
                >
                  <span className="font-medium">Advanced settings</span>
                  <ChevronDown
                    className={cn(
                      'text-muted-foreground size-4 transition-transform',
                      mcpAdvancedOpen && 'rotate-180',
                    )}
                  />
                </button>
                {mcpAdvancedOpen ? (
                  <div className="space-y-3 border-t px-3 py-3">
                    {mcpMode === 'remote' ? (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-2">
                          <label className="text-muted-foreground text-xs font-medium">
                            Custom headers
                          </label>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className="h-7 gap-1 px-2 text-xs"
                            onClick={() =>
                              setMcpHeaderRows(rows => [...rows, newHeaderRow()])
                            }
                          >
                            <Plus className="size-3.5" />
                            Add header
                          </Button>
                        </div>
                        <div className="space-y-2">
                          {mcpHeaderRows.map(row => (
                            <div
                              key={row.id}
                              className="grid grid-cols-[1fr_1fr_auto] gap-2"
                            >
                              <Input
                                value={row.name}
                                onChange={event =>
                                  setMcpHeaderRows(rows =>
                                    rows.map(item =>
                                      item.id === row.id
                                        ? { ...item, name: event.target.value }
                                        : item,
                                    ),
                                  )
                                }
                                placeholder="Header name"
                                className="font-mono text-sm"
                              />
                              <Input
                                type="password"
                                value={row.value}
                                onChange={event =>
                                  setMcpHeaderRows(rows =>
                                    rows.map(item =>
                                      item.id === row.id
                                        ? { ...item, value: event.target.value }
                                        : item,
                                    ),
                                  )
                                }
                                placeholder="Value"
                                className="font-mono text-sm"
                                autoComplete="off"
                              />
                              <Button
                                type="button"
                                size="icon"
                                variant="ghost"
                                className="size-9"
                                disabled={mcpHeaderRows.length <= 1}
                                onClick={() =>
                                  setMcpHeaderRows(rows =>
                                    rows.length <= 1
                                      ? rows
                                      : rows.filter(item => item.id !== row.id),
                                  )
                                }
                              >
                                <Trash2 className="size-3.5" />
                              </Button>
                            </div>
                          ))}
                        </div>
                        <p className="text-muted-foreground text-xs">
                          Example: Authorization / Bearer sk-… or X-API-Key /
                          your-key. Values are stored as secrets.
                        </p>
                      </div>
                    ) : null}

                    <div className="space-y-2">
                      <label className="text-muted-foreground text-xs font-medium">
                        OAuth Client ID (optional)
                      </label>
                      <Input
                        value={mcpOauthClientId}
                        onChange={event =>
                          setMcpOauthClientId(event.target.value)
                        }
                        placeholder="Stored for future OAuth connect"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-muted-foreground text-xs font-medium">
                        OAuth Server URL (optional)
                      </label>
                      <Input
                        value={mcpOauthServerUrl}
                        onChange={event =>
                          setMcpOauthServerUrl(event.target.value)
                        }
                        placeholder="https://auth.example.com"
                        className="font-mono text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-muted-foreground text-xs font-medium">
                        Scopes (optional)
                      </label>
                      <Input
                        value={mcpOauthScopes}
                        onChange={event => setMcpOauthScopes(event.target.value)}
                        placeholder="openid profile"
                      />
                    </div>
                    {mcpMode === 'remote' ? (
                      <div className="space-y-2">
                        <label className="text-muted-foreground text-xs font-medium">
                          Headers helper command (optional)
                        </label>
                        <Input
                          value={mcpHeadersHelper}
                          onChange={event =>
                            setMcpHeadersHelper(event.target.value)
                          }
                          placeholder={`echo '{"Authorization":"Bearer …"}'`}
                          className="font-mono text-sm"
                        />
                        <p className="text-muted-foreground text-xs">
                          Shell command that prints a JSON object of headers on
                          stdout. When set and successful, it replaces static
                          headers.
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="flex justify-end">
                <Button
                  disabled={
                    creatingCustom || !mcpName.trim() || !mcpTarget.trim()
                  }
                  onClick={() => void submitCustomMcp()}
                >
                  {creatingCustom ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : null}
                  Add server
                </Button>
              </div>
            </div>

            <div className="mt-3 space-y-2">
              {customServers.map(server => (
                <div
                  key={server.id}
                  className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="bg-muted text-muted-foreground grid size-6 shrink-0 place-items-center rounded">
                        <Plug className="size-3.5" />
                      </span>
                      <span className="truncate text-sm font-medium">
                        {server.name}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {server.transport === 'streamable_http'
                          ? 'Streamable HTTP'
                          : server.transport === 'sse'
                            ? 'SSE'
                            : 'stdio'}
                      </span>
                      {server.headersConfigured ? (
                        <span className="text-muted-foreground text-xs">
                          · headers
                        </span>
                      ) : null}
                    </div>
                    {server.description ? (
                      <p className="text-muted-foreground mt-1 truncate text-xs">
                        {server.description}
                      </p>
                    ) : null}
                    <p className="text-muted-foreground mt-1 truncate font-mono text-xs">
                      {server.command
                        ? `${server.command} ${server.args.join(' ')}`.trim()
                        : server.url}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <McpToggle
                      enabled={server.enabled}
                      label={`Enable ${server.name}`}
                      onToggle={() =>
                        void onToggleCustom(server.id, !server.enabled)
                      }
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      onClick={() => void onDeleteMcp(server.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
              {customServers.length === 0 ? (
                <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                  No custom MCP servers yet.
                </p>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </ScrollArea>
  )
}
