import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, TerminalSession } from '@sandwalk/agent-ui-core'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const toast = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  message: vi.fn()
}))
vi.mock('sonner', () => ({ toast }))

import {
  continueSessionIn,
  convertTerminalToAgent,
  convertTerminalToSession,
  importExternalSessionAsChat,
  launchExternalAgent,
  newestExternalSession,
  refreshInstalledAgents,
  useExternalAgentActions
} from './external-agent-actions'
import { useTerminalsStore } from './terminals-store'

const now = '2026-10-14T12:00:00.000Z'

function terminal(over: Partial<TerminalSession> = {}): TerminalSession {
  return {
    id: 'term_1',
    title: 'Claude Code',
    titleSource: 'user',
    projectId: 'proj',
    workspacePath: '/work',
    shell: null,
    originChatId: null,
    slotKey: null,
    status: 'idle',
    organizeLabel: null,
    lastActivityAt: null,
    createdAt: now,
    updatedAt: now,
    ...over
  }
}

function session(over: Partial<AgentSession> = {}): AgentSession {
  return {
    id: 'chat_1',
    title: 'Weather',
    titleSource: 'user',
    status: 'idle',
    organizeLabel: null,
    projectId: 'proj',
    specialistId: null,
    sandboxBackend: null,
    provider: null,
    model: null,
    openaiProfileId: null,
    workspacePath: '/work',
    source: null,
    sourceLabel: null,
    clientSurface: 'ui',
    lastMessageAt: null,
    createdAt: now,
    updatedAt: now,
    ...over
  } as AgentSession
}

function makeClient(over: Partial<Record<keyof LocalAgentClient, unknown>> = {}) {
  return {
    listExternalAgents: vi.fn(async () => ({
      agents: [
        { kind: 'claude', label: 'Claude Code', installed: true, path: '/bin/claude' },
        { kind: 'fx', label: 'fx', installed: false, path: null }
      ],
      sessions: [
        {
          kind: 'claude',
          label: 'Claude Code',
          id: 'ext-1',
          title: 'fix tests',
          cwd: '/work',
          updatedAt: now,
          turns: 3
        }
      ]
    })),
    importExternalSession: vi.fn(async () => session({ id: 'chat_imported', source: 'claude' })),
    launchExternalAgent: vi.fn(async () => ({
      kind: 'codex',
      command: '/bin/codex',
      terminal: terminal({ id: 'term_new', title: 'Codex' }),
      pty: { id: 'p', sessionId: 'term_new', title: 'Codex', cwd: '/work', cols: 80, rows: 24, pid: 1, status: 'running' }
    })),
    handoffSession: vi.fn(async (_id: string, input: { native?: boolean }) => ({
      kind: 'claude',
      path: '/work/.sandwalk/handoff-chat_1.md',
      prompt: 'Read it',
      workspacePath: '/work',
      messages: 2,
      native: Boolean(input.native),
      terminal: terminal({ id: 'term_handoff', title: 'Claude Code' })
    })),
    ...over
  } as unknown as LocalAgentClient
}

