import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { KeyRound, Loader2, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import {
  authStatusLabel,
  CustomServerIcon,
  customServerNeedsAuth,
  isAuthReconnectMessage,
  serverNeedsAuth
} from './mcp-custom-server-helpers'
import { formatConnectError, McpToggle } from './mcp-view-shared'

export { customServerNeedsAuth }

export function McpCustomServerList({
  installedServers,
  catalogById,
  focusedMcpKey,
  onOpenServer,
  onOpenCatalog,
  onToggleCustom,
  onToggleCatalog,
  onDeleteMcp,
  onConnectCustom,
  onConnectCatalog,
  onAddNew
}: {
  installedServers: McpServer[]
  catalogById: Map<string, McpCatalogEntry>
  focusedMcpKey: string | null
  onOpenServer?: (server: McpServer) => void
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onToggleCustom: (id: string, enabled: boolean) => void
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => void
  onDeleteMcp: (id: string) => void
  onConnectCustom?: (
    server: McpServer,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onConnectCatalog: (
    catalogId: string,
    input: { method: 'oauth' | 'api_key'; apiKey?: string }
  ) => Promise<ConnectMcpResult>
  onAddNew?: () => void
}) {
  const [apiKeyServerId, setApiKeyServerId] = useState<string | null>(null)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [waitingId, setWaitingId] = useState<string | null>(null)
  const [waitingCatalogId, setWaitingCatalogId] = useState<string | null>(null)

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data
      if (!data || data.type !== 'fastfold-mcp-oauth') return
      if (!waitingId && !waitingCatalogId) return

      const catalogId = String(data.catalogId || '')
      const serverId = String(data.serverId || '')

      if (waitingCatalogId) {
        if (catalogId && catalogId !== waitingCatalogId) return
        if (!catalogId && serverId && serverId !== waitingId) return
      } else if (waitingId) {
        // Custom Connect waiting — ignore catalog OAuth messages.
        if (catalogId) return
        if (serverId !== waitingId) return
      }

      setWaitingId(null)
      setWaitingCatalogId(null)
      setPendingId(null)
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth')
      } else {
        setApiKeyServerId(prev => prev || waitingId)
        toast.error(data.error || 'OAuth failed')
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [waitingId, waitingCatalogId])

  const connectOAuth = async (server: McpServer) => {
    setPendingId(server.id)
    setApiKeyServerId(null)
    try {
      const result = server.catalogId
        ? await onConnectCatalog(server.catalogId, { method: 'oauth' })
        : onConnectCustom
          ? await onConnectCustom(server, { method: 'oauth' })
          : null
      if (!result) return
      if (result.authorizeUrl) {
        window.open(
          result.authorizeUrl,
          'fastfold-mcp-oauth',
          'width=560,height=720'
        )
        setWaitingId(server.id)
        setWaitingCatalogId(server.catalogId || null)
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
    if (!apiKeyDraft.trim()) return
    setPendingId(server.id)
    try {
      const result = server.catalogId
        ? await onConnectCatalog(server.catalogId, {
            method: 'api_key',
            apiKey: apiKeyDraft.trim()
          })
        : onConnectCustom
          ? await onConnectCustom(server, {
              method: 'api_key',
              apiKey: apiKeyDraft.trim()
            })
          : null
      if (!result) return
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

  const openRow = (server: McpServer) => {
    if (server.catalogId) {
      const entry = catalogById.get(server.catalogId)
      if (entry && onOpenCatalog) {
        onOpenCatalog(entry)
        return
      }
    }
    onOpenServer?.(server)
  }

  const canOpen = (server: McpServer) => {
    if (server.catalogId && catalogById.get(server.catalogId) && onOpenCatalog) {
      return true
    }
    return Boolean(onOpenServer)
  }

  if (installedServers.length === 0 && !onAddNew) {
    return (
      <p className="text-muted-foreground mt-3 rounded-xl border border-dashed p-4 text-sm">
        No MCP servers installed yet.
      </p>
    )
  }

  return (
    <div className="bg-card mt-3 divide-y overflow-hidden rounded-xl border">
      {installedServers.map(server => {
        const catalogEntry = server.catalogId
          ? catalogById.get(server.catalogId)
          : undefined
        const needsAuth = serverNeedsAuth(server, catalogEntry)
        const needsReconnect = isAuthReconnectMessage(
          catalogEntry?.statusMessage
        )
        const needsConnect = needsAuth || needsReconnect
        const canConnect = Boolean(
          server.catalogId ? onConnectCatalog : onConnectCustom
        )
        // Always show off while unauthenticated (matches Cursor).
        const shownEnabled = needsConnect ? false : server.enabled
        const waiting = waitingId === server.id
        const pending = pendingId === server.id
        const showApiKey = apiKeyServerId === server.id
        const openable = canOpen(server)
        const status = authStatusLabel(server, catalogEntry, {
          waiting,
          needsAuth: needsConnect
        })

        return (
          <div key={server.id}>
            <div
              id={`mcp-server-${server.id}`}
              role={openable ? 'button' : undefined}
              tabIndex={openable ? 0 : undefined}
              onClick={() => openable && openRow(server)}
              onKeyDown={event => {
                if (!openable) return
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  openRow(server)
                }
              }}
              className={cn(
                'hover:bg-muted/40 flex items-center gap-3 px-3 py-3 transition-colors',
                openable && 'cursor-pointer',
                focusedMcpKey === `server-${server.id}` &&
                  'ring-ring ring-2 ring-inset'
              )}
            >
              <div className="relative shrink-0">
                <span className="bg-muted text-foreground grid size-6 place-items-center overflow-hidden rounded-md border">
                  <CustomServerIcon server={server} />
                </span>
                <span
                  className={cn(
                    'border-card absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full border-2',
                    shownEnabled
                      ? 'bg-emerald-500'
                      : needsConnect || waiting
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
                  {shownEnabled &&
                  typeof server.toolCount === 'number' &&
                  !needsConnect &&
                  !waiting ? (
                    <span className="text-muted-foreground text-xs">
                      Tools ({server.toolCount})
                    </span>
                  ) : null}
                </div>
                <p
                  className={cn(
                    'mt-0.5 truncate text-xs',
                    status.tone === 'amber'
                      ? 'text-amber-700 dark:text-amber-300'
                      : status.tone === 'waiting'
                        ? 'text-amber-700/80 dark:text-amber-300/80'
                        : 'text-muted-foreground'
                  )}
                  title={
                    needsReconnect
                      ? catalogEntry?.statusMessage || status.text
                      : undefined
                  }
                >
                  {status.text}
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
                        setWaitingCatalogId(null)
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
                ) : needsConnect && canConnect ? (
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
                      if (!server.enabled && needsConnect) {
                        toast.message('Connect this server before enabling')
                        return
                      }
                      if (server.catalogId && catalogEntry) {
                        onToggleCatalog(catalogEntry, !server.enabled)
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

            {showApiKey && canConnect && !waiting ? (
              <div
                className="bg-muted/20 flex flex-wrap items-center gap-2 border-t px-3 py-2.5"
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
          className="hover:bg-muted/40 flex w-full items-center gap-3 px-3 py-3 text-left transition-colors"
        >
          <span className="bg-muted text-muted-foreground grid size-6 place-items-center rounded-md border">
            <Plus className="size-3.5" />
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
    </div>
  )
}
