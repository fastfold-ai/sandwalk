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
import type { SessionChatState } from '@/lib/sessions'

type UseAppBootstrapLoadersArgs = {
  client: LocalAgentClient
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
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
  const loadSessionsRef = useRef<(() => Promise<void>) | null>(null)
  const sessionPreviewsRef = useRef<Record<string, string>>({})
  const previewInFlightRef = useRef(new Set<string>())
  sessionPreviewsRef.current = sessionPreviews

  const loadSessions = useCallback(async () => {
    const nextSessions = await client.listSessions()
    setSessions(nextSessions)
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
    // Intentionally skip message-preview fetches here — bootstrap used to fan
    // out listMessages for 12 sessions on every connect (including /). Home
    // loads previews lazily via loadSessionPreviews for visible cards only.
  }, [client, setChatBySessionId])

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
              const history = await client.listMessages(id, signal)
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
    setProjects(await client.listProjects())
  }, [client])

  const loadSkills = useCallback(async () => {
    const items = await client.listSkills()
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const key = skill.name.trim().toLowerCase()
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    setSkills(unique)
  }, [client])

  const loadIntegrations = useCallback(async () => {
    setIntegrations(await client.listIntegrations())
  }, [client])

  const loadMcpServers = useCallback(async () => {
    setMcpServers(await client.listMcpServers())
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      setMcpCatalog(await client.listMcpCatalog())
    } finally {
      setMcpCatalogLoading(false)
    }
  }, [client])

  const refreshMcp = useCallback(async () => {
    await Promise.all([loadMcpServers(), loadMcpCatalog()])
  }, [loadMcpCatalog, loadMcpServers])

  const loadSpecialists = useCallback(async () => {
    setSpecialistsLoading(true)
    try {
      setSpecialists(await client.listSpecialists())
    } catch {
      setSpecialists([])
    } finally {
      setSpecialistsLoading(false)
    }
  }, [client])

  const loadModelOptions = useCallback(async () => {
    try {
      const [models, profiles] = await Promise.all([
        client.listModels({
          enabledOnly: true,
          discover: true
        }),
        client.listModelProfiles().catch(() => [])
      ])
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