describe('external-agent-actions', () => {
  const openItem = vi.fn()
  const reloadSessions = vi.fn(async () => undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    useTerminalsStore.setState({ terminals: [] })
    useExternalAgentActions.setState({ bindings: null, busy: {}, installed: null })
  })

  it('warns when nothing is bound yet', async () => {
    expect(await convertTerminalToSession(terminal(), 'claude')).toBeNull()
    expect(toast.error).toHaveBeenCalledWith('Not connected to the Sandwalk server yet.')
  })

  it('refreshInstalledAgents records which CLIs exist', async () => {
    const client = makeClient()
    await refreshInstalledAgents(client)
    expect(useExternalAgentActions.getState().installed).toEqual({ claude: true, fx: false })
    expect(client.listExternalAgents).toHaveBeenCalledWith({ sessions: false })
  })

  it('newestExternalSession asks for one session of that kind in that folder', async () => {
    const client = makeClient()
    const newest = await newestExternalSession(client, 'claude', '/work')
    expect(newest?.id).toBe('ext-1')
    expect(client.listExternalAgents).toHaveBeenCalledWith({ kind: 'claude', cwd: '/work', limit: 1 })
  })

  it('convertTerminalToSession imports the newest session and opens the chat', async () => {
    const client = makeClient()
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    const result = await convertTerminalToSession(terminal(), 'claude')
    expect(result?.id).toBe('chat_imported')
    expect(client.importExternalSession).toHaveBeenCalledWith({
      kind: 'claude',
      sessionId: 'ext-1',
      projectId: 'proj',
      workspacePath: '/work'
    })
    expect(openItem).toHaveBeenCalledWith('chat_imported')
    expect(toast.success).toHaveBeenCalled()
    expect(useExternalAgentActions.getState().busy).toEqual({})
  })

  it('convertTerminalToSession explains when the CLI has not saved anything yet', async () => {
    const client = makeClient({
      listExternalAgents: vi.fn(async () => ({ agents: [], sessions: [] }))
    })
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    expect(await convertTerminalToSession(terminal(), 'codex')).toBeNull()
    expect(toast.message).toHaveBeenCalledWith(
      'No Codex session saved yet for this folder.',
      expect.anything()
    )
    expect(client.importExternalSession).not.toHaveBeenCalled()
  })

  it('convertTerminalToAgent imports the session, then hands it off to the other CLI', async () => {
    const client = makeClient()
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    const term = await convertTerminalToAgent(terminal(), 'claude', 'codex')
    expect(term?.id).toBe('term_handoff')
    expect(client.importExternalSession).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'claude', sessionId: 'ext-1' })
    )
    expect(client.handoffSession).toHaveBeenCalledWith(
      'chat_imported',
      expect.objectContaining({ kind: 'codex', launch: true, native: false })
    )
    // The bridge chat is not opened — the new CLI terminal is.
    expect(openItem).toHaveBeenCalledTimes(1)
    expect(openItem).toHaveBeenCalledWith('term_handoff')
    expect(toast.success).toHaveBeenCalledWith('Opened Codex on the Claude Code session.')
    expect(useExternalAgentActions.getState().busy).toEqual({})
  })

  it('convertTerminalToAgent stops when the CLI has nothing saved yet', async () => {
    const client = makeClient({
      listExternalAgents: vi.fn(async () => ({ agents: [], sessions: [] }))
    })
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    expect(await convertTerminalToAgent(terminal(), 'claude', 'codex')).toBeNull()
    expect(client.handoffSession).not.toHaveBeenCalled()
  })

  it('continueSessionIn opens the launched terminal and marks its agent', async () => {
    const client = makeClient()
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    const term = await continueSessionIn(session(), 'claude', { native: true })
    expect(term?.id).toBe('term_handoff')
    expect(client.handoffSession).toHaveBeenCalledWith('chat_1', {
      kind: 'claude',
      launch: true,
      native: true,
      projectId: 'proj'
    })
    expect(useTerminalsStore.getState().terminals[0]).toMatchObject({ id: 'term_handoff', agent: 'claude' })
    expect(openItem).toHaveBeenCalledWith('term_handoff')
    expect(toast.success).toHaveBeenCalledWith("Opened Claude Code on this chat's history.")
  })

  it('continueSessionIn surfaces server errors as toasts', async () => {
    const client = makeClient({
      handoffSession: vi.fn(async () => {
        throw new Error('Claude Code is not installed (no `claude` on PATH).')
      })
    })
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    expect(await continueSessionIn(session(), 'claude')).toBeNull()
    expect(toast.error).toHaveBeenCalledWith('Claude Code is not installed (no `claude` on PATH).')
  })

  it('importExternalSessionAsChat and launchExternalAgent route through the client', async () => {
    const client = makeClient()
    useExternalAgentActions.getState().bind({ client, openItem, reloadSessions })
    const imported = await importExternalSessionAsChat(
      { kind: 'claude', label: 'Claude Code', id: 'ext-1', title: 't', cwd: '/work', updatedAt: now, turns: 1 },
      { open: false }
    )
    expect(imported?.id).toBe('chat_imported')
    expect(openItem).not.toHaveBeenCalled()

    const launched = await launchExternalAgent('codex', { workspacePath: '/work' })
    expect(launched?.id).toBe('term_new')
    expect(client.launchExternalAgent).toHaveBeenCalledWith({ kind: 'codex', workspacePath: '/work' })
    expect(openItem).toHaveBeenCalledWith('term_new')
  })
})
