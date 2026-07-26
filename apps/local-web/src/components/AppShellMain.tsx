import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { DashboardMainViews } from '@/components/agents/DashboardMainViews'
import {
  AppShellMainDragStrip,
  AppShellTitleBar,
  ConnectionLimitBanner
} from '@/components/app/app-shell-main-chrome'
import {
  type AppShellMainProps,
  isDashboardMainView
} from '@/components/app/app-shell-main-props'
import { buildDashboardMainViewsProps } from '@/components/app/build-dashboard-main-views-props'
import {
  SHELL_SIDEBAR_MOTION_MS,
  ShellNavStrip
} from '@/components/ShellNavStrip'
import { ResizablePanel } from '@/components/ui/resizable'
import { useCrossfadeFlag } from '@/hooks/useDeferredTrue'

export type { AppShellMainProps } from '@/components/app/app-shell-main-props'

export function AppShellMain(props: AppShellMainProps) {
  const showSimpleTitleBar =
    !props.showSessionTabs &&
    !(
      props.isHome ||
      props.isLibrary ||
      props.isProjectHome ||
      props.isDashboard
    )
  // Collapsed: toggle + back/forward on the main pane.
  // With session tabs, those controls live in SessionMainHeader (one row).
  // Open + no session tabs: empty drag band aligned with the sidebar strip.
  const showCollapsedNavStrip = useCrossfadeFlag(
    props.sidebarCollapsed && !props.showSessionTabs,
    SHELL_SIDEBAR_MOTION_MS,
    100
  )
  const showMainDragStrip =
    !showCollapsedNavStrip &&
    !props.showSessionTabs &&
    !showSimpleTitleBar

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
        {showCollapsedNavStrip ? (
          <div className="fade-in animate-in duration-200">
            <ShellNavStrip
              sidebarCollapsed
              surface="main"
              onToggleSidebar={() => props.setSidebarCollapsed(false)}
            />
          </div>
        ) : null}
        {showMainDragStrip ? <AppShellMainDragStrip /> : null}
        {showSimpleTitleBar ? (
          <AppShellTitleBar activeTitle={props.activeTitle} />
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
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
            pendingApproval={props.pendingApproval}
            approvalSubmitting={props.approvalSubmitting}
            onSubmitApprovals={props.onSubmitApprovals}
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
      </div>
    </ResizablePanel>
  )
}
