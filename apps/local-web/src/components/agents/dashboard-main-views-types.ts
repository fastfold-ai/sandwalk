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
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

import type { DashboardSection } from '@/components/agents/DashboardSidebar'
import type { DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import type { CreateDraftSession } from '@/lib/draft-agent'
import type { SkillsViewMode } from '@/lib/skills-catalog'

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
  loadSessionPreviews: (
    sessionIds: string[],
    signal?: AbortSignal
  ) => Promise<void>
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
  isDashboardAppearance: boolean
  isDashboardAgentRuntime: boolean
  isDashboardAgentPrompts: boolean
  isDashboardVoice: boolean
  isDashboardAgentSandbox: boolean
  isDashboardAgentSecurity: boolean
  isDashboardModels: boolean
  isDashboardData: boolean
  isDashboardTools: boolean
  isDashboardDoctor: boolean
  isDashboardBench: boolean
  isDashboardStorage: boolean
  isDashboardEnvironment: boolean
  isSkills: boolean
  isIntegrations: boolean
  isDashboardMcp: boolean
  isDashboardSpecialists: boolean
  isHome: boolean
  isLibrary: boolean
  isProjectHome: boolean
  isSandboxLocalDetail: boolean
  isSandboxModalDetail: boolean
  pendingMentionRef: MutableRefObject<string | string[] | null>
  pendingAttachmentsRef: MutableRefObject<{
    sessionId: string
    paths: string[]
  } | null>
  openSessionTab: (id: string, scopeKey?: string) => void
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
  changeBackend: (url: string, apiKey?: string) => void | Promise<void>
  disconnectBackend: () => void | Promise<void>
  loadStorage: (signal?: AbortSignal) => ReturnType<LocalAgentClient['getStorage']>
  loadEnvironment: (signal?: AbortSignal) => ReturnType<LocalAgentClient['getEnvironment']>
  refreshSessionSandbox: (
    targetSessionId?: string | null
  ) => Promise<import('@sandwalk/agent-ui-core').SessionSandboxStatus | null>
  onCreateProject: () => void
  createSession: CreateDraftSession
  onOpenProject: (projectId: string) => void
  onOpenProjectSettings: () => void
  togglePinProject: (project: AgentProject) => void | Promise<void>
  deleteProject: (project: AgentProject) => void | Promise<void>
}
