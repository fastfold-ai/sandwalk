import type { McpCatalogEntry } from '@sandwalk/agent-ui-core'
import { Plus, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'

export function McpSuggestedStrip({
  suggested,
  onInstall,
  onResetDefaults,
  onOpenCatalog
}: {
  suggested: McpCatalogEntry[]
  onInstall: (catalogId: string) => void | Promise<void>
  onResetDefaults?: () => void | Promise<void>
  onOpenCatalog?: (entry: McpCatalogEntry) => void
}) {
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [resetting, setResetting] = useState(false)

  if (suggested.length === 0) return null

  return (
    <div className="space-y-2 rounded-xl border border-dashed px-3 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-foreground text-sm font-semibold">Suggested</p>
          <p className="text-muted-foreground text-xs">
            Catalog templates you removed — add them back anytime.
          </p>
        </div>
        {onResetDefaults ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 gap-1 px-2 text-xs"
            disabled={resetting || pendingId !== null}
            onClick={() => {
              void (async () => {
                setResetting(true)
                try {
                  await onResetDefaults()
                } finally {
                  setResetting(false)
                }
              })()
            }}
          >
            <RotateCcw className="size-3.5" />
            Reset to defaults
          </Button>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {suggested.map(entry => (
          <div
            key={entry.id}
            className="bg-card flex items-center gap-2 rounded-lg border px-2.5 py-1.5"
          >
            <button
              type="button"
              className="text-left text-sm font-medium hover:underline"
              onClick={() => onOpenCatalog?.(entry)}
            >
              {entry.name}
            </button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 gap-1 px-2 text-xs"
              disabled={pendingId === entry.id || resetting}
              onClick={() => {
                void (async () => {
                  setPendingId(entry.id)
                  try {
                    await onInstall(entry.id)
                    toast.success(`Added ${entry.name}`)
                  } catch (err) {
                    toast.error(
                      err instanceof Error ? err.message : 'Could not add MCP'
                    )
                  } finally {
                    setPendingId(null)
                  }
                })()
              }}
            >
              <Plus className="size-3.5" />
              Add
            </Button>
          </div>
        ))}
      </div>
    </div>
  )
}
