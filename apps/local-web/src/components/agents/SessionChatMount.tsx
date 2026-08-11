import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession
} from '@sandwalk/agent-ui-core'
import { type Dispatch, type RefObject, type SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { SessionChatBody } from '@/components/agents/session-main/session-chat-body'
import {
  usePerSessionChatState,
  type PerSessionChatStateArgs
} from '@/hooks/usePerSessionChatState'

/**
 * Instantiates a full per-session chat surface (mensajes SSE stream, composer,
 * sandbox, actions, timeline) for ONE sessionId. Renders the SessionChatBody
 * bound to that per-session state.
 *
 * Split view mounts N of these side by side; single-tab view mounts one.
 *
 * NOTE: this component receives the shared globals (projects, sessions,
 * etc.) as props too so callers don't have to re-thread them from the app
 * shell — they're just relayed to SessionChatBody unchanged.
 */

type SharedGlobals = {
  isInspect: boolean
  showChatSkeleton: boolean
  projects: AgentProject[]
  recentProjectIds: string[]
  onNewProject: () => void
  selectAllProjects: () => void
  selectProjectScope: (projectId: string) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  chatScrollRef: RefObject<HTMLDivElement | null>
  chatEndRef: RefObject<HTMLDivElement | null>
  expandedToolRunKeys: Record<string, boolean>
  runIdByMessageId: Record<string, string>
  usageByRunId: Record<string, { inputTokens: number; outputTokens: number }>
  copiedMessageId: string | null
  setCopiedMessageId: Dispatch<SetStateAction<string | null>>
  liveDelta: string
  showScrollToBottom: boolean
  scrollChatToBottom: () => void
  patchChat: (
    sessionId: string,
    updater: (prev: import('@/lib/sessions').SessionChatState) => import('@/lib/sessions').SessionChatState
  ) => void
  ensureWorkspaceForMentions?: () => void | Promise<void>
  navigate: NavigateFunction
  client: LocalAgentClient
  error: string | null
}

export type SessionChatMountProps = {
  perSessionArgs: PerSessionChatStateArgs
  shared: SharedGlobals
  /**
   * Modo split view del panel. `undefined` = chat normal single-tab (composer
   * flotante centrado). Cuando existe, activa el composer "embedded" pegado
   * al bottom del panel con animación slide up/down según `focused`.
   */
  splitMode?: { focused: boolean }
}

export function SessionChatMount({
  perSessionArgs,
  shared,
  splitMode
}: SessionChatMountProps) {
  const perSession = usePerSessionChatState(perSessionArgs)
  const {
    chat,
    conversationTimeline,
    agentComposerSlotProps,
    activeRunTodos,
    activeRunTools,
    activeBuildPlan,
    builtPlanPaths,
    submitApprovals
  } = perSession

  return (
    <SessionChatBody
      client={shared.client}
      navigate={shared.navigate}
      sessionId={perSessionArgs.sessionId}
      session={perSessionArgs.session}
      isInspect={shared.isInspect}
      messages={chat.messages}
      tools={chat.tools}
      messagesLoaded={chat.messagesLoaded}
      runActive={chat.runActive}
      showChatSkeleton={shared.showChatSkeleton}
      agentComposerSlotProps={{
        ...agentComposerSlotProps,
        onEnsureWorkspaceFiles: shared.ensureWorkspaceForMentions
      }}
      projects={shared.projects}
      recentProjectIds={shared.recentProjectIds}
      activeProjectId={perSessionArgs.activeProjectId}
      onNewProject={shared.onNewProject}
      selectAllProjects={shared.selectAllProjects}
      selectProjectScope={shared.selectProjectScope}
      updateSession={shared.updateSession}
      chatScrollRef={shared.chatScrollRef}
      chatEndRef={shared.chatEndRef}
      conversationTimeline={conversationTimeline}
      expandedToolRunKeys={shared.expandedToolRunKeys}
      patchChat={shared.patchChat}
      runIdByMessageId={shared.runIdByMessageId}
      usageByRunId={shared.usageByRunId}
      copiedMessageId={shared.copiedMessageId}
      setCopiedMessageId={shared.setCopiedMessageId}
      activeRunTools={activeRunTools}
      activeRunTodos={activeRunTodos}
      activeBuildPlan={activeBuildPlan}
      builtPlanPaths={builtPlanPaths}
      liveDelta={shared.liveDelta}
      pendingApproval={chat.pendingApproval}
      approvalSubmitting={chat.approvalSubmitting}
      onSubmitApprovals={submitApprovals}
      showScrollToBottom={shared.showScrollToBottom}
      scrollChatToBottom={shared.scrollChatToBottom}
      setFilesPanelCollapsed={perSessionArgs.setFilesPanelCollapsed}
      setPendingOpenPath={perSessionArgs.setPendingOpenPath}
      error={shared.error}
      splitMode={splitMode}
    />
  )
}
