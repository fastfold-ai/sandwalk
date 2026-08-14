import type { AgentModel } from '@sandwalk/agent-ui-core'
import { Loader, Plus, RefreshCw, Star, Trash2 } from 'lucide-react'
import { ListRowsSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { catalogModelPrefKey } from '@/lib/composer-models'
import { cn } from '@/lib/utils'

import { ModelFavoriteButton, ModelToggle } from './models-view-shared'
import type { ModelSourceFilter } from './models-view-utils'

export function ModelsListSection({
  query,
  sourceFilter,
  providerFilter,
  models,
  favoriteKeys,
  loading,
  refreshing,
  filteredModels,
  visibleModels,
  providerFilterOptions,
  canToggleModelList,
  showAllModels,
  pendingEnabled,
  onQueryChange,
  onSourceFilterChange,
  onProviderFilterChange,
  onShowAllModelsChange,
  onOpenCustomCreate,
  onOpenCreate,
  onRefresh,
  onToggleModel,
  onToggleFavorite,
  onRemoveCustomModel
}: {
  query: string
  sourceFilter: ModelSourceFilter
  providerFilter: string
  models: AgentModel[]
  favoriteKeys: string[]
  loading: boolean
  refreshing: boolean
  filteredModels: AgentModel[]
  visibleModels: AgentModel[]
  providerFilterOptions: Array<{ id: string; label: string; count: number }>
  canToggleModelList: boolean
  showAllModels: boolean
  pendingEnabled: Record<string, boolean>
  onQueryChange: (value: string) => void
  onSourceFilterChange: (value: ModelSourceFilter) => void
  onProviderFilterChange: (value: string) => void
  onShowAllModelsChange: (value: boolean | ((open: boolean) => boolean)) => void
  onOpenCustomCreate: () => void
  onOpenCreate: () => void
  onRefresh: () => void
  onToggleModel: (model: AgentModel) => void
  onToggleFavorite: (model: AgentModel) => void
  onRemoveCustomModel: (model: AgentModel) => void
}) {
  const favoriteSet = new Set(favoriteKeys)
  return (
    <section className="bg-muted/20 border-border/60 space-y-0 overflow-hidden rounded-xl border shadow-sm">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Input
          value={query}
          onChange={event => onQueryChange(event.target.value)}
          placeholder="Add or search model"
          className="border-0 bg-transparent shadow-none focus-visible:ring-0"
        />
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground h-8 shrink-0 gap-1 whitespace-nowrap"
          onClick={onOpenCustomCreate}
        >
          <Plus className="size-3.5" />
          Add Custom Model
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground hover:text-foreground h-8 shrink-0 gap-1 whitespace-nowrap"
          onClick={() => {
            onOpenCreate()
          }}
        >
          <Plus className="size-3.5" />
          Add Local Model
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0"
          disabled={refreshing || loading}
          onClick={onRefresh}
          aria-label="Refresh models"
        >
          {refreshing || loading ? (
            <Loader className="animate-spin" />
          ) : (
            <RefreshCw />
          )}
        </Button>
      </div>

      <div className="space-y-2 border-b px-3 py-2">
        <div className="flex flex-wrap items-center gap-1">
          {(
            [
              { id: 'all', label: 'All' },
              { id: 'favorites', label: 'Favorites' },
              { id: 'cloud', label: 'Cloud' },
              { id: 'local', label: 'Local' }
            ] as const
          ).map(option => (
            <button
              key={option.id}
              type="button"
              className={cn(
                'inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                sourceFilter === option.id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => {
                onSourceFilterChange(option.id)
                onShowAllModelsChange(false)
                if (option.id === 'local') onProviderFilterChange('local')
                else if (option.id === 'favorites') onProviderFilterChange('all')
                else if (option.id === 'cloud' && providerFilter === 'local') {
                  onProviderFilterChange('all')
                }
              }}
            >
              {option.id === 'favorites' ? (
                <Star
                  className={cn(
                    'size-3',
                    sourceFilter === 'favorites' && 'fill-current'
                  )}
                />
              ) : null}
              {option.label}
            </button>
          ))}
        </div>
        {providerFilterOptions.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1">
            <button
              type="button"
              className={cn(
                'rounded-md px-2 py-1 text-xs font-normal transition-colors',
                providerFilter === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => {
                onProviderFilterChange('all')
                onShowAllModelsChange(false)
              }}
            >
              All ({models.length})
            </button>
            {providerFilterOptions.map(option => (
              <button
                key={option.id}
                type="button"
                className={cn(
                  'rounded-md px-2 py-1 text-xs font-normal transition-colors',
                  providerFilter === option.id
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => {
                  onProviderFilterChange(option.id)
                  onShowAllModelsChange(false)
                  if (option.id === 'local') onSourceFilterChange('local')
                  else if (sourceFilter === 'local') onSourceFilterChange('cloud')
                }}
              >
                {option.label} ({option.count})
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="divide-y">
        {loading && models.length === 0 ? (
          <ListRowsSkeleton rows={8} />
        ) : filteredModels.length === 0 ? (
          <div className="text-muted-foreground px-4 py-8 text-sm">
            {query.trim()
              ? 'No models match this search.'
              : sourceFilter === 'favorites'
                ? 'No favorite models yet. Star a model to pin it here.'
                : providerFilter !== 'all'
                  ? 'No models match this provider filter.'
                  : sourceFilter === 'local'
                    ? 'No local models yet. Add a Local LLM endpoint to discover them.'
                    : sourceFilter === 'cloud'
                      ? 'No cloud models match this filter.'
                      : 'No models match this search.'}
          </div>
        ) : (
          visibleModels.map(model => {
            const key = `${model.provider}:${model.profileId || model.source}:${model.id}`
            const sourceLabel =
              model.source === 'cloud'
                ? `${model.provider} · cloud`
                : model.source === 'custom'
                  ? `${model.provider} · custom`
                  : `local · ${model.profileId || 'endpoint'}`
            return (
              <div
                key={key}
                className="group flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {model.label}
                  </div>
                  <div className="text-muted-foreground truncate text-xs">
                    {sourceLabel}
                    {model.health ? ` · ${model.health}` : ''}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <ModelFavoriteButton
                    favorite={favoriteSet.has(catalogModelPrefKey(model))}
                    label={model.label}
                    onToggle={() => onToggleFavorite(model)}
                  />
                  {model.source === 'custom' ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8"
                      onClick={() => onRemoveCustomModel(model)}
                      aria-label={`Remove ${model.label}`}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  ) : null}
                  <ModelToggle
                    enabled={model.enabled}
                    pending={Boolean(pendingEnabled[key])}
                    label={`${model.enabled ? 'Hide' : 'Show'} ${model.label}`}
                    onToggle={() => onToggleModel(model)}
                  />
                </div>
              </div>
            )
          })
        )}
      </div>
      {canToggleModelList ? (
        <div className="border-t px-4 py-3">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-sm font-medium"
            onClick={() => onShowAllModelsChange(open => !open)}
          >
            {showAllModels
              ? 'Show fewer models'
              : `View All Models (${filteredModels.length})`}
          </button>
        </div>
      ) : null}
    </section>
  )
}
