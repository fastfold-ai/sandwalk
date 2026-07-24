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
}

export function useModelsViewProfiles({
  localProfiles,
  load,
  setError,
  onCreateProfile,
  onUpdateProfile,
  onDeleteProfile,
  onProbeProfile,
  onDiscoverEndpoint
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

  const discoverModels = async () => {
    const baseUrl = form.baseUrl.trim()
    if (!baseUrl) {
      setDiscoverError('Enter a base URL before discovering models.')
      return
    }
    setDiscovering(true)
    setDiscoverError(null)
    try {
      const result = await onDiscoverEndpoint({
        backend: form.backend,
        baseUrl,
        apiKey: form.apiKey.trim() || null
      })
      const nextModels = result.models || []
      setDiscoveredModels(nextModels)
      setDiscoverSource(result.modelsSource || null)
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
    } finally {
      setDiscovering(false)
    }
  }

  const saveProfile = async () => {
    setSavingProfile(true)
    setError(null)
    try {
      const defaultModel =
        discoveredModels[0] || editing?.defaultModel || null
      const input: UpsertModelProfileInput = {
        label: form.label.trim() || null,
        backend: editing?.isCloud ? 'openai' : form.backend,
        baseUrl: editing?.isCloud ? null : form.baseUrl.trim() || null,
        defaultModel,
        apiKey: form.apiKey.trim() || null
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
    saveProfile,
    removeProfile,
    probeProfile
  }
}
