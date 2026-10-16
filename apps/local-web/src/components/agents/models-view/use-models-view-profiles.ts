import type {
  DiscoverModelEndpointInput,
  DoctorCheckResult,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  PROFILE_BACKENDS,
  profileBackend,
  type ProfileBackendValue,
  type ProfileFormState
} from './models-view-utils'

export type ProfileProbeStatus = {
  tone: DoctorCheckResult['status']
  label: string
  detail: string | null
  probing: boolean
}

function statusFromProbe(result: {
  health: string
  error: string | null
  models: string[]
}): Omit<ProfileProbeStatus, 'probing'> {
  const health = result.health || 'error'
  if (health === 'healthy') {
    return {
      tone: 'ok',
      label: 'Connected',
      detail:
        result.models.length > 0
          ? `${result.models.length} models`
          : 'Reachable'
    }
  }
  if (health === 'no_models') {
    return {
      tone: 'warn',
      label: 'No models',
      detail: result.error || 'Endpoint reachable but returned no models'
    }
  }
  // Match Doctor local-endpoint checks: unreachable is warn, not hard error.
  return {
    tone: 'warn',
    label: 'Unreachable',
    detail: result.error || 'Local endpoint unreachable'
  }
}

type ModelsViewProfilesInput = {
  localProfiles: ModelProfile[]
  load: (discover?: boolean) => Promise<void>
  setError: (error: string | null) => void
  onCreateProfile: (
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ) => Promise<ModelProfile>
  onUpdateProfile: (
    profileId: string,
    input: UpsertModelProfileInput,
    signal?: AbortSignal
  ) => Promise<ModelProfile>
  onDeleteProfile: (profileId: string, signal?: AbortSignal) => Promise<void>
  onProbeProfile: (
    profileId: string,
    signal?: AbortSignal
  ) => Promise<ModelProfileProbeResult>
  onDiscoverEndpoint: (
    input: DiscoverModelEndpointInput,
    signal?: AbortSignal
  ) => Promise<ModelProfileProbeResult>
  /** Load a saved Local LLM API key (for discover when draft is empty). */
  onRevealProfileSecret?: (profileId: string) => Promise<string>
}

