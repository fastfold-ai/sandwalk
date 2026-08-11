import { AgentSessionMainPanel } from '@/components/agents/AgentSessionMainPanel'
import { skillChipToken } from '@/components/agents/composer-parts'
import { DashboardMainViews } from '@/components/agents/DashboardMainViews'
import { SitesView } from '@/components/agents/SitesView'
import {
  AppShellMainDragStrip,
  AppShellTitleBar
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
import { isDraftAgentSessionId } from '@/lib/draft-agent'

export type { AppShellMainProps } from '@/components/app/app-shell-main-props'

export function AppShellMain(props: AppShellMainProps) {
  // Draft New Agent already has SessionMainHeader (files/terminal chrome).
  // Don't stack a redundant "New Chat" title row when no tabs are open.
  const showSimpleTitleBar =
    !props.showSessionTabs &&
    !isDraftAgentSessionId(props.sessionId) &&
    !(
      props.isHome ||
      props.isLibrary ||
      props.isSites ||
      props.isProjectHome ||
      props.isDashboard
    )
  // Collapsed: toggle + back/forward on the main pane.
  // With session tabs, those controls live in SessionMainHeader (one row).
  const showCollapsedNavStrip = useCrossfadeFlag(
    props.sidebarCollapsed && !props.showSessionTabs,
    SHELL_SIDEBAR_MOTION_MS,
    100
  )
  const addSite = async () => {
    await props.createSession(undefined, {
      composer: `${skillChipToken('sites-building')} Create a site for …`
    })
  }

  return (
    <ResizablePanel
      id="main"
      order={2}
      defaultSize={77}
      minSize={40}
      className="min-w-0"
    >
      <div className="sandwalk-shell-main relative flex h-full min-w-0 flex-col bg-background">
        {/* Layout-neutral drag hit target — every main view, does not shift content. */}
        <AppShellMainDragStrip />
        {showCollapsedNavStrip ? (
          <div className="relative z-20 fade-in animate-in duration-200">
            <ShellNavStrip
              sidebarCollapsed
              surface="main"
              onToggleSidebar={() => props.setSidebarCollapsed(false)}
            />
          </div>
        ) : null}
        {showSimpleTitleBar ? (
          <div className="relative z-20">
            <AppShellTitleBar activeTitle={props.activeTitle} />
          </div>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {props.isSites ? (
          <SitesView
            client={props.client}
            navigate={props.navigate}
            siteId={props.siteId}
            sessions={props.sessions}
            projects={props.projects}
            onAddSite={() => void addSite()}
          />
        ) : isDashboardMainView(props) ? (
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
            createSession={props.createSession}
            openSessionTab={props.openSessionTab}
            prefetchSessionMessages={props.prefetchSessionMessages}
            closeSessionTab={props.closeSessionTab}
            closeOtherSessionTabs={props.closeOtherSessionTabs}
            reorderSessionTabs={props.reorderSessionTabs}
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
            draftWorkspaceSessionId={props.draftWorkspaceSessionId}
            setDraftWorkspaceSessionId={props.setDraftWorkspaceSessionId}
            pendingOpenPath={props.pendingOpenPath}
            setPendingOpenPath={props.setPendingOpenPath}
            setComposer={props.setComposer}
            setComposerFiles={props.setComposerFiles}
            activeGroup={props.activeGroup}
            perSessionBaseArgs={props.perSessionBaseArgs}
            allSessions={props.allSessions}
            setTabGroupActiveChat={props.setTabGroupActiveChat}
          />
        )}
        </div>
      </div>
    </ResizablePanel>
  )
}
