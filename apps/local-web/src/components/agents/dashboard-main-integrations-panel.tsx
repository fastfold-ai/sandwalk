import { validateIntegrationOrProbeModal } from '@/lib/app-helpers'

import {
  navigateToIntegration,
  openVercelIntegrationTerminal
} from './dashboard-main-view-helpers'
import { IntegrationsView } from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainIntegrationsPanel({
  client,
  navigate,
  sessions,
  activeProjectId,
  integrations,
  integrationValues,
  selectedIntegrationKey,
  connecting,
  setIntegrationValues,
  loadIntegrations,
  loadSessions
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'sessions'
  | 'activeProjectId'
  | 'integrations'
  | 'integrationValues'
  | 'selectedIntegrationKey'
  | 'connecting'
  | 'setIntegrationValues'
  | 'loadIntegrations'
  | 'loadSessions'
>) {
  return (
    <IntegrationsView
      terminalClient={client}
      integrations={integrations}
      loading={connecting && integrations.length === 0}
      selectedKey={selectedIntegrationKey}
      values={integrationValues}
      sessions={sessions}
      onValueChange={(envName, value) =>
        setIntegrationValues(current => ({
          ...current,
          [envName]: value
        }))
      }
      onSelect={key => navigateToIntegration(navigate, integrations, key)}
      onSave={async override => {
        if (!selectedIntegrationKey) return
        await client.updateIntegration(
          selectedIntegrationKey,
          override ?? integrationValues
        )
        setIntegrationValues({})
        await loadIntegrations()
      }}
      onValidate={async key => validateIntegrationOrProbeModal(client, key)}
      onAutofill={async key => {
        await client.autofillIntegration(key)
        await loadIntegrations()
      }}
      onSetup={async key => {
        const result = await client.setupIntegration(key)
        await loadIntegrations()
        return result
      }}
      onOpenVercelTerminal={() =>
        openVercelIntegrationTerminal({
          client,
          sessions,
          activeProjectId,
          loadSessions
        })
      }
      onRemove={async key => {
        await client.removeIntegration(key)
        if (selectedIntegrationKey === key) {
          navigate('/dashboard/integrations', { replace: true })
        }
        await loadIntegrations()
      }}
      onReload={loadIntegrations}
    />
  )
}
