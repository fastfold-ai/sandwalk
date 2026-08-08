import type {
  ConnectMcpResult,
  McpCatalogEntry,
  McpServer,
  ValidateMcpResult
} from '@sandwalk/agent-ui-core'
import { useState } from 'react'
import { toast } from 'sonner'

import { ScrollArea } from '@/components/ui/scroll-area'

import { McpDetailLocalSetupDialog } from './mcp-detail-local-setup'
import {
  McpDetailApiKeyBar,
  McpDetailHeaderBar,
  McpDetailInfoAside,
  McpDetailStatsAside,
  McpDetailToolsSection
} from './mcp-detail-panels'
import { useMcpDetailView } from './use-mcp-detail-view'

export function McpDetailView({
  kind,
  catalogEntry,
  server,
  onBack,
  onLoadTools,
  onToggleEnabled,
  onConnectCatalog,
  onDisconnectCatalog,
  onRefreshMeta,
  onRevealStoredSecret,
  onInstallLocal
}: {
  kind: 'catalog' | 'server'
  catalogEntry?: McpCatalogEntry | null
  server?: McpServer | null
  onBack: () => void
  onLoadTools: () => Promise<ValidateMcpResult>
  onToggleEnabled?: (enabled: boolean) => Promise<void>
  onConnectCatalog?: (input: {
    method: 'oauth' | 'api_key'
    apiKey?: string
  }) => Promise<ConnectMcpResult>
  onDisconnectCatalog?: () => Promise<ConnectMcpResult | void>
  onRefreshMeta?: () => Promise<void>
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
  onInstallLocal?: (opts?: { force?: boolean }) => Promise<void>
}) {
  const [setupOpen, setSetupOpen] = useState(false)
  const [reinstallPending, setReinstallPending] = useState(false)
  const state = useMcpDetailView({
    kind,
    catalogEntry,
    server,
    onLoadTools,
    onToggleEnabled,
    onConnectCatalog,
    onDisconnectCatalog,
    onRefreshMeta,
    onRevealStoredSecret
  })

  const handleInstallLocal = onInstallLocal
    ? async (opts?: { force?: boolean }) => {
        await onInstallLocal(opts)
        await onRefreshMeta?.()
        await state.loadTools(true)
      }
    : undefined

  const handleReinstallLocal = handleInstallLocal
    ? async () => {
        setReinstallPending(true)
        try {
          await handleInstallLocal({ force: true })
          toast.success('Launcher reinstalled', {
            description: state.catalogEntry?.name || 'PyMOL'
          })
        } catch (err) {
          toast.error(err instanceof Error ? err.message : String(err), {
            description: state.catalogEntry?.name || 'PyMOL'
          })
        } finally {
          setReinstallPending(false)
        }
      }
    : undefined

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <McpDetailHeaderBar
        state={state}
        onBack={onBack}
        onOpenSetup={
          state.isLocalStdio ? () => setSetupOpen(true) : undefined
        }
        onReinstallLocal={handleReinstallLocal}
        reinstallPending={reinstallPending}
      />
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
          <McpDetailApiKeyBar state={state} />
          <div className="grid items-start gap-4 lg:grid-cols-[240px_minmax(0,1fr)_220px]">
            <McpDetailInfoAside state={state} />
            <McpDetailToolsSection state={state} />
            <McpDetailStatsAside state={state} />
          </div>
        </div>
      </ScrollArea>
      {state.isLocalStdio ? (
        <McpDetailLocalSetupDialog
          open={setupOpen}
          onOpenChange={setSetupOpen}
          state={state}
          onInstallLocal={handleInstallLocal}
        />
      ) : null}
    </div>
  )
}
