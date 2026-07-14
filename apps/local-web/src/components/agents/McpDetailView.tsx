import type {
  McpCatalogEntry,
  McpServer,
  McpToolDetail,
  ValidateMcpResult
} from '@sandwalk/agent-ui-core'
import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  Loader2,
  Plug,
  RefreshCw,
  Search,
  Wrench
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const MCP_ICONS: Record<string, { src: string; invertInDark?: boolean }> = {
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  linear: { src: '/integrations/linear.png' }
}

function McpIcon({
  id,
  name,
  className
}: {
  id?: string | null
  name: string
  className?: string
}) {
  const icon = id ? MCP_ICONS[id] : undefined
  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          'size-9 rounded object-contain',
          icon.invertInDark && 'dark:invert',
          className
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted text-muted-foreground grid size-9 shrink-0 place-items-center rounded',
        className
      )}
      aria-label={name}
    >
      <Plug className="size-5" />
    </span>
  )
}

function schemaPropertyEntries(schema: Record<string, unknown> | null) {
  if (!schema || typeof schema !== 'object') return []
  const properties = schema.properties
  if (!properties || typeof properties !== 'object' || Array.isArray(properties)) {
    return []
  }
  const required = Array.isArray(schema.required)
    ? schema.required.map(String)
    : []
  return Object.entries(properties as Record<string, unknown>).map(
    ([key, value]) => {
      const prop =
        value && typeof value === 'object' && !Array.isArray(value)
          ? (value as Record<string, unknown>)
          : {}
      const typeValue = prop.type
      const typeLabel = Array.isArray(typeValue)
        ? typeValue.map(String).join(' | ')
        : typeof typeValue === 'string'
          ? typeValue
          : 'any'
      return {
        key,
        required: required.includes(key),
        type: typeLabel,
        description:
          typeof prop.description === 'string' ? prop.description : null
      }
    }
  )
}

function firstParagraph(text: string, maxChars = 220): string {
  const cleaned = text.replace(/\s+/g, ' ').trim()
  if (!cleaned) return ''
  const cut = cleaned.split(/(?<=\.)\s+/)[0] || cleaned
  if (cut.length <= maxChars) return cut
  return `${cut.slice(0, maxChars - 1).trimEnd()}…`
}

