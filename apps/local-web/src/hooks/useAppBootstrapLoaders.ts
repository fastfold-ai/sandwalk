import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  AgentSkill,
  IntegrationSummary,
  McpCatalogEntry,
  McpServer,
  RuntimeSettings,
  SandboxSettings,
  Specialist
} from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useCallback, useRef, useState } from 'react'

import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'
import { dedupeAsync } from '@/lib/dedupe-async'
import type { SessionChatState } from '@/lib/sessions'

type UseAppBootstrapLoadersArgs = {
  client: LocalAgentClient
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
}

/** Fields the sidebar renders — enough to tell a real change from a re-fetch. */
export function sessionsUnchanged(a: AgentSession[], b: AgentSession[]) {
  if (a.length !== b.length) return false
  return a.every((item, index) => {
    const other = b[index]
    return (
      item.id === other.id &&
      item.title === other.title &&
      item.status === other.status &&
      item.updatedAt === other.updatedAt &&
      item.lastMessageAt === other.lastMessageAt &&
      item.organizeLabel === other.organizeLabel &&
      item.projectId === other.projectId
    )
  })
}

export function useAppBootstrapLoaders({
  client,
  setChatBySessionId
}: UseAppBootstrapLoadersArgs) {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [projects, setProjects] = useState<AgentProject[]>([])
  const [sessionPreviews, setSessionPreviews] = useState<
    Record<string, string>
  >({})
  const [skills, setSkills] = useState<AgentSkill[]>([])
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [mcpServers, setMcpServers] = useState<McpServer[]>([])
  const [mcpCatalog, setMcpCatalog] = useState<McpCatalogEntry[]>([])
  const [mcpCatalogLoading, setMcpCatalogLoading] = useState(false)
  const [specialists, setSpecialists] = useState<Specialist[]>([])
  const [specialistsLoading, setSpecialistsLoading] = useState(false)
  const [runtimeSettings, setRuntimeSettings] =
    useState<RuntimeSettings | null>(null)
  const [sandboxSettings, setSandboxSettings] =
    useState<SandboxSettings | null>(null)
  const [modelOptions, setModelOptions] = useState<ComposerModelOption[]>([])
  const loadSessionsRef = useRef<
    ((options?: { force?: boolean }) => Promise<void>) | null
  >(null)
  const loadSkillsRef = useRef<(() => Promise<void>) | null>(null)
  const sessionsRevisionRef = useRef<string | null>(null)
  const sessionPreviewsRef = useRef<Record<string, string>>({})
  const previewInFlightRef = useRef(new Set<string>())
  const specialistsRef = useRef(specialists)
  sessionPreviewsRef.current = sessionPreviews
  specialistsRef.current = specialists

  const loadSessions = useCallback(
    async (options?: { force?: boolean }) => {
      const key = `sessions:${client.baseUrl}`
      // Cheap watermark first: idle UIs only hit a tiny aggregate query until
      // CLI / Slack / another client actually changes the session list.
      if (!options?.force) {
        try {
          const revision = await dedupeAsync(`${key}:rev`, () =>
            client.getSessionsRevision()
          )
          if (revision === sessionsRevisionRef.current) return
        } catch {
          // Older servers without /sessions/revision fall through to full list.
        }
      }
      const nextSessions = await dedupeAsync(key, () => client.listSessions())
      try {
        sessionsRevisionRef.current = await client.getSessionsRevision()
      } catch {
        sessionsRevisionRef.current = null
      }
      // Keep the previous array when nothing moved, so a forced refresh cannot
      // re-render the sidebar on a timer when the payload is identical.
      setSessions(current =>
        sessionsUnchanged(current, nextSessions) ? current : nextSessions
      )
      setChatBySessionId(current => {
        let changed = false
        const next = { ...current }
        for (const item of nextSessions) {
          const prev = next[item.id]
          if (!prev) continue
          const shouldRun = item.status === 'running'
          if (prev.runActive === shouldRun) continue
          next[item.id] = { ...prev, runActive: shouldRun }
          changed = true
        }
        return changed ? next : current
      })
      // Previews load lazily from Home via loadSessionPreviews.
    },
    [client, setChatBySessionId]
  )

  loadSessionsRef.current = loadSessions

  const loadSessionPreviews = useCallback(
    async (sessionIds: string[], signal?: AbortSignal) => {
      const missing = sessionIds.filter(id => {
        if (sessionPreviewsRef.current[id] !== undefined) return false
        if (previewInFlightRef.current.has(id)) return false
        return true
      })
      if (missing.length === 0 || signal?.aborted) return

      for (const id of missing) previewInFlightRef.current.add(id)

      const concurrency = Math.min(3, missing.length)
      let cursor = 0
      const entries: Array<readonly [string, string]> = []

      try {
        const workers = Array.from({ length: concurrency }, async () => {
          while (cursor < missing.length) {
            if (signal?.aborted) return
            const index = cursor
            cursor += 1
            const id = missing[index]
            try {
              // Dedupe concurrent StrictMode remounts for the same session.
              // Avoid binding AbortSignal into the shared promise — remount aborts
              // would cancel the coalesced fetch for every waiter.
              const history = await dedupeAsync(
                `preview:${client.baseUrl}:${id}`,
                () => client.listMessages(id)
              )
              if (signal?.aborted) return
              entries.push([
                id,
                history.at(-1)?.content?.trim() || 'No messages yet.'
              ])
            } catch (cause: unknown) {
              if (signal?.aborted) return
              if (cause instanceof Error && cause.name === 'AbortError') return
              entries.push([id, 'No messages yet.'])
            }
          }
        })

        await Promise.all(workers)
      } finally {
        for (const id of missing) previewInFlightRef.current.delete(id)
      }

      if (signal?.aborted || entries.length === 0) return
      setSessionPreviews(current => {
        const next = { ...current }
        for (const [id, preview] of entries) {
          if (next[id] === undefined) next[id] = preview
        }
        return next
      })
    },
    [client]
  )

  const loadProjects = useCallback(async () => {
    const items = await dedupeAsync(`projects:${client.baseUrl}`, () =>
      client.listProjects()
    )
    setProjects(items)
  }, [client])

  const loadSkills = useCallback(async () => {
    const items = await dedupeAsync(`skills:${client.baseUrl}`, () =>
      client.listSkills()
    )
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const key = skill.name.trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    setSkills(unique)
  }, [client])

  loadSkillsRef.current = loadSkills

  const loadIntegrations = useCallback(async () => {
    setIntegrations(
      await dedupeAsync(`integrations:${client.baseUrl}`, () =>
        client.listIntegrations()
      )
    )
  }, [client])

  const loadMcpServers = useCallback(async () => {
    setMcpServers(
      await dedupeAsync(`mcp-servers:${client.baseUrl}`, () =>
        client.listMcpServers()
      )
    )
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      setMcpCatalog(
        await dedupeAsync(`mcp-catalog:${client.baseUrl}`, () =>
          client.listMcpCatalog()
        )
      )
    } finally {
      setMcpCatalogLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    await Promise.all([loadMcpServers(), loadMcpCatalog()])
  }, [loadMcpCatalog, loadMcpServers])

  const loadSpecialists = useCallback(async () => {
    // Only skeleton when we have nothing to show — avoids list flicker on refresh/toggle.
    if (specialistsRef.current.length === 0) setSpecialistsLoading(true)
    try {
      setSpecialists(
        await dedupeAsync(`specialists:${client.baseUrl}`, () =>
          client.listSpecialists()
        )
      )
    } catch {
      setSpecialists([])
    } finally {
      setSpecialistsLoading(false)
    }
  }, [client])

  const loadModelOptions = useCallback(async () => {
    try {
      const [models, profiles] = await dedupeAsync(
        `models:${client.baseUrl}`,
        () =>
          Promise.all([
            client.listModels({
              enabledOnly: true,
              discover: true
            }),
            client.listModelProfiles().catch(() => [])
          ])
      )
      const backendsByProfileId = Object.fromEntries(
        (profiles || []).map(profile => [profile.id, profile.backend])
      )
      setModelOptions(
        toComposerModelOptions(
          models.map(model => ({
            ...model,
            backend:
              model.backend ??
              (model.profileId
                ? backendsByProfileId[model.profileId] || null
                : null)
          }))
        )
      )
    } catch {
      // Keep the last known selector list if the catalog request fails.
    }
  }, [client])

  const loadStorage = useCallback(
    (signal?: AbortSignal) => client.getStorage(signal),
    [client]
  )
  const loadEnvironment = useCallback(
    (signal?: AbortSignal) => client.getEnvironment(signal),
    [client]
  )
  const loadServerStatus = useCallback(
    (signal?: AbortSignal) => client.getServerStatus(signal),
    [client]
  )

  return {
    sessions,
    setSessions,
    projects,
    sessionPreviews,
    loadSessionPreviews,
    skills,
    integrations,
    mcpServers,
    mcpCatalog,
    mcpCatalogLoading,
    specialists,
    specialistsLoading,
    runtimeSettings,
    setRuntimeSettings,
    sandboxSettings,
    setSandboxSettings,
    modelOptions,
    loadSessionsRef,
    loadSkillsRef,
    loadSessions,
    loadProjects,
    loadSkills,
    loadIntegrations,
    loadMcpServers,
    loadMcpCatalog,
    refreshMcp,
    loadSpecialists,
    loadModelOptions,
    loadStorage,
    loadEnvironment,
    loadServerStatus
  }
}
