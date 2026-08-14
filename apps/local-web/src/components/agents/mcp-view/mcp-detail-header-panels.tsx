import { ArrowLeft, ChevronDown, ExternalLink, KeyRound, Loader, Plug, RefreshCw, RotateCcw, Unplug, Wrench } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { openInSystemBrowser } from '@/lib/desktop'

import { McpApiKeyDialog } from './mcp-api-key-dialog'
import { McpIcon } from './mcp-view-shared'
import type { McpDetailViewState } from './use-mcp-detail-view'

export function McpDetailHeaderBar({
  state,
  onBack,
  onOpenSetup,
  onReinstallLocal,
  reinstallPending
}: {
  state: McpDetailViewState
  onBack: () => void
  onOpenSetup?: () => void
  /** Recreate the managed local launcher venv (PyMOL). */
  onReinstallLocal?: () => Promise<void>
  reinstallPending?: boolean
}) {
  const navigate = useNavigate()
  const {
    showCatalogActions,
    hasBothAuth,
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
    docsUrl,
    isLocalStdio
  } = state

  return (
    <DetailStickyNav>
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
          onClick={() => navigate('/dashboard/mcp')}
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
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1.5 px-2 text-xs"
                    disabled={connectPending || disconnectPending}
                  >
                    {connectPending ? (
                      <Loader className="size-3.5 animate-spin" />
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
                variant="ghost"
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={connectPending || disconnectPending}
                onClick={() => primaryConnect()}
              >
                {connectPending ? (
                  <Loader className="size-3.5 animate-spin" />
                ) : (
                  <Plug className="size-3.5" />
                )}
                {connectLabel}
              </Button>
            )}
            {configured && onDisconnectCatalog ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 gap-1.5 px-2 text-xs"
                disabled={connectPending || disconnectPending}
                onClick={() => void disconnect()}
              >
                {disconnectPending ? (
                  <Loader className="size-3.5 animate-spin" />
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
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs"
          disabled={loading || refreshing || connectPending}
          onClick={() => void loadTools(true)}
        >
          {refreshing ? (
            <Loader className="size-3.5 animate-spin" />
          ) : (
            <RefreshCw className="size-3.5" />
          )}
          Refresh tools
        </Button>
        {isLocalStdio && onOpenSetup ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-xs"
            onClick={onOpenSetup}
          >
            <Wrench className="size-3.5" />
            {configured ? 'Setup' : 'Install'}
          </Button>
        ) : null}
        {isLocalStdio && configured && onReinstallLocal ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-xs"
            disabled={Boolean(reinstallPending) || loading || refreshing}
            onClick={() => void onReinstallLocal()}
          >
            {reinstallPending ? (
              <Loader className="size-3.5 animate-spin" />
            ) : (
              <RotateCcw className="size-3.5" />
            )}
            Reinstall
          </Button>
        ) : null}
        {docsUrl ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 px-2 text-xs"
            onClick={() => void openInSystemBrowser(docsUrl)}
          >
            Docs
            <ExternalLink className="size-3.5" />
          </Button>
        ) : null}
      </div>
    </DetailStickyNav>
  )
}

export function McpDetailApiKeyDialog({
  state
}: {
  state: McpDetailViewState
}) {
  const {
    showCatalogActions,
    showApiKey,
    supportsApiKey,
    catalogEntry,
    apiKeyDraft,
    setApiKeyDraft,
    connectApiKey,
    setShowApiKey,
    revealStoredApiKey,
    configured,
    disconnect,
    onValidateIntegration,
    loadTools,
    onDisconnectCatalog
  } = state

  if (!showCatalogActions || !supportsApiKey || !catalogEntry) return null

  const setupUrl =
    catalogEntry.id === 'huggingface'
      ? 'https://huggingface.co/settings/tokens'
      : catalogEntry.setupUrl

  return (
    <McpApiKeyDialog
      open={showApiKey}
      onOpenChange={open => {
        setShowApiKey(open)
        if (!open) setApiKeyDraft('')
      }}
      title={`${catalogEntry.name} API Key`}
      description={catalogEntry.description}
      icon={
        <McpIcon
          id={catalogEntry.id}
          name={catalogEntry.name}
          url={catalogEntry.url}
        />
      }
      configured={configured}
      maskedPreview={catalogEntry.maskedPreview}
      placeholderUnset={catalogEntry.apiKeyEnvVar || 'Enter your API key'}
      setupUrl={setupUrl}
      draft={apiKeyDraft}
      onDraftChange={setApiKeyDraft}
      onRevealStored={revealStoredApiKey}
      onSave={() => connectApiKey()}
      onTest={async () => {
        if (apiKeyDraft.trim()) {
          const saved = await connectApiKey()
          if (!saved.ok) return saved
        }
        if (onValidateIntegration && catalogEntry.integrationKey) {
          const result = await onValidateIntegration(
            catalogEntry.integrationKey
          )
          if (result.ok) await loadTools(true)
          return result
        }
        const next = await loadTools(true)
        return {
          ok: Boolean(next?.ok),
          message:
            next?.message ||
            (next?.ok
              ? `Connected · ${next.toolCount ?? 0} tools`
              : 'Probe failed')
        }
      }}
      onRemove={onDisconnectCatalog ? () => disconnect() : undefined}
    />
  )
}
