import { useCallback, useRef, type MutableRefObject, type SetStateAction } from 'react'

import { resolveSelectedIntegrationKey } from '@/components/app/app-display'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer
} from '@sandwalk/agent-ui-core'

import type { SessionChatState } from '@/lib/sessions'

type UseAppRouteContextInput = {
  decodedIntegrationRouteName: string | null
  normalizedIntegrationRouteName: string | null
  integrations: IntegrationSummary[]
  projectScopeId: string | null
  openTabIds: string[]
  projects: AgentProject[]
  mcpCatalogDetailId: string | null
  mcpCatalog: McpCatalogEntry[]
  mcpServerDetailId: string | null
  mcpServers: McpServer[]
  sessionId: string | null
  sessions: AgentSession[]
}

export function useAppRouteContext(input: UseAppRouteContextInput) {
  const catalogSearchEnabled =
    input.integrations.find(item => item.key === 'skills-sh')?.configured ?? false

  const selectedIntegrationKey = resolveSelectedIntegrationKey(
    input.decodedIntegrationRouteName,
    input.normalizedIntegrationRouteName,
    input.integrations
  )

  const activeProjectId = input.projectScopeId
  const activeProject =
    input.projects.find(project => project.id === activeProjectId) || null
  const activeIntegration =
    input.integrations.find(item => item.key === selectedIntegrationKey) || null
  const mcpDetailCatalogEntry = input.mcpCatalogDetailId
    ? input.mcpCatalog.find(entry => entry.id === input.mcpCatalogDetailId) || null
    : null
  const mcpDetailServer = input.mcpServerDetailId
    ? input.mcpServers.find(server => server.id === input.mcpServerDetailId) || null
    : null
  const session =
    input.sessions.find(item => item.id === input.sessionId) || null

  return {
    catalogSearchEnabled,
    selectedIntegrationKey,
    activeProjectId,
    activeProject,
    activeIntegration,
    mcpDetailCatalogEntry,
    mcpDetailServer,
    session
  }
}

export function usePrefetchSessionMessages(
  client: LocalAgentClient,
  chatBySessionIdRef: MutableRefObject<Record<string, SessionChatState>>,
  patchChat: (
    sessionId: string,
    updater: (prev: SessionChatState) => SessionChatState
  ) => void
) {
  return useCallback(
    async (id: string, signal?: AbortSignal) => {
      if (chatBySessionIdRef.current[id]?.messagesLoaded) return
      try {
        const history = await client.listMessages(id, signal)
        if (signal?.aborted) return
        patchChat(id, prev => ({
          ...prev,
          messages: history,
          messagesLoaded: true
        }))
      } catch (cause: unknown) {
        if (signal?.aborted) return
        if (cause instanceof Error && cause.name === 'AbortError') return
      }
    },
    [client, patchChat, chatBySessionIdRef]
  )
}

export function useChatBySessionIdBridge() {
  const setChatBySessionIdRef = useRef(
    (_value: SetStateAction<Record<string, SessionChatState>>) => {}
  )
  const setChatBySessionIdBridge = useCallback(
    (value: SetStateAction<Record<string, SessionChatState>>) => {
      setChatBySessionIdRef.current(value)
    },
    []
  )
  return { setChatBySessionIdRef, setChatBySessionIdBridge }
}
