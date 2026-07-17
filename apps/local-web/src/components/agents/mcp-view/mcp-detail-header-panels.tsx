import {
  ArrowLeft,
  ChevronDown,
  ExternalLink,
  KeyRound,
  Loader2,
  Plug,
  RefreshCw,
  Unplug
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'

import type { McpDetailViewState } from './use-mcp-detail-view'

export function McpDetailHeaderBar({
  state,
  onBack
}: {
  state: McpDetailViewState
  onBack: () => void
}) {
  const {
    showCatalogActions,
    hasBothAuth,
    needsReconnect,
    connectPending,
    disconnectPending,
    connectLabel,
    configured,
    onDisconnectCatalog,
    connectOAuth,
    setShowApiKey,
    primaryConnect,
    disconnect,
    loading,
    refreshing,
    loadTools,
    docsUrl
  } = state

  return (
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
      <div className="flex flex-wrap items-center justify-end gap-2">
        {showCatalogActions ? (
          <>
            {hasBothAuth ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant={needsReconnect ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs"
                    disabled={connectPending || disconnectPending}
                  >
                    {connectPending ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Plug className="size-3.5" />
                    )}
                    {connectLabel}
                    <ChevronDown className="size-3.5 opacity-70" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44">
                  <DropdownMenuItem
                    disabled={connectPending}
                    onSelect={() => void connectOAuth()}
                  >
                    With OAuth
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    disabled={connectPending}
                    onSelect={() => setShowApiKey(true)}
                  >
                    <KeyRound className="mr-2 size-3.5" />
                    With API key
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <Button
                type="button"
                variant={needsReconnect ? 'default' : 'outline'}
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={connectPending || disconnectPending}
                onClick={() => primaryConnect()}
              >
                {connectPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Plug className="size-3.5" />
                )}
                {connectLabel}
              </Button>
            )}
            {configured && onDisconnectCatalog ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={connectPending || disconnectPending}
                onClick={() => void disconnect()}
              >
                {disconnectPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Unplug className="size-3.5" />
                )}
                Disconnect
              </Button>
            ) : null}
          </>
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs"
          disabled={loading || refreshing || connectPending}
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
  )
}

export function McpDetailApiKeyBar({ state }: { state: McpDetailViewState }) {
  const {
    showCatalogActions,
    showApiKey,
    supportsApiKey,
    catalogEntry,
    apiKeyDraft,
    setApiKeyDraft,
    connectPending,
    connectApiKey,
    setShowApiKey
  } = state

  if (!showCatalogActions || !showApiKey || !supportsApiKey) return null

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-muted/20 px-3 py-2.5">
      <Input
        type="password"
        className="max-w-md"
        placeholder={catalogEntry?.apiKeyEnvVar || 'API key'}
        value={apiKeyDraft}
        onChange={event => setApiKeyDraft(event.target.value)}
        disabled={connectPending}
      />
      <Button
        type="button"
        size="sm"
        className="h-8 text-xs"
        disabled={connectPending}
        onClick={() => void connectApiKey()}
      >
        {connectPending ? (
          <Loader2 className="mr-1.5 size-3.5 animate-spin" />
        ) : null}
        Save & connect
      </Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-8 text-xs"
        disabled={connectPending}
        onClick={() => {
          setShowApiKey(false)
          setApiKeyDraft('')
        }}
      >
        Cancel
      </Button>
      {catalogEntry?.setupUrl || catalogEntry?.id === 'huggingface' ? (
        <a
          href={
            catalogEntry?.id === 'huggingface'
              ? 'https://huggingface.co/settings/tokens'
              : catalogEntry?.setupUrl || '#'
          }
          target="_blank"
          rel="noreferrer"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs underline-offset-2 hover:underline"
        >
          Get API token
          <ExternalLink className="size-3" />
        </a>
      ) : null}
    </div>
  )
}
