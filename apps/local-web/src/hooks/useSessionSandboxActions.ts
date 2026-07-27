import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  SandboxSettings,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction
} from 'react'

import { type SandboxActionPhase } from '@/components/agents/Composer'
import { isDraftAgentSessionId } from '@/lib/draft-agent'

type SandboxActionsArgs = {
  client: LocalAgentClient
  sessionId: string | null
  sessionIdRef: MutableRefObject<string | null>
  session: AgentSession | null
  sessionSandboxStatus: SessionSandboxStatus | null
  sessionSandboxPhase: SandboxActionPhase
  sandboxActionSessionRef: MutableRefObject<string | null>
  setSessionSandboxStatus: Dispatch<SetStateAction<SessionSandboxStatus | null>>
  setSessionSandboxPhase: Dispatch<SetStateAction<SandboxActionPhase>>
  setSandboxSettings: Dispatch<SetStateAction<SandboxSettings | null>>
  setError: Dispatch<SetStateAction<string | null>>
  loadSessions: () => Promise<void>
  loadProjects: () => Promise<void>
  refreshSessionSandbox: (targetSessionId?: string | null) => Promise<SessionSandboxStatus | null>
  ensureAgentSession: (
    projectId?: string | null,
    options?: { navigate?: boolean }
  ) => Promise<string | null>
}

export function createSessionSandboxActions({
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
}: SandboxActionsArgs) {
  const selectSessionSandboxBackend = async (
    backend: 'builtin' | 'modal'
  ) => {
    const ensuredId = session?.id ?? (await ensureAgentSession())
    if (!ensuredId || isDraftAgentSessionId(ensuredId)) return
    if (
      backend === 'modal' &&
      sessionSandboxStatus?.modalConfigured !== true
    ) {
      return
    }
    const targetId = ensuredId
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
    if (sessionSandboxPhase !== 'idle') return
    const targetId = await ensureAgentSession()
    if (!targetId || isDraftAgentSessionId(targetId)) return
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
    if (!sessionId || isDraftAgentSessionId(sessionId)) return
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
    if (sessionSandboxPhase !== 'idle') return
    const targetId = await ensureAgentSession()
    if (!targetId || isDraftAgentSessionId(targetId)) return
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
              cpuImage: next.cpuImage,
              gpuImage: next.gpuImage,
              baseImage:
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
    selectSessionSandboxBackend,
    startSessionSandbox,
    stopSessionSandbox,
    restartSessionSandbox,
    updateSessionSandboxCompute
  }
}
