import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { emptySessionChatState } from '@/lib/sessions'

import { useAppBootstrapLoaders } from './useAppBootstrapLoaders'

function session(overrides: Partial<AgentSession> = {}): AgentSession {
  return {
    id: 'a',
    title: 'One',
    status: 'idle',
    organizeLabel: null,
    projectId: 'p1',
    specialistId: null,
    workspacePath: null,
    lastMessageAt: null,
    createdAt: '2026-07-25T00:00:00Z',
    updatedAt: '2026-07-25T00:00:00Z',
    ...overrides
  } as AgentSession
}

function fakeClient(
  baseUrl: string,
  overrides: Partial<LocalAgentClient> = {}
): LocalAgentClient {
  return {
    baseUrl,
    getSessionsRevision: async () => 'rev-1',
    listSessions: async () => [session({ status: 'running' })],
    listSessionsByIds: async () => [
      session({ id: 'foreign', title: 'Other', projectId: 'p2' })
    ],
    listMessages: async () => [{ content: ' hello ' }],
    listProjects: async () => [{ id: 'p1', name: 'Lab' }],
    listSkills: async () => [],
    listIntegrations: async () => [],
    listMcpServers: async () => [],
    listMcpCatalog: async () => [{ id: 'catalog' }],
    listSpecialists: async () => [{ id: 'spec' }],
    listModels: async () => [
      {
        id: 'gemma',
        label: 'Gemma',
        provider: 'local',
        source: 'profile',
        profileId: 'llama_local',
        enabled: true
      }
    ],
    listModelProfiles: async () => [{ id: 'llama_local', backend: 'llama' }],
    getStorage: async () => ({ ok: true }),
    getEnvironment: async () => ({ ok: true }),
    getServerStatus: async () => ({ ok: true }),
    ...overrides
  } as unknown as LocalAgentClient
}

describe('useAppBootstrapLoaders', () => {
  it('loads sessions, catalogs, and foreign chats', async () => {
    const chat: Record<string, ReturnType<typeof emptySessionChatState>> = {
      a: emptySessionChatState()
    }
    const { result } = renderHook(() =>
      useAppBootstrapLoaders({
        client: fakeClient('http://loaders-a'),
        setChatBySessionId: updater => {
          const next = typeof updater === 'function' ? updater(chat) : updater
          Object.assign(chat, next)
        }
      })
    )

    await act(async () => {
      await result.current.loadSessions()
    })
    expect(result.current.sessions.map(item => item.id)).toEqual(['a'])
    expect(result.current.sessionsInitialLoadDone).toBe(true)
    expect(chat.a.runActive).toBe(true)

    await act(async () => {
      await result.current.loadSessions()
    })
    expect(result.current.sessions).toHaveLength(1)

    await act(async () => {
      await result.current.loadSessions({ projectId: 'p1', force: true })
      await result.current.loadForeignSessions(['foreign', 'grp_side', ''])
      await result.current.loadSessionPreviews(['a', 'grp_side'])
      await result.current.loadProjects()
      await result.current.loadSkills()
      await result.current.loadIntegrations()
      await result.current.loadMcpServers()
      await result.current.loadMcpCatalog()
      await result.current.refreshMcp()
      await result.current.loadSpecialists()
      await result.current.loadModelOptions({ force: true })
      await result.current.loadStorage()
      await result.current.loadEnvironment()
      await result.current.loadServerStatus()
    })
    expect(result.current.sessions.some(item => item.id === 'foreign')).toBe(
      true
    )
    expect(result.current.sessionPreviews.a).toBe('hello')
    expect(result.current.projects).toHaveLength(1)
    expect(result.current.mcpCatalog).toHaveLength(1)
    expect(result.current.modelOptions[0]?.backend).toBe('llama')
  })

  it('keeps the last catalog when a loader fails', async () => {
    const { result } = renderHook(() =>
      useAppBootstrapLoaders({
        client: fakeClient('http://loaders-b', {
          getSessionsRevision: async () => {
            throw new Error('old server')
          },
          listModels: async () => {
            throw new Error('catalog down')
          },
          listMessages: async () => {
            throw new Error('no history')
          },
          listSessionsByIds: async () => {
            throw new Error('missing')
          }
        }),
        setChatBySessionId: () => {}
      })
    )
    await act(async () => {
      await result.current.loadSessions({ force: true })
      await result.current.loadModelOptions({ force: true })
      await result.current.loadSessionPreviews(['a'])
      await result.current.loadForeignSessions(['missing'])
    })
    expect(result.current.modelOptions).toEqual([])
    expect(result.current.sessionPreviews.a).toBe('No messages yet.')
  })
})
