import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import type { SessionChatState } from '@/lib/sessions'

export type UseSessionActionsArgs = {
  client: LocalAgentClient
  navigate: NavigateFunction
  activeProjectId: string | null
  tabsScopeKey: string
  sessionId: string | null
  /**
   * Id shown as the active tab in the strip. When the URL points at a
   * group (`/agents/grp_...`) this is the group id, NOT the resolved
   * child chat id like `sessionId` — using `sessionId` for strip logic
   * mismatches "close the group tab" against "the active session is a
   * child chat", so close became a no-op and the effect that syncs
   * `activeGroup → openSessionTab` re-added the group on the next tick.
   */
  stripSessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  session: AgentSession | null
  /**
   * Render-time sessions list. Only the selection hook (sidebar bulk
   * actions) needs it; tab/crud handlers read `sessionsRef` so per-pane
   * mounts don't re-render when an unrelated row changes.
   */
  sessions: AgentSession[]
  sessionsRef: MutableRefObject<AgentSession[]>
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
  openTabIds: string[]
  setOpenTabIds: (value: string[] | ((current: string[]) => string[])) => void
  /**
   * Split-view groups indexed by id — needed by `closeOtherSessionTabs`
   * to keep pinned groups even when the user asks to close everything
   * else. Only groups can be pinned; individual chats can't be pinned
   * yet.
   */
  tabGroups: SessionGroup[]
  /** Latest `tabGroups` by ref — read only inside handlers. */
  tabGroupsRef: MutableRefObject<SessionGroup[]>
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
  loadSessions: (options?: {
    force?: boolean
    projectId?: string | null
  }) => Promise<void>
  loadProjects: () => Promise<void>
  setError: Dispatch<SetStateAction<string | null>>
  setCollapsedSidebarSections: Dispatch<
    SetStateAction<Record<string, boolean>>
  >
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setTerminalOpen: Dispatch<SetStateAction<boolean>>
}
