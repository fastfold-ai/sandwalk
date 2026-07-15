import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'

import { AgentSandboxViewBody } from './sandbox-view/agent-sandbox-view-body'

export function AgentSandboxView({
  connected,
  sandboxSettings,
  modalIntegration,
  onLoadSandboxSettings,
  onUpdateSandboxSettings,
  onProbeSandbox,
  onSaveModalIntegration,
  onRemoveModalIntegration,
  onRefreshIntegrations,
  onBack,
  embedded = false,
  bare = false
}: {
  connected: boolean
  sandboxSettings: SandboxSettings | null
  modalIntegration?: IntegrationSummary | null
  onLoadSandboxSettings?: () => Promise<SandboxSettings | null>
  onUpdateSandboxSettings: (
    changes: Partial<SandboxSettings>
  ) => Promise<SandboxSettings>
  onProbeSandbox?: () => Promise<SandboxProbeReport>
  onSaveModalIntegration?: (
    values: Record<string, string>
  ) => Promise<IntegrationSummary>
  onRemoveModalIntegration?: () => Promise<void>
  onRefreshIntegrations?: () => Promise<void>
  onBack?: () => void
  embedded?: boolean
  /** Skip page chrome / ScrollArea (e.g. onboarding embed). */
  bare?: boolean
}) {
  const body = (
    <AgentSandboxViewBody
      connected={connected}
      sandboxSettings={sandboxSettings}
      modalIntegration={modalIntegration}
      onLoadSandboxSettings={onLoadSandboxSettings}
      onUpdateSandboxSettings={onUpdateSandboxSettings}
      onProbeSandbox={onProbeSandbox}
      onSaveModalIntegration={onSaveModalIntegration}
      onRemoveModalIntegration={onRemoveModalIntegration}
      onRefreshIntegrations={onRefreshIntegrations}
      onBack={onBack}
      embedded={embedded}
      bare={bare}
    />
  )

  if (bare) return body
  return <ScrollArea className="flex-1">{body}</ScrollArea>
}
