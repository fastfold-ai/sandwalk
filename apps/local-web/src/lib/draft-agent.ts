/** Client-only sentinel for /agents/new before a real session exists. */
export const DRAFT_AGENT_SESSION_ID = 'new'

export type DraftSessionSeed = {
  composer?: string
  composerSkills?: string[]
}

export type CreateDraftSession = (
  projectId?: string | null,
  seed?: DraftSessionSeed
) => Promise<void>

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
    isDraftAgentSessionId(id) ||
    // FAS-107 X3 Fase 6a: los terminales tienen su propia ruta
    // `/terminals/:id`. Un `term_*` que caiga en `/agents/:id` es un
    // error de navegación — el router debe descartarlo. `navigateToSession`
    // (App.tsx) redirige preventivamente a la ruta correcta.
    (typeof id === 'string' && id.startsWith('term_'))
  )
}

/**
 * FAS-107 X3 Fase 6a: navigate helper que elige la ruta correcta según
 * el prefijo del id. Antes cada consumidor duplicaba el switch
 * (`id.startsWith('term_') ? '/terminals/' : '/agents/'`), y bastaba
 * con olvidarse uno para que el sistema cayera en la ruta ambigua.
 *
 * - `term_*` → `/terminals/:id`
 * - `chat_*`, `grp_*`, drafts → `/agents/:id`
 */
export function sessionRoutePath(id: string): string {
  if (id.startsWith('term_')) return `/terminals/${id}`
  return `/agents/${id}`
}
