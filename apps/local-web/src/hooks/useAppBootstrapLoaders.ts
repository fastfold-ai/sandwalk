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
import { sameArrayBy } from '@/lib/stable-equal'

/** Short client TTL so remounts / StrictMode don't re-hit the API. */
const LIST_TTL_MS = 20_000
const MODEL_TTL_MS = 45_000

type UseAppBootstrapLoadersArgs = {
  client: LocalAgentClient
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
}

/**
 * Promote runActive from the session list (other surfaces starting a run).
 * Never demote from a list snapshot — that race (POST in flight, poll still
 * idle) lets the composer send again and 409s. SSE / Stop own the idle flip.
 */
export function mergeRunActiveFromSessions(
  current: Record<string, SessionChatState>,
  sessions: AgentSession[]
) {
  let changed = false
  const next = { ...current }
  for (const item of sessions) {
    const prev = next[item.id]
    if (!prev) continue
    const shouldRun =
      item.status === 'running' || item.status === 'awaiting_approval'
    if (prev.runActive === shouldRun) continue
    if (prev.runActive && !shouldRun) continue
    next[item.id] = { ...prev, runActive: shouldRun }
    changed = true
  }
  return changed ? next : current
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
  // FAS-107 Fase 4: flag para distinguir "aún cargando" vs "cargó vacío".
  // Sin este flag, los cleanups de openTabIds usaban `sessions.length === 0`
  // como guard, que en un proyecto legítimamente vacío bloqueaba el barrido
  // y dejaba chips huérfanos vivos.
  const [sessionsInitialLoadDone, setSessionsInitialLoadDone] = useState(false)
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
  /** When set, listSessions is project-scoped (includes bench cells). */
  const sessionsListScopeRef = useRef<string | null>(null)
  const sessionPreviewsRef = useRef<Record<string, string>>({})
  const previewInFlightRef = useRef(new Set<string>())
  const specialistsRef = useRef(specialists)
  sessionPreviewsRef.current = sessionPreviews
  specialistsRef.current = specialists
  // Cross-project split groups (`grp_*` in localStorage) can reference chats
  // that live outside the current project scope. `loadSessions` only fetches
  // the scoped list, so those "foreign" chats are absent from `sessions`,
  // which breaks split panel headers (Untitled + missing actions) and hides
  // them in the sidebar. `foreignInFlightRef` dedupes concurrent fetches for
  // the same ids; `sessionsRef` mirrors `sessions` so the merger can dedupe
  // without adding `sessions` as a callback dep (which would rebuild the
  // resolver on every render).
  const foreignInFlightRef = useRef(new Set<string>())
  // Ids that `loadForeignSessions` pulled in for a split group. A list
  // refresh keeps these even when the fresh payload omits them: the
  // global list excludes bench chats and the scoped list excludes other
  // projects, so without this the group vanished for a frame on every
  // click and came back once the foreign fetch re-ran.
  const foreignHydratedRef = useRef(new Set<string>())
  const sessionsRef = useRef<AgentSession[]>([])
  sessionsRef.current = sessions

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
      // Cheap watermark first for the global list (bench cells omitted).
      // Project scope includes bench cells and skips this watermark.
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
      //
      // Preserve foreign chats: cross-project split groups can reference
      // chats outside the current project scope. `loadForeignSessions`
      // hydrates them into `sessions`, but a subsequent scoped `loadSessions`
      // (TTL refresh, forced reload) used to REPLACE the whole array,
      // dropping those foreigns and causing a visible flicker while the
      // useEffect re-detected them and re-fetched. Now we keep any chat
      // whose `projectId` doesn't match the active scope — those are the
      // foreign hydrations we resolved separately. Chats deleted from the
      // active scope still disappear (they had matching projectId).
      setSessions(current => {
        const scopedIds = new Set(nextSessions.map(s => s.id))
        const hydrated = foreignHydratedRef.current
        // A hydrated chat that is no longer in the cache was deleted;
        // forget it so it cannot be preserved back in.
        const cached = new Set(current.map(s => s.id))
        for (const id of Array.from(hydrated)) {
          if (!cached.has(id)) hydrated.delete(id)
        }
        const preservedForeign = current.filter(s => {
          if (scopedIds.has(s.id)) return false
          if (hydrated.has(s.id)) return true
          // Scoped list: also keep chats from other projects that were
          // merged in earlier (cross-project splits), minus bench cells.
          return Boolean(projectId) && s.projectId !== projectId && s.source !== 'bench'
        })
        const merged =
          preservedForeign.length > 0
            ? [...nextSessions, ...preservedForeign]
            : nextSessions
        return sessionsUnchanged(current, merged) ? current : merged
      })
      setChatBySessionId(current =>
        mergeRunActiveFromSessions(current, nextSessions)
      )
      // FAS-107 Fase 4: primera carga completa. A partir de ahora los
      // cleanups pueden distinguir "sessions vacío porque cargó vacío"
      // de "sessions vacío porque aún no cargó".
      setSessionsInitialLoadDone(true)
      // Previews load lazily from Home via loadSessionPreviews.
    },
    [client, setChatBySessionId]
  )

  loadSessionsRef.current = loadSessions

  /**
   * Hydrate metadata for chatIds that appear in split groups but live
   * outside the current project scope. Idempotent: dedupes against the
   * current `sessions` cache and any in-flight lookups. Silently ignores
   * ids the backend can't resolve (chat was deleted while still in a group).
   * Called on bootstrap, on scope changes, on addToGroup/promotePending,
   * and after Move-to-project so the panel header, sidebar entry, and
   * chat body stay coherent regardless of which project the user is in.
   */
  const loadForeignSessions = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0) return
      const knownIds = new Set(sessionsRef.current.map(s => s.id))
      const missing = ids.filter(id => {
        if (!id) return false
        if (isSessionGroupId(id)) return false
        if (knownIds.has(id)) return false
        if (foreignInFlightRef.current.has(id)) return false
        return true
      })
      if (missing.length === 0) return
      for (const id of missing) foreignInFlightRef.current.add(id)
      try {
        const fetched = await client.listSessionsByIds(missing)
        if (fetched.length === 0) return
        for (const item of fetched) foreignHydratedRef.current.add(item.id)
        setSessions(current => {
          const byId = new Map(current.map(s => [s.id, s]))
          let changed = false
          for (const item of fetched) {
            const prev = byId.get(item.id)
            if (
              !prev ||
              prev.title !== item.title ||
              prev.projectId !== item.projectId ||
              prev.updatedAt !== item.updatedAt ||
              prev.lastMessageAt !== item.lastMessageAt ||
              prev.status !== item.status ||
              prev.organizeLabel !== item.organizeLabel
            ) {
              byId.set(item.id, item)
              changed = true
            }
          }
          if (!changed) return current
          // Preserve original ordering when possible; append new entries at
          // the end so we don't shuffle the sidebar every merge.
          const merged: AgentSession[] = []
          const seen = new Set<string>()
          for (const s of current) {
            const next = byId.get(s.id)
            if (next) {
              merged.push(next)
              seen.add(s.id)
            }
          }
          for (const item of fetched) {
            if (!seen.has(item.id)) merged.push(item)
          }
          return merged
        })
      } catch {
        // Backend older than the bulk endpoint or transient network — the
        // caller may retry on the next event; nothing else needs to happen.
      } finally {
        for (const id of missing) foreignInFlightRef.current.delete(id)
      }
    },
    [client]
  )

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
    // Same rows → keep the previous reference so memoized consumers
    // (transcript rows, composer) do not re-render after every run.
    setSkills(prev =>
      sameArrayBy(prev, unique, skill => JSON.stringify(skill)) ? prev : unique
    )
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

  const loadModelOptions = useCallback(async (options?: { force?: boolean }) => {
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
        { ttlMs: MODEL_TTL_MS, force: options?.force }
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
    sessionsInitialLoadDone,
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
    loadForeignSessions,
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
