import type { Location, NavigateFunction } from 'react-router-dom'

import type { AppShellProps } from '@/components/app-shell-props'
import type { buildAgentComposerSlotProps } from '@/components/app/build-agent-composer-slot-props'
import type { useAppBootstrap } from '@/hooks/useAppBootstrap'
import type { useAppOpenTabs } from '@/hooks/useAppOpenTabs'
import type { useAppRouting } from '@/hooks/useAppRouting'
import type { useAppUiState } from '@/hooks/useAppUiState'
import type { useChatScroll } from '@/hooks/useChatScroll'
import type { useSessionActions } from '@/hooks/useSessionActions'
import type { useSessionChatState } from '@/hooks/useSessionChatState'
import type { useSessionSandbox } from '@/hooks/useSessionSandbox'
import type { groupSessions } from '@/lib/sessions'
import type { TranscriptEntry } from '@/components/agents/transcript'
import type { AgentSession } from '@sandwalk/agent-ui-core'

type AppShellBridgeInput = {
  ui: ReturnType<typeof useAppUiState>
  route: ReturnType<typeof useAppRouting>
  bootstrap: ReturnType<typeof useAppBootstrap>
  context: {
    activeProjectId: string | null
    activeProject: AppShellProps['activeProject']
    catalogSearchEnabled: boolean
    selectedIntegrationKey: string | null
    mcpDetailCatalogEntry: AppShellProps['mcpDetailCatalogEntry']
    mcpDetailServer: AppShellProps['mcpDetailServer']
    session: AppShellProps['session']
  }
  chat: ReturnType<typeof useSessionChatState>
  tabs: ReturnType<typeof useAppOpenTabs>
  actions: ReturnType<typeof useSessionActions>
  sandbox: ReturnType<typeof useSessionSandbox>
  scroll: ReturnType<typeof useChatScroll>
  location: Location
  navigate: NavigateFunction
  sections: ReturnType<typeof groupSessions>
  openTabs: AgentSession[]
  orderedVisibleSessionIds: string[]
  showSessionTabs: boolean
  activeTitle: string
  canShowFilesPanel: boolean
  conversationTimeline: TranscriptEntry[]
  agentComposerSlotProps: ReturnType<typeof buildAgentComposerSlotProps>
  activeRunTodos: AppShellProps['activeRunTodos']
  activeRunTools: AppShellProps['activeRunTools']
  activeBuildPlan: AppShellProps['activeBuildPlan']
  builtPlanPaths: AppShellProps['builtPlanPaths']
  submitApprovals: AppShellProps['onSubmitApprovals']
  showConnectionLimitWarning: boolean
  runningCount: number
  prefetchSessionMessages: AppShellProps['prefetchSessionMessages']
  showChatSkeleton: boolean
}

