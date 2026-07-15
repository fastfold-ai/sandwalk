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

import { syncSandboxPhaseFromStatus } from './session-sandbox-status-sync'
import { useSessionSandboxStream } from './use-session-sandbox-stream'

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
  setError
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
    [client, sessionId, sessionIdRef]
  )

  useEffect(() => {
    if (!sessionId || !health) return
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

  const selectSessionSandboxBackend = async (
    backend: 'builtin' | 'modal'
  ) => {
    if (!session) return
    if (
      backend === 'modal' &&
      sessionSandboxStatus?.modalConfigured !== true
    ) {
      return
    }
    const targetId = session.id
    try {
      if (backend === 'builtin' && sessionSandboxStatus?.status === 'running') {
        sandboxActionSessionRef.current = targetId
        setSessionSandboxPhase('stopping')
        try {
          await client.stopSessionSandbox(targetId)
        } catch {
          // Best-effort stop when leaving Modal for this chat.
        } finally {
          if (sandboxActionSessionRef.current === targetId) {
            sandboxActionSessionRef.current = null
          }
          if (sessionIdRef.current === targetId) {
            setSessionSandboxPhase('idle')
          }
        }
      }
      await client.updateSession(targetId, { sandboxBackend: backend })
      await Promise.all([loadSessions(), loadProjects()])
      const status = await refreshSessionSandbox(targetId)
      if (
        backend === 'modal' &&
        status?.modalConfigured !== false &&
        status?.status !== 'running'
      ) {
        sandboxActionSessionRef.current = targetId
        setSessionSandboxPhase('starting')
        void client
          .startSessionSandbox(targetId)
          .then(next => {
            if (sessionIdRef.current === targetId) {
              setSessionSandboxStatus(next)
            }
          })
          .catch(cause => {
            setError(
              cause instanceof Error
                ? cause.message
                : 'Unable to start sandbox'
            )
            void refreshSessionSandbox(targetId)
          })
          .finally(() => {
            if (sandboxActionSessionRef.current === targetId) {
              sandboxActionSessionRef.current = null
            }
            if (sessionIdRef.current === targetId) {
              setSessionSandboxPhase('idle')
            }
          })
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to update sandbox backend'
      )
      await refreshSessionSandbox(targetId)
      setSessionSandboxPhase('idle')
      sandboxActionSessionRef.current = null
    }
  }

  const startSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('starting')
    try {
      const status = await client.startSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to start sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const stopSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('stopping')
    try {
      const status = await client.stopSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to stop sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const restartSessionSandbox = async () => {
    if (!sessionId) return
    const targetId = sessionId
    if (sessionSandboxPhase !== 'idle') return
    sandboxActionSessionRef.current = targetId
    setSessionSandboxPhase('restarting')
    try {
      const status = await client.restartSessionSandbox(targetId)
      if (sessionIdRef.current === targetId) {
        setSessionSandboxStatus(status)
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to restart sandbox'
      )
      await refreshSessionSandbox(targetId)
    } finally {
      if (sandboxActionSessionRef.current === targetId) {
        sandboxActionSessionRef.current = null
      }
      if (sessionIdRef.current === targetId) {
        setSessionSandboxPhase('idle')
      }
    }
  }

  const updateSessionSandboxCompute = async (changes: {
    computeType: 'cpu' | 'gpu'
    gpuClass: string
    cpuCores: number
    ramGb: number
  }) => {
    try {
      const next = await client.updateSandboxSettings(changes)
      setSandboxSettings(next)
      setSessionSandboxStatus(current =>
        current
          ? {
              ...current,
              computeType: next.computeType,
              gpuClass: next.gpuClass,
              cpuCores: next.cpuCores,
              ramGb: next.ramGb,
              cpuImage:
                next.computeType === 'gpu' ? next.gpuImage : next.cpuImage
            }
          : current
      )
      if (sessionId) await refreshSessionSandbox(sessionId)
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to update sandbox compute'
      )
    }
  }

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
