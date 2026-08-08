import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import { ArrowRight } from 'lucide-react'

import { CardGridSkeleton } from '@/components/agents/PageSkeletons'
import { cn } from '@/lib/utils'

import { McpCatalogCard } from './mcp-catalog-card'
import type { CatalogStatusPatch } from './mcp-view-shared'

export function McpFeaturedSection({
  featuredOnly,
  featuredLabel,
  featuredCatalog,
  featuredVisible,
  catalogLoading,
  featuredLimit,
  statusPatch,
  pendingId,
  focusedMcpKey,
  showApiKey,
  apiKeyDraft,
  onShowAll,
  onOpenCatalog,
  onConnectOAuth,
  onConnectApiKey,
  onToggleCatalog,
  onPendingIdChange,
  onStatusPatchChange,
  onShowApiKeyChange,
  onApiKeyDraftChange,
  onRevealStoredSecret
}: {
  featuredOnly: boolean
  featuredLabel: string
  featuredCatalog: McpCatalogEntry[]
  featuredVisible: McpCatalogEntry[]
  catalogLoading?: boolean
  featuredLimit?: number | null
  statusPatch: Record<string, CatalogStatusPatch>
  pendingId: string | null
  focusedMcpKey: string | null
  showApiKey: Record<string, boolean>
  apiKeyDraft: Record<string, string>
  onShowAll?: () => void
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onConnectOAuth: (entry: McpCatalogEntry) => void
  onConnectApiKey: (entry: McpCatalogEntry) => void
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onPendingIdChange: (id: string | null) => void
  onStatusPatchChange: (
    updater: (
      prev: Record<string, CatalogStatusPatch>,
    ) => Record<string, CatalogStatusPatch>,
  ) => void
  onShowApiKeyChange: (id: string, show: boolean) => void
  onApiKeyDraftChange: (id: string, value: string) => void
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
}) {
  return (
    <section className={featuredOnly ? 'space-y-3' : 'space-y-2'}>
      <div
        className={cn(
          'flex gap-2',
          featuredOnly ? 'items-end justify-between' : 'items-center justify-between',
        )}
      >
        {featuredOnly ? (
          onShowAll ? (
            <div>
              <h3 className="text-base font-semibold tracking-tight">
                {featuredLabel}
              </h3>
              <p className="text-muted-foreground text-xs font-medium">
                Featured ({featuredCatalog.length})
              </p>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">{featuredLabel}</p>
          )
        ) : (
          <p className="text-muted-foreground text-xs font-medium">
            Featured ({featuredCatalog.length})
          </p>
        )}
        {featuredOnly && onShowAll ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-medium transition-colors"
            onClick={onShowAll}
          >
            Show all
            <ArrowRight className="size-3.5" />
          </button>
        ) : null}
      </div>
      {catalogLoading && featuredCatalog.length === 0 ? (
        <CardGridSkeleton
          cards={
            featuredOnly && featuredLimit !== null
              ? Math.min(featuredLimit ?? 2, 4)
              : 4
          }
          columns={2}
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {featuredVisible.map(entry => (
            <McpCatalogCard
              key={entry.id}
              entry={entry}
              statusPatch={statusPatch[entry.id]}
              pendingId={pendingId}
              focusedMcpKey={focusedMcpKey}
              showApiKey={Boolean(showApiKey[entry.id])}
              apiKeyDraft={apiKeyDraft[entry.id] || ''}
              onOpenCatalog={onOpenCatalog}
              onConnectOAuth={onConnectOAuth}
              onConnectApiKey={onConnectApiKey}
              onToggleCatalog={onToggleCatalog}
              onPendingIdChange={onPendingIdChange}
              onStatusPatchChange={onStatusPatchChange}
              onShowApiKeyChange={onShowApiKeyChange}
              onApiKeyDraftChange={onApiKeyDraftChange}
              onRevealStoredSecret={onRevealStoredSecret}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export function McpMoreCatalogSection({
  moreCatalog,
  statusPatch,
  pendingId,
  focusedMcpKey,
  showApiKey,
  apiKeyDraft,
  onOpenCatalog,
  onConnectOAuth,
  onConnectApiKey,
  onToggleCatalog,
  onPendingIdChange,
  onStatusPatchChange,
  onShowApiKeyChange,
  onApiKeyDraftChange,
  onRevealStoredSecret
}: {
  moreCatalog: McpCatalogEntry[]
  statusPatch: Record<string, CatalogStatusPatch>
  pendingId: string | null
  focusedMcpKey: string | null
  showApiKey: Record<string, boolean>
  apiKeyDraft: Record<string, string>
  onOpenCatalog?: (entry: McpCatalogEntry) => void
  onConnectOAuth: (entry: McpCatalogEntry) => void
  onConnectApiKey: (entry: McpCatalogEntry) => void
  onToggleCatalog: (entry: McpCatalogEntry, enabled: boolean) => Promise<void>
  onPendingIdChange: (id: string | null) => void
  onStatusPatchChange: (
    updater: (
      prev: Record<string, CatalogStatusPatch>,
    ) => Record<string, CatalogStatusPatch>,
  ) => void
  onShowApiKeyChange: (id: string, show: boolean) => void
  onApiKeyDraftChange: (id: string, value: string) => void
  onRevealStoredSecret?: (integrationKey: string) => Promise<string>
}) {
  if (moreCatalog.length === 0) return null

  return (
    <section className="space-y-2">
      <p className="text-muted-foreground text-xs font-medium">
        More ({moreCatalog.length})
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {moreCatalog.map(entry => (
          <McpCatalogCard
            key={entry.id}
            entry={entry}
            statusPatch={statusPatch[entry.id]}
            pendingId={pendingId}
            focusedMcpKey={focusedMcpKey}
            showApiKey={Boolean(showApiKey[entry.id])}
            apiKeyDraft={apiKeyDraft[entry.id] || ''}
            onOpenCatalog={onOpenCatalog}
            onConnectOAuth={onConnectOAuth}
            onConnectApiKey={onConnectApiKey}
            onToggleCatalog={onToggleCatalog}
            onPendingIdChange={onPendingIdChange}
            onStatusPatchChange={onStatusPatchChange}
            onShowApiKeyChange={onShowApiKeyChange}
            onApiKeyDraftChange={onApiKeyDraftChange}
            onRevealStoredSecret={onRevealStoredSecret}
          />
        ))}
      </div>
    </section>
  )
}
