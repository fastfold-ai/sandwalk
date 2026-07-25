import type {
  IntegrationSummary,
  SandboxProbeReport,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import { useEffect, useMemo, useRef, useState } from 'react'

import { defaultModalFields } from './sandbox-modal-section'
import {
  clampNumber,
  DEFAULT_CPU_IMAGE,
  DEFAULT_GPU_IMAGE,
  DEFAULT_IDLE_TTL,
  DEFAULT_MODAL_APP,
  defaultImageDraft,
  type ImageDraft,
  settingsToImageDraft} from './sandbox-view-utils'
import { createAgentSandboxModalHandlers } from './use-agent-sandbox-modal-handlers'

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

  const { runProbe, saveModalTokens, clearModalTokens, showDone } =
    createAgentSandboxModalHandlers({
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
    })

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
