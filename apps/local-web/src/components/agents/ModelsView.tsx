import type {
  AgentModel,
  CreateAgentModelInput,
  DiscoverModelEndpointInput,
  IntegrationSummary,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'
import { Info } from 'lucide-react'
import { useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  ModelsCustomDialog,
  ModelsMultimodalGuideDialog,
  ModelsProfileDialog
} from './models-view/models-view-dialogs'
import { ModelsListSection } from './models-view/models-view-list'
import {
  ModelsApiKeysSection,
  ModelsCustomSection,
  ModelsProfilesSection
} from './models-view/models-view-settings'
import { applyBackendDefaults } from './models-view/models-view-utils'
import { useModelsViewState } from './models-view/use-models-view-state'

/** Models catalog + Local LLM connection status. */
export function ModelsView({
  integrations,
  onListModels,
  onUpdateModelEnabled,
  onCreateCustomModel,
  onDeleteCustomModel,
  onListProfiles,
  onCreateProfile,
  onUpdateProfile,
  onDeleteProfile,
  onProbeProfile,
  onDiscoverEndpoint,
  onSaveProviderKey,
  onClearProviderKey,
  onTestProviderKey,
  onRevealStoredSecret,
  onRevealProfileSecret,
  embedded = false
}: {
  integrations: IntegrationSummary[]
  onListModels: (options?: {
    discover?: boolean
    signal?: AbortSignal
  }) => Promise<AgentModel[]>
  onUpdateModelEnabled: (
    modelId: string,
    enabled: boolean,
    signal?: AbortSignal,
    provider?: string | null
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
  /** Load a saved API key for show/copy in the key modal. */
  onRevealStoredSecret: (key: string) => Promise<string>
  /** Load a saved Local LLM API key for show/copy / discover. */
  onRevealProfileSecret: (profileId: string) => Promise<string>
  /** Compact chrome for setup wizard embedding. */
  embedded?: boolean
}) {
  // Keep latest callback in a ref so HMR / identity churn can't leave Test
  // holding an undefined function from an earlier render.
  const testRef = useRef(onTestProviderKey)
  testRef.current = onTestProviderKey
  const runTestProviderKey = (key: string) => {
    const run = testRef.current
    if (typeof run !== 'function') {
      return Promise.resolve({
        ok: false,
        message: 'Test is unavailable. Reload the Models page and try again.'
      })
    }
    return run(key)
  }

  const clearRef = useRef(onClearProviderKey)
  clearRef.current = onClearProviderKey
  const runClearProviderKey = (key: string) => {
    const run = clearRef.current
    if (typeof run !== 'function') {
      return Promise.reject(
        new Error('Remove is unavailable. Reload the Models page and try again.')
      )
    }
    return run(key)
  }

  const state = useModelsViewState({
    integrations,
    onListModels,
    onUpdateModelEnabled,
    onCreateCustomModel,
    onDeleteCustomModel,
    onListProfiles,
    onCreateProfile,
    onUpdateProfile,
    onDeleteProfile,
    onProbeProfile,
    onDiscoverEndpoint,
    onSaveProviderKey,
    onClearProviderKey: runClearProviderKey,
    onTestProviderKey: runTestProviderKey,
    onRevealProfileSecret
  })
  const [multimodalGuideOpen, setMultimodalGuideOpen] = useState(false)

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      <div
        className={cn(
          'mx-auto w-full space-y-8',
          embedded ? 'max-w-5xl p-1' : 'max-w-7xl px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8'
        )}
      >
        {!embedded ? (
          <div>
            <h2 className="text-2xl font-semibold">Models</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Choose which cloud and local models are available to the agent.
            </p>
          </div>
        ) : null}

        {state.error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {state.error}
          </div>
        ) : null}

        <ModelsListSection
          query={state.query}
          sourceFilter={state.sourceFilter}
          providerFilter={state.providerFilter}
          models={state.models}
          loading={state.loading}
          refreshing={state.refreshing}
          filteredModels={state.filteredModels}
          visibleModels={state.visibleModels}
          providerFilterOptions={state.providerFilterOptions}
          canToggleModelList={state.canToggleModelList}
          showAllModels={state.showAllModels}
          pendingEnabled={state.pendingEnabled}
          onQueryChange={state.setQuery}
          onSourceFilterChange={state.setSourceFilter}
          onProviderFilterChange={state.setProviderFilter}
          onShowAllModelsChange={state.setShowAllModels}
          onOpenCustomCreate={state.openCustomCreate}
          onOpenCreate={() => {
            state.setProfilesOpen(true)
            state.openCreate()
          }}
          onRefresh={() => void state.refresh()}
          onToggleModel={model => void state.toggleModel(model)}
          onRemoveCustomModel={model => void state.removeCustomModel(model)}
        />

        <div className="-mt-4">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground h-8 gap-1.5 px-2"
            onClick={() => setMultimodalGuideOpen(true)}
          >
            <Info className="size-3.5" />
            Multimodal support
          </Button>
        </div>

        <ModelsApiKeysSection
          open={state.apiKeysOpen}
          providerIntegrations={state.providerIntegrations}
          keyDrafts={state.keyDrafts}
          endpointDrafts={state.endpointDrafts}
          revealedKeys={state.revealedKeys}
          cloudStatusFor={state.cloudStatusFor}
          onOpenChange={state.setApiKeysOpen}
          onKeyDraftChange={(key, value) =>
            state.setKeyDrafts(prev => ({ ...prev, [key]: value }))
          }
          onEndpointDraftChange={(key, value) =>
            state.setEndpointDrafts(prev => ({ ...prev, [key]: value }))
          }
          onRevealedKeyChange={(key, revealed) =>
            state.setRevealedKeys(prev => ({ ...prev, [key]: revealed }))
          }
          onRevealStoredSecret={onRevealStoredSecret}
          onSaveProviderKey={integration => state.saveProviderKey(integration)}
          onClearProviderKey={integration =>
            state.clearProviderKey(integration)
          }
          onTestProviderKey={state.testProviderKey}
        />

        <ModelsProfilesSection
          open={state.profilesOpen}
          localProfiles={state.localProfiles}
          probeStatusById={state.probeStatusById}
          onOpenChange={state.setProfilesOpen}
          onOpenCreate={state.openCreate}
          onOpenEdit={state.openEdit}
        />

        <ModelsCustomSection
          open={state.customOpen}
          customModels={state.customModels}
          onOpenChange={state.setCustomOpen}
          onOpenCustomCreate={state.openCustomCreate}
          onRemoveCustomModel={model => void state.removeCustomModel(model)}
        />
      </div>

      <ModelsProfileDialog
        open={state.dialogOpen}
        editing={state.editing}
        form={state.form}
        selectedBackend={state.selectedBackend}
        savingProfile={state.savingProfile}
        discovering={state.discovering}
        testingProfile={state.testingProfile}
        testResult={state.testResult}
        discoveredModels={state.discoveredModels}
        discoverSource={state.discoverSource}
        discoverError={state.discoverError}
        showProfileApiKey={state.showProfileApiKey}
        onOpenChange={open => {
          state.setDialogOpen(open)
          if (!open) {
            state.resetDiscoverState()
            state.resetProfileDialogSecrets()
          }
        }}
        onFormChange={state.setForm}
        onBackendChange={backend => {
          state.setForm(prev => applyBackendDefaults(backend, prev))
          state.resetDiscoverState()
        }}
        onDiscoverModels={() => void state.discoverModels()}
        onTestProfile={() => void state.testProfile()}
        onSaveProfile={() => void state.saveProfile()}
        onRemoveProfile={profile => void state.removeProfile(profile)}
        onShowProfileApiKeyChange={state.setShowProfileApiKey}
        onRevealStoredSecret={onRevealProfileSecret}
        onResetDiscoverState={state.resetDiscoverState}
      />

      <ModelsCustomDialog
        open={state.customDialogOpen}
        customForm={state.customForm}
        savingCustom={state.savingCustom}
        onOpenChange={state.setCustomDialogOpen}
        onCustomFormChange={state.setCustomForm}
        onSaveCustomModel={() => void state.saveCustomModel()}
      />

      <ModelsMultimodalGuideDialog
        open={multimodalGuideOpen}
        onOpenChange={setMultimodalGuideOpen}
        models={state.models}
      />
    </ScrollArea>
  )
}
