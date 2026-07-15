import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  BackendHealth,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  Specialist
} from '@sandwalk/agent-ui-core'
import { lazy, Suspense, type Dispatch, type SetStateAction } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

import { AppErrorBoundary } from '@/components/AppErrorBoundary'
import { type DashboardSection } from '@/components/agents/DashboardSidebar'
import {
  DashboardPageSkeleton,
  type DashboardSkeletonKind
} from '@/components/agents/PageSkeletons'
import { validateIntegrationOrProbeModal } from '@/lib/app-helpers'
import { onboardingPath } from '@/lib/onboarding'
import {
  catalogSkillDetailPath,
  type SkillsViewMode
} from '@/lib/skills-catalog'

const AgentRuntimeView = lazy(() =>
  import('@/components/agents/AgentRuntimeView').then(m => ({
    default: m.AgentRuntimeView
  }))
)
const AgentPromptsView = lazy(() =>
  import('@/components/agents/AgentPromptsView').then(m => ({
    default: m.AgentPromptsView
  }))
)
const AgentSandboxView = lazy(() =>
  import('@/components/agents/AgentSandboxView').then(m => ({
    default: m.AgentSandboxView
  }))
)
const DashboardOverviewView = lazy(() =>
  import('@/components/agents/DashboardOverviewView').then(m => ({
    default: m.DashboardOverviewView
  }))
)
const DataView = lazy(() =>
  import('@/components/agents/DataView').then(m => ({ default: m.DataView }))
)
const DoctorView = lazy(() =>
  import('@/components/agents/DoctorView').then(m => ({ default: m.DoctorView }))
)
const EnvironmentView = lazy(() =>
  import('@/components/agents/EnvironmentView').then(m => ({
    default: m.EnvironmentView
  }))
)
const GeneralView = lazy(() =>
  import('@/components/agents/GeneralView').then(m => ({
    default: m.GeneralView
  }))
)
const HomeView = lazy(() =>
  import('@/components/agents/HomeView').then(m => ({ default: m.HomeView }))
)
const IntegrationsView = lazy(() =>
  import('@/components/agents/IntegrationsView').then(m => ({
    default: m.IntegrationsView
  }))
)
const McpView = lazy(() =>
  import('@/components/agents/McpView').then(m => ({ default: m.McpView }))
)
const McpDetailView = lazy(() =>
  import('@/components/agents/McpDetailView').then(m => ({
    default: m.McpDetailView
  }))
)
const SandboxListView = lazy(() =>
  import('@/components/agents/SandboxListView').then(m => ({
    default: m.SandboxListView
  }))
)
const ModelsView = lazy(() =>
  import('@/components/agents/ModelsView').then(m => ({ default: m.ModelsView }))
)
const ServerStatusView = lazy(() =>
  import('@/components/agents/ServerStatusView').then(m => ({
    default: m.ServerStatusView
  }))
)
const SkillsView = lazy(() =>
  import('@/components/agents/SkillsView').then(m => ({ default: m.SkillsView }))
)
const SpecialistsView = lazy(() =>
  import('@/components/agents/SpecialistsView').then(m => ({
    default: m.SpecialistsView
  }))
)
const StorageView = lazy(() =>
  import('@/components/agents/StorageView').then(m => ({
    default: m.StorageView
  }))
)
const ToolsView = lazy(() =>
  import('@/components/agents/ToolsView').then(m => ({ default: m.ToolsView }))
)

