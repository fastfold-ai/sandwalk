import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { DashboardMainViews } from '@/components/agents/DashboardMainViews'
import {
  AppShellFloatingSidebarToggle,
  AppShellTitleBar,
  ConnectionLimitBanner
} from '@/components/app/app-shell-main-chrome'
import {
  type AppShellMainProps,
  isDashboardMainView
} from '@/components/app/app-shell-main-props'
import { buildDashboardMainViewsProps } from '@/components/app/build-dashboard-main-views-props'
import { ResizablePanel } from '@/components/ui/resizable'

export type { AppShellMainProps } from '@/components/app/app-shell-main-props'

export function AppShellMain(props: AppShellMainProps) {
  const showSimpleTitleBar =
    !props.showSessionTabs &&
    !(props.isHome || props.isProjectHome || props.isDashboard)
  const showFloatingSidebarToggle =
    (props.isHome || props.isProjectHome || props.isDashboard) &&
    props.sidebarCollapsed

  return (
    <ResizablePanel
      id="main"
      order={2}
      defaultSize={82}
      minSize={40}
      className="min-w-0"
    >
      <div className="relative flex h-full min-w-0 flex-col">
        {props.showConnectionLimitWarning ? (
          <ConnectionLimitBanner
            runningCount={props.runningCount}
            onDismiss={() => props.setConnectionLimitDismissed(true)}
          />
        ) : null}
        {showSimpleTitleBar ? (
          <AppShellTitleBar
            sidebarCollapsed={props.sidebarCollapsed}
            setSidebarCollapsed={props.setSidebarCollapsed}
            activeTitle={props.activeTitle}
          />
        ) : null}
        {showFloatingSidebarToggle ? (
          <AppShellFloatingSidebarToggle
            setSidebarCollapsed={props.setSidebarCollapsed}
          />
        ) : null}

        {isDashboardMainView(props) ? (
          <DashboardMainViews {...buildDashboardMainViewsProps(props)} />
        ) : (
          <AgentSessionMainPanel
            client={props.client}
            navigate={props.navigate}
            sidebarCollapsed={props.sidebarCollapsed}
            setSidebarCollapsed={props.setSidebarCollapsed}
            openTabs={props.openTabs}
            sessionId={props.sessionId}
            session={props.session}
            openSessionTab={props.openSessionTab}
            prefetchSessionMessages={props.prefetchSessionMessages}
            closeSessionTab={props.closeSessionTab}
            closeOtherSessionTabs={props.closeOtherSessionTabs}
            openRenameDialog={props.openRenameDialog}
            updateSession={props.updateSession}
            exportTranscript={props.exportTranscript}
            setDeleteTarget={props.setDeleteTarget}
            projects={props.projects}
            selectProjectScope={props.selectProjectScope}
            cliMenuOpen={props.cliMenuOpen}
            setCliMenuOpen={props.setCliMenuOpen}
            copiedResumeCommand={props.copiedResumeCommand}
            setCopiedResumeCommand={props.setCopiedResumeCommand}
            terminalOpen={props.terminalOpen}
            setTerminalOpen={props.setTerminalOpen}
            filesPanelCollapsed={props.filesPanelCollapsed}
            setFilesPanelCollapsed={props.setFilesPanelCollapsed}
            isInspect={props.isInspect}
            messages={props.messages}
            tools={props.tools}
            messagesLoaded={props.messagesLoaded}
            runActive={props.runActive}
            showChatSkeleton={props.showChatSkeleton}
            agentComposerSlotProps={props.agentComposerSlotProps}
            recentProjectIds={props.recentProjectIds}
            activeProjectId={props.activeProjectId}
            onNewProject={() => props.setNewProjectOpen(true)}
            selectAllProjects={props.selectAllProjects}
            chatScrollRef={props.chatScrollRef}
            chatEndRef={props.chatEndRef}
            conversationTimeline={props.conversationTimeline}
            expandedToolRunKeys={props.expandedToolRunKeys}
            patchChat={props.patchChat}
            runIdByMessageId={props.runIdByMessageId}
            usageByRunId={props.usageByRunId}
            copiedMessageId={props.copiedMessageId}
            setCopiedMessageId={props.setCopiedMessageId}
            activeRunTools={props.activeRunTools}
            activeRunTodos={props.activeRunTodos}
            activeBuildPlan={props.activeBuildPlan}
            builtPlanPaths={props.builtPlanPaths}
            liveDelta={props.liveDelta}
            showScrollToBottom={props.showScrollToBottom}
            scrollChatToBottom={props.scrollChatToBottom}
            error={props.error}
            canShowFilesPanel={props.canShowFilesPanel}
            filesPanelRef={props.filesPanelRef}
            workspaceVersion={props.workspaceVersion}
            pendingOpenPath={props.pendingOpenPath}
            setPendingOpenPath={props.setPendingOpenPath}
            setComposer={props.setComposer}
            setComposerFiles={props.setComposerFiles}
          />
        )}
      </div>
    </ResizablePanel>
  )
}
