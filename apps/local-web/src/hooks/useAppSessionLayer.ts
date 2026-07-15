import { useMemo } from 'react'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { Location, NavigateFunction } from 'react-router-dom'

import { buildConversationTimeline } from '@/components/agents/transcript'
import { buildAgentComposerSlotProps } from '@/components/app/build-agent-composer-slot-props'
import { CONCURRENT_RUN_SOFT_LIMIT, computeRunningCount } from '@/components/app/app-display'
import { usePrefetchSessionMessages } from '@/hooks/useAppRouteContext'
import { useChatScroll } from '@/hooks/useChatScroll'
import { useSessionActions } from '@/hooks/useSessionActions'
import { useSessionChatSend } from '@/hooks/useSessionChatSend'
import { useSessionChatState } from '@/hooks/useSessionChatState'
import { useSessionChatStream } from '@/hooks/useSessionChatStream'
import { useSessionSandbox } from '@/hooks/useSessionSandbox'
import type { SessionChatState } from '@/lib/sessions'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  AgentSkill,
  BackendHealth,
  McpServer,
  RuntimeSettings,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { ComposerModelOption } from '@/lib/composer-models'

type SessionLayerArgs = {
  client: LocalAgentClient
  health: BackendHealth | null
  sessions: AgentSession[]
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
  setError: Dispatch<SetStateAction<string | null>>
  loadSessions: () => Promise<void>
  loadSessionsRef: MutableRefObject<(() => Promise<void>) | null>
  loadProjects: () => Promise<void>
  setSandboxSettings: Dispatch<SetStateAction<import('@sandwalk/agent-ui-core').SandboxSettings | null>>
  skills: AgentSkill[]
  mcpServers: McpServer[]
  modelOptions: ComposerModelOption[]
  specialists: Specialist[]
  runtimeSettings: RuntimeSettings | null
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  loadModelOptions: () => Promise<void>
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  session: AgentSession | null
  activeProjectId: string | null
  activeProject: AgentProject | null
  navigate: NavigateFunction
  location: Location
  tabsScopeKey: string
  openTabsByProject: Record<string, string[]>
  setOpenTabsByProject: Dispatch<SetStateAction<Record<string, string[]>>>
  patchOpenTabs: (
    scopeKey: string,
    updater: (current: string[]) => string[]
  ) => void
  setOpenTabIds: (value: string[] | ((current: string[]) => string[])) => void
  lastSessionByScope: Record<string, string>
  setLastSessionByScope: Dispatch<SetStateAction<Record<string, string>>>
  setProjectScopeId: Dispatch<SetStateAction<string | null>>
  setRecentProjectIds: Dispatch<SetStateAction<string[]>>
  setCollapsedSidebarSections: Dispatch<SetStateAction<Record<string, boolean>>>
  setConnectionLimitDismissed: Dispatch<SetStateAction<boolean>>
  setWorkspaceVersion: Dispatch<SetStateAction<number>>
  workspaceFiles: WorkspaceFile[]
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  setChatBySessionIdRef: MutableRefObject<
    Dispatch<SetStateAction<Record<string, SessionChatState>>> | null
  >
}

