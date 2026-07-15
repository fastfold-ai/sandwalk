import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { useEffect, useMemo, useRef, useState } from 'react'

import { defaultModalFields } from './sandbox-modal-section'
import {
  clampNumber,
  defaultImageDraft,
  DEFAULT_CPU_IMAGE,
  DEFAULT_GPU_IMAGE,
  DEFAULT_IDLE_TTL,
  DEFAULT_MODAL_APP,
  settingsToImageDraft,
  type ImageDraft
} from './sandbox-view-utils'

export function useAgentSandboxView({
  connected,
  sandboxSettings,
  modalIntegration,
  onLoadSandboxSettings,
  onUpdateSandboxSettings,
  onProbeSandbox,
  onSaveModalIntegration,
  onRemoveModalIntegration,
  onRefreshIntegrations
}: {
  connected: boolean
  sandboxSettings: SandboxSettings | null
  modalIntegration?: IntegrationSummary | null
  onLoadSandboxSettings?: () => Promise<SandboxSettings | null>
  onUpdateSandboxSettings: (
    changes: Partial<SandboxSettings>
  ) => Promise<SandboxSettings>
  onProbeSandbox?: () => Promise<SandboxProbeReport>
  onSaveModalIntegration?: (
    values: Record<string, string>
  ) => Promise<IntegrationSummary>
  onRemoveModalIntegration?: () => Promise<void>
  onRefreshIntegrations?: () => Promise<void>
}) {
  const [draft, setDraft] = useState<ImageDraft>(() =>
    settingsToImageDraft(sandboxSettings)
  )
  const [saved, setSaved] = useState<ImageDraft>(() =>
    settingsToImageDraft(sandboxSettings)
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorStack, setErrorStack] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const [probeOk, setProbeOk] = useState(false)
  const [probeDetail, setProbeDetail] = useState<string | null>(null)
  const [tokenDrafts, setTokenDrafts] = useState<Record<string, string>>({})
  const [savingTokens, setSavingTokens] = useState(false)
  const [overlay, setOverlay] = useState<{
    phase: 'working' | 'done'
    message: string
    description?: string
  } | null>(null)
  const savedRef = useRef(saved)
  savedRef.current = saved
  const preserveDraftRef = useRef(false)
  const onLoadSandboxSettingsRef = useRef(onLoadSandboxSettings)
  onLoadSandboxSettingsRef.current = onLoadSandboxSettings

  useEffect(() => {
    if (!sandboxSettings) return
    const next = settingsToImageDraft(sandboxSettings)
    setSaved(next)
    setDraft(prev => {
      if (preserveDraftRef.current) return prev
      const dirty =
        JSON.stringify(prev) !== JSON.stringify(savedRef.current)
      return dirty ? prev : next
    })
    setUnavailable(false)
  }, [sandboxSettings])

  useEffect(() => {
    if (sandboxSettings || !connected || !onLoadSandboxSettingsRef.current) {
      return
    }
    let cancelled = false
    void onLoadSandboxSettingsRef.current()
      .then(next => {
        if (cancelled) return
        if (!next) {
          setUnavailable(true)
          setError(
            'FastFold Agent API 404: Not Found [GET /v1/settings/sandbox]'
          )
          setErrorStack(null)
        }
      })
      .catch(err => {
        if (cancelled) return
        setUnavailable(true)
        setError(err instanceof Error ? err.message : String(err))
        setErrorStack(err instanceof Error ? err.stack || null : null)
      })
    return () => {
      cancelled = true
    }
  }, [connected, sandboxSettings])

  const dirty = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(saved),
    [draft, saved]
  )
  const atDefaults = useMemo(
    () => JSON.stringify(draft) === JSON.stringify(defaultImageDraft()),
    [draft]
  )

  const modalReady = Boolean(
    modalIntegration?.configured ?? sandboxSettings?.modalConfigured
  )
  const modalFields = modalIntegration?.fields ?? defaultModalFields()
  const tokenDirty = Object.values(tokenDrafts).some(value => value.trim())
  const formDisabled = !connected || busy || unavailable

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

  async function apply(nextDraft: ImageDraft = draft) {
    if (!connected || busy || unavailable) return
    setBusy(true)
    setError(null)
    setErrorStack(null)
    setOverlay({
      phase: 'working',
      message: 'Saving sandbox…',
      description: 'Used when a chat enables Modal Sandbox.'
    })
    try {
      const next = await onUpdateSandboxSettings({
        modalApp: nextDraft.modalApp.trim() || DEFAULT_MODAL_APP,
        idleTtlSeconds: Math.round(
          clampNumber(
            nextDraft.idleTtlSeconds,
            60,
            86400,
            Number(DEFAULT_IDLE_TTL)
          )
        ),
        cpuImage: nextDraft.cpuImage.trim() || DEFAULT_CPU_IMAGE,
        gpuImage: nextDraft.gpuImage.trim() || DEFAULT_GPU_IMAGE,
        pipPackages: nextDraft.pipPackages.trim()
      })
      const normalized = settingsToImageDraft(next)
      setDraft(normalized)
      setSaved(normalized)
      setUnavailable(false)
      await showDone('Sandbox saved')
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
      setErrorStack(err instanceof Error ? err.stack || null : null)
    } finally {
      setBusy(false)
    }
  }

  function restoreDefaults() {
    setDraft(defaultImageDraft())
  }

  function retryLoad() {
    if (!onLoadSandboxSettings) return
    setError(null)
    setErrorStack(null)
    setUnavailable(false)
    void onLoadSandboxSettings()
      .then(next => {
        if (!next) {
          setUnavailable(true)
          setError(
            'FastFold Agent API 404: Not Found [GET /v1/settings/sandbox]'
          )
        }
      })
      .catch(err => {
        setUnavailable(true)
        setError(err instanceof Error ? err.message : String(err))
        setErrorStack(err instanceof Error ? err.stack || null : null)
      })
  }

  return {
    draft,
    setDraft,
    busy,
    error,
    errorStack,
    unavailable,
    probeOk,
    probeDetail,
    tokenDrafts,
    savingTokens,
    overlay,
    dirty,
    atDefaults,
    modalReady,
    modalFields,
    tokenDirty,
    formDisabled,
    runProbe,
    saveModalTokens,
    clearModalTokens,
    apply,
    restoreDefaults,
    retryLoad,
    setTokenDrafts,
    setProbeOk,
    setProbeDetail,
    onLoadSandboxSettings,
    onProbeSandbox,
    onSaveModalIntegration
  }
}
