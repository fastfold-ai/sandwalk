import type { ComponentProps, Dispatch, MutableRefObject, RefObject, SetStateAction } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { Location, NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { type DashboardMainViewsProps } from '@/components/agents/DashboardMainViews'
import { type DashboardSection } from '@/components/agents/DashboardSidebar'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { type SessionChatState, groupSessions } from '@/lib/sessions'
import { type SkillsViewMode, type parseCatalogSkillId } from '@/lib/skills-catalog'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentProject,
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  AgentTodo,
  BackendHealth,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'

export type AppShellProps = {
  sidebarPanelRef: RefObject<ImperativePanelHandle | null>
  isDashboard: boolean
  dashboardSection: DashboardSection
  sidebarUserName: string | null
  setSidebarCollapsed: Dispatch<SetStateAction<boolean>>
  logoutSession: () => void | Promise<void>
  refreshCloudUserName: () => void | Promise<void>
  health: BackendHealth | null
  backendUrl: string
  projects: AgentProject[]
  activeProjectId: string | null
  sections: ReturnType<typeof groupSessions>
  collapsedSidebarSections: Record<string, boolean>
  sessionId: string | null
  chatBySessionId: Record<string, SessionChatState>
  orderedVisibleSessionIds: string[]
  selectedSessionIds: Set<string>
  threadMenuOpenId: string | null
  batchBusy: boolean
  canShowFilesPanel: boolean
  filesPanelCollapsed: boolean
  navigate: NavigateFunction
  setProjectScopeId: Dispatch<SetStateAction<string | null>>
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  setProjectSettingsOpen: Dispatch<SetStateAction<boolean>>
  setNewProjectOpen: Dispatch<SetStateAction<boolean>>
  setGlobalSearchOpen: Dispatch<SetStateAction<boolean>>
  createSession: (projectId?: string | null) => Promise<void>
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  clearSessionSelection: () => void
  batchArchiveSelected: () => void | Promise<void>
  batchMoveSelected: (projectId: string | null) => void | Promise<void>
  batchExportSelected: () => void | Promise<void>
  setBatchDeletePending: Dispatch<SetStateAction<boolean>>
  setCollapsedSidebarSections: Dispatch<SetStateAction<Record<string, boolean>>>
  selectSessionRange: (orderedIds: string[], targetId: string) => void
  toggleSessionSelected: (id: string) => void
  setSelectionAnchorId: Dispatch<SetStateAction<string | null>>
  openSessionTab: (id: string, scopeKey?: string) => void
  prefetchSessionMessages: (id: string, signal?: AbortSignal) => void | Promise<void>
  setThreadMenuOpenId: Dispatch<SetStateAction<string | null>>
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  sidebarCollapsed: boolean
  showConnectionLimitWarning: boolean
  runningCount: number
  setConnectionLimitDismissed: Dispatch<SetStateAction<boolean>>
  showSessionTabs: boolean
  isHome: boolean
  isProjectHome: boolean
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
  location: Location
  dashboardSkeletonKind: DashboardSkeletonKind
  connecting: boolean
  sessions: AgentSession[]
  sessionPreviews: Record<string, string>
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
  setSkillDetail: Dispatch<SetStateAction<AgentSkillDetail | null>>
  setIntegrationValues: Dispatch<SetStateAction<Record<string, string>>>
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  setSandboxSettings: Dispatch<SetStateAction<SandboxSettings | null>>
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
  loadStorage: DashboardMainViewsProps['loadStorage']
  loadEnvironment: DashboardMainViewsProps['loadEnvironment']
  refreshSessionSandbox: DashboardMainViewsProps['refreshSessionSandbox']
  togglePinProject: DashboardMainViewsProps['togglePinProject']
  deleteProject: DashboardMainViewsProps['deleteProject']
  openTabs: AgentSession[]
  session: AgentSession | null
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
  cliMenuOpen: boolean
  setCliMenuOpen: Dispatch<SetStateAction<boolean>>
  copiedResumeCommand: boolean
  setCopiedResumeCommand: Dispatch<SetStateAction<boolean>>
  terminalOpen: boolean
  setTerminalOpen: Dispatch<SetStateAction<boolean>>
  isInspect: boolean
  messages: AgentMessage[]
  tools: TranscriptTool[]
  messagesLoaded: boolean
  runActive: boolean
  showChatSkeleton: boolean
  agentComposerSlotProps: ComponentProps<typeof AgentComposerSlot>
  recentProjectIds: string[]
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
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  activeRunTools: TranscriptTool[]
  activeRunTodos: AgentTodo[]
  liveDelta: string
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  error: string | null
  filesPanelRef: RefObject<ImperativePanelHandle | null>
  workspaceVersion: number
  pendingOpenPath: string | null
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  setComposer: Dispatch<SetStateAction<string>>
  setComposerFiles: Dispatch<SetStateAction<string[]>>
  globalSearchOpen: boolean
  newProjectOpen: boolean
  activeProject: AgentProject | null
  workspaceFiles: WorkspaceFile[]
  pendingMentionRef: MutableRefObject<string | null>
  createProject: (input: {
    name: string
    description: string
    agentContext: string
  }) => Promise<void>
  projectSettingsOpen: boolean
  saveProjectSettings: (input: {
    name: string
    description: string
    agentContext: string
  }) => Promise<void>
  renameTarget: AgentSession | null
  renameValue: string
  setRenameTarget: Dispatch<SetStateAction<AgentSession | null>>
  setRenameValue: Dispatch<SetStateAction<string>>
  submitRename: () => Promise<void>
  deleteTarget: AgentSession | null
  confirmDelete: () => Promise<void>
  batchDeletePending: boolean
  confirmBatchDelete: () => Promise<void>
}
