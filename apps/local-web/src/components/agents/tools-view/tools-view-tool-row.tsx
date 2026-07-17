import type { ToolSummary } from '@sandwalk/agent-ui-core'
import { Check, Database, TriangleAlert } from 'lucide-react'

import { cn } from '@/lib/utils'

import {
  statusClass,
  tierClass,
  ToolToggle,
  toolIsToggleable,
  toolTier
} from './tools-view-shared'

export function ToolsViewToolRow({
  tool,
  pending,
  onOpenData,
  onToggle,
  resolveRequirement
}: {
  tool: ToolSummary
  pending: boolean
  onOpenData: () => void
  onToggle: () => void
  resolveRequirement: (token: string) => {
    datasetId: string | null
    installed: boolean | null
  }
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{tool.id}</span>
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              tierClass(toolTier(tool))
            )}
          >
            {toolTier(tool) === 'core' ? 'Core' : 'Extra'}
          </span>
          {tool.status !== 'stable' ? (
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-xs font-medium',
                statusClass(tool.status)
              )}
            >
              {tool.status}
            </span>
          ) : null}
        </div>
        <p className="text-muted-foreground mt-1 text-sm">{tool.description}</p>
        {tool.requiresData.length > 0 ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span className="text-muted-foreground text-xs">Requires:</span>
            {tool.requiresData.map(req => {
              const { installed } = resolveRequirement(req)
              return (
                <button
                  key={req}
                  type="button"
                  onClick={onOpenData}
                  title={
                    installed === null
                      ? undefined
                      : installed
                        ? 'Dataset installed'
                        : 'Dataset not installed'
                  }
                  className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 font-mono text-[11px]"
                >
                  {installed === true ? (
                    <Check className="size-3 text-emerald-600" />
                  ) : installed === false ? (
                    <TriangleAlert className="size-3 text-amber-600" />
                  ) : (
                    <Database className="size-3" />
                  )}
                  {req}
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
      <ToolToggle
        enabled={tool.enabled}
        pending={pending}
        locked={!toolIsToggleable(tool)}
        label={
          toolIsToggleable(tool)
            ? `${tool.enabled ? 'Disable' : 'Enable'} ${tool.id}`
            : `${tool.id} (core — always on)`
        }
        onToggle={onToggle}
      />
    </div>
  )
}