export type DashboardMainViewsProps = {
  client: LocalAgentClient
  navigate: NavigateFunction
  location: Location
  dashboardSection: DashboardSection
  dashboardSkeletonKind: DashboardSkeletonKind
  backendUrl: string
  health: BackendHealth | null
  connecting: boolean
  sessions: AgentSession[]
  projects: AgentProject[]
  sessionPreviews: Record<string, string>
  activeProjectId: string | null
  skills: AgentSkill[]
  skillDetail: AgentSkillDetail | null
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogSearchEnabled: boolean
  isCatalogSearchPath: boolean
  skillsViewMode: SkillsViewMode
  integrations: IntegrationSummary[]
  integrationValues: Record<string, string>
  selectedIntegrationKey: string | null
  mcpServers: McpServer[]
  mcpCatalog: McpCatalogEntry[]
  mcpCatalogLoading: boolean
  mcpCatalogDetailId: string | null
  mcpServerDetailId: string | null
  mcpDetailCatalogEntry: McpCatalogEntry | null
  mcpDetailServer: McpServer | null
  isMcpDetail: boolean
  specialists: Specialist[]
  specialistsLoading: boolean
  specialistsViewMode: 'list' | 'new' | 'edit'
  specialistsEditId: string | null
  runtimeSettings: RuntimeSettings | null
  sandboxSettings: SandboxSettings | null
  isDashboardOverview: boolean
  isDashboardStatus: boolean
  isDashboardGeneral: boolean
  isDashboardAgentRuntime: boolean
  isDashboardAgentPrompts: boolean
  isDashboardAgentSandbox: boolean
  isDashboardModels: boolean
  isDashboardData: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardStorage: boolean
  isDashboardEnvironment: boolean
  isSkills: boolean
  isIntegrations: boolean
  isDashboardMcp: boolean
  isDashboardSpecialists: boolean
  isHome: boolean
  isProjectHome: boolean
  isSandboxLocalDetail: boolean
  isSandboxModalDetail: boolean
  setSkillDetail: Dispatch<SetStateAction<AgentSkillDetail | null>>
  setIntegrationValues: Dispatch<SetStateAction<Record<string, string>>>
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  setSandboxSettings: Dispatch<SetStateAction<SandboxSettings | null>>
  loadSkills: () => Promise<void>
  loadIntegrations: () => Promise<void>
  loadMcpServers: () => Promise<void>
  refreshMcp: () => Promise<void>
  loadSpecialists: () => Promise<void>
  loadModelOptions: () => Promise<void>
  loadSessions: () => Promise<void>
  loadServerStatus: (signal?: AbortSignal) => ReturnType<LocalAgentClient['getServerStatus']>
  loadAccountForUi: (options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }) => ReturnType<LocalAgentClient['getAccount']>
  logoutAccount: (signal?: AbortSignal) => ReturnType<LocalAgentClient['logoutAccount']>
  loadStorage: (signal?: AbortSignal) => ReturnType<LocalAgentClient['getStorage']>
  loadEnvironment: (signal?: AbortSignal) => ReturnType<LocalAgentClient['getEnvironment']>
  refreshSessionSandbox: (
    targetSessionId?: string | null
  ) => Promise<import('@sandwalk/agent-ui-core').SessionSandboxStatus | null>
  onCreateProject: () => void
  createSession: (projectId?: string | null) => Promise<void>
  onOpenProject: (projectId: string) => void
  togglePinProject: (project: AgentProject) => void | Promise<void>
  deleteProject: (project: AgentProject) => void | Promise<void>
}

