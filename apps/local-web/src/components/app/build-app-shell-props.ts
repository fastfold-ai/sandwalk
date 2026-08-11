import type { AgentSession } from '@sandwalk/agent-ui-core'
import type { Location, NavigateFunction } from 'react-router-dom'

import type { TranscriptEntry } from '@/components/agents/transcript'
import type { buildAgentComposerSlotProps } from '@/components/app/build-agent-composer-slot-props'
import type { AppShellProps } from '@/components/app-shell-props'
import type { useAppBootstrap } from '@/hooks/useAppBootstrap'
import type { useAppOpenTabs } from '@/hooks/useAppOpenTabs'
import type { useAppTabGroups } from '@/hooks/useAppTabGroups'
import type { useAppRouting } from '@/hooks/useAppRouting'
import type { useAppUiState } from '@/hooks/useAppUiState'
import type { useChatScroll } from '@/hooks/useChatScroll'
import type { useSessionActions } from '@/hooks/useSessionActions'
import type { useSessionChatState } from '@/hooks/useSessionChatState'
import type { useSessionSandbox } from '@/hooks/useSessionSandbox'
import type { groupSessions } from '@/lib/sessions'

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
  prefetchSessionMessages: AppShellProps['prefetchSessionMessages']
  showChatSkeleton: boolean
  tabGroupsStore: ReturnType<typeof useAppTabGroups>
  activeGroup: AppShellProps['activeGroup']
  perSessionBaseArgs: AppShellProps['perSessionBaseArgs']
  allSessions: AppShellProps['allSessions']
  onSplitWithNextTab: AppShellProps['onSplitWithNextTab']
  selectedChatIds: AppShellProps['selectedChatIds']
  toggleSelectChat: AppShellProps['toggleSelectChat']
  clearSelectChats: AppShellProps['clearSelectChats']
  createSplitFromSelection: AppShellProps['createSplitFromSelection']
  createSplitFromSidebar: AppShellProps['createSplitFromSidebar']
  canSplitFromSidebar: AppShellProps['canSplitFromSidebar']
  onSelectTabGroup: AppShellProps['onSelectTabGroup']
}

export function buildAppShellProps(input: AppShellBridgeInput): AppShellProps {
  return {
    sidebarPanelRef: input.ui.sidebarPanelRef,
    isDashboard: input.route.isDashboard,
    dashboardSection: input.route.dashboardSection,
    isSites: input.route.isSites,
    siteId: input.route.siteId,
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
    batchMarkReadSelected: input.actions.batchMarkReadSelected,
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
    showSessionTabs: input.showSessionTabs,
    isHome: input.route.isHome,
    isLibrary: input.route.isLibrary,
    isProjectHome: input.route.isProjectHome,
    activeTitle: input.activeTitle,
    isDashboardOverview: input.route.isDashboardOverview,
    isDashboardStatus: input.route.isDashboardStatus,
    isDashboardGeneral: input.route.isDashboardGeneral,
    isDashboardAppearance: input.route.isDashboardAppearance,
    isDashboardAgentRuntime: input.route.isDashboardAgentRuntime,
    isDashboardAgentSandbox: input.route.isDashboardAgentSandbox,
    isDashboardAgentSecurity: input.route.isDashboardAgentSecurity,
    isDashboardAgentPrompts: input.route.isDashboardAgentPrompts,
    isDashboardVoice: input.route.isDashboardVoice,
    isDashboardModels: input.route.isDashboardModels,
    isDashboardData: input.route.isDashboardData,
    isDashboardTools: input.route.isDashboardTools,
    isDashboardDoctor: input.route.isDashboardDoctor,
    isDashboardBench: input.route.isDashboardBench,
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
    loadProjects: input.bootstrap.loadProjects,
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
    reorderSessionTabs: input.actions.reorderSessionTabs,
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
    draftWorkspaceSessionId: input.ui.draftWorkspaceSessionId,
    setDraftWorkspaceSessionId: input.ui.setDraftWorkspaceSessionId,
    pendingOpenPath: input.ui.pendingOpenPath,
    setPendingOpenPath: input.ui.setPendingOpenPath,
    setComposer: input.chat.setComposer,
    setComposerFiles: input.chat.setComposerFiles,
    globalSearchOpen: input.ui.globalSearchOpen,
    newProjectOpen: input.ui.newProjectOpen,
    activeProject: input.context.activeProject,
    workspaceFiles: input.ui.workspaceFiles,
    pendingMentionRef: input.ui.pendingMentionRef,
    pendingAttachmentsRef: input.ui.pendingAttachmentsRef,
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
    confirmBatchDelete: input.actions.confirmBatchDelete,
    tabGroups: input.tabGroupsStore.tabGroups,
    createTabGroup: input.tabGroupsStore.createGroup,
    dissolveTabGroup: input.tabGroupsStore.dissolveGroup,
    addChatToGroup: input.tabGroupsStore.addToGroup,
    removeChatFromGroup: input.tabGroupsStore.removeFromGroup,
    renameTabGroup: input.tabGroupsStore.renameGroup,
    setTabGroupColor: input.tabGroupsStore.setGroupColor,
    setTabGroupPinned: input.tabGroupsStore.setGroupPinned,
    setTabGroupActiveChat: input.tabGroupsStore.setGroupActiveChat,
    reorderChatsInTabGroup: input.tabGroupsStore.reorderChatsInGroup,
    activeGroup: input.activeGroup,
    perSessionBaseArgs: input.perSessionBaseArgs,
    allSessions: input.allSessions,
    onSplitWithNextTab: input.onSplitWithNextTab,
    selectedChatIds: input.selectedChatIds,
    toggleSelectChat: input.toggleSelectChat,
    clearSelectChats: input.clearSelectChats,
    createSplitFromSelection: input.createSplitFromSelection,
    createSplitFromSidebar: input.createSplitFromSidebar,
    canSplitFromSidebar: input.canSplitFromSidebar,
    onSelectTabGroup: input.onSelectTabGroup
  }
}
