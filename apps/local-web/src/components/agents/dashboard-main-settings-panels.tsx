import { onboardingPath } from '@/lib/onboarding'

import type { DashboardMainViewsProps } from './dashboard-main-views-types'
import {
  AgentPromptsView,
  AgentRuntimeView,
  AgentSandboxView,
  DataView,
  DoctorView,
  EnvironmentView,
  GeneralView,
  ModelsView,
  SandboxListView,
  ServerStatusView,
  StorageView,
  ToolsView
} from './dashboard-main-views-lazy'

export function DashboardMainSettingsPanels(props: DashboardMainViewsProps) {
  const {
    client,
    navigate,
    backendUrl,
    health,
    integrations,
    runtimeSettings,
    sandboxSettings,
    isDashboardStatus,
    isDashboardGeneral,
    isDashboardAgentRuntime,
    isDashboardAgentPrompts,
    isDashboardAgentSandbox,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardModels,
    isDashboardTools,
    isDashboardData,
    isDashboardDoctor,
    isDashboardStorage,
    isDashboardEnvironment,
    setRuntimeSettings,
    setSandboxSettings,
    loadServerStatus,
    loadAccountForUi,
    logoutAccount,
    loadStorage,
    loadEnvironment,
    loadIntegrations,
    loadModelOptions,
    refreshSessionSandbox
  } = props

  if (isDashboardStatus) {
    return (
      <ServerStatusView
        onLoad={loadServerStatus}
        onClearCache={signal => client.clearRuntimeCache(signal)}
      />
    )
  }

  if (isDashboardGeneral) {
    return (
      <GeneralView
        backendUrl={backendUrl}
        backendVersion={health?.version ?? null}
        connected={Boolean(health)}
        onLoadAccount={loadAccountForUi}
        onLogoutAccount={logoutAccount}
        onOpenSetupWizard={() => {
          navigate(onboardingPath('welcome'))
        }}
      />
    )
  }

  if (isDashboardAgentRuntime) {
    return (
      <AgentRuntimeView
        connected={Boolean(health)}
        runtimeSettings={runtimeSettings}
        onUpdateRuntimeSettings={async changes => {
          const next = await client.updateRuntimeSettings(changes)
          setRuntimeSettings(next)
          return next
        }}
      />
    )
  }

  if (isDashboardAgentPrompts) {
    return (
      <AgentPromptsView
        connected={Boolean(health)}
        onGetPromptBudget={(options, signal) =>
          client.getPromptBudget(options, signal)
        }
        onListSpecialists={signal => client.listSpecialists(signal)}
      />
    )
  }

  if (isDashboardAgentSandbox) {
    if (isSandboxLocalDetail) {
      return (
        <EnvironmentView
          title="Local Sandbox"
          description="Python environment the agent uses for Local Sandbox chats. Manage packages used by skills and tools. Core dependencies stay locked."
          onBack={() => navigate('/dashboard/agent/sandbox')}
          onLoad={loadEnvironment}
          onInstall={(name, options) =>
            client.installEnvironmentPackage(name, options)
          }
          onUninstall={(name, signal) =>
            client.uninstallEnvironmentPackage(name, signal)
          }
        />
      )
    }
    if (isSandboxModalDetail) {
      return (
        <AgentSandboxView
          connected={Boolean(health)}
          sandboxSettings={sandboxSettings}
          modalIntegration={
            integrations.find(item => item.key === 'modal') || null
          }
          onBack={() => navigate('/dashboard/agent/sandbox')}
          onLoadSandboxSettings={async () => {
            const next = await client.getSandboxSettings()
            setSandboxSettings(next)
            return next
          }}
          onUpdateSandboxSettings={async changes => {
            const next = await client.updateSandboxSettings(changes)
            setSandboxSettings(next)
            return next
          }}
          onProbeSandbox={() => client.probeSandboxSettings()}
          onSaveModalIntegration={async values => {
            const next = await client.updateIntegration('modal', values)
            await loadIntegrations()
            const settings = await client.getSandboxSettings()
            setSandboxSettings(settings)
            await refreshSessionSandbox()
            return next
          }}
          onRemoveModalIntegration={async () => {
            await client.removeIntegration('modal')
            await loadIntegrations()
            const settings = await client.getSandboxSettings()
            setSandboxSettings(settings)
            await refreshSessionSandbox()
          }}
          onRefreshIntegrations={async () => {
            await loadIntegrations()
            const settings = await client.getSandboxSettings()
            setSandboxSettings(settings)
            await refreshSessionSandbox()
          }}
        />
      )
    }
    return (
      <SandboxListView
        onOpen={id => navigate(`/dashboard/agent/sandbox/${id}`)}
      />
    )
  }

  if (isDashboardModels) {
    return (
      <ModelsView
        integrations={integrations}
        onListModels={options => client.listModels(options)}
        onUpdateModelEnabled={async (modelId, enabled, signal) => {
          const updated = await client.updateModelEnabled(
            modelId,
            enabled,
            signal
          )
          void loadModelOptions()
          return updated
        }}
        onCreateCustomModel={async (input, signal) => {
          const created = await client.createCustomModel(input, signal)
          void loadModelOptions()
          return created
        }}
        onDeleteCustomModel={async (modelId, signal) => {
          await client.deleteCustomModel(modelId, signal)
          void loadModelOptions()
        }}
        onListProfiles={signal => client.listModelProfiles({ signal })}
        onCreateProfile={async (input, signal) => {
          const created = await client.createModelProfile(input, signal)
          void loadModelOptions()
          return created
        }}
        onUpdateProfile={async (profileId, input, signal) => {
          const updated = await client.updateModelProfile(
            profileId,
            input,
            signal
          )
          void loadModelOptions()
          return updated
        }}
        onDeleteProfile={async (profileId, signal) => {
          await client.deleteModelProfile(profileId, signal)
          void loadModelOptions()
        }}
        onProbeProfile={(profileId, signal) =>
          client.probeModelProfile(profileId, signal)
        }
        onDiscoverEndpoint={(input, signal) =>
          client.discoverModelEndpoint(input, signal)
        }
        onSaveProviderKey={async (key, envVar, value) => {
          await client.updateIntegration(key, { [envVar]: value })
          await loadIntegrations()
          await loadModelOptions()
        }}
        onClearProviderKey={async key => {
          await client.removeIntegration(key)
          await loadIntegrations()
          await loadModelOptions()
        }}
      />
    )
  }

  if (isDashboardTools) {
    return (
      <ToolsView
        onListTools={signal => client.listTools({ signal })}
        onUpdateToolEnabled={(toolId, enabled, signal) =>
          client.updateToolEnabled(toolId, enabled, signal)
        }
        onBatchUpdateTools={(action, ids, signal) =>
          client.batchUpdateTools(action, ids, signal)
        }
        onListDatasets={signal => client.listDatasets(signal)}
        onOpenData={() => navigate('/dashboard/datasets')}
      />
    )
  }

  if (isDashboardData) {
    return (
      <DataView
        onListDatasets={signal => client.listDatasets(signal)}
        onInstallDataset={(datasetId, signal) =>
          client.installDataset(datasetId, signal)
        }
        onRemoveDataset={(datasetId, signal) =>
          client.removeDataset(datasetId, signal)
        }
      />
    )
  }

  if (isDashboardDoctor) {
    return (
      <DoctorView
        onRun={signal => client.runDoctor(signal)}
        onDownloadDiagnostics={(uiDiagnostics, signal) =>
          client.downloadDiagnostics(uiDiagnostics, signal)
        }
      />
    )
  }

  if (isDashboardStorage) {
    return <StorageView onLoad={loadStorage} />
  }

  if (isDashboardEnvironment) {
    return (
      <EnvironmentView
        onLoad={loadEnvironment}
        onInstall={(name, options) =>
          client.installEnvironmentPackage(name, options)
        }
        onUninstall={(name, signal) =>
          client.uninstallEnvironmentPackage(name, signal)
        }
      />
    )
  }

  return null
}
