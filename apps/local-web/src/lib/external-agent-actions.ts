import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  ExternalAgentKind,
  ExternalSessionSummary,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { toast } from 'sonner'
import { create } from 'zustand'

import { EXTERNAL_AGENT_LABELS } from '@/components/agents/ExternalAgentIcon'
import { useTerminalsStore } from '@/lib/terminals-store'

/**
 * Actions that bridge Sandwalk and the coding-agent CLIs (Claude Code,
 * Codex, OpenCode, fx). Menus deep in the tree call these without a prop
 * cascade; `App` binds the client and navigation once at boot.
 */
type Bindings = {
  client: LocalAgentClient
  /** Register a chat/terminal in the tab strip and route to it. */
  openItem: (id: string) => void
  /** Pull the session list again so an imported chat shows up at once. */
  reloadSessions: () => Promise<unknown>
}

type ExternalAgentActionsState = {
  bindings: Bindings | null
  busy: Record<string, boolean>
  /** Which CLIs are on PATH; null until the first probe. */
  installed: Partial<Record<ExternalAgentKind, boolean>> | null
  bind: (bindings: Bindings | null) => void
  setBusy: (key: string, value: boolean) => void
  setInstalled: (installed: Partial<Record<ExternalAgentKind, boolean>>) => void
}

export const useExternalAgentActions = create<ExternalAgentActionsState>()(set => ({
  bindings: null,
  busy: {},
  installed: null,
  bind: bindings => set({ bindings }),
  setBusy: (key, value) =>
    set(state => {
      if (Boolean(state.busy[key]) === value) return state
      const next = { ...state.busy }
      if (value) next[key] = true
      else delete next[key]
      return { busy: next }
    }),
  setInstalled: installed => set({ installed })
}))

/** Probe which agent CLIs are installed; cheap (no session scan). */
export async function refreshInstalledAgents(client: LocalAgentClient): Promise<void> {
  try {
    const result = await client.listExternalAgents({ sessions: false })
    const installed: Partial<Record<ExternalAgentKind, boolean>> = {}
    for (const agent of result.agents) installed[agent.kind] = agent.installed
    useExternalAgentActions.getState().setInstalled(installed)
  } catch {
    // Offline or old server: menus fall back to "unknown" (enabled).
  }
}

/** True when known-installed, or unknown (so the menu still offers it). */
export function useAgentInstalled(kind: ExternalAgentKind): boolean {
  return useExternalAgentActions(state => state.installed?.[kind] ?? true)
}

function bindingsOrWarn(): Bindings | null {
  const bindings = useExternalAgentActions.getState().bindings
  if (!bindings) toast.error('Not connected to the Sandwalk server yet.')
  return bindings
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  return fallback
}

/** Newest session of `kind` recorded for `cwd`, or null. */
export async function newestExternalSession(
  client: LocalAgentClient,
  kind: ExternalAgentKind,
  cwd: string | null
): Promise<ExternalSessionSummary | null> {
  const result = await client.listExternalAgents({ kind, cwd, limit: 1 })
  return result.sessions[0] ?? null
}

/**
 * Terminal tab → "Convert to Sandwalk session": import the CLI's most recent
 * session for that folder as a chat and open it. The terminal stays open.
 */
export async function convertTerminalToSession(
  terminal: TerminalSession,
  kind: ExternalAgentKind
): Promise<AgentSession | null> {
  const bindings = bindingsOrWarn()
  if (!bindings) return null
  const { client, openItem, reloadSessions } = bindings
  const key = `convert:${terminal.id}`
  const actions = useExternalAgentActions.getState()
  if (actions.busy[key]) return null
  actions.setBusy(key, true)
  const label = EXTERNAL_AGENT_LABELS[kind]
  try {
    const cwd = terminal.workspacePath
    const newest = await newestExternalSession(client, kind, cwd)
    if (!newest) {
      toast.message(`No ${label} session saved yet for this folder.`, {
        description: 'Send a message in the CLI first, then convert.'
      })
      return null
    }
    const session = await client.importExternalSession({
      kind,
      sessionId: newest.id,
      projectId: terminal.projectId,
      workspacePath: cwd
    })
    await reloadSessions()
    openItem(session.id)
    toast.success(`Imported “${session.title}” from ${label}.`)
    return session
  } catch (error) {
    toast.error(errorText(error, `Could not import the ${label} session.`))
    return null
  } finally {
    useExternalAgentActions.getState().setBusy(key, false)
  }
}

/**
 * Chat → "Continue in <CLI>": write the handoff file (and, for Claude Code /
 * Codex with `native`, their own session file), open a terminal running the
 * CLI on it, and route to that terminal.
 */
export async function continueSessionIn(
  session: AgentSession,
  kind: ExternalAgentKind,
  options: { native?: boolean } = {}
): Promise<TerminalSession | null> {
  const bindings = bindingsOrWarn()
  if (!bindings) return null
  const { client, openItem } = bindings
  const key = `handoff:${session.id}`
  const actions = useExternalAgentActions.getState()
  if (actions.busy[key]) return null
  actions.setBusy(key, true)
  const label = EXTERNAL_AGENT_LABELS[kind]
  try {
    const result = await client.handoffSession(session.id, {
      kind,
      launch: true,
      native: Boolean(options.native),
      projectId: session.projectId
    })
    const terminal = result.terminal
    if (!terminal) {
      toast.message(`Wrote the handoff file for ${label}.`, {
        description: result.path
      })
      return null
    }
    useTerminalsStore.getState().addOptimistic({ ...terminal, agent: kind })
    openItem(terminal.id)
    toast.success(
      result.native
        ? `Opened ${label} on this chat's history.`
        : `Opened ${label} with the handoff file.`
    )
    return terminal
  } catch (error) {
    toast.error(errorText(error, `Could not open ${label}.`))
    return null
  } finally {
    useExternalAgentActions.getState().setBusy(key, false)
  }
}

/** Dashboard / onboarding: import a picked external session as a chat. */
export async function importExternalSessionAsChat(
  summary: ExternalSessionSummary,
  options: { projectId?: string | null; open?: boolean } = {}
): Promise<AgentSession | null> {
  const bindings = bindingsOrWarn()
  if (!bindings) return null
  const { client, openItem, reloadSessions } = bindings
  try {
    const session = await client.importExternalSession({
      kind: summary.kind,
      sessionId: summary.id,
      projectId: options.projectId ?? null,
      workspacePath: summary.cwd
    })
    await reloadSessions()
    if (options.open !== false) openItem(session.id)
    return session
  } catch (error) {
    toast.error(errorText(error, `Could not import from ${summary.label}.`))
    return null
  }
}

/** Open a terminal running `kind` in a folder (menu "Open in …"). */
export async function launchExternalAgent(
  kind: ExternalAgentKind,
  options: {
    workspacePath?: string | null
    projectId?: string | null
    originChatId?: string | null
  } = {}
): Promise<TerminalSession | null> {
  const bindings = bindingsOrWarn()
  if (!bindings) return null
  const { client, openItem } = bindings
  const label = EXTERNAL_AGENT_LABELS[kind]
  try {
    const result = await client.launchExternalAgent({ kind, ...options })
    useTerminalsStore.getState().addOptimistic({ ...result.terminal, agent: kind })
    openItem(result.terminal.id)
    return result.terminal
  } catch (error) {
    toast.error(errorText(error, `Could not open ${label}.`))
    return null
  }
}
