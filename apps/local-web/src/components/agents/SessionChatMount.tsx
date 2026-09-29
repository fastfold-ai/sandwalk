import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession
} from '@sandwalk/agent-ui-core'
import { type Dispatch, type RefObject, type SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { perfCount } from '@/lib/perf-probe'

import { SessionChatBody } from '@/components/agents/session-main/session-chat-body'
import {
  type PerSessionChatStateArgs,
  usePerSessionChatState} from '@/hooks/usePerSessionChatState'

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
  perfCount('render.SessionChatMount')
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
      /*
       * Refs del scroll PROPIOS de cada mount (`perSession.scroll.*`) —
       * NO los del shell. Con N paneles, si todos escribieran al mismo
       * ref del shell, React solo conservaría el último — el "sticky
       * bottom" y el botón scroll-to-bottom apuntarían a un panel al
       * azar en vez de al que los originó.
       */
      chatScrollRef={perSession.scroll.chatScrollRef}
      chatEndRef={perSession.scroll.chatEndRef}
      conversationTimeline={conversationTimeline}
      /*
       * Per-session, not `shared.*`: those are the shell's active chat and
       * painted pane A's usage badges / expanded tool runs in pane B.
       */
      expandedToolRunKeys={chat.expandedToolRunKeys}
      patchChat={shared.patchChat}
      runIdByMessageId={chat.runIdByMessageId}
      usageByRunId={chat.usageByRunId}
      copiedMessageId={shared.copiedMessageId}
      setCopiedMessageId={shared.setCopiedMessageId}
      activeRunTools={activeRunTools}
      activeRunTodos={activeRunTodos}
      activeBuildPlan={activeBuildPlan}
      builtPlanPaths={builtPlanPaths}
      /*
       * `liveDelta` PROPIO del chatId del mount — antes se usaba
       * `shared.liveDelta` (del shell/chat activo del grupo), lo cual
       * hacía que el streaming SSE del panel focused apareciera también
       * en los otros paneles del split view. Cada mount debe leer su
       * delta específico del store por-sesión.
       */
      liveDelta={chat.liveDelta}
      pendingApproval={chat.pendingApproval}
      approvalSubmitting={chat.approvalSubmitting}
      onSubmitApprovals={submitApprovals}
      showScrollToBottom={perSession.scroll.showScrollToBottom}
      scrollChatToBottom={perSession.scroll.scrollChatToBottom}
      setFilesPanelCollapsed={perSessionArgs.setFilesPanelCollapsed}
      setPendingOpenPath={perSessionArgs.setPendingOpenPath}
      error={shared.error}
      splitMode={splitMode}
    />
  )
}
