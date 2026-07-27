/** Client-only sentinel for /agents/new before a real session exists. */
export const DRAFT_AGENT_SESSION_ID = 'new'

/**
 * PTY scope for terminals opened outside an agent session (cwd = $HOME).
 * Not a chat route — only used with the sessions PTY API.
 */
export const HOST_TERMINAL_SESSION_ID = 'host'

export function isDraftAgentSessionId(
  id: string | null | undefined
): boolean {
  return id === DRAFT_AGENT_SESSION_ID
}

export function isHostTerminalSessionId(
  id: string | null | undefined
): boolean {
  return id === HOST_TERMINAL_SESSION_ID
}

/** Session ids that are route segments, not API session UUIDs. */
export function isReservedAgentRouteId(
  id: string | null | undefined
): boolean {
  return (
    id === 'home' ||
    id === 'skills' ||
    id === 'integrations' ||
    isHostTerminalSessionId(id) ||
    isDraftAgentSessionId(id)
  )
}