export function buildAppShellProps(input: AppShellBridgeInput): AppShellProps {
  return {
    sidebarPanelRef: input.ui.sidebarPanelRef,
    isDashboard: input.route.isDashboard,
    dashboardSection: input.route.dashboardSection,
    sidebarUserName: input.bootstrap.sidebarUserName,
    setSidebarCollapsed: input.ui.setSidebarCollapsed,
    logoutSession: input.bootstrap.logoutSession,
    refreshCloudUserName: input.bootstrap.refreshCloudUserName,
    health: input.bootstrap.health,
    backendUrl: input.bootstrap.backendUrl,
    projects: input.bootstrap.projects,
    activeProjectId: input.context.activeProjectId,
    sections: input.sections,
    collapsedSidebarSections: input.ui.collapsedSidebarSections,
    sessionId: input.route.sessionId,
    chatBySessionId: input.chat.chatBySessionId,
    orderedVisibleSessionIds: input.orderedVisibleSessionIds,
    selectedSessionIds: input.actions.selectedSessionIds,
    threadMenuOpenId: input.ui.threadMenuOpenId,
    batchBusy: input.actions.batchBusy,
    canShowFilesPanel: input.canShowFilesPanel,
    filesPanelCollapsed: input.ui.filesPanelCollapsed,
    navigate: input.navigate,
    setProjectScopeId: input.ui.setProjectScopeId,
    selectAllProjects: input.actions.selectAllProjects,
    selectProjectScope: input.actions.selectProjectScope,
    setProjectSettingsOpen: input.ui.setProjectSettingsOpen,
    setNewProjectOpen: input.ui.setNewProjectOpen,
    setGlobalSearchOpen: input.ui.setGlobalSearchOpen,
    createSession: input.actions.createSession,
    setFilesPanelCollapsed: input.ui.setFilesPanelCollapsed,
    clearSessionSelection: input.actions.clearSessionSelection,
    batchArchiveSelected: input.actions.batchArchiveSelected,
    batchMoveSelected: input.actions.batchMoveSelected,
    batchExportSelected: input.actions.batchExportSelected,
    setBatchDeletePending: input.actions.setBatchDeletePending,
    setCollapsedSidebarSections: input.ui.setCollapsedSidebarSections,
    selectSessionRange: input.actions.selectSessionRange,
    toggleSessionSelected: input.actions.toggleSessionSelected,
    setSelectionAnchorId: input.actions.setSelectionAnchorId,
    openSessionTab: input.tabs.openSessionTab,
    prefetchSessionMessages: input.prefetchSessionMessages,
    setThreadMenuOpenId: input.ui.setThreadMenuOpenId,
    openRenameDialog: input.actions.openRenameDialog,
    updateSession: input.actions.updateSession,
    exportTranscript: input.actions.exportTranscript,
    setDeleteTarget: input.actions.setDeleteTarget,
    sidebarCollapsed: input.ui.sidebarCollapsed,
    showConnectionLimitWarning: input.showConnectionLimitWarning,
    runningCount: input.runningCount,
    setConnectionLimitDismissed: input.ui.setConnectionLimitDismissed,
    showSessionTabs: input.showSessionTabs,
    isHome: input.route.isHome,
    isProjectHome: input.route.isProjectHome,
    activeTitle: input.activeTitle,
    isDashboardOverview: input.route.isDashboardOverview,
    isDashboardStatus: input.route.isDashboardStatus,
    isDashboardGeneral: input.route.isDashboardGeneral,
    isDashboardAgentRuntime: input.route.isDashboardAgentRuntime,
    isDashboardAgentSandbox: input.route.isDashboardAgentSandbox,
    isDashboardAgentPrompts: input.route.isDashboardAgentPrompts,
    isDashboardModels: input.route.isDashboardModels,
    isDashboardData: input.route.isDashboardData,
    isDashboardTools: input.route.isDashboardTools,
    isDashboardDoctor: input.route.isDashboardDoctor,
    isDashboardStorage: input.route.isDashboardStorage,
    isDashboardEnvironment: input.route.isDashboardEnvironment,
    isSkills: input.route.isSkills,
    isIntegrations: input.route.isIntegrations,
    isDashboardMcp: input.route.isDashboardMcp,
    isDashboardSpecialists: input.route.isDashboardSpecialists,
    client: input.bootstrap.client,
    location: input.location,
    dashboardSkeletonKind: input.route.dashboardSkeletonKind,
    connecting: input.bootstrap.connecting,
    sessions: input.bootstrap.sessions,
    sessionPreviews: input.bootstrap.sessionPreviews,
    skills: input.bootstrap.skills,
    skillDetail: input.ui.skillDetail,
    catalogSkillRoute: input.route.catalogSkillRoute,
    catalogSearchEnabled: input.context.catalogSearchEnabled,
    isCatalogSearchPath: input.route.isCatalogSearchPath,
    skillsViewMode: input.route.skillsViewMode,
    integrations: input.bootstrap.integrations,
    integrationValues: input.ui.integrationValues,
    selectedIntegrationKey: input.context.selectedIntegrationKey,
    mcpServers: input.bootstrap.mcpServers,
    mcpCatalog: input.bootstrap.mcpCatalog,
    mcpCatalogLoading: input.bootstrap.mcpCatalogLoading,
    mcpCatalogDetailId: input.route.mcpCatalogDetailId,
    mcpServerDetailId: input.route.mcpServerDetailId,
    mcpDetailCatalogEntry: input.context.mcpDetailCatalogEntry,
    mcpDetailServer: input.context.mcpDetailServer,
    isMcpDetail: input.route.isMcpDetail,
    specialists: input.bootstrap.specialists,
    specialistsLoading: input.bootstrap.specialistsLoading,
    specialistsViewMode: input.route.specialistsViewMode,
    specialistsEditId: input.route.specialistsEditId,
    runtimeSettings: input.bootstrap.runtimeSettings,
    sandboxSettings: input.bootstrap.sandboxSettings,
    isSandboxLocalDetail: input.route.isSandboxLocalDetail,
    isSandboxModalDetail: input.route.isSandboxModalDetail,
    setSkillDetail: input.ui.setSkillDetail,
    setIntegrationValues: input.ui.setIntegrationValues,
    setRuntimeSettings: input.bootstrap.setRuntimeSettings,
    setSandboxSettings: input.bootstrap.setSandboxSettings,
    loadSkills: input.bootstrap.loadSkills,
    loadIntegrations: input.bootstrap.loadIntegrations,
    loadMcpServers: input.bootstrap.loadMcpServers,
    refreshMcp: input.bootstrap.refreshMcp,
    loadSpecialists: input.bootstrap.loadSpecialists,
    loadModelOptions: input.bootstrap.loadModelOptions,
    loadSessions: input.bootstrap.loadSessions,
    loadSessionPreviews: input.bootstrap.loadSessionPreviews,
    loadServerStatus: input.bootstrap.loadServerStatus,
    loadAccountForUi: input.bootstrap.loadAccountForUi,
    logoutAccount: input.bootstrap.logoutAccount,
    changeBackend: input.bootstrap.changeBackend,
    disconnectBackend: input.bootstrap.disconnectBackend,
    loadStorage: input.bootstrap.loadStorage,
    loadEnvironment: input.bootstrap.loadEnvironment,
    refreshSessionSandbox: input.sandbox.refreshSessionSandbox,
    togglePinProject: input.actions.togglePinProject,
    deleteProject: input.actions.deleteProject,
    openTabs: input.openTabs,
    session: input.context.session,
    closeSessionTab: input.actions.closeSessionTab,
    closeOtherSessionTabs: input.actions.closeOtherSessionTabs,
    cliMenuOpen: input.ui.cliMenuOpen,
    setCliMenuOpen: input.ui.setCliMenuOpen,
    copiedResumeCommand: input.ui.copiedResumeCommand,
    setCopiedResumeCommand: input.ui.setCopiedResumeCommand,
    terminalOpen: input.ui.terminalOpen,
    setTerminalOpen: input.ui.setTerminalOpen,
    isInspect: input.route.isInspect,
    messages: input.chat.messages,
    tools: input.chat.tools,
    messagesLoaded: input.chat.messagesLoaded,
    runActive: input.chat.runActive,
    showChatSkeleton: input.showChatSkeleton,
    agentComposerSlotProps: input.agentComposerSlotProps,
    recentProjectIds: input.ui.recentProjectIds,
    chatScrollRef: input.scroll.chatScrollRef,
    chatEndRef: input.scroll.chatEndRef,
    conversationTimeline: input.conversationTimeline,
    expandedToolRunKeys: input.chat.expandedToolRunKeys,
    patchChat: input.chat.patchChat,
    runIdByMessageId: input.chat.runIdByMessageId,
    usageByRunId: input.chat.usageByRunId,
    copiedMessageId: input.ui.copiedMessageId,
    setCopiedMessageId: input.ui.setCopiedMessageId,
    activeRunTools: input.activeRunTools,
    activeRunTodos: input.activeRunTodos,
    activeBuildPlan: input.activeBuildPlan,
    builtPlanPaths: input.builtPlanPaths,
    liveDelta: input.chat.liveDelta,
    pendingApproval: input.chat.pendingApproval,
    approvalSubmitting: input.chat.approvalSubmitting,
    onSubmitApprovals: input.submitApprovals,
    showScrollToBottom: input.scroll.showScrollToBottom,
    scrollChatToBottom: input.scroll.scrollChatToBottom,
    error: input.bootstrap.error,
    filesPanelRef: input.ui.filesPanelRef,
    workspaceVersion: input.ui.workspaceVersion,
    pendingOpenPath: input.ui.pendingOpenPath,
    setPendingOpenPath: input.ui.setPendingOpenPath,
    setComposer: input.chat.setComposer,
    setComposerFiles: input.chat.setComposerFiles,
    globalSearchOpen: input.ui.globalSearchOpen,
    newProjectOpen: input.ui.newProjectOpen,
    activeProject: input.context.activeProject,
    workspaceFiles: input.ui.workspaceFiles,
    pendingMentionRef: input.ui.pendingMentionRef,
    createProject: input.actions.createProject,
    projectSettingsOpen: input.ui.projectSettingsOpen,
    saveProjectSettings: input.actions.saveProjectSettings,
    renameTarget: input.actions.renameTarget,
    renameValue: input.actions.renameValue,
    setRenameTarget: input.actions.setRenameTarget,
    setRenameValue: input.actions.setRenameValue,
    submitRename: input.actions.submitRename,
    deleteTarget: input.actions.deleteTarget,
    confirmDelete: input.actions.confirmDelete,
    batchDeletePending: input.actions.batchDeletePending,
    confirmBatchDelete: input.actions.confirmBatchDelete
  }
}
