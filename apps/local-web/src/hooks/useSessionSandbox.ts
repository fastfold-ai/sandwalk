import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  BackendHealth,
  SandboxSettings,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState
} from 'react'

import { type SandboxActionPhase } from '@/components/agents/Composer'
import { isDraftAgentSessionId } from '@/lib/draft-agent'

import { syncSandboxPhaseFromStatus } from './session-sandbox-status-sync'
import { useSessionSandboxStream } from './use-session-sandbox-stream'
import { createSessionSandboxActions } from './useSessionSandboxActions'

type UseSessionSandboxArgs = {
  client: LocalAgentClient
  health: BackendHealth | null
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  session: AgentSession | null
  loadSessions: () => Promise<void>
  loadProjects: () => Promise<void>
  setSandboxSettings: Dispatch<SetStateAction<SandboxSettings | null>>
  setError: Dispatch<SetStateAction<string | null>>
  ensureAgentSession: (
    projectId?: string | null,
    options?: { navigate?: boolean }
  ) => Promise<string | null>
}

export function useSessionSandbox({
  client,
  health,
  sessionId,
  sessionIdRef,
  session,
  loadSessions,
  loadProjects,
  setSandboxSettings,
  setError,
  ensureAgentSession
}: UseSessionSandboxArgs) {
  const [sessionSandboxStatus, setSessionSandboxStatus] =
    useState<SessionSandboxStatus | null>(null)
  const [sessionSandboxPhase, setSessionSandboxPhase] =
    useState<SandboxActionPhase>('idle')
  const sandboxActionSessionRef = useRef<string | null>(null)

  useSessionSandboxStream({
    client,
    health,
    sessionId,
    sandboxBackend: session?.sandboxBackend,
    sandboxActionSessionRef,
    setSessionSandboxStatus,
    setSessionSandboxPhase
  })

  const refreshSessionSandbox = useCallback(
    async (targetSessionId?: string | null) => {
      const id = targetSessionId ?? sessionId
      if (!id) {
        setSessionSandboxStatus(null)
        return null
      }
      // S2: terminals no tienen sandbox (viven en /v1/terminals/:id).
      // Pedirlo devuelve 404 y ensucia la consola.
      if (id.startsWith('term_')) {
        setSessionSandboxStatus(null)
        return null
      }
      if (isDraftAgentSessionId(id)) {
        try {
          const settings = await client.getSandboxSettings()
          setSandboxSettings(settings)
          const status: SessionSandboxStatus = {
            sessionId: id,
            backend: 'builtin',
            sessionBackend: null,
            globalBackend: settings.backend,
            status: 'ready',
            providerSandboxName: null,
            modalConfigured: settings.modalConfigured,
            computeType: settings.computeType,
            gpuClass: settings.gpuClass,
            cpuCores: settings.cpuCores,
            ramGb: settings.ramGb,
            cpuImage: settings.cpuImage,
            gpuImage: settings.gpuImage,
            baseImage:
              settings.computeType === 'gpu'
                ? settings.gpuImage
                : settings.cpuImage,
            detail: null
          }
          setSessionSandboxStatus(status)
          return status
        } catch {
          setSessionSandboxStatus(null)
          return null
        }
      }
      try {
        const status = await client.getSessionSandbox(id)
        if ((targetSessionId ?? sessionIdRef.current) === id) {
          setSessionSandboxStatus(status)
          syncSandboxPhaseFromStatus(
            status,
            id,
            sandboxActionSessionRef,
            setSessionSandboxPhase
          )
        }
        return status
      } catch {
        if ((targetSessionId ?? sessionIdRef.current) === id) {
          setSessionSandboxStatus(null)
        }
        return null
      }
    },
    [client, sessionId, sessionIdRef, setSandboxSettings]
  )

  useEffect(() => {
    if (!sessionId || !health || isDraftAgentSessionId(sessionId)) return
    const pending =
      sessionSandboxPhase !== 'idle' ||
      sessionSandboxStatus?.status === 'starting' ||
      sessionSandboxStatus?.status === 'stopping'
    if (!pending) return
    const timer = window.setInterval(() => {
      void refreshSessionSandbox(sessionId)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [
    health,
    refreshSessionSandbox,
    sessionId,
    sessionSandboxPhase,
    sessionSandboxStatus?.status
  ])

  const {
    selectSessionSandboxBackend,
    startSessionSandbox,
    stopSessionSandbox,
    restartSessionSandbox,
    updateSessionSandboxCompute
  } = createSessionSandboxActions({
    client,
    sessionId,
    sessionIdRef,
    session,
    sessionSandboxStatus,
    sessionSandboxPhase,
    sandboxActionSessionRef,
    setSessionSandboxStatus,
    setSessionSandboxPhase,
    setSandboxSettings,
    setError,
    loadSessions,
    loadProjects,
    refreshSessionSandbox,
    ensureAgentSession
  })

  return {
    sessionSandboxStatus,
    sessionSandboxPhase,
    refreshSessionSandbox,
    selectSessionSandboxBackend,
    startSessionSandbox,
    stopSessionSandbox,
    restartSessionSandbox,
    updateSessionSandboxCompute
  }
}
