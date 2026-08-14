import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'
import { KeyRound, Loader, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { McpApiKeyDialog } from './mcp-api-key-dialog'
import {
  authStatusLabel,
  CustomServerIcon,
  customServerNeedsAuth,
  isAuthReconnectMessage,
  isLocalStdioServer,
  serverNeedsAuth
} from './mcp-custom-server-helpers'
import {
  disposeMcpOAuthWatch,
  openMcpOAuthBrowser
} from './mcp-oauth-browser'
import { formatConnectError, McpIcon, McpToggle } from './mcp-view-shared'

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
  onRefresh,
  onRevealStoredSecret,
  onDisconnectCatalog,
  onValidateIntegration,
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
  onRefresh?: () => Promise<void>
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
  onDisconnectCatalog?: (catalogId: string) => Promise<void>
  onValidateIntegration?: (
    integrationKey: string
  ) => Promise<{ ok: boolean; message: string }>
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

      disposeMcpOAuthWatch()
      setWaitingId(null)
      setWaitingCatalogId(null)
      setPendingId(null)
      if (data.ok) {
        toast.dismiss()
        toast.success(data.message || 'Connected via OAuth')
        void onRefresh?.()
      } else {
        setApiKeyServerId(prev => prev || waitingId)
        toast.error(data.error || 'OAuth failed')
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [onRefresh, waitingId, waitingCatalogId])

  // Clear "Waiting for callback…" once catalog/server shows connected (Tauri
  // system-browser OAuth has no window.opener postMessage).
  useEffect(() => {
    if (!waitingId && !waitingCatalogId) return
    const server = installedServers.find(item => item.id === waitingId)
    const catalog = waitingCatalogId
      ? catalogById.get(waitingCatalogId)
      : server?.catalogId
        ? catalogById.get(server.catalogId)
        : undefined
    const ready = Boolean(
      (catalog && catalog.configured) ||
        (server && !serverNeedsAuth(server, catalog))
    )
    if (!ready) return
    disposeMcpOAuthWatch()
    setWaitingId(null)
    setWaitingCatalogId(null)
    toast.dismiss()
    toast.success(
      catalog
        ? `Connected · ${catalog.toolCount ?? 0} tools`
        : 'Connected via OAuth',
      { description: catalog?.name || server?.name }
    )
  }, [catalogById, installedServers, waitingCatalogId, waitingId])

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
        setWaitingId(server.id)
        setWaitingCatalogId(server.catalogId || null)
        await openMcpOAuthBrowser(result.authorizeUrl, async () => {
          await onRefresh?.()
          // Detail/list effects also dispose when catalog shows connected;
          // return false so polling continues until then or postMessage.
          return false
        })
        toast.message('Complete sign-in in your browser…', {
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
      const apiKeyOnly = /uses api key auth, not oauth/i.test(message)
      const oauthUnavailable =
        apiKeyOnly ||
        /no oauth registration|use api key|could not discover oauth/i.test(
          message
        )
      if (apiKeyOnly || oauthUnavailable) {
        toast.message('API key required', {
          description: `${server.name} uses an API key — enter it in the dialog to connect.`
        })
      } else {
        toast.error(message, { description: server.name })
      }
      setApiKeyServerId(server.id)
    } finally {
      setPendingId(null)
    }
  }

  const connectApiKey = async (
    server: McpServer
  ): Promise<{ ok: boolean; message: string }> => {
    if (!apiKeyDraft.trim()) {
      return { ok: false, message: 'API key is required' }
    }
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
      if (!result) {
        return { ok: false, message: 'Connect is unavailable.' }
      }
      if (result.ok) {
        const message = result.message || 'Authenticated'
        toast.success(message)
        setApiKeyDraft('')
        return { ok: true, message }
      }
      const message = result.message || 'Authentication failed'
      toast.error(message)
      return { ok: false, message }
    } catch (err) {
      const message = formatConnectError(err)
      toast.error(message)
      return { ok: false, message }
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
        const isLocal = isLocalStdioServer(server, catalogEntry)
        const needsAuth =
          !isLocal && serverNeedsAuth(server, catalogEntry)
        const needsReconnect =
          !isLocal &&
          isAuthReconnectMessage(catalogEntry?.statusMessage)
        const needsSetup = isLocal && !catalogEntry?.configured
        const needsConnect = needsAuth || needsReconnect
        const canConnect = Boolean(
          server.catalogId ? onConnectCatalog : onConnectCustom
        )
        const apiKeyOnly = catalogEntry?.authMode === 'api_key'
        const supportsApiKeyDialog =
          !isLocal &&
          canConnect &&
          Boolean(
            apiKeyOnly ||
              catalogEntry?.authMode === 'api_key_or_oauth' ||
              (!catalogEntry && server.transport !== 'stdio')
          )
        // Prefer token mint pages over general MCP settings when known.
        const tokenSetupUrl =
          catalogEntry?.id === 'huggingface'
            ? 'https://huggingface.co/settings/tokens'
            : catalogEntry?.setupUrl || null
        // Always show off while unauthenticated / unset up (matches Cursor).
        const shownEnabled =
          needsConnect || needsSetup ? false : server.enabled
        const waiting = waitingId === server.id
        const pending = pendingId === server.id
        const showApiKey = apiKeyServerId === server.id
        const openable = canOpen(server)
        const status = authStatusLabel(server, catalogEntry, {
          waiting,
          needsAuth: needsConnect,
          needsSetup
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
                      <Loader className="size-3.5 animate-spin" />
                      Waiting for callback…
                    </Button>
                  </>
                ) : needsSetup && openable ? (
                  <Button
                    type="button"
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    onClick={() => openRow(server)}
                  >
                    Set up
                  </Button>
                ) : needsConnect && canConnect ? (
                  <>
                    {apiKeyOnly ? null : (
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
                    )}
                    {apiKeyOnly && showApiKey ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => {
                          setApiKeyServerId(null)
                          setApiKeyDraft('')
                        }}
                      >
                        Cancel
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      className="h-7 px-2.5 text-xs"
                      disabled={pending}
                      onClick={() => {
                        if (apiKeyOnly) {
                          setApiKeyServerId(server.id)
                          return
                        }
                        void connectOAuth(server)
                      }}
                    >
                      {pending ? (
                        <Loader className="mr-1.5 size-3.5 animate-spin" />
                      ) : null}
                      Connect
                    </Button>
                  </>
                ) : (
                  <McpToggle
                    enabled={shownEnabled}
                    label={`Enable ${server.name}`}
                    onToggle={() => {
                      if (!server.enabled && needsSetup) {
                        toast.message('Finish setup before enabling', {
                          description: server.name
                        })
                        if (openable) openRow(server)
                        return
                      }
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

            {supportsApiKeyDialog ? (
              <div onClick={event => event.stopPropagation()}>
                <McpApiKeyDialog
                  open={showApiKey && !waiting}
                  onOpenChange={open => {
                    setApiKeyServerId(open ? server.id : null)
                    if (!open) setApiKeyDraft('')
                  }}
                  title={`${server.name} API Key`}
                  description={
                    catalogEntry?.description || server.description
                  }
                  icon={
                    catalogEntry ? (
                      <McpIcon
                        id={catalogEntry.id}
                        name={catalogEntry.name}
                        url={catalogEntry.url}
                      />
                    ) : (
                      <CustomServerIcon server={server} />
                    )
                  }
                  configured={Boolean(catalogEntry?.configured)}
                  maskedPreview={catalogEntry?.maskedPreview}
                  placeholderUnset={
                    catalogEntry?.apiKeyEnvVar || 'API key or Bearer token'
                  }
                  setupUrl={tokenSetupUrl}
                  draft={apiKeyDraft}
                  onDraftChange={setApiKeyDraft}
                  onRevealStored={
                    catalogEntry?.integrationKey && onRevealStoredSecret
                      ? () =>
                          onRevealStoredSecret(catalogEntry.integrationKey!)
                      : undefined
                  }
                  onSave={() => connectApiKey(server)}
                  onTest={
                    onValidateIntegration && catalogEntry?.integrationKey
                      ? async () => {
                          if (apiKeyDraft.trim()) {
                            const saved = await connectApiKey(server)
                            if (!saved.ok) return saved
                          }
                          return onValidateIntegration(
                            catalogEntry.integrationKey!
                          )
                        }
                      : undefined
                  }
                  onRemove={
                    catalogEntry?.configured &&
                    catalogEntry.id &&
                    onDisconnectCatalog
                      ? async () => {
                          await onDisconnectCatalog(catalogEntry.id)
                          toast.success('Disconnected', {
                            description: server.name
                          })
                          await onRefresh?.()
                        }
                      : undefined
                  }
                />
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
