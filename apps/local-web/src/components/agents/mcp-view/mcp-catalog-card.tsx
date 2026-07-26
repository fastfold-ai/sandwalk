import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import {
  ChevronDown,
  ExternalLink,
  KeyRound,
  Loader2,
} from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

import {
  authMeta,
  type CatalogStatusPatch,
  formatConnectError,
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
}: {
  entry: McpCatalogEntry
  statusPatch: CatalogStatusPatch | undefined
  pendingId: string | null
  focusedMcpKey: string | null
  showApiKey: boolean
  apiKeyDraft: string
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onConnectOAuth: (entry: McpCatalogEntry) => void
  onConnectApiKey: (entry: McpCatalogEntry) => void
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onPendingIdChange: (id: string | null) => void
  onStatusPatchChange: (
    updater: (
      prev: Record<string, CatalogStatusPatch>,
    ) => Record<string, CatalogStatusPatch>,
  ) => void
  onShowApiKeyChange: (id: string, show: boolean) => void
  onApiKeyDraftChange: (id: string, value: string) => void
}) {
  const view = withStatusPatch(entry, statusPatch)
  const pending = pendingId === view.id
  const supportsApiKey = view.authMode !== 'oauth'
  const supportsOAuth = view.authMode !== 'api_key'
  const hasBoth = supportsApiKey && supportsOAuth
  const isSetup = view.configured || view.connected || view.enabled
  const label = isSetup ? 'Reconnect' : 'Connect'

  const primaryConnect = () => {
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
        'bg-background/60 hover:bg-muted/40 flex h-full flex-col rounded-lg p-3 transition-colors',
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
                  'Connect with OAuth or API key first, then enable.',
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
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" />
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
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : null}
            {label}
          </Button>
        )}
        {view.docsUrl ? (
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

      {showApiKey && supportsApiKey ? (
        <div
          className="mt-3 flex flex-wrap items-center gap-2 border-t border-border/50 pt-3"
          onClick={event => event.stopPropagation()}
        >
          <Input
            type="password"
            className="max-w-md"
            placeholder={view.apiKeyEnvVar || 'API key'}
            autoFocus
            value={apiKeyDraft}
            onChange={event => onApiKeyDraftChange(view.id, event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') onConnectApiKey(view)
            }}
          />
          <Button
            size="sm"
            disabled={pending || !apiKeyDraft.trim()}
            onClick={() => onConnectApiKey(view)}
          >
            Save & enable
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onShowApiKeyChange(view.id, false)}
          >
            Cancel
          </Button>
          {view.setupUrl || view.id === 'huggingface' ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs underline-offset-2 hover:underline"
              onClick={() =>
                void openInSystemBrowser(
                  view.id === 'huggingface'
                    ? 'https://huggingface.co/settings/tokens'
                    : view.setupUrl || ''
                )
              }
            >
              Get API token
              <ExternalLink className="size-3" />
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
