import { validateIntegrationOrProbeModal } from '@/lib/app-helpers'

import {
  navigateToIntegration,
  openVercelIntegrationTerminal
} from './dashboard-main-view-helpers'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'
import { IntegrationsView } from './dashboard-main-views-lazy'

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
      onValueChange={(envName, value) =>
        setIntegrationValues(current => ({
          ...current,
          [envName]: value
        }))
      }
      onSelect={key => navigateToIntegration(navigate, integrations, key)}
      onSave={async () => {
        if (!selectedIntegrationKey) return
        await client.updateIntegration(
          selectedIntegrationKey,
          integrationValues
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
    />
  )
}