function ToolCard({ tool }: { tool: McpToolDetail }) {
  const [open, setOpen] = useState(false)
  const properties = useMemo(
    () => schemaPropertyEntries(tool.inputSchema),
    [tool.inputSchema]
  )
  const hasSchema =
    properties.length > 0 ||
    (tool.inputSchema != null && Object.keys(tool.inputSchema).length > 0)
  const summary = tool.description
    ? firstParagraph(tool.description)
    : tool.title?.trim() || null
  const showFullDescription =
    open && Boolean(tool.description && tool.description !== summary)

  return (
    <div className="overflow-hidden rounded-lg border border-border/70">
      <button
        type="button"
        className="hover:bg-muted/40 flex w-full items-start gap-3 px-3 py-3 text-left transition-colors"
        onClick={() => setOpen(current => !current)}
        aria-expanded={open}
      >
        <span className="bg-muted text-muted-foreground mt-0.5 grid size-7 shrink-0 place-items-center rounded">
          <Wrench className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <code className="truncate text-sm font-medium">{tool.name}</code>
            {tool.title && tool.title !== tool.name ? (
              <span className="text-muted-foreground truncate text-xs">
                {tool.title}
              </span>
            ) : null}
            {hasSchema || tool.description ? (
              <ChevronDown
                className={cn(
                  'text-muted-foreground ml-auto size-4 shrink-0 transition-transform',
                  open && 'rotate-180'
                )}
              />
            ) : null}
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            {summary || 'No description provided.'}
          </p>
        </div>
      </button>
      {open && (showFullDescription || hasSchema) ? (
        <div className="border-t border-border/60 bg-muted/20 space-y-3 px-3 py-3">
          {showFullDescription ? (
            <p className="text-muted-foreground whitespace-pre-wrap text-xs leading-relaxed">
              {tool.description}
            </p>
          ) : null}
          {hasSchema ? (
            properties.length > 0 ? (
              <div className="space-y-2.5">
                <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Parameters
                </p>
                {properties.map(prop => (
                  <div key={prop.key} className="space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <code className="text-foreground font-medium">{prop.key}</code>
                      <span className="text-muted-foreground">{prop.type}</span>
                      {prop.required ? (
                        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                          required
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-[10px]">
                          optional
                        </span>
                      )}
                    </div>
                    {prop.description ? (
                      <p className="text-muted-foreground text-xs leading-relaxed">
                        {prop.description}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <pre className="text-muted-foreground overflow-x-auto font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(tool.inputSchema, null, 2)}
              </pre>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export function McpDetailView({
  kind,
  catalogEntry,
  server,
  onBack,
  onLoadTools,
  onToggleEnabled
}: {
  kind: 'catalog' | 'server'
  catalogEntry?: McpCatalogEntry | null
  server?: McpServer | null
  onBack: () => void
  onLoadTools: () => Promise<ValidateMcpResult>
  onToggleEnabled?: (enabled: boolean) => Promise<void>
}) {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ValidateMcpResult | null>(null)
  const [togglePending, setTogglePending] = useState(false)
  const [toolQuery, setToolQuery] = useState('')

  const title =
    kind === 'catalog'
      ? catalogEntry?.name || 'MCP'
      : server?.name || 'MCP'
  const description =
    kind === 'catalog'
      ? catalogEntry?.description || null
      : server?.description || null
  const enabled =
    kind === 'catalog'
      ? Boolean(catalogEntry?.enabled)
      : Boolean(server?.enabled)
  const connected =
    kind === 'catalog'
      ? Boolean(catalogEntry?.connected)
      : Boolean(server?.enabled)
  const docsUrl =
    kind === 'catalog' ? catalogEntry?.docsUrl || null : null
  const transport =
    kind === 'catalog'
      ? catalogEntry?.transport || null
      : server?.transport || null
  const endpoint =
    kind === 'catalog'
      ? catalogEntry?.url || null
      : server?.url || server?.command || null

  const tools = useMemo(() => {
    if (result?.toolDetails?.length) return result.toolDetails
    return (result?.tools || []).map(name => ({
      name,
      title: null,
      description: null,
      inputSchema: null
    }))
  }, [result])

  const filteredTools = useMemo(() => {
    const q = toolQuery.trim().toLowerCase()
    if (!q) return tools
    return tools.filter(tool => {
      const haystack = [tool.name, tool.title, tool.description]
        .filter(Boolean)
        .join('\n')
        .toLowerCase()
      return haystack.includes(q)
    })
  }, [toolQuery, tools])

  const missingDescriptions =
    tools.length > 0 && tools.every(tool => !tool.description)

  async function loadTools(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError(null)
    try {
      const next = await onLoadTools()
      setResult(next)
      if (!next.ok) {
        setError(next.message || 'Unable to load MCP tools')
      }
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void loadTools(false)
    // Intentionally reload when the target MCP changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, catalogEntry?.id, server?.id])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">/</span>
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              MCPs
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              disabled={loading || refreshing}
              onClick={() => void loadTools(true)}
            >
              {refreshing ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              Refresh tools
            </Button>
            {docsUrl ? (
              <a
                href={docsUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
              >
                Docs
                <ExternalLink className="size-3.5" />
              </a>
            ) : null}
          </div>
        </div>

        <div className="grid items-start gap-4 lg:grid-cols-[240px_minmax(0,1fr)_220px]">
          <aside className="space-y-3 lg:sticky lg:top-4 lg:border-r lg:border-border/60 lg:pr-4">
            <div className="space-y-2">
              <McpIcon
                id={kind === 'catalog' ? catalogEntry?.id : null}
                name={title}
              />
              <div className="min-w-0 space-y-0.5">
                <div className="flex items-start justify-between gap-2">
                  <h1 className="break-all text-lg font-semibold">{title}</h1>
                  {onToggleEnabled ? (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={enabled}
                      aria-label={enabled ? `Disable ${title}` : `Enable ${title}`}
                      disabled={togglePending}
                      className={cn(
                        'relative mt-1 inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
                        enabled
                          ? 'bg-black/75 dark:bg-zinc-300/50'
                          : 'bg-zinc-200 dark:bg-zinc-700',
                        togglePending && 'cursor-not-allowed opacity-60'
                      )}
                      onClick={() => {
                        setTogglePending(true)
                        void onToggleEnabled(!enabled)
                          .catch(() => undefined)
                          .finally(() => setTogglePending(false))
                      }}
                    >
                      <span
                        className={cn(
                          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
                          enabled ? 'translate-x-4' : 'translate-x-0.5'
                        )}
                      />
                    </button>
                  ) : null}
                </div>
                <p className="text-muted-foreground mb-6 pb-3 text-sm leading-relaxed">
                  {description || 'MCP server'}
                </p>
                <div className="mt-6 space-y-1 border-t border-border/60 pt-5 text-xs">
                  <div className="text-muted-foreground flex items-center gap-1.5">
                    <span className="text-foreground/90 font-medium">Type:</span>
                    <span className="truncate">
                      {kind === 'catalog' ? 'Featured' : 'Custom'}
                    </span>
                  </div>
                  {transport ? (
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <span className="text-foreground/90 font-medium">
                        Transport:
                      </span>
                      <span className="truncate">{transport}</span>
                    </div>
                  ) : null}
                  {kind === 'catalog' && catalogEntry?.authMethod ? (
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <span className="text-foreground/90 font-medium">
                        Auth:
                      </span>
                      <span className="truncate">
                        {catalogEntry.authMethod === 'oauth'
                          ? 'OAuth'
                          : 'API key'}
                      </span>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </aside>

          <section className="min-w-0 space-y-4 overflow-x-hidden p-1">
            <div>
              <h2 className="text-base font-semibold">Available tools</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Tool calls exposed by this MCP, including descriptions and
                parameter schemas when available.
              </p>
            </div>

            {!loading && tools.length > 0 ? (
              <div className="relative">
                <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
                <Input
                  value={toolQuery}
                  onChange={event => setToolQuery(event.target.value)}
                  placeholder="Search tools…"
                  className="h-8 pl-8 text-sm"
                  aria-label="Search tools"
                />
              </div>
            ) : null}

            {loading ? (
              <div className="text-muted-foreground flex items-center gap-2 text-sm">
                <Loader2 className="size-4 animate-spin" />
                Loading tools…
              </div>
            ) : null}

            {!loading && error ? (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
                {error}
              </div>
            ) : null}

            {!loading && !error && missingDescriptions ? (
              <div className="text-muted-foreground rounded-lg border border-border/70 bg-muted/30 px-3 py-2.5 text-sm">
                Tool names loaded, but descriptions were not returned by the
                agent server probe. Click Refresh tools after updating or
                restarting the local agent server.
              </div>
            ) : null}

            {!loading && !error && tools.length === 0 ? (
              <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                No tools reported by this MCP yet. Connect and enable it, then
                refresh.
              </p>
            ) : null}

            {!loading && tools.length > 0 && filteredTools.length === 0 ? (
              <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
                No tools match “{toolQuery.trim()}”.
              </p>
            ) : null}

            {!loading && filteredTools.length > 0 ? (
              <div className="space-y-2">
                {filteredTools.map(tool => (
                  <ToolCard key={tool.name} tool={tool} />
                ))}
              </div>
            ) : null}
          </section>

          <aside className="space-y-5 lg:sticky lg:top-4">
            <div>
              <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                Tools
              </p>
              <p className="mt-1 text-3xl font-semibold tabular-nums">
                {result?.toolCount ??
                  catalogEntry?.toolCount ??
                  tools.length ??
                  0}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                Status
              </p>
              <p className="mt-1 inline-flex items-center gap-1.5 text-sm">
                <span
                  className={cn(
                    'size-1.5 rounded-full',
                    connected ? 'bg-emerald-500' : 'bg-muted-foreground/50'
                  )}
                />
                {connected ? 'Connected' : enabled ? 'Enabled' : 'Disabled'}
              </p>
            </div>
            {endpoint ? (
              <div>
                <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Endpoint
                </p>
                <p className="text-muted-foreground mt-1 break-all font-mono text-xs leading-relaxed">
                  {endpoint}
                </p>
              </div>
            ) : null}
            {result?.message ? (
              <div>
                <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Last probe
                </p>
                <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                  {result.message}
                </p>
              </div>
            ) : null}
          </aside>
        </div>
      </div>
    </ScrollArea>
  )
}
