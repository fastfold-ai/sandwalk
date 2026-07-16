import type { ComponentProps, RefObject } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { Location, NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import {
  type DashboardMainViewsProps
} from '@/components/agents/DashboardMainViews'
import { type DashboardSection } from '@/components/agents/DashboardSidebar'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type SessionChatState } from '@/lib/sessions'
import {
  type SkillsViewMode,
  parseCatalogSkillId
} from '@/lib/skills-catalog'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentProject,
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  AgentPlanCard,
  AgentTodo,
  BackendHealth,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  Specialist
} from '@sandwalk/agent-ui-core'

export type AppShellMainProps = {
  sidebarCollapsed: boolean
  setSidebarCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
  showConnectionLimitWarning: boolean
  runningCount: number
  setConnectionLimitDismissed: (value: boolean | ((current: boolean) => boolean)) => void
  showSessionTabs: boolean
  isHome: boolean
  isProjectHome: boolean
  isDashboard: boolean
  activeTitle: string
  isDashboardOverview: boolean
  isDashboardStatus: boolean
  isDashboardGeneral: boolean
  isDashboardAgentRuntime: boolean
  isDashboardAgentSandbox: boolean
  isDashboardAgentPrompts: boolean
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
  catalogSkillRoute: ReturnType<typeof parseCatalogSkillId>
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
  isSandboxLocalDetail: boolean
  isSandboxModalDetail: boolean
  setSkillDetail: DashboardMainViewsProps['setSkillDetail']
  setIntegrationValues: DashboardMainViewsProps['setIntegrationValues']
  setRuntimeSettings: DashboardMainViewsProps['setRuntimeSettings']
  setSandboxSettings: DashboardMainViewsProps['setSandboxSettings']
  loadSkills: DashboardMainViewsProps['loadSkills']
  loadIntegrations: DashboardMainViewsProps['loadIntegrations']
  loadMcpServers: DashboardMainViewsProps['loadMcpServers']
  refreshMcp: DashboardMainViewsProps['refreshMcp']
  loadSpecialists: DashboardMainViewsProps['loadSpecialists']
  loadModelOptions: DashboardMainViewsProps['loadModelOptions']
  loadSessions: DashboardMainViewsProps['loadSessions']
  loadSessionPreviews: DashboardMainViewsProps['loadSessionPreviews']
  loadServerStatus: DashboardMainViewsProps['loadServerStatus']
  loadAccountForUi: DashboardMainViewsProps['loadAccountForUi']
  logoutAccount: DashboardMainViewsProps['logoutAccount']
  changeBackend: DashboardMainViewsProps['changeBackend']
  disconnectBackend: DashboardMainViewsProps['disconnectBackend']
  loadStorage: DashboardMainViewsProps['loadStorage']
  loadEnvironment: DashboardMainViewsProps['loadEnvironment']
  refreshSessionSandbox: DashboardMainViewsProps['refreshSessionSandbox']
  togglePinProject: DashboardMainViewsProps['togglePinProject']
  deleteProject: DashboardMainViewsProps['deleteProject']
  setNewProjectOpen: (value: boolean | ((current: boolean) => boolean)) => void
  setProjectScopeId: (value: string | null | ((current: string | null) => string | null)) => void
  createSession: (projectId?: string | null) => Promise<void>
  openTabs: AgentSession[]
  sessionId: string | null
  session: AgentSession | null
  openSessionTab: (id: string, scopeKey?: string) => void
  prefetchSessionMessages: (id: string, signal?: AbortSignal) => void | Promise<void>
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: (value: AgentSession | null | ((current: AgentSession | null) => AgentSession | null)) => void
  selectProjectScope: (projectId: string) => void
  cliMenuOpen: boolean
  setCliMenuOpen: (value: boolean | ((current: boolean) => boolean)) => void
  copiedResumeCommand: boolean
  setCopiedResumeCommand: (value: boolean | ((current: boolean) => boolean)) => void
  terminalOpen: boolean
  setTerminalOpen: (value: boolean | ((current: boolean) => boolean)) => void
  filesPanelCollapsed: boolean
  setFilesPanelCollapsed: (value: boolean | ((current: boolean) => boolean)) => void
  isInspect: boolean
  messages: AgentMessage[]
  tools: TranscriptTool[]
  messagesLoaded: boolean
  runActive: boolean
  showChatSkeleton: boolean
  agentComposerSlotProps: ComponentProps<typeof AgentComposerSlot>
  recentProjectIds: string[]
  selectAllProjects: () => void
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  conversationTimeline: TranscriptEntry[]
  expandedToolRunKeys: Record<string, boolean>
  patchChat: (
    sessionId: string,
    updater: (prev: SessionChatState) => SessionChatState
  ) => void
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  copiedMessageId: string | null
  setCopiedMessageId: (value: string | null | ((current: string | null) => string | null)) => void
  activeRunTools: TranscriptTool[]
  activeRunTodos: AgentTodo[]
  activeBuildPlan: AgentPlanCard | null
  builtPlanPaths: string[]
  liveDelta: string
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  error: string | null
  canShowFilesPanel: boolean
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  workspaceVersion: number
  pendingOpenPath: string | null
  setPendingOpenPath: (value: string | null | ((current: string | null) => string | null)) => void
  setComposer: (value: string | ((current: string) => string)) => void
  setComposerFiles: (value: string[] | ((current: string[]) => string[])) => void
}

export function isDashboardMainView(props: AppShellMainProps) {
  return (
    props.isDashboardOverview ||
    props.isDashboardStatus ||
    props.isDashboardGeneral ||
    props.isDashboardAgentRuntime ||
    props.isDashboardAgentSandbox ||
    props.isDashboardAgentPrompts ||
    props.isDashboardModels ||
    props.isDashboardData ||
    props.isDashboardTools ||
    props.isDashboardDoctor ||
    props.isDashboardStorage ||
    props.isDashboardEnvironment ||
    props.isSkills ||
    props.isIntegrations ||
    props.isDashboardMcp ||
    props.isDashboardSpecialists ||
    props.isHome ||
    props.isProjectHome
  )
}
