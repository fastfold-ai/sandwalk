import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'

type ModalHandlersArgs = {
  connected: boolean
  busy: boolean
  savingTokens: boolean
  modalReady: boolean
  tokenDirty: boolean
  tokenDrafts: Record<string, string>
  preserveDraftRef: MutableRefObject<boolean>
  onProbeSandbox?: () => Promise<import('@sandwalk/agent-ui-core').SandboxProbeReport>
  onSaveModalIntegration?: (
    values: Record<string, string>
  ) => Promise<IntegrationSummary>
  onRemoveModalIntegration?: () => Promise<void>
  onRefreshIntegrations?: () => Promise<void>
  onLoadSandboxSettings?: () => Promise<
    import('@sandwalk/agent-ui-core').SandboxSettings | null
  >
  setBusy: Dispatch<SetStateAction<boolean>>
  setError: Dispatch<SetStateAction<string | null>>
  setErrorStack: Dispatch<SetStateAction<string | null>>
  setProbeOk: Dispatch<SetStateAction<boolean>>
  setProbeDetail: Dispatch<SetStateAction<string | null>>
  setTokenDrafts: Dispatch<SetStateAction<Record<string, string>>>
  setSavingTokens: Dispatch<SetStateAction<boolean>>
  setOverlay: Dispatch<
    SetStateAction<{
      phase: 'working' | 'done'
      message: string
      description?: string
    } | null>
  >
}

export function createAgentSandboxModalHandlers({
  connected,
  busy,
  savingTokens,
  modalReady,
  tokenDirty,
  tokenDrafts,
  preserveDraftRef,
  onProbeSandbox,
  onSaveModalIntegration,
  onRemoveModalIntegration,
  onRefreshIntegrations,
  onLoadSandboxSettings,
  setBusy,
  setError,
  setErrorStack,
  setProbeOk,
  setProbeDetail,
  setTokenDrafts,
  setSavingTokens,
  setOverlay
}: ModalHandlersArgs) {
  async function showDone(message: string, description?: string) {
    setOverlay({ phase: 'done', message, description })
    await new Promise(resolve => setTimeout(resolve, 900))
    setOverlay(null)
  }

  async function runProbe() {
    if (!onProbeSandbox || !connected || busy || !modalReady) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setProbeDetail(null)
    setOverlay({
      phase: 'working',
      message: 'Probing Modal…',
      description:
        'Creating a sandbox, syncing files, and running a health check.'
    })
    try {
      const report = await onProbeSandbox()
      setProbeOk(report.ok)
      const failed = report.steps.find(step => !step.ok)
      setProbeDetail(
        report.ok
          ? 'Modal sandbox probe passed.'
          : failed?.detail || 'Modal sandbox probe failed.'
      )
      if (!report.ok) {
        setOverlay(null)
        return
      }
      await showDone('Probe healthy', 'Modal sandbox is ready to use.')
    } catch (err) {
      setProbeOk(false)
      setOverlay(null)
      const message = err instanceof Error ? err.message : String(err)
      const missingProbe =
        /\/v1\/settings\/sandbox\/probe/i.test(message) &&
        /\b404\b|not found/i.test(message)
      setProbeDetail(
        missingProbe
          ? 'Probe endpoint missing on this agent server. Restart sandwalk / `sandwalk serve` after updating the CLI, then retry.'
          : message
      )
    } finally {
      setBusy(false)
    }
  }

  async function saveModalTokens() {
    if (!onSaveModalIntegration || !tokenDirty || savingTokens) return
    setSavingTokens(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving Modal tokens…'
    })
    preserveDraftRef.current = true
    try {
      const values = Object.fromEntries(
        Object.entries(tokenDrafts)
          .map(([key, value]) => [key, value.trim()])
          .filter(([, value]) => Boolean(value))
      )
      await onSaveModalIntegration(values)
      setTokenDrafts({})
      setProbeOk(false)
      setProbeDetail(null)
      await onRefreshIntegrations?.()
      await onLoadSandboxSettings?.()
      await showDone('Tokens saved', 'Run Test connection to verify Modal.')
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setSavingTokens(false)
      queueMicrotask(() => {
        preserveDraftRef.current = false
      })
    }
  }

  async function clearModalTokens() {
    if (!onRemoveModalIntegration || savingTokens) return
    setSavingTokens(true)
    setError(null)
    preserveDraftRef.current = true
    try {
      await onRemoveModalIntegration()
      setProbeOk(false)
      setProbeDetail(null)
      setTokenDrafts({})
      await onRefreshIntegrations?.()
      await onLoadSandboxSettings?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setSavingTokens(false)
      queueMicrotask(() => {
        preserveDraftRef.current = false
      })
    }
  }

  return { runProbe, saveModalTokens, clearModalTokens, showDone }
}