export function DashboardMainViews({
  client,
  navigate,
  location,
  dashboardSection,
  dashboardSkeletonKind,
  backendUrl,
  health,
  connecting,
  sessions,
  projects,
  sessionPreviews,
  activeProjectId,
  skills,
  skillDetail,
  catalogSkillRoute,
  catalogSearchEnabled,
  isCatalogSearchPath,
  skillsViewMode,
  integrations,
  integrationValues,
  selectedIntegrationKey,
  mcpServers,
  mcpCatalog,
  mcpCatalogLoading,
  mcpCatalogDetailId,
  mcpServerDetailId,
  mcpDetailCatalogEntry,
  mcpDetailServer,
  isMcpDetail,
  specialists,
  specialistsLoading,
  specialistsViewMode,
  specialistsEditId,
  runtimeSettings,
  sandboxSettings,
  isDashboardOverview,
  isDashboardStatus,
  isDashboardGeneral,
  isDashboardAgentRuntime,
  isDashboardAgentPrompts,
  isDashboardAgentSandbox,
  isDashboardModels,
  isDashboardData,
  isDashboardTools,
  isDashboardDoctor,
  isDashboardStorage,
  isDashboardEnvironment,
  isSkills,
  isIntegrations,
  isDashboardMcp,
  isDashboardSpecialists,
  isHome,
  isProjectHome,
  isSandboxLocalDetail,
  isSandboxModalDetail,
  setSkillDetail,
  setIntegrationValues,
  setRuntimeSettings,
  setSandboxSettings,
  loadSkills,
  loadIntegrations,
  loadMcpServers,
  refreshMcp,
  loadSpecialists,
  loadModelOptions,
  loadSessions,
  loadServerStatus,
  loadAccountForUi,
  logoutAccount,
  loadStorage,
  loadEnvironment,
  refreshSessionSandbox,
  onCreateProject,
  createSession,
  onOpenProject,
  togglePinProject,
  deleteProject
}: DashboardMainViewsProps) {
  return (
    <Suspense
      fallback={<DashboardPageSkeleton kind={dashboardSkeletonKind} />}
    >
      <AppErrorBoundary
        variant="panel"
        resetKeys={[dashboardSection, location.pathname]}
      >
        {isDashboardOverview ? (
        <DashboardOverviewView sessions={sessions}>
          <SkillsView
            featuredOnly
            mode="list"
            skills={skills}
            loading={connecting && skills.length === 0}
            detail={null}
            catalogSkillRoute={null}
            catalogSearchEnabled={catalogSearchEnabled}
            onShowAll={() => navigate('/dashboard/skills')}
            onOpen={name =>
              navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
            }
            onOpenCatalogDetail={skill =>
              navigate(catalogSkillDetailPath(skill))
            }
            onBack={() => navigate('/dashboard/skills')}
            onOpenImportGithub={() =>
              navigate('/dashboard/skills/import/github')
            }
            onOpenImportFile={() =>
              navigate('/dashboard/skills/import/file')
            }
            onOpenTrustedSources={() =>
              navigate('/dashboard/skills/trusted/sources')
            }
            onOpenCatalogSetup={() =>
              navigate('/dashboard/integrations/vercel')
            }
            onInstall={async source => {
              const installed = await client.installSkill(source)
              await loadSkills()
              return installed
            }}
            onUpload={async file => {
              await client.installSkillFile(file)
              await loadSkills()
            }}
            onLoadSuggestedSources={signal =>
              client.listSkillSources(signal)
            }
            onSearchCatalog={(query, signal) =>
              client.searchSkillCatalog(query, 12, signal)
            }
            onGetCatalogDetail={(source, skill, signal) =>
              client.getCatalogSkillDetail(source, skill, signal)
            }
            onGetCatalogAudit={(source, skill, signal) =>
              client.getCatalogSkillAudit(source, skill, signal)
            }
            onBulkAction={async (action, names) => {
              const result = await client.bulkSkillAction(action, names)
              await loadSkills()
              return result
            }}
            onSetEnabled={async (name, enabled) => {
              await client.setSkillEnabled(name, enabled)
              await loadSkills()
            }}
            onRemove={async name => {
              await client.removeSkill(name)
              await loadSkills()
            }}
          />
          <McpView
            featuredOnly
            mcpServers={mcpServers}
            catalog={mcpCatalog}
            catalogLoading={mcpCatalogLoading}
            onShowAll={() => navigate('/dashboard/mcp')}
            onRefresh={refreshMcp}
            onConnectCatalog={async (catalogId, input) => {
              const result = await client.connectMcpCatalog(
                catalogId,
                input
              )
              await refreshMcp()
              await loadIntegrations()
              return result
            }}
            onToggleCatalog={async (entry, enabled) => {
              await client.setMcpCatalogEnabled(entry.id, enabled)
              await refreshMcp()
            }}
            onCreateMcp={async input => {
              await client.createMcpServer(input)
              await loadMcpServers()
            }}
            onDeleteMcp={async id => {
              await client.deleteMcpServer(id)
              await loadMcpServers()
            }}
            onToggleCustom={async (id, enabled) => {
              await client.updateMcpServer(id, { enabled })
              await loadMcpServers()
            }}
            onOpenCatalog={entry =>
              navigate(
                `/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`
              )
            }
          />
          <IntegrationsView
            featuredOnly
            terminalClient={client}
            integrations={integrations}
            loading={connecting && integrations.length === 0}
            selectedKey={null}
            values={{}}
            onShowAll={() => navigate('/dashboard/integrations')}
            onValueChange={() => {}}
            onSelect={key => {
              if (!key) {
                navigate('/dashboard/integrations')
                return
              }
              const target = integrations.find(item => item.key === key)
              const segment = (target?.name || key)
                .trim()
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-+|-+$/g, '')
              navigate(
                `/dashboard/integrations/${encodeURIComponent(segment || key)}`
              )
            }}
            onSave={async () => {}}
            onValidate={async key =>
              validateIntegrationOrProbeModal(client, key)
            }
            onAutofill={async key => {
              await client.autofillIntegration(key)
              await loadIntegrations()
            }}
            onSetup={async key => {
              const result = await client.setupIntegration(key)
              await loadIntegrations()
              return result
            }}
            onOpenVercelTerminal={async () => {
              const existing = sessions.find(item =>
                String(item.workspacePath || '')
                  .trim()
                  .endsWith('/.sandwalk/vercel-integration')
              )
              if (existing) return existing.id
              const created = await client.createSession({
                title: 'Vercel integration setup',
                workspacePath: '~/.sandwalk/vercel-integration',
                projectId: activeProjectId || undefined
              })
              await loadSessions()
              return created.id
            }}
            onRemove={async key => {
              await client.removeIntegration(key)
              await loadIntegrations()
            }}
          />
        </DashboardOverviewView>
          ) : isDashboardStatus ? (
        <ServerStatusView
          onLoad={loadServerStatus}
          onClearCache={signal => client.clearRuntimeCache(signal)}
        />
          ) : isDashboardGeneral ? (
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
          ) : isDashboardAgentRuntime ? (
        <AgentRuntimeView
          connected={Boolean(health)}
          runtimeSettings={runtimeSettings}
          onUpdateRuntimeSettings={async changes => {
            const next = await client.updateRuntimeSettings(changes)
            setRuntimeSettings(next)
            return next
          }}
        />
          ) : isDashboardAgentPrompts ? (
        <AgentPromptsView
          connected={Boolean(health)}
          onGetPromptBudget={(options, signal) =>
            client.getPromptBudget(options, signal)
          }
          onListSpecialists={signal => client.listSpecialists(signal)}
        />
          ) : isDashboardAgentSandbox ? (
        isSandboxLocalDetail ? (
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
        ) : isSandboxModalDetail ? (
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
        ) : (
          <SandboxListView
            onOpen={id =>
              navigate(`/dashboard/agent/sandbox/${id}`)
            }
          />
        )
          ) : isDashboardModels ? (
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
          ) : isDashboardTools ? (
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
          ) : isDashboardData ? (
        <DataView
          onListDatasets={signal => client.listDatasets(signal)}
          onInstallDataset={(datasetId, signal) =>
            client.installDataset(datasetId, signal)
          }
          onRemoveDataset={(datasetId, signal) =>
            client.removeDataset(datasetId, signal)
          }
        />
          ) : isDashboardDoctor ? (
        <DoctorView
          onRun={signal => client.runDoctor(signal)}
          onDownloadDiagnostics={(uiDiagnostics, signal) =>
            client.downloadDiagnostics(uiDiagnostics, signal)
          }
        />
          ) : isDashboardStorage ? (
        <StorageView onLoad={loadStorage} />
          ) : isDashboardEnvironment ? (
        <EnvironmentView
          onLoad={loadEnvironment}
          onInstall={(name, options) =>
            client.installEnvironmentPackage(name, options)
          }
          onUninstall={(name, signal) =>
            client.uninstallEnvironmentPackage(name, signal)
          }
        />
          ) : isSkills ? (
        <SkillsView
          mode={skillsViewMode}
          skills={skills}
          loading={connecting && skills.length === 0}
          detail={skillDetail}
          catalogSkillRoute={catalogSkillRoute}
          catalogSearchEnabled={catalogSearchEnabled}
          openCatalogSearchInitially={isCatalogSearchPath}
          onOpen={name =>
            navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
          }
          onOpenCatalogDetail={skill =>
            navigate(catalogSkillDetailPath(skill))
          }
          onBack={() => navigate('/dashboard/skills')}
          onOpenImportGithub={() => navigate('/dashboard/skills/import/github')}
          onOpenImportFile={() => navigate('/dashboard/skills/import/file')}
          onOpenTrustedSources={() => navigate('/dashboard/skills/trusted/sources')}
          onOpenCatalogSetup={() => navigate('/dashboard/integrations/vercel')}
          onInstall={async source => {
            const installed = await client.installSkill(source)
            await loadSkills()
            return installed
          }}
          onUpload={async file => {
            await client.installSkillFile(file)
            await loadSkills()
          }}
          onLoadSuggestedSources={signal => client.listSkillSources(signal)}
          onSearchCatalog={(query, signal) =>
            client.searchSkillCatalog(query, 12, signal)
          }
          onGetCatalogDetail={(source, skill, signal) =>
            client.getCatalogSkillDetail(source, skill, signal)
          }
          onGetCatalogAudit={(source, skill, signal) =>
            client.getCatalogSkillAudit(source, skill, signal)
          }
          onBulkAction={async (action, names) => {
            const result = await client.bulkSkillAction(action, names)
            if (action === 'remove') {
              setSkillDetail(current =>
                current && result.succeeded.includes(current.name) ? null : current
              )
            } else if (skillDetail && result.succeeded.includes(skillDetail.name)) {
              const refreshed = await client.getSkill(skillDetail.name)
              setSkillDetail(refreshed)
            }
            await loadSkills()
            return result
          }}
          onSetEnabled={async (name, enabled) => {
            const updated = await client.setSkillEnabled(name, enabled)
            setSkillDetail(current =>
              current && current.name === name ? updated : current
            )
            await loadSkills()
          }}
          onRemove={async name => {
            await client.removeSkill(name)
            setSkillDetail(current =>
              current && current.name === name ? null : current
            )
            await loadSkills()
          }}
        />
          ) : isIntegrations ? (
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
          onSelect={key => {
            if (!key) {
              navigate('/dashboard/integrations')
              return
            }
            const target = integrations.find(item => item.key === key)
            const segment = (target?.name || key)
              .trim()
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, '-')
              .replace(/^-+|-+$/g, '')
            navigate(
              `/dashboard/integrations/${encodeURIComponent(segment || key)}`
            )
          }}
          onSave={async () => {
            if (!selectedIntegrationKey) return
            await client.updateIntegration(
              selectedIntegrationKey,
              integrationValues
            )
            setIntegrationValues({})
            await loadIntegrations()
          }}
          onValidate={async key =>
            validateIntegrationOrProbeModal(client, key)
          }
          onAutofill={async key => {
            await client.autofillIntegration(key)
            await loadIntegrations()
          }}
          onSetup={async key => {
            const result = await client.setupIntegration(key)
            await loadIntegrations()
            return result
          }}
          onOpenVercelTerminal={async () => {
            const existing = sessions.find(item =>
              String(item.workspacePath || '')
                .trim()
                .endsWith('/.sandwalk/vercel-integration')
            )
            if (existing) return existing.id
            const created = await client.createSession({
              title: 'Vercel integration setup',
              workspacePath: '~/.sandwalk/vercel-integration',
              projectId: activeProjectId || undefined
            })
            await loadSessions()
            return created.id
          }}
          onRemove={async key => {
            await client.removeIntegration(key)
            if (selectedIntegrationKey === key) {
              navigate('/dashboard/integrations', { replace: true })
            }
            await loadIntegrations()
          }}
        />
          ) : isDashboardMcp ? (
        isMcpDetail ? (
          <McpDetailView
            kind={mcpCatalogDetailId ? 'catalog' : 'server'}
            catalogEntry={mcpDetailCatalogEntry}
            server={mcpDetailServer}
            onBack={() => navigate('/dashboard/mcp')}
            onLoadTools={async () => {
              if (mcpCatalogDetailId) {
                return client.validateMcpCatalog(mcpCatalogDetailId)
              }
              if (mcpServerDetailId) {
                return client.validateMcpServer(mcpServerDetailId)
              }
              return {
                ok: false,
                toolCount: 0,
                message: 'MCP not found',
                tools: [],
                toolDetails: []
              }
            }}
            onToggleEnabled={
              mcpCatalogDetailId && mcpDetailCatalogEntry
                ? async enabled => {
                    await client.setMcpCatalogEnabled(
                      mcpCatalogDetailId,
                      enabled
                    )
                    await refreshMcp()
                  }
                : mcpServerDetailId
                  ? async enabled => {
                      await client.updateMcpServer(mcpServerDetailId, {
                        enabled
                      })
                      await loadMcpServers()
                    }
                  : undefined
            }
            onConnectCatalog={
              mcpCatalogDetailId
                ? async input => {
                    const result = await client.connectMcpCatalog(
                      mcpCatalogDetailId,
                      input
                    )
                    await refreshMcp()
                    await loadIntegrations()
                    return result
                  }
                : undefined
            }
            onDisconnectCatalog={
              mcpCatalogDetailId
                ? async () => {
                    const result =
                      await client.disconnectMcpCatalog(mcpCatalogDetailId)
                    await refreshMcp()
                    await loadIntegrations()
                    return result
                  }
                : undefined
            }
            onRefreshMeta={async () => {
              await refreshMcp()
              await loadIntegrations()
            }}
          />
        ) : (
          <McpView
            mcpServers={mcpServers}
            catalog={mcpCatalog}
            catalogLoading={mcpCatalogLoading}
            onRefresh={refreshMcp}
            onConnectCatalog={async (catalogId, input) => {
              const result = await client.connectMcpCatalog(catalogId, input)
              await refreshMcp()
              await loadIntegrations()
              return result
            }}
            onToggleCatalog={async (entry, enabled) => {
              await client.setMcpCatalogEnabled(entry.id, enabled)
              await refreshMcp()
            }}
            onCreateMcp={async input => {
              await client.createMcpServer(input)
              await loadMcpServers()
            }}
            onDeleteMcp={async id => {
              await client.deleteMcpServer(id)
              await loadMcpServers()
            }}
            onToggleCustom={async (id, enabled) => {
              await client.updateMcpServer(id, { enabled })
              await loadMcpServers()
            }}
            onOpenCatalog={entry =>
              navigate(
                `/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`
              )
            }
            onOpenServer={server =>
              navigate(
                `/dashboard/mcp/server/${encodeURIComponent(server.id)}`
              )
            }
          />
        )
          ) : isDashboardSpecialists ? (
        <SpecialistsView
          mode={specialistsViewMode}
          specialistId={specialistsEditId}
          specialists={specialists}
          skills={skills}
          mcpServers={mcpServers}
          mcpCatalog={mcpCatalog}
          loading={specialistsLoading}
          onRefresh={loadSpecialists}
          onCreate={input => client.createSpecialist(input)}
          onUpdate={(id, input) => client.updateSpecialist(id, input)}
          onDelete={id => client.deleteSpecialist(id)}
          onOpenNew={() => navigate('/dashboard/specialists/new')}
          onOpenEdit={id =>
            navigate(`/dashboard/specialists/${encodeURIComponent(id)}`)
          }
          onBack={() => navigate('/dashboard/specialists')}
          onManageSkills={() => navigate('/dashboard/skills')}
          onManageMcps={() => navigate('/dashboard/mcp')}
          onOpenSkill={name =>
            navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
          }
          onOpenMcp={({ kind, id }) => {
            const hash =
              kind === 'catalog'
                ? `catalog-${encodeURIComponent(id)}`
                : `server-${encodeURIComponent(id)}`
            navigate(`/dashboard/mcp#${hash}`)
          }}
          onEnableSkill={async name => {
            await client.setSkillEnabled(name, true)
            await loadSkills()
          }}
          onInstallSkill={async source => {
            await client.installSkill(source)
            await loadSkills()
          }}
          onListTools={signal => client.listTools({ signal })}
        />
          ) : isHome || isProjectHome ? (
        <HomeView
          projects={projects}
          sessions={sessions}
          previews={sessionPreviews}
          userName={health.userName}
          activeProjectId={activeProjectId}
          onCreateProject={onCreateProject}
          onCreateSession={projectId => void createSession(projectId)}
          onOpenProject={onOpenProject}
          onOpenSession={id => navigate(`/agents/${id}`)}
          onTogglePinProject={project => void togglePinProject(project)}
          onDeleteProject={project => void deleteProject(project)}
        />
        ) : null}
      </AppErrorBoundary>
    </Suspense>
  )
}
