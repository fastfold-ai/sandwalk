import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Loader } from 'lucide-react'
import { DataView } from '@/components/agents/DataView'

import { OnboardingIntegrationDetail } from './onboarding/onboarding-integration-detail'
import { OnboardingIntegrationsFeaturedGrid } from './onboarding/onboarding-integrations-featured-grid'
import { useOnboardingIntegrations } from './onboarding/use-onboarding-integrations'

export function OnboardingIntegrationsStep({
  client
}: {
  client: LocalAgentClient
}) {
  const integrations = useOnboardingIntegrations(client)

  if (integrations.loading && integrations.featured.length === 0) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader className="size-4 animate-spin" />
        Loading integrations…
      </p>
    )
  }

  return (
    <div className="space-y-5 pb-2">
      <OnboardingIntegrationsFeaturedGrid
        featured={integrations.featured}
        selectedKey={integrations.selected?.key || null}
        onPick={integrations.pick}
      />

      {integrations.selected ? (
        <OnboardingIntegrationDetail
          client={client}
          selected={integrations.selected}
          isVercel={integrations.isVercel}
          values={integrations.values}
          showSecrets={integrations.showSecrets}
          busy={integrations.busy}
          setupResult={integrations.setupResult}
          setupRunning={integrations.setupRunning}
          openingTerminal={integrations.openingTerminal}
          terminalOpen={integrations.terminalOpen}
          terminalSessionId={integrations.terminalSessionId}
          terminalStartupNonce={integrations.terminalStartupNonce}
          onRunVercelSetup={() => void integrations.runVercelSetup()}
          onCloseTerminal={() => integrations.setTerminalOpen(false)}
          onValueChange={(envVar, value) =>
            integrations.setValues(prev => ({ ...prev, [envVar]: value }))
          }
          onToggleSecret={envVar =>
            integrations.setShowSecrets(prev => ({
              ...prev,
              [envVar]: !prev[envVar]
            }))
          }
          onTestKey={() => void integrations.testKey()}
          onSave={() => void integrations.save()}
          onFastfoldImported={async () => {
            await integrations.refresh()
            integrations.setNotice('Fastfold AI Cloud connected.')
          }}
        />
      ) : null}

      {integrations.error ? (
        <p className="text-destructive text-sm">{integrations.error}</p>
      ) : null}
      {integrations.notice ? (
        <p className="text-muted-foreground text-sm">{integrations.notice}</p>
      ) : null}

      <div className="border-t border-border/60 pt-5">
        <DataView
          bare
          title="Datasets"
          description="Install open-access datasets your tools use. Others need a manual download."
          onListDatasets={signal => client.listDatasets(signal)}
          onInstallDataset={(datasetId, signal) =>
            client.installDataset(datasetId, signal)
          }
          onRemoveDataset={(datasetId, signal) =>
            client.removeDataset(datasetId, signal)
          }
        />
        <p className="text-muted-foreground mt-3 text-xs">
          Later you can manage datasets in your dashboard.
        </p>
      </div>
    </div>
  )
}
