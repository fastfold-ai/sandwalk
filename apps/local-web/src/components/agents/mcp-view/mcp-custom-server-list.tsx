import type { ConnectMcpResult, McpServer } from '@sandwalk/agent-ui-core'
import { KeyRound, Loader2, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { McpMark } from '@/components/McpMark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { formatConnectError, McpToggle } from './mcp-view-shared'

function transportLabel(server: McpServer): string {
  if (server.transport === 'streamable_http') return 'HTTP'
  if (server.transport === 'sse') return 'SSE'
  return 'stdio'
}

function subtitle(server: McpServer): string {
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

function faviconUrlForServer(server: McpServer): string | null {
  const raw = server.url?.trim()
  if (!raw) return null
  try {
    const withScheme = raw.includes('://') ? raw : `https://${raw}`
    const host = new URL(withScheme).hostname
    if (!host) return null
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`
  } catch {
    return null
  }
}

function CustomServerIcon({ server }: { server: McpServer }) {
  const favicon = faviconUrlForServer(server)
  const [failed, setFailed] = useState(false)

  if (favicon && !failed) {
    return (
      <img
        src={favicon}
        alt=""
        className="size-5 rounded-sm object-contain"
        onError={() => setFailed(true)}
      />
    )
  }
  return <McpMark className="size-4" />
}

export function McpCustomServerList({
  customServers,
  focusedMcpKey,
  onOpenServer,
  onToggleCustom,
  onDeleteMcp,
  onConnect,
  onAddNew
}: {
  customServers: McpServer[]
  focusedMcpKey: string | null
  onOpenServer?: (server: McpServer) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
  onConnect?: (
    server: McpServer,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onAddNew?: () => void
}) {
  const [apiKeyServerId, setApiKeyServerId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [waitingId, setWaitingId] = useState<string | null>(null)

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      if (!waitingId) return
      // Catalog OAuth includes catalogId — ignore for custom Connect waiting.
      if (data.catalogId) return
      const serverId = String(data.serverId || '')
      if (serverId !== waitingId) return
      setWaitingId(null)
      setPendingId(null)
      if (!data.ok) {
        setApiKeyServerId(prev => prev || waitingId)
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [waitingId])

  const connectOAuth = async (server: McpServer) => {
    if (!onConnect) return
    setPendingId(server.id)
    setApiKeyServerId(null)
    try {
      const result = await onConnect(server, { method: 'oauth' })
      if (result.authorizeUrl) {
        window.open(
          result.authorizeUrl,
          'fastfold-mcp-oauth',
          'width=560,height=720'
        )
        setWaitingId(server.id)
        toast.message('Complete sign-in in the browser window…', {
          description: server.name
        })
      } else if (!result.ok) {
        toast.error(result.message || 'OAuth connect failed', {
          description: server.name
        })
        setApiKeyServerId(server.id)
      }
    } catch (err) {
      const message = formatConnectError(err)
      const oauthUnavailable =
        /no oauth registration|use api key|could not discover oauth/i.test(
          message
        )
      toast.error(
        oauthUnavailable
          ? `${server.name} does not advertise OAuth — use an API key instead.`
          : message,
        { description: server.name }
      )
      setApiKeyServerId(server.id)
    } finally {
      setPendingId(null)
    }
  }

  const connectApiKey = async (server: McpServer) => {
    if (!onConnect || !apiKeyDraft.trim()) return
    setPendingId(server.id)
    try {
      const result = await onConnect(server, {
        method: 'api_key',
        apiKey: apiKeyDraft.trim()
      })
      if (result.ok) {
        toast.success(result.message || 'Authenticated')
        setApiKeyServerId(null)
        setApiKeyDraft('')
      } else {
        toast.error(result.message || 'Authentication failed')
      }
    } catch (err) {
      toast.error(formatConnectError(err))
    } finally {
      setPendingId(null)
    }
  }

  return (
    <div className="mt-3 space-y-2">
      {customServers.map(server => {
        const needsAuth = customServerNeedsAuth(server)
        // Always show off while unauthenticated (matches Cursor).
        const shownEnabled = needsAuth ? false : server.enabled
        const waiting = waitingId === server.id
        const pending = pendingId === server.id
        const showApiKey = apiKeyServerId === server.id

        return (
          <div key={server.id} className="space-y-2">
            <div
              id={`mcp-server-${server.id}`}
              role={onOpenServer ? 'button' : undefined}
              tabIndex={onOpenServer ? 0 : undefined}
              onClick={() => onOpenServer?.(server)}
              onKeyDown={event => {
                if (!onOpenServer) return
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onOpenServer(server)
                }
              }}
              className={cn(
                'bg-card hover:bg-muted/40 flex items-center gap-3 rounded-xl border px-3 py-3 transition-colors',
                onOpenServer && 'cursor-pointer',
                focusedMcpKey === `server-${server.id}` &&
                  'ring-ring ring-2 ring-offset-2 ring-offset-background'
              )}
            >
              <div className="relative shrink-0">
                <span className="bg-muted text-foreground grid size-9 place-items-center rounded-lg border">
                  <CustomServerIcon server={server} />
                </span>
                <span
                  className={cn(
                    'border-background absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2',
                    shownEnabled
                      ? 'bg-emerald-500'
                      : needsAuth || waiting
                        ? 'bg-amber-500'
                        : 'bg-muted-foreground/40'
                  )}
                  aria-hidden
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-semibold">
                    {server.name}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {transportLabel(server)}
                  </span>
                </div>
                <p className="text-muted-foreground mt-0.5 truncate text-xs">
                  {waiting
                    ? 'Waiting for callback…'
                    : needsAuth
                      ? 'Needs authentication'
                      : subtitle(server)}
                </p>
              </div>

              <div
                className="flex shrink-0 items-center gap-1.5"
                onClick={event => event.stopPropagation()}
              >
                {waiting ? (
                  <>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => {
                        setWaitingId(null)
                        toast.message('OAuth cancelled')
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 gap-1.5 px-2.5 text-xs"
                      disabled
                    >
                      <Loader2 className="size-3.5 animate-spin" />
                      Waiting for callback…
                    </Button>
                  </>
                ) : needsAuth && onConnect ? (
                  <>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 gap-1 px-2 text-xs"
                      onClick={() => {
                        setApiKeyServerId(showApiKey ? null : server.id)
                        setApiKeyDraft('')
                      }}
                    >
                      <KeyRound className="size-3.5" />
                      {showApiKey ? 'Cancel' : 'API key'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 px-2.5 text-xs"
                      disabled={pending}
                      onClick={() => void connectOAuth(server)}
                    >
                      {pending ? (
                        <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                      ) : null}
                      Connect
                    </Button>
                  </>
                ) : (
                  <McpToggle
                    enabled={shownEnabled}
                    label={`Enable ${server.name}`}
                    onToggle={() => {
                      if (!server.enabled && needsAuth) {
                        toast.message('Connect this server before enabling')
                        return
                      }
                      onToggleCustom(server.id, !server.enabled)
                    }}
                  />
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  aria-label={`Remove ${server.name}`}
                  onClick={() => onDeleteMcp(server.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>

            {showApiKey && onConnect && !waiting ? (
              <div
                className="bg-muted/20 flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2.5"
                onClick={event => event.stopPropagation()}
              >
                <Input
                  type="password"
                  className="max-w-md"
                  placeholder="API key or Bearer token"
                  value={apiKeyDraft}
                  autoFocus
                  disabled={pending}
                  onChange={event => setApiKeyDraft(event.target.value)}
                  onKeyDown={event => {
                    if (event.key === 'Enter') void connectApiKey(server)
                  }}
                />
                <Button
                  type="button"
                  size="sm"
                  className="h-8 text-xs"
                  disabled={pending || !apiKeyDraft.trim()}
                  onClick={() => void connectApiKey(server)}
                >
                  {pending ? (
                    <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  ) : null}
                  Save
                </Button>
              </div>
            ) : null}
          </div>
        )
      })}

      {onAddNew ? (
        <button
          type="button"
          onClick={onAddNew}
          className="bg-card hover:bg-muted/40 flex w-full items-center gap-3 rounded-xl border border-dashed px-3 py-3 text-left transition-colors"
        >
          <span className="bg-muted text-muted-foreground grid size-9 place-items-center rounded-lg border">
            <Plus className="size-4" />
          </span>
          <span className="min-w-0">
            <span className="text-foreground block text-sm font-semibold">
              New MCP Server
            </span>
            <span className="text-muted-foreground block text-xs">
              Add a custom MCP server
            </span>
          </span>
        </button>
      ) : null}

      {customServers.length === 0 && !onAddNew ? (
        <p className="text-muted-foreground rounded-lg border border-dashed p-4 text-sm">
          No custom MCP servers yet.
        </p>
      ) : null}
    </div>
  )
}
