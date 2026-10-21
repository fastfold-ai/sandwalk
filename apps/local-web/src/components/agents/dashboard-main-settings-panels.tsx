import { onboardingPath } from '@/lib/onboarding'

import {
  AgentPromptsView,
  AgentRuntimeView,
  AgentSandboxView,
  AgentSecurityView,
  AppearanceView,
  BenchView,
  DataView,
  DoctorView,
  EnvironmentView,
  GeneralView,
  LogsView,
  MemoryView,
  ModelsView,
  SandboxListView,
  StorageView,
  ToolsView,
  VoiceView
} from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'
import { ChatGPTSignInCard } from './models-view/ChatGPTSignInCard'

export function DashboardMainSettingsPanels(props: DashboardMainViewsProps) {
  const {
    client,
    navigate,
    dashboardSection,
    backendUrl,
    health,
    projects,
    specialists,
    sessions,
    activeProjectId,
    integrations,
    runtimeSettings,
    sandboxSettings,
    isDashboardGeneral,
    isDashboardAppearance,
    isDashboardAgentRuntime,
    isDashboardAgentPrompts,
    isDashboardVoice,
    isDashboardAgentSandbox,
    isDashboardAgentSecurity,
    isSandboxLocalDetail,
    isSandboxModalDetail,
    isDashboardModels,
    isDashboardTools,
    isDashboardData,
    isDashboardDoctor,
    isDashboardLogs,
    isDashboardBench,
    isDashboardStorage,
    isDashboardEnvironment,
    setRuntimeSettings,
    setSandboxSettings,
    loadAccountForUi,
    logoutAccount,
    changeBackend,
    disconnectBackend,
    loadStorage,
    loadEnvironment,
    loadIntegrations,
    loadModelOptions,
    refreshSessionSandbox
  } = props

  if (isDashboardGeneral) {
    return (
      <GeneralView
        backendUrl={backendUrl}
        backendVersion={health?.version ?? null}
        connected={Boolean(health)}
        onLoadAccount={loadAccountForUi}
        onLogoutAccount={logoutAccount}
        onChangeBackend={changeBackend}
        onDisconnectBackend={disconnectBackend}
        onOpenSetupWizard={() => {
          navigate(onboardingPath('welcome'))
        }}
        onResetSettings={() => client.resetAppSettings().then(() => undefined)}
      />
    )
  }

  if (isDashboardAppearance) {
    return <AppearanceView />
  }

  if (isDashboardAgentRuntime) {
    return (
      <AgentRuntimeView
        connected={Boolean(health)}
        client={client}
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
        onGetRuntimeSettings={signal => client.getRuntimeSettings(signal)}
        onUpdateRuntimeSettings={async (changes, signal) => {
          const next = await client.updateRuntimeSettings(changes, signal)
          setRuntimeSettings(next)
          return next
        }}
      />
    )
  }

  if (isDashboardAgentSecurity) {
    return (
      <AgentSecurityView
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

  if (isDashboardVoice) {
    return <VoiceView />
  }

  if (dashboardSection === 'memory') {
    return (
      <MemoryView
        client={client}
        projects={projects}
        specialists={specialists}
        sessions={sessions}
        activeProjectId={activeProjectId}
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
        key="models-api-key-test-v3"
        llamaRuntime={{
          load: () => client.llamaRuntimeStatus(),
          ensure: () => client.llamaRuntimeEnsure(),
          catalog: query => client.llamaRuntimeCatalog(query),
          install: (repo, quant) => client.llamaRuntimeInstall(repo, quant),
          remove: modelId => client.llamaRuntimeRemove(modelId),
          loadModel: modelId => client.llamaRuntimeLoad(modelId),
          unloadModel: modelId => client.llamaRuntimeUnload(modelId),
          update: () => client.llamaRuntimeUpdate()
        }}
        integrations={integrations}
        onListModels={options => client.listModels(options)}
        onUpdateModelEnabled={async (modelId, enabled, signal, provider) => {
          const updated = await client.updateModelEnabled(
            modelId,
            enabled,
            signal,
            provider
          )
          void loadModelOptions({ force: true })
          return updated
        }}
        onCreateCustomModel={async (input, signal) => {
          const created = await client.createCustomModel(input, signal)
          void loadModelOptions({ force: true })
          return created
        }}
        onDeleteCustomModel={async (modelId, signal) => {
          await client.deleteCustomModel(modelId, signal)
          void loadModelOptions({ force: true })
        }}
        onListProfiles={signal => client.listModelProfiles({ signal })}
        onCreateProfile={async (input, signal) => {
          const created = await client.createModelProfile(input, signal)
          void loadModelOptions({ force: true })
          return created
        }}
        onUpdateProfile={async (profileId, input, signal) => {
          const updated = await client.updateModelProfile(
            profileId,
            input,
            signal
          )
          void loadModelOptions({ force: true })
          return updated
        }}
        onDeleteProfile={async (profileId, signal) => {
          await client.deleteModelProfile(profileId, signal)
          void loadModelOptions({ force: true })
        }}
        onProbeProfile={(profileId, signal) =>
          client.probeModelProfile(profileId, signal)
        }
        onDiscoverEndpoint={(input, signal) =>
          client.discoverModelEndpoint(input, signal)
        }
        onSaveProviderKey={async (key, values) => {
          await client.updateIntegration(key, values)
          await loadIntegrations()
          await loadModelOptions({ force: true })
        }}
        onClearProviderKey={async key => {
          await client.removeIntegration(key)
          await loadIntegrations()
          await loadModelOptions({ force: true })
        }}
        onTestProviderKey={key => client.validateIntegration(key)}
        onRevealStoredSecret={async key => {
          const revealed = await client.revealIntegrationSecret(key)
          return revealed.value
        }}
        onRevealProfileSecret={async profileId => {
          const revealed = await client.revealModelProfileSecret(profileId)
          return revealed.value
        }}
        onLoadModelPreferences={() => client.getModelPreferences()}
        onToggleModelFavorite={model =>
          client.toggleModelFavorite({
            provider: model.provider,
            model: model.id,
            profileId: model.profileId
          })
        }
        renderChatGPTSignIn={reload => (
          <ChatGPTSignInCard
            client={client}
            onConnected={async () => {
              await reload()
              await loadModelOptions({ force: true })
            }}
            onDisconnected={async () => {
              await reload()
              await loadModelOptions({ force: true })
            }}
          />
        )}
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

  if (isDashboardLogs) {
    return <LogsView onLoad={signal => client.getServices(signal)} />
  }

  if (isDashboardBench) {
    return (
      <BenchView
        client={client}
        runtimeSettings={runtimeSettings}
        setRuntimeSettings={setRuntimeSettings}
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
