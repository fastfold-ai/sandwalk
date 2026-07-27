import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import type { SessionChatState } from '@/lib/sessions'

export type UseSessionActionsArgs = {
  client: LocalAgentClient
  navigate: NavigateFunction
  activeProjectId: string | null
  tabsScopeKey: string
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  session: AgentSession | null
  sessions: AgentSession[]
  setSessions: Dispatch<SetStateAction<AgentSession[]>>
  activeProject: AgentProject | null
  openTabsByProject: Record<string, string[]>
  setOpenTabsByProject: Dispatch<SetStateAction<Record<string, string[]>>>
  lastSessionByScope: Record<string, string>
  setLastSessionByScope: Dispatch<SetStateAction<Record<string, string>>>
  setProjectScopeId: Dispatch<SetStateAction<string | null>>
  setRecentProjectIds: Dispatch<SetStateAction<string[]>>
  patchOpenTabs: (
    scopeKey: string,
    updater: (current: string[]) => string[]
  ) => void
  setOpenTabIds: (value: string[] | ((current: string[]) => string[])) => void
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
  composerLiveRef: MutableRefObject<string>
  loadSessions: () => Promise<void>
  loadProjects: () => Promise<void>
  setError: Dispatch<SetStateAction<string | null>>
  setCollapsedSidebarSections: Dispatch<
    SetStateAction<Record<string, boolean>>
  >
}
