import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSummary,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { Monitor } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { AgentSandboxView } from '@/components/agents/AgentSandboxView'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

import { OnboardingSandboxLocalPanel } from './onboarding/onboarding-sandbox-local-panel'
import type { SandboxTab } from './onboarding/onboarding-sandbox-utils'

const MODAL_ICON = INTEGRATION_ICONS.modal

export function OnboardingSandboxStep({
  client
}: {
  client: LocalAgentClient
}) {
  const [tab, setTab] = useState<SandboxTab>('local')
  const [report, setReport] = useState<
    import('@sandwalk/agent-ui-core').EnvironmentReport | null
  >(null)
  const [envLoading, setEnvLoading] = useState(true)
  const [envError, setEnvError] = useState<string | null>(null)
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({})

  const [sandboxSettings, setSandboxSettings] =
    useState<SandboxSettings | null>(null)
  const [modalIntegration, setModalIntegration] =
    useState<IntegrationSummary | null>(null)

  const loadEnvironment = useCallback(async () => {
    setEnvLoading(true)
    setEnvError(null)
    try {
      const next = await client.getEnvironment()
      setReport(next)
    } catch (err) {
      setEnvError(err instanceof Error ? err.message : String(err))
    } finally {
      setEnvLoading(false)
    }
  }, [client])

  const refreshModal = useCallback(async () => {
    try {
      const [settings, integrations] = await Promise.all([
        client.getSandboxSettings(),
        client.listIntegrations()
      ])
      setSandboxSettings(settings)
      setModalIntegration(
        integrations.find(item => item.key === 'modal') ?? null
      )
      return settings
    } catch {
      return null
    }
  }, [client])

  useEffect(() => {
    void loadEnvironment()
    void refreshModal()
  }, [loadEnvironment, refreshModal])

  useEffect(() => {
    if (tab === 'modal' && !sandboxSettings) void refreshModal()
  }, [tab, sandboxSettings, refreshModal])

  const loadSandboxSettings = useCallback(async () => {
    const next = await client.getSandboxSettings()
    setSandboxSettings(next)
    return next
  }, [client])

  const updateSandboxSettings = useCallback(
    async (changes: Partial<SandboxSettings>) => {
      const next = await client.updateSandboxSettings(changes)
      setSandboxSettings(next)
      return next
    },
    [client]
  )

  const saveModalIntegration = useCallback(
    async (values: Record<string, string>) => {
      const next = await client.updateIntegration('modal', values)
      setModalIntegration(next)
      return next
    },
    [client]
  )

  const removeModalIntegration = useCallback(async () => {
    await client.removeIntegration('modal')
    setModalIntegration(null)
  }, [client])

  const probeSandbox = useCallback(
    () => client.probeSandboxSettings(),
    [client]
  )

  const refreshIntegrations = useCallback(async () => {
    await refreshModal()
  }, [refreshModal])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setTab('local')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
            tab === 'local'
              ? 'border-foreground/25 bg-muted/60'
              : 'border-border/60 hover:bg-muted/40'
          )}
        >
          <Monitor className="size-3.5 shrink-0" />
          Local Sandbox
          <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[10px] font-medium">
            Default
          </span>
        </button>
        <button
          type="button"
          onClick={() => setTab('modal')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
            tab === 'modal'
              ? 'border-foreground/25 bg-muted/60'
              : 'border-border/60 hover:bg-muted/40'
          )}
        >
          {MODAL_ICON ? (
            <img
              src={MODAL_ICON.src}
              alt=""
              className="size-3.5 shrink-0 rounded object-contain"
            />
          ) : null}
          Modal Sandbox
        </button>
      </div>

      {tab === 'local' ? (
        <OnboardingSandboxLocalPanel
          envError={envError}
          envLoading={envLoading}
          report={report}
          groupOpen={groupOpen}
          onToggleGroup={groupId =>
            setGroupOpen(current => ({
              ...current,
              [groupId]: !current[groupId]
            }))
          }
        />
      ) : (
        <AgentSandboxView
          bare
          embedded
          connected
          sandboxSettings={sandboxSettings}
          modalIntegration={modalIntegration}
          onLoadSandboxSettings={loadSandboxSettings}
          onUpdateSandboxSettings={updateSandboxSettings}
          onProbeSandbox={probeSandbox}
          onSaveModalIntegration={saveModalIntegration}
          onRemoveModalIntegration={removeModalIntegration}
          onRefreshIntegrations={refreshIntegrations}
        />
      )}
    </div>
  )
}
