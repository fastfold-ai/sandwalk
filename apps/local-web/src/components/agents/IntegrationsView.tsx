import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { IntegrationsDetailView } from './integrations-view/integrations-view-detail'
import {
  IntegrationsFeaturedOverview,
  IntegrationsMainListView
} from './integrations-view/integrations-view-list'
import {
  integrationManagementPath,
  integrationsOwnedByIntegrations
} from './integrations-view/integrations-view-ownership'

export function IntegrationsView({
  terminalClient,
  integrations,
  loading = false,
  selectedKey,
  values,
  sessions = [],
  featuredOnly = false,
  onShowAll,
  onSelect,
  onValueChange,
  onSave,
  onValidate,
  onAutofill,
  onSetup,
  onOpenVercelTerminal,
  onRemove,
  embedded = false
}: {
  terminalClient: LocalAgentClient
  integrations: IntegrationSummary[]
  loading?: boolean
  selectedKey: string | null
  values: Record<string, string>
  sessions?: AgentSession[]
  featuredOnly?: boolean
  onShowAll?: () => void
  onSelect: (key: string | null) => void
  onValueChange: (envName: string, value: string) => void
  onSave: () => Promise<void>
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
  onSetup: (key: string) => Promise<IntegrationSetupResult>
  onOpenVercelTerminal: () => Promise<string>
  onRemove: (key: string) => Promise<void>
  embedded?: boolean
}) {
  const navigate = useNavigate()
  const ownedIntegrations = integrationsOwnedByIntegrations(integrations)
  const requested = integrations.find(item => item.key === selectedKey)
  const managementPath = requested
    ? integrationManagementPath(requested)
    : null
  const selected = ownedIntegrations.find(item => item.key === selectedKey)

  useEffect(() => {
    if (managementPath) navigate(managementPath, { replace: true })
  }, [managementPath, navigate])

  if (managementPath) return null

  if (selected) {
    return (
      <IntegrationsDetailView
        terminalClient={terminalClient}
        selected={selected}
        values={values}
        sessions={sessions}
        onBack={() => onSelect(null)}
        onValueChange={onValueChange}
        onSave={onSave}
        onValidate={onValidate}
        onAutofill={onAutofill}
        onSetup={onSetup}
        onOpenVercelTerminal={onOpenVercelTerminal}
        onRemove={onRemove}
      />
    )
  }

  if (featuredOnly) {
    return (
      <IntegrationsFeaturedOverview
        integrations={ownedIntegrations}
        loading={loading}
        onShowAll={onShowAll}
        onSelect={onSelect}
      />
    )
  }

  return (
    <IntegrationsMainListView
      integrations={ownedIntegrations}
      loading={loading}
      embedded={embedded}
      onSelect={onSelect}
    />
  )
}