export function useModelsViewProfiles({
  localProfiles,
  load,
  setError,
  onCreateProfile,
  onUpdateProfile,
  onDeleteProfile,
  onProbeProfile,
  onDiscoverEndpoint,
  onRevealProfileSecret
}: ModelsViewProfilesInput) {
  const [profilesOpen, setProfilesOpen] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<ModelProfile | null>(null)
  const [savingProfile, setSavingProfile] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [discoverSource, setDiscoverSource] = useState<string | null>(null)
  const [discoverError, setDiscoverError] = useState<string | null>(null)
  const [showProfileApiKey, setShowProfileApiKey] = useState(false)
  const [testingProfile, setTestingProfile] = useState(false)
  const [testResult, setTestResult] = useState<{
    ok: boolean
    message: string
  } | null>(null)
  const [probeStatusById, setProbeStatusById] = useState<
    Record<string, ProfileProbeStatus>
  >({})
  const [form, setForm] = useState<ProfileFormState>({
    label: '',
    backend: 'ollama',
    baseUrl: 'http://127.0.0.1:11434/v1',
    apiKey: ''
  })

  const selectedBackend = profileBackend(form.backend) || PROFILE_BACKENDS[0]
  const onProbeProfileRef = useRef(onProbeProfile)
  onProbeProfileRef.current = onProbeProfile
  const localProfilesRef = useRef(localProfiles)
  localProfilesRef.current = localProfiles
  const probedIdsKeyRef = useRef('')

  const checkProfileStatus = useCallback(async (profile: ModelProfile) => {
    setProbeStatusById(current => ({
      ...current,
      [profile.id]: {
        tone: current[profile.id]?.tone || 'warn',
        label: current[profile.id]?.label || 'Checking…',
        detail: current[profile.id]?.detail || null,
        probing: true
      }
    }))
    try {
      const result = await onProbeProfileRef.current(profile.id)
      const next = statusFromProbe(result)
      setProbeStatusById(current => ({
        ...current,
        [profile.id]: { ...next, probing: false }
      }))
      return result
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err)
      setProbeStatusById(current => ({
        ...current,
        [profile.id]: {
          tone: 'warn',
          label: 'Unreachable',
          detail,
          probing: false
        }
      }))
      throw err
    }
  }, [])

  // One-shot: ref-guarded so re-renders / HMR cannot re-enter setState.
  useEffect(() => {
    if (!profilesOpen) {
      probedIdsKeyRef.current = ''
      return
    }
    const profiles = localProfilesRef.current
    const key = profiles
      .map(profile => profile.id)
      .sort()
      .join('\0')
    if (!key || probedIdsKeyRef.current === key) return
    probedIdsKeyRef.current = key
    for (const profile of profiles) {
      void checkProfileStatus(profile).catch(() => null)
    }
  }, [checkProfileStatus, localProfiles, profilesOpen])

  const resetDiscoverState = () => {
    setDiscoveredModels([])
    setDiscoverSource(null)
    setDiscoverError(null)
    setTestResult(null)
  }

  const resetProfileDialogSecrets = () => {
    setShowProfileApiKey(false)
  }

  const openCreate = () => {
    setEditing(null)
    const ollama = PROFILE_BACKENDS[0]
    setForm({
      label: ollama.defaultLabel,
      backend: ollama.value,
      baseUrl: ollama.baseUrl,
      apiKey: ''
    })
    resetDiscoverState()
    resetProfileDialogSecrets()
    setDialogOpen(true)
  }

  const openEdit = (profile: ModelProfile) => {
    const backendValue =
      profile.backend === 'openai'
        ? 'other'
        : ((PROFILE_BACKENDS.find(item => item.value === profile.backend)
            ?.value || 'other') as ProfileBackendValue)
    setEditing(profile)
    setForm({
      label: profile.label,
      backend: backendValue,
      baseUrl: profile.baseUrl || '',
      apiKey: ''
    })
    resetDiscoverState()
    resetProfileDialogSecrets()
    setDialogOpen(true)
  }

  const resolveDraftApiKey = async (): Promise<string | null> => {
    let apiKey = form.apiKey.trim() || null
    // Reuse the stored profile key when the draft is empty (leave-blank-to-keep).
    if (!apiKey && editing?.hasApiKey && editing.id && onRevealProfileSecret) {
      try {
        apiKey = (await onRevealProfileSecret(editing.id)).trim() || null
      } catch {
        // Fall through; discover/probe will surface auth errors.
      }
    }
    return apiKey
  }

  const applyProbeToEditingCard = (result: ModelProfileProbeResult) => {
    if (!editing) return
    const next = statusFromProbe(result)
    setProbeStatusById(current => ({
      ...current,
      [editing.id]: { ...next, probing: false }
    }))
  }

  const discoverModels = async () => {
    const baseUrl = form.baseUrl.trim()
    if (!baseUrl) {
      setDiscoverError('Enter a base URL before discovering models.')
      return
    }
    setDiscovering(true)
    setDiscoverError(null)
    setTestResult(null)
    try {
      const result = await onDiscoverEndpoint({
        backend: form.backend,
        baseUrl,
        apiKey: await resolveDraftApiKey()
      })
      const nextModels = result.models || []
      setDiscoveredModels(nextModels)
      setDiscoverSource(result.modelsSource || null)
      applyProbeToEditingCard(result)
      if (result.error && nextModels.length === 0) {
        setDiscoverError(result.error)
        return
      }
      if (nextModels.length === 0) {
        setDiscoverError(
          'No models found. Check the base URL and API key, then try again.'
        )
      }
    } catch (err) {
      setDiscoverError(err instanceof Error ? err.message : String(err))
      setDiscoveredModels([])
      setDiscoverSource(null)
      if (editing) {
        setProbeStatusById(current => ({
          ...current,
          [editing.id]: {
            tone: 'warn',
            label: 'Unreachable',
            detail: err instanceof Error ? err.message : String(err),
            probing: false
          }
        }))
      }
    } finally {
      setDiscovering(false)
    }
  }

  /** Reachability check for the draft URL/key; updates Connected/Unreachable. */
  const testProfile = async () => {
    const baseUrl = form.baseUrl.trim()
    if (!baseUrl) {
      setTestResult({
        ok: false,
        message: 'Enter a base URL before testing.'
      })
      return
    }
    setTestingProfile(true)
    setTestResult(null)
    setDiscoverError(null)
    if (editing) {
      setProbeStatusById(current => ({
        ...current,
        [editing.id]: {
          tone: current[editing.id]?.tone || 'warn',
          label: 'Checking…',
          detail: current[editing.id]?.detail || null,
          probing: true
        }
      }))
    }
    try {
      const result = await onDiscoverEndpoint({
        backend: form.backend,
        baseUrl,
        apiKey: await resolveDraftApiKey()
      })
      const nextModels = result.models || []
      setDiscoveredModels(nextModels)
      setDiscoverSource(result.modelsSource || null)
      applyProbeToEditingCard(result)
      const status = statusFromProbe(result)
      // Connected or reachable-with-no-models both count as a successful Test.
      const reachable = status.label !== 'Unreachable'
      setTestResult({
        ok: reachable,
        message: reachable
          ? nextModels.length > 0
            ? `Reachable — ${nextModels.length} model${nextModels.length === 1 ? '' : 's'} found.`
            : status.detail || 'Endpoint reachable.'
          : status.detail || result.error || 'Local endpoint unreachable'
      })
      if (!reachable && result.error) {
        setDiscoverError(result.error)
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err)
      setTestResult({ ok: false, message: detail })
      setDiscoverError(detail)
      setDiscoveredModels([])
      setDiscoverSource(null)
      if (editing) {
        setProbeStatusById(current => ({
          ...current,
          [editing.id]: {
            tone: 'warn',
            label: 'Unreachable',
            detail,
            probing: false
          }
        }))
      }
    } finally {
      setTestingProfile(false)
    }
  }

  const saveProfile = async (modelId?: string) => {
    setSavingProfile(true)
    setError(null)
    try {
      const defaultModel =
        modelId || discoveredModels[0] || editing?.defaultModel || null
      const input: UpsertModelProfileInput = {
        id: modelId ? 'llama_local' : undefined,
        label: form.label.trim() || (modelId ? 'Llama' : null),
        backend: editing?.isCloud ? 'openai' : modelId ? 'llama' : form.backend,
        baseUrl: editing?.isCloud
          ? null
          : modelId
            ? 'http://127.0.0.1:9931/v1'
            : form.baseUrl.trim() || null,
        defaultModel,
        apiKey: modelId ? null : form.apiKey.trim() || null
      }
      if (editing) {
        await onUpdateProfile(editing.id, input)
      } else {
        await onCreateProfile(input)
      }
      setDialogOpen(false)
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingProfile(false)
    }
  }

  const removeProfile = async (profile: ModelProfile) => {
    if (profile.isCloud) return
    if (!window.confirm(`Delete profile “${profile.label}”?`)) return
    setError(null)
    try {
      await onDeleteProfile(profile.id)
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const probeProfile = async (profile: ModelProfile) => {
    setError(null)
    try {
      const result = await checkProfileStatus(profile)
      if (result?.error && result.models.length === 0) {
        setError(`${profile.label}: ${result.error}`)
      }
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return {
    profilesOpen,
    dialogOpen,
    editing,
    savingProfile,
    discovering,
    testingProfile,
    testResult,
    discoveredModels,
    discoverSource,
    discoverError,
    showProfileApiKey,
    form,
    selectedBackend,
    probeStatusById,
    setProfilesOpen,
    setDialogOpen,
    setForm,
    setShowProfileApiKey,
    resetDiscoverState,
    resetProfileDialogSecrets,
    openCreate,
    openEdit,
    discoverModels,
    testProfile,
    saveProfile,
    removeProfile,
    probeProfile
  }
}
