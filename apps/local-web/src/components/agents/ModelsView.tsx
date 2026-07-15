import type {
  AgentModel,
  CreateAgentModelInput,
  DiscoverModelEndpointInput,
  IntegrationSummary,
  ModelProfile,
  ModelProfileProbeResult,
  UpsertModelProfileInput
} from '@sandwalk/agent-ui-core'

import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  ModelsCustomDialog,
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
    envVar: string,
    value: string
  ) => Promise<void>
  onClearProviderKey: (key: string) => Promise<void>
  /** Compact chrome for setup wizard embedding. */
  embedded?: boolean
}) {
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
    onClearProviderKey
  })

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      <div
        className={cn(
          'mx-auto w-full space-y-8',
          embedded ? 'max-w-5xl p-1' : 'max-w-7xl p-4 md:p-6'
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

        <ModelsApiKeysSection
          open={state.apiKeysOpen}
          providerIntegrations={state.providerIntegrations}
          keyDrafts={state.keyDrafts}
          savingKeys={state.savingKeys}
          revealedKeys={state.revealedKeys}
          onOpenChange={state.setApiKeysOpen}
          onKeyDraftChange={(key, value) =>
            state.setKeyDrafts(prev => ({ ...prev, [key]: value }))
          }
          onRevealedKeyChange={(key, revealed) =>
            state.setRevealedKeys(prev => ({ ...prev, [key]: revealed }))
          }
          onSaveProviderKey={integration =>
            void state.saveProviderKey(integration)
          }
          onClearProviderKey={integration =>
            void state.clearProviderKey(integration)
          }
        />

        <ModelsCustomSection
          open={state.customOpen}
          customModels={state.customModels}
          onOpenChange={state.setCustomOpen}
          onOpenCustomCreate={state.openCustomCreate}
          onRemoveCustomModel={model => void state.removeCustomModel(model)}
        />

        <ModelsProfilesSection
          open={state.profilesOpen}
          localProfiles={state.localProfiles}
          onOpenChange={state.setProfilesOpen}
          onOpenCreate={state.openCreate}
          onProbeProfile={profile => void state.probeProfile(profile)}
          onOpenEdit={state.openEdit}
          onRemoveProfile={profile => void state.removeProfile(profile)}
        />
      </div>

      <ModelsProfileDialog
        open={state.dialogOpen}
        editing={state.editing}
        form={state.form}
        selectedBackend={state.selectedBackend}
        savingProfile={state.savingProfile}
        discovering={state.discovering}
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
        onSaveProfile={() => void state.saveProfile()}
        onShowProfileApiKeyChange={state.setShowProfileApiKey}
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
    </ScrollArea>
  )
}
