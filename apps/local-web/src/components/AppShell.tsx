import { PanelLeft } from 'lucide-react'
import type { ComponentProps, Dispatch, MutableRefObject, RefObject, SetStateAction } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'
import type { Location, NavigateFunction } from 'react-router-dom'

import { AgentComposerSlot } from '@/components/agents/AgentComposerSlot'
import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { AgentSessionSidebar } from '@/components/agents/AgentSessionSidebar'
import {
  DashboardMainViews,
  type DashboardMainViewsProps
} from '@/components/agents/DashboardMainViews'
import {
  type DashboardSection,
  DashboardSidebar
} from '@/components/agents/DashboardSidebar'
import { type DashboardSkeletonKind } from '@/components/agents/PageSkeletons'
import { type TranscriptEntry } from '@/components/agents/transcript'
import { type TranscriptTool } from '@/components/agents/ToolCard'
import { AppDialogs } from '@/components/AppDialogs'
import { Button } from '@/components/ui/button'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { SHELL_PANELS_AUTO_SAVE_ID } from '@/lib/app-storage'
import { type SessionChatState, groupSessions } from '@/lib/sessions'
import { type SkillsViewMode, type parseCatalogSkillId } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'
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

export function AppShell({
  sidebarPanelRef,
  isDashboard,
  dashboardSection,
  sidebarUserName,
  setSidebarCollapsed,
  logoutSession,
  refreshCloudUserName,
  health,
  backendUrl,
  projects,
  activeProjectId,
  sections,
  collapsedSidebarSections,
  sessionId,
  chatBySessionId,
  orderedVisibleSessionIds,
  selectedSessionIds,
  threadMenuOpenId,
  batchBusy,
  canShowFilesPanel,
  filesPanelCollapsed,
  navigate,
  setProjectScopeId,
  selectAllProjects,
  selectProjectScope,
  setProjectSettingsOpen,
  setNewProjectOpen,
  setGlobalSearchOpen,
  createSession,
  setFilesPanelCollapsed,
  clearSessionSelection,
  batchArchiveSelected,
  batchMoveSelected,
  batchExportSelected,
  setBatchDeletePending,
  setCollapsedSidebarSections,
  selectSessionRange,
  toggleSessionSelected,
  setSelectionAnchorId,
  openSessionTab,
  prefetchSessionMessages,
  setThreadMenuOpenId,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget,
  sidebarCollapsed,
  showConnectionLimitWarning,
  runningCount,
  setConnectionLimitDismissed,
  showSessionTabs,
  isHome,
  isProjectHome,
  activeTitle,
  isDashboardOverview,
  isDashboardStatus,
  isDashboardGeneral,
  isDashboardAgentRuntime,
  isDashboardAgentSandbox,
  isDashboardAgentPrompts,
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
  client,
  location,
  dashboardSkeletonKind,
  connecting,
  sessions,
  sessionPreviews,
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
  togglePinProject,
  deleteProject,
  openTabs,
  session,
  closeSessionTab,
  closeOtherSessionTabs,
  cliMenuOpen,
  setCliMenuOpen,
  copiedResumeCommand,
  setCopiedResumeCommand,
  terminalOpen,
  setTerminalOpen,
  isInspect,
  messages,
  tools,
  messagesLoaded,
  runActive,
  showChatSkeleton,
  agentComposerSlotProps,
  recentProjectIds,
  chatScrollRef,
  chatEndRef,
  conversationTimeline,
  expandedToolRunKeys,
  patchChat,
  runIdByMessageId,
  usageByRunId,
  copiedMessageId,
  setCopiedMessageId,
  activeRunTools,
  activeRunTodos,
  liveDelta,
  showScrollToBottom,
  scrollChatToBottom,
  error,
  filesPanelRef,
  workspaceVersion,
  pendingOpenPath,
  setPendingOpenPath,
  setComposer,
  setComposerFiles,
  globalSearchOpen,
  newProjectOpen,
  activeProject,
  workspaceFiles,
  pendingMentionRef,
  createProject,
  projectSettingsOpen,
  saveProjectSettings,
  renameTarget,
  renameValue,
  setRenameTarget,
  setRenameValue,
  submitRename,
  deleteTarget,
  confirmDelete,
  batchDeletePending,
  confirmBatchDelete
}: AppShellProps) {
  return (
    <>
      <ResizablePanelGroup
        direction="horizontal"
        autoSaveId={SHELL_PANELS_AUTO_SAVE_ID}
        className="bg-background h-full w-full overflow-hidden"
      >
        <ResizablePanel
          id="sidebar"
          order={1}
          ref={sidebarPanelRef}
          collapsible
          collapsedSize={0}
          defaultSize={18}
          minSize={12}
          maxSize={30}
          onCollapse={() => setSidebarCollapsed(true)}
          onExpand={() => setSidebarCollapsed(false)}
          className="min-w-0"
        >
        <aside className="bg-sidebar flex h-full flex-col overflow-hidden">
          {isDashboard ? (
            <DashboardSidebar
              active={dashboardSection}
              userName={sidebarUserName}
              onCollapse={() => setSidebarCollapsed(true)}
              onLogout={logoutSession}
              onRefreshUser={refreshCloudUserName}
              backendVersion={health?.version ?? null}
              backendUrl={backendUrl}
              connected={Boolean(health)}
            />
          ) : (
            <AgentSessionSidebar
              projects={projects}
              activeProjectId={activeProjectId}
              sections={sections}
              collapsedSidebarSections={collapsedSidebarSections}
              sessionId={sessionId}
              chatBySessionId={chatBySessionId}
              orderedVisibleSessionIds={orderedVisibleSessionIds}
              selectedSessionIds={selectedSessionIds}
              threadMenuOpenId={threadMenuOpenId}
              batchBusy={batchBusy}
              canShowFilesPanel={canShowFilesPanel}
              filesPanelCollapsed={filesPanelCollapsed}
              sidebarUserName={sidebarUserName}
              health={health}
              backendUrl={backendUrl}
              navigate={navigate}
              onNavigateHome={() => {
                setProjectScopeId(null)
                navigate('/')
              }}
              onSelectAllProjects={selectAllProjects}
              onSelectProject={selectProjectScope}
              onOpenProjectSettings={() => setProjectSettingsOpen(true)}
              onNewProject={() => setNewProjectOpen(true)}
              onOpenGlobalSearch={() => setGlobalSearchOpen(true)}
              onCollapseSidebar={() => setSidebarCollapsed(true)}
              onCreateSession={() => createSession(activeProjectId)}
              onToggleFilesPanel={() =>
                setFilesPanelCollapsed(current => !current)
              }
              onClearSessionSelection={clearSessionSelection}
              onBatchArchiveSelected={batchArchiveSelected}
              onBatchMoveSelected={batchMoveSelected}
              onBatchExportSelected={batchExportSelected}
              onBatchDeletePending={() => setBatchDeletePending(true)}
              setCollapsedSidebarSections={setCollapsedSidebarSections}
              selectSessionRange={selectSessionRange}
              toggleSessionSelected={toggleSessionSelected}
              setSelectionAnchorId={setSelectionAnchorId}
              openSessionTab={openSessionTab}
              prefetchSessionMessages={prefetchSessionMessages}
              setThreadMenuOpenId={setThreadMenuOpenId}
              openRenameDialog={openRenameDialog}
              updateSession={updateSession}
              exportTranscript={exportTranscript}
              setDeleteTarget={setDeleteTarget}
              onLogout={logoutSession}
              onRefreshUser={refreshCloudUserName}
            />
          )}
        </aside>
        </ResizablePanel>

        <ResizableHandle
          className={cn(
            'w-px',
            sidebarCollapsed && 'pointer-events-none opacity-0'
          )}
        />

        <ResizablePanel
          id="main"
          order={2}
          defaultSize={82}
          minSize={40}
          className="min-w-0"
        >
        <div className="relative flex h-full min-w-0 flex-col">
          {showConnectionLimitWarning ? (
            <div className="border-border bg-amber-500/10 text-amber-950 dark:text-amber-100 flex shrink-0 items-start gap-3 border-b px-3 py-2 text-xs">
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {runningCount} agents running at once
                </p>
                <p className="text-muted-foreground mt-0.5">
                  Browsers allow about 6 live connections to the local API. With
                  this many concurrent runs, opening files or switching chats
                  can stall. Prefer finishing some runs before starting more.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 shrink-0 px-2 text-xs"
                onClick={() => setConnectionLimitDismissed(true)}
              >
                Dismiss
              </Button>
            </div>
          ) : null}
          {!showSessionTabs &&
          !(isHome || isProjectHome || isDashboard) ? (
            <div className="flex h-10 shrink-0 items-center gap-1 border-b px-1.5 md:px-2">
              {sidebarCollapsed ? (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0"
                  onClick={() => setSidebarCollapsed(false)}
                  aria-label="Show sidebar"
                >
                  <PanelLeft className="size-4" />
                </Button>
              ) : null}
              <span className="min-w-0 flex-1 truncate px-2 text-sm font-medium">
                {activeTitle}
              </span>
            </div>
          ) : null}
          {(isHome || isProjectHome || isDashboard) && sidebarCollapsed ? (
            <div className="absolute left-2 top-2 z-20">
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => setSidebarCollapsed(false)}
                aria-label="Show sidebar"
              >
                <PanelLeft className="size-4" />
              </Button>
            </div>
          ) : null}

          {isDashboardOverview ||
          isDashboardStatus ||
          isDashboardGeneral ||
          isDashboardAgentRuntime ||
          isDashboardAgentSandbox ||
          isDashboardAgentPrompts ||
          isDashboardModels ||
          isDashboardData ||
          isDashboardTools ||
          isDashboardDoctor ||
          isDashboardStorage ||
          isDashboardEnvironment ||
          isSkills ||
          isIntegrations ||
          isDashboardMcp ||
          isDashboardSpecialists ||
          isHome ||
          isProjectHome ? (
            <DashboardMainViews
              client={client}
              navigate={navigate}
              location={location}
              dashboardSection={dashboardSection}
              dashboardSkeletonKind={dashboardSkeletonKind}
              backendUrl={backendUrl}
              health={health}
              connecting={connecting}
              sessions={sessions}
              projects={projects}
              sessionPreviews={sessionPreviews}
              activeProjectId={activeProjectId}
              skills={skills}
              skillDetail={skillDetail}
              catalogSkillRoute={catalogSkillRoute}
              catalogSearchEnabled={catalogSearchEnabled}
              isCatalogSearchPath={isCatalogSearchPath}
              skillsViewMode={skillsViewMode}
              integrations={integrations}
              integrationValues={integrationValues}
              selectedIntegrationKey={selectedIntegrationKey}
              mcpServers={mcpServers}
              mcpCatalog={mcpCatalog}
              mcpCatalogLoading={mcpCatalogLoading}
              mcpCatalogDetailId={mcpCatalogDetailId}
              mcpServerDetailId={mcpServerDetailId}
              mcpDetailCatalogEntry={mcpDetailCatalogEntry}
              mcpDetailServer={mcpDetailServer}
              isMcpDetail={isMcpDetail}
              specialists={specialists}
              specialistsLoading={specialistsLoading}
              specialistsViewMode={specialistsViewMode}
              specialistsEditId={specialistsEditId}
              runtimeSettings={runtimeSettings}
              sandboxSettings={sandboxSettings}
              isDashboardOverview={isDashboardOverview}
              isDashboardStatus={isDashboardStatus}
              isDashboardGeneral={isDashboardGeneral}
              isDashboardAgentRuntime={isDashboardAgentRuntime}
              isDashboardAgentPrompts={isDashboardAgentPrompts}
              isDashboardAgentSandbox={isDashboardAgentSandbox}
              isDashboardModels={isDashboardModels}
              isDashboardData={isDashboardData}
              isDashboardTools={isDashboardTools}
              isDashboardDoctor={isDashboardDoctor}
              isDashboardStorage={isDashboardStorage}
              isDashboardEnvironment={isDashboardEnvironment}
              isSkills={isSkills}
              isIntegrations={isIntegrations}
              isDashboardMcp={isDashboardMcp}
              isDashboardSpecialists={isDashboardSpecialists}
              isHome={isHome}
              isProjectHome={isProjectHome}
              isSandboxLocalDetail={isSandboxLocalDetail}
              isSandboxModalDetail={isSandboxModalDetail}
              setSkillDetail={setSkillDetail}
              setIntegrationValues={setIntegrationValues}
              setRuntimeSettings={setRuntimeSettings}
              setSandboxSettings={setSandboxSettings}
              loadSkills={loadSkills}
              loadIntegrations={loadIntegrations}
              loadMcpServers={loadMcpServers}
              refreshMcp={refreshMcp}
              loadSpecialists={loadSpecialists}
              loadModelOptions={loadModelOptions}
              loadSessions={loadSessions}
              loadServerStatus={loadServerStatus}
              loadAccountForUi={loadAccountForUi}
              logoutAccount={logoutAccount}
              loadStorage={loadStorage}
              loadEnvironment={loadEnvironment}
              refreshSessionSandbox={refreshSessionSandbox}
              onCreateProject={() => setNewProjectOpen(true)}
              createSession={createSession}
              onOpenProject={id => {
                setProjectScopeId(id)
                navigate(`/projects/${id}`)
              }}
              togglePinProject={togglePinProject}
              deleteProject={deleteProject}
            />
          ) : (
            <AgentSessionMainPanel
              client={client}
              navigate={navigate}
              sidebarCollapsed={sidebarCollapsed}
              setSidebarCollapsed={setSidebarCollapsed}
              openTabs={openTabs}
              sessionId={sessionId}
              session={session}
              openSessionTab={openSessionTab}
              prefetchSessionMessages={prefetchSessionMessages}
              closeSessionTab={closeSessionTab}
              closeOtherSessionTabs={closeOtherSessionTabs}
              openRenameDialog={openRenameDialog}
              updateSession={updateSession}
              exportTranscript={exportTranscript}
              setDeleteTarget={setDeleteTarget}
              projects={projects}
              selectProjectScope={selectProjectScope}
              cliMenuOpen={cliMenuOpen}
              setCliMenuOpen={setCliMenuOpen}
              copiedResumeCommand={copiedResumeCommand}
              setCopiedResumeCommand={setCopiedResumeCommand}
              terminalOpen={terminalOpen}
              setTerminalOpen={setTerminalOpen}
              filesPanelCollapsed={filesPanelCollapsed}
              setFilesPanelCollapsed={setFilesPanelCollapsed}
              isInspect={isInspect}
              messages={messages}
              tools={tools}
              messagesLoaded={messagesLoaded}
              runActive={runActive}
              showChatSkeleton={showChatSkeleton}
              agentComposerSlotProps={agentComposerSlotProps}
              recentProjectIds={recentProjectIds}
              activeProjectId={activeProjectId}
              onNewProject={() => setNewProjectOpen(true)}
              selectAllProjects={selectAllProjects}
              chatScrollRef={chatScrollRef}
              chatEndRef={chatEndRef}
              conversationTimeline={conversationTimeline}
              expandedToolRunKeys={expandedToolRunKeys}
              patchChat={patchChat}
              runIdByMessageId={runIdByMessageId}
              usageByRunId={usageByRunId}
              copiedMessageId={copiedMessageId}
              setCopiedMessageId={setCopiedMessageId}
              activeRunTools={activeRunTools}
              activeRunTodos={activeRunTodos}
              liveDelta={liveDelta}
              showScrollToBottom={showScrollToBottom}
              scrollChatToBottom={scrollChatToBottom}
              error={error}
              canShowFilesPanel={canShowFilesPanel}
              filesPanelRef={filesPanelRef}
              workspaceVersion={workspaceVersion}
              pendingOpenPath={pendingOpenPath}
              setPendingOpenPath={setPendingOpenPath}
              setComposer={setComposer}
              setComposerFiles={setComposerFiles}
            />
          )}
        </div>
        </ResizablePanel>
      </ResizablePanelGroup>

      <AppDialogs
        client={client}
        navigate={navigate}
        globalSearchOpen={globalSearchOpen}
        setGlobalSearchOpen={setGlobalSearchOpen}
        sessions={sessions}
        sessionId={sessionId}
        sessionTitle={session?.title}
        activeProject={activeProject}
        activeProjectId={activeProjectId}
        workspaceFiles={workspaceFiles}
        openSessionTab={openSessionTab}
        setFilesPanelCollapsed={setFilesPanelCollapsed}
        setPendingOpenPath={setPendingOpenPath}
        pendingMentionRef={pendingMentionRef}
        setComposer={setComposer}
        setComposerFiles={setComposerFiles}
        createSession={createSession}
        newProjectOpen={newProjectOpen}
        setNewProjectOpen={setNewProjectOpen}
        createProject={createProject}
        projectSettingsOpen={projectSettingsOpen}
        setProjectSettingsOpen={setProjectSettingsOpen}
        saveProjectSettings={saveProjectSettings}
        renameTarget={renameTarget}
        renameValue={renameValue}
        setRenameTarget={setRenameTarget}
        setRenameValue={setRenameValue}
        submitRename={submitRename}
        deleteTarget={deleteTarget}
        setDeleteTarget={setDeleteTarget}
        confirmDelete={confirmDelete}
        batchDeletePending={batchDeletePending}
        setBatchDeletePending={setBatchDeletePending}
        batchBusy={batchBusy}
        selectedSessionIds={selectedSessionIds}
        confirmBatchDelete={confirmBatchDelete}
      />
    </>
  )
}