export function useAppSessionLayer(args: SessionLayerArgs) {
  const chat = useSessionChatState(args.sessionId)
  args.setChatBySessionIdRef.current = chat.setChatBySessionId

  const runningCount = computeRunningCount(args.sessions)
  const runningSessionIdsKey = args.sessions
    .filter(item => item.status === 'running')
    .map(item => item.id)
    .sort()
    .join(',')

  useSessionChatStream({
    client: args.client,
    health: args.health,
    sessionId: args.sessionId,
    sessionIdRef: args.sessionIdRef,
    sessions: args.sessions,
    runningSessionIdsKey,
    chatBySessionIdRef: chat.chatBySessionIdRef,
    patchChat: chat.patchChat,
    setSessions: args.setSessions,
    setWorkspaceVersion: args.setWorkspaceVersion,
    setError: args.setError,
    loadSessionsRef: args.loadSessionsRef
  })

  const send = useSessionChatSend({
    client: args.client,
    sessionId: args.sessionId,
    sessions: args.sessions,
    runActive: chat.runActive,
    composer: chat.composer,
    composerSkills: chat.composerSkills,
    composerFiles: chat.composerFiles,
    composerLiveRef: chat.composerLiveRef,
    queuedMessages: chat.queuedMessages,
    editingQueuedId: chat.editingQueuedId,
    setEditingQueuedId: chat.setEditingQueuedId,
    pendingImmediateSendRef: chat.pendingImmediateSendRef,
    drainingQueueRef: chat.drainingQueueRef,
    chatBySessionIdRef: chat.chatBySessionIdRef,
    patchChat: chat.patchChat,
    setSessions: args.setSessions,
    setError: args.setError,
    setConnectionLimitDismissed: args.setConnectionLimitDismissed
  })

  const prefetchSessionMessages = usePrefetchSessionMessages(
    args.client,
    chat.chatBySessionIdRef,
    chat.patchChat
  )

  const sandbox = useSessionSandbox({
    client: args.client,
    health: args.health,
    sessionId: args.sessionId,
    sessionIdRef: args.sessionIdRef,
    session: args.session,
    loadSessions: args.loadSessions,
    loadProjects: args.loadProjects,
    setSandboxSettings: args.setSandboxSettings,
    setError: args.setError
  })

  const actions = useSessionActions({
    client: args.client,
    navigate: args.navigate,
    activeProjectId: args.activeProjectId,
    tabsScopeKey: args.tabsScopeKey,
    sessionId: args.sessionId,
    session: args.session,
    sessions: args.sessions,
    setSessions: args.setSessions,
    activeProject: args.activeProject,
    openTabsByProject: args.openTabsByProject,
    setOpenTabsByProject: args.setOpenTabsByProject,
    lastSessionByScope: args.lastSessionByScope,
    setLastSessionByScope: args.setLastSessionByScope,
    setProjectScopeId: args.setProjectScopeId,
    setRecentProjectIds: args.setRecentProjectIds,
    patchOpenTabs: args.patchOpenTabs,
    setOpenTabIds: args.setOpenTabIds,
    patchChat: chat.patchChat,
    setChatBySessionId: chat.setChatBySessionId,
    loadSessions: args.loadSessions,
    loadProjects: args.loadProjects,
    setError: args.setError,
    setCollapsedSidebarSections: args.setCollapsedSidebarSections
  })

  const conversationTimeline = useMemo(
    () =>
      buildConversationTimeline({
        messages: chat.messages,
        tools: chat.tools,
        todosByRunId: chat.todosByRunId,
        runIdByMessageId: chat.runIdByMessageId,
        activeRunId: chat.activeRunId
      }),
    [
      chat.activeRunId,
      chat.messages,
      chat.runIdByMessageId,
      chat.todosByRunId,
      chat.tools
    ]
  )

  const scroll = useChatScroll({
    sessionId: args.sessionId,
    messagesLoaded: chat.messagesLoaded,
    messagesLength: chat.messages.length,
    conversationTimelineLength: conversationTimeline.length
  })

  const agentComposerSlotProps = buildAgentComposerSlotProps({
    sessionId: args.sessionId,
    session: args.session,
    client: args.client,
    navigate: args.navigate,
    composerLiveRef: chat.composerLiveRef,
    queuedMessages: chat.queuedMessages,
    editingQueuedId: chat.editingQueuedId,
    editQueuedMessage: send.editQueuedMessage,
    sendQueuedMessageNow: send.sendQueuedMessageNow,
    removeQueuedMessage: send.removeQueuedMessage,
    cancelEditQueuedMessage: send.cancelEditQueuedMessage,
    composer: chat.composer,
    runActive: chat.runActive,
    skills: args.skills,
    mcpServers: args.mcpServers,
    composerSkills: chat.composerSkills,
    composerFiles: chat.composerFiles,
    workspaceFiles: args.workspaceFiles,
    modelOptions: args.modelOptions,
    specialists: args.specialists,
    sessionSandboxStatus: sandbox.sessionSandboxStatus,
    sessionSandboxPhase: sandbox.sessionSandboxPhase,
    setComposer: chat.setComposer,
    setComposerSkills: chat.setComposerSkills,
    setComposerFiles: chat.setComposerFiles,
    setFilesPanelCollapsed: args.setFilesPanelCollapsed,
    setPendingOpenPath: args.setPendingOpenPath,
    handleComposerSend: send.handleComposerSend,
    setWorkspaceVersion: args.setWorkspaceVersion,
    runtimeSettings: args.runtimeSettings,
    tokenUsage: chat.tokenUsage,
    selectSessionSpecialist: actions.selectSessionSpecialist,
    selectSessionSandboxBackend: sandbox.selectSessionSandboxBackend,
    updateSessionSandboxCompute: sandbox.updateSessionSandboxCompute,
    startSessionSandbox: sandbox.startSessionSandbox,
    stopSessionSandbox: sandbox.stopSessionSandbox,
    restartSessionSandbox: sandbox.restartSessionSandbox,
    setRuntimeSettings: args.setRuntimeSettings,
    loadModelOptions: args.loadModelOptions
  })

  const activeRunTodos = chat.activeRunId
    ? chat.todosByRunId[chat.activeRunId] || []
    : []
  const activeRunTools = chat.activeRunId
    ? chat.tools.filter(
        tool => tool.runId === chat.activeRunId && !tool.messageId
      )
    : []

  return {
    chat,
    send,
    sandbox,
    actions,
    prefetchSessionMessages,
    conversationTimeline,
    scroll,
    agentComposerSlotProps,
    activeRunTodos,
    activeRunTools,
    runningCount,
    runningSessionIdsKey,
    concurrentRunSoftLimit: CONCURRENT_RUN_SOFT_LIMIT
  }
}
