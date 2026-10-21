import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import { ChevronDown, ExternalLink, KeyRound, Loader } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

import { McpApiKeyDialog } from './mcp-api-key-dialog'
import {
  authMeta,
  type CatalogStatusPatch,
  formatConnectError,
  isLocalStdioCatalog,
  McpIcon,
  McpToggle,
  statusBadge,
  withStatusPatch,
} from './mcp-view-shared'

export function McpCatalogCard({
  entry,
  statusPatch,
  pendingId,
  focusedMcpKey,
  showApiKey,
  apiKeyDraft,
  onOpenCatalog,
  onConnectOAuth,
  onConnectApiKey,
  onToggleCatalog,
  onPendingIdChange,
  onStatusPatchChange,
  onShowApiKeyChange,
  onApiKeyDraftChange,
  onRevealStoredSecret,
  onDisconnectCatalog,
  onValidateIntegration
}: {
  entry: McpCatalogEntry
  statusPatch: CatalogStatusPatch | undefined
  pendingId: string | null
  focusedMcpKey: string | null
  showApiKey: boolean
  apiKeyDraft: string
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onConnectOAuth: (entry: McpCatalogEntry) => void
  onConnectApiKey: (
    entry: McpCatalogEntry
  ) => Promise<{ ok: boolean; message: string } | void>
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onPendingIdChange: (id: string | null) => void
  onStatusPatchChange: (
    updater: (
      prev: Record<string, CatalogStatusPatch>,
    ) => Record<string, CatalogStatusPatch>,
  ) => void
  onShowApiKeyChange: (id: string, show: boolean) => void
  onApiKeyDraftChange: (id: string, value: string) => void
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
  onDisconnectCatalog?: (catalogId: string) => Promise<void>
  onValidateIntegration?: (
    integrationKey: string
  ) => Promise<{ ok: boolean; message: string }>
}) {
  const view = withStatusPatch(entry, statusPatch)
  const pending = pendingId === view.id
  const isLocal = isLocalStdioCatalog(view)
  const supportsApiKey = !isLocal && view.authMode !== 'oauth'
  const supportsOAuth = !isLocal && view.authMode !== 'api_key'
  const hasBoth = supportsApiKey && supportsOAuth
  const isSetup = view.configured || view.connected || view.enabled
  const label = isLocal
    ? isSetup
      ? 'Open'
      : 'Set up'
    : isSetup
      ? 'Reconnect'
      : 'Connect'

  const primaryConnect = () => {
    if (isLocal) {
      onOpenCatalog?.(view)
      return
    }
    if (supportsOAuth && view.preferredAuth === 'oauth') {
      onConnectOAuth(view)
      return
    }
    if (supportsApiKey && !supportsOAuth) {
      onShowApiKeyChange(view.id, true)
      return
    }
    if (supportsOAuth) {
      onConnectOAuth(view)
      return
    }
    onShowApiKeyChange(view.id, true)
  }

  const setupUrl =
    view.id === 'huggingface'
      ? 'https://huggingface.co/settings/tokens'
      : view.setupUrl

  return (
    <div
      id={`mcp-catalog-${view.id}`}
      key={view.id}
      role={onOpenCatalog ? 'button' : undefined}
      tabIndex={onOpenCatalog ? 0 : undefined}
      onClick={() => onOpenCatalog?.(view)}
      onKeyDown={event => {
        if (!onOpenCatalog) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpenCatalog(view)
        }
      }}
      className={cn(
        'border-border/50 bg-muted/20 hover:border-border hover:bg-muted/35 flex h-full flex-col rounded-2xl border p-3.5 transition-all',
        onOpenCatalog && 'cursor-pointer',
        focusedMcpKey === `catalog-${view.id}` &&
          'ring-ring ring-2 ring-offset-2 ring-offset-background',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <McpIcon id={view.id} name={view.name} url={view.url} />
            <span className="truncate text-sm font-medium">{view.name}</span>
            {authMeta(view)}
            {statusBadge(view, onOpenCatalog)}
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
              view.enabled ? `Disable ${view.name}` : `Enable ${view.name}`
            }
            onToggle={() => {
              if (!view.configured && !view.enabled) {
                toast.error(
                  isLocal
                    ? `Run setup first (sandwalk mcp install ${view.id}), then enable.`
                    : 'Connect with OAuth or API key first, then enable.',
                  { description: view.name },
                )
                return
              }
              const nextEnabled = !view.enabled
              onPendingIdChange(view.id)
              onStatusPatchChange(prev => ({
                ...prev,
                [view.id]: nextEnabled
                  ? {
                      // Only flip enabled optimistically — connected/toolCount
                      // come from the enable probe response after refresh.
                      enabled: true,
                    }
                  : {
                      enabled: false,
                      connected: false,
                      statusMessage: null,
                      toolCount: null,
                    },
              }))
              void onToggleCatalog(view, nextEnabled)
                .then(() =>
                  toast.success(nextEnabled ? 'Enabled' : 'Disabled', {
                    description: view.name,
                  }),
                )
                .catch((err: unknown) => {
                  onStatusPatchChange(prev => {
                    const next = { ...prev }
                    delete next[view.id]
                    return next
                  })
                  toast.error(formatConnectError(err), {
                    description: view.name,
                  })
                })
                .finally(() => onPendingIdChange(null))
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
                onClick={event => event.stopPropagation()}
              >
                {pending ? (
                  <Loader className="mr-1.5 size-3.5 animate-spin" />
                ) : null}
                {label}
                <ChevronDown className="ml-1 size-3.5 opacity-70" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-44">
              <DropdownMenuItem
                disabled={pending}
                onSelect={() => onConnectOAuth(view)}
              >
                With OAuth
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={pending}
                onSelect={() => onShowApiKeyChange(view.id, true)}
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
            onClick={event => {
              event.stopPropagation()
              primaryConnect()
            }}
          >
            {pending ? (
              <Loader className="mr-1.5 size-3.5 animate-spin" />
            ) : null}
            {label}
          </Button>
        )}
        {view.setupUrl && isLocal ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground ml-auto inline-flex shrink-0 items-center gap-1 text-xs"
            onClick={event => {
              event.stopPropagation()
              void openInSystemBrowser(view.setupUrl!)
            }}
          >
            Plugin zip <ExternalLink className="size-3" />
          </button>
        ) : view.docsUrl ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground ml-auto inline-flex shrink-0 items-center gap-1 text-xs"
            onClick={event => {
              event.stopPropagation()
              void openInSystemBrowser(view.docsUrl!)
            }}
          >
            Docs <ExternalLink className="size-3" />
          </button>
        ) : null}
      </div>

      {supportsApiKey ? (
        <div onClick={event => event.stopPropagation()}>
          <McpApiKeyDialog
            open={showApiKey}
            onOpenChange={open => {
              onShowApiKeyChange(view.id, open)
              if (!open) onApiKeyDraftChange(view.id, '')
            }}
            title={`${view.name} API Key`}
            description={view.description}
            icon={<McpIcon id={view.id} name={view.name} url={view.url} />}
            configured={Boolean(view.configured)}
            maskedPreview={view.maskedPreview}
            placeholderUnset={view.apiKeyEnvVar || 'Enter your API key'}
            setupUrl={setupUrl}
            draft={apiKeyDraft}
            onDraftChange={value => onApiKeyDraftChange(view.id, value)}
            onRevealStored={
              view.integrationKey && onRevealStoredSecret
                ? () => onRevealStoredSecret(view.integrationKey!)
                : undefined
            }
            onSave={async () => {
              const result = await onConnectApiKey(view)
              return (
                result || {
                  ok: true,
                  message: 'API key saved.'
                }
              )
            }}
            onTest={
              onValidateIntegration && view.integrationKey
                ? async () => {
                    if (apiKeyDraft.trim()) {
                      const saved = await onConnectApiKey(view)
                      if (saved && !saved.ok) return saved
                    }
                    return onValidateIntegration(view.integrationKey!)
                  }
                : undefined
            }
            onRemove={
              view.configured && onDisconnectCatalog
                ? async () => {
                    await onDisconnectCatalog(view.id)
                    toast.success('Disconnected', { description: view.name })
                  }
                : undefined
            }
          />
        </div>
      ) : null}
    </div>
  )
}
