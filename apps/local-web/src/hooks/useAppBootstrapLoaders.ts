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
import { isSessionGroupId } from '@sandwalk/agent-ui-core'
import type { Dispatch, SetStateAction } from 'react'
import { useCallback, useRef, useState } from 'react'

import { applyChatDateBoosts } from '@/lib/chat-date-boost'
import {
  type ComposerModelOption,
  toComposerModelOptions
} from '@/lib/composer-models'
import { dedupeAsync, invalidateDedupe } from '@/lib/dedupe-async'
import type { SessionChatState } from '@/lib/sessions'

/** Short client TTL so remounts / StrictMode don't re-hit the API. */
const LIST_TTL_MS = 20_000
const MODEL_TTL_MS = 45_000

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
    ((options?: {
      force?: boolean
      projectId?: string | null
    }) => Promise<void>) | null
  >(null)
  const loadSkillsRef = useRef<(() => Promise<void>) | null>(null)
  const sessionsRevisionRef = useRef<string | null>(null)
  /** When set, listSessions is project-scoped (includes bench). */
  const sessionsListScopeRef = useRef<string | null>(null)
  const sessionPreviewsRef = useRef<Record<string, string>>({})
  const previewInFlightRef = useRef(new Set<string>())
  const specialistsRef = useRef(specialists)
  sessionPreviewsRef.current = sessionPreviews
  specialistsRef.current = specialists

  const loadSessions = useCallback(
    async (options?: { force?: boolean; projectId?: string | null }) => {
      if (options && 'projectId' in options) {
        const nextScope = options.projectId ?? null
        if (sessionsListScopeRef.current !== nextScope) {
          sessionsListScopeRef.current = nextScope
          // Scope change must not reuse the global revision watermark.
          sessionsRevisionRef.current = null
        }
      }
      const projectId = sessionsListScopeRef.current
      const key = projectId
        ? `sessions:${client.baseUrl}:project:${projectId}`
        : `sessions:${client.baseUrl}`
      // Cheap watermark first for the global (non-bench) list. Project scope
      // includes bench sessions that do not bump the global revision.
      if (!options?.force && !projectId) {
        try {
          const revision = await dedupeAsync(`${key}:rev`, () =>
            client.getSessionsRevision()
          )
          if (revision === sessionsRevisionRef.current) return
        } catch {
          // Older servers without /sessions/revision fall through to full list.
        }
      }
      const rawSessions = await dedupeAsync(key, () =>
        client.listSessions(projectId ? { projectId } : undefined)
      )
      // Apply chat date boosts: chats agrupados en un split se muestran con
      // la fecha del split (Today) hasta que reciban actividad real que
      // supere ese boost — ver `lib/chat-date-boost.ts`.
      const nextSessions = applyChatDateBoosts(rawSessions)
      if (!projectId) {
        try {
          sessionsRevisionRef.current = await client.getSessionsRevision()
        } catch {
          sessionsRevisionRef.current = null
        }
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
          const shouldRun =
            item.status === 'running' || item.status === 'awaiting_approval'
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
        // Group ids are frontend-only tab wrappers; they have no
        // /sessions/grp_*/messages route on the backend.
        if (isSessionGroupId(id)) return false
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
    const items = await dedupeAsync(
      `projects:${client.baseUrl}`,
      () => client.listProjects(),
      { ttlMs: LIST_TTL_MS }
    )
    setProjects(items)
  }, [client])

  const loadSkills = useCallback(async () => {
    // No client TTL — installs/toggles must see fresh rows; backend list is TTL'd.
    invalidateDedupe(`skills:${client.baseUrl}`)
    const items = await dedupeAsync(`skills:${client.baseUrl}`, () =>
      client.listSkills()
    )
    const seen = new Set<string>()
    const unique = items.filter(skill => {
      const skillKey = skill.name.trim().toLowerCase()
      if (!skillKey || seen.has(skillKey)) return false
      seen.add(skillKey)
      return true
    })
    setSkills(unique)
  }, [client])

  loadSkillsRef.current = loadSkills

  const loadIntegrations = useCallback(async () => {
    setIntegrations(
      await dedupeAsync(
        `integrations:${client.baseUrl}`,
        () => client.listIntegrations(),
        { ttlMs: LIST_TTL_MS }
      )
    )
  }, [client])

  const loadMcpServers = useCallback(async () => {
    invalidateDedupe(`mcp-servers:${client.baseUrl}`)
    setMcpServers(
      await dedupeAsync(`mcp-servers:${client.baseUrl}`, () =>
        client.listMcpServers()
      )
    )
  }, [client])

  const loadMcpCatalog = useCallback(async () => {
    setMcpCatalogLoading(true)
    try {
      invalidateDedupe(`mcp-catalog:${client.baseUrl}`)
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
        await dedupeAsync(
          `specialists:${client.baseUrl}`,
          () => client.listSpecialists(),
          { ttlMs: LIST_TTL_MS }
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
          ]),
        { ttlMs: MODEL_TTL_MS }
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
