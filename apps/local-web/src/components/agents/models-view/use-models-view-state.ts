import type {
  AgentModel,
  CreateAgentModelInput,
  DiscoverModelEndpointInput,
  IntegrationSummary,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'
import { useState } from 'react'

import { useModelsViewApiKeys } from './use-models-view-api-keys'
import { useModelsViewCustom } from './use-models-view-custom'
import { useModelsViewData } from './use-models-view-data'
import { useModelsViewProfiles } from './use-models-view-profiles'

type ModelsViewCallbacks = {
  integrations: IntegrationSummary[]
  onListModels: (options?: {
    discover?: boolean
    signal?: AbortSignal
  }) => Promise<AgentModel[]>
  onUpdateModelEnabled: (
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onCreateCustomModel: (
    input: CreateAgentModelInput,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onDeleteCustomModel: (
    modelId: string,
    signal?: AbortSignal
  ) => Promise<void>
  onListProfiles: (signal?: AbortSignal) => Promise<ModelProfile[]>
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
  onSaveProviderKey: (
    key: string,
    values: Record<string, string>
  ) => Promise<void>
  onClearProviderKey: (key: string) => Promise<void>
  onTestProviderKey: (
    key: string
  ) => Promise<{ ok: boolean; message: string }>
}

export function useModelsViewState(callbacks: ModelsViewCallbacks) {
  const [error, setError] = useState<string | null>(null)

  const data = useModelsViewData({
    integrations: callbacks.integrations,
    onListModels: callbacks.onListModels,
    onUpdateModelEnabled: callbacks.onUpdateModelEnabled,
    onListProfiles: callbacks.onListProfiles,
    setError
  })

  const apiKeys = useModelsViewApiKeys({
    load: data.load,
    setError,
    onSaveProviderKey: callbacks.onSaveProviderKey,
    onClearProviderKey: callbacks.onClearProviderKey,
    onTestProviderKey: callbacks.onTestProviderKey
  })

  const custom = useModelsViewCustom({
    load: data.load,
    setError,
    onCreateCustomModel: callbacks.onCreateCustomModel,
    onDeleteCustomModel: callbacks.onDeleteCustomModel
  })

  const profiles = useModelsViewProfiles({
    localProfiles: data.localProfiles,
    load: data.load,
    setError,
    onCreateProfile: callbacks.onCreateProfile,
    onUpdateProfile: callbacks.onUpdateProfile,
    onDeleteProfile: callbacks.onDeleteProfile,
    onProbeProfile: callbacks.onProbeProfile,
    onDiscoverEndpoint: callbacks.onDiscoverEndpoint
  })

  return {
    ...data,
    ...apiKeys,
    ...custom,
    ...profiles,
    error
  }
}
