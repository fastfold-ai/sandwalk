import type { ToolSummary } from '@sandwalk/agent-ui-core'
import { Search } from 'lucide-react'

import { SpecialistToggle } from '@/components/agents/specialists-view/specialists-view-shared'
import { Input } from '@/components/ui/input'

export function SpecialistsEditorToolsSection({
  toolCount,
  toolNames,
  toolQuery,
  onToolQueryChange,
  toolsLoading,
  catalogToolCount,
  coreTools,
  extraTools,
  onSetTierTools,
  onToggleTool
}: {
  toolCount: number
  toolNames: string[]
  toolQuery: string
  onToolQueryChange: (query: string) => void
  toolsLoading: boolean
  catalogToolCount: number
  coreTools: ToolSummary[]
  extraTools: ToolSummary[]
  onSetTierTools: (tools: ToolSummary[], enabled: boolean) => void
  onToggleTool: (toolId: string) => void
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-medium">Tools ({toolCount})</h2>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Allowlist for this specialist. Core tools are the usual defaults;
            Extra tools are opt-in.
          </p>
        </div>
      </div>
      <div className="relative">
        <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2" />
        <Input
          value={toolQuery}
          onChange={event => onToolQueryChange(event.target.value)}
          placeholder="Search tools"
          className="border-border/50 bg-muted/40 h-9 pl-9"
        />
      </div>
      {toolsLoading && catalogToolCount === 0 ? (
        <p className="text-muted-foreground py-2 text-sm">Loading tools…</p>
      ) : catalogToolCount === 0 ? (
        <p className="text-muted-foreground py-2 text-sm">No tools available.</p>
      ) : (
        <div className="space-y-4">
          {(
            [
              { label: 'Core', tools: coreTools },
              { label: 'Extra', tools: extraTools }
            ] as const
          ).map(group => (
            <div key={group.label} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  {group.label} ({group.tools.length})
                </p>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground text-[11px] transition-colors"
                    onClick={() => onSetTierTools(group.tools, true)}
                  >
                    All
                  </button>
                  <span className="text-muted-foreground/40 text-[11px]">/</span>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground text-[11px] transition-colors"
                    onClick={() => onSetTierTools(group.tools, false)}
                  >
                    None
                  </button>
                </div>
              </div>
              {group.tools.length === 0 ? (
                <p className="text-muted-foreground text-xs">
                  No {group.label.toLowerCase()} tools match.
                </p>
              ) : (
                <div className="divide-border/40 max-h-56 divide-y overflow-y-auto rounded-xl border border-border/40">
                  {group.tools.map(tool => {
                    const checked = toolNames.includes(tool.id)
                    return (
                      <div
                        key={tool.id}
                        className="flex items-start justify-between gap-3 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-mono text-xs font-medium">
                            {tool.id}
                          </p>
                          <p className="text-muted-foreground mt-0.5 line-clamp-1 text-xs">
                            {tool.description}
                          </p>
                        </div>
                        <SpecialistToggle
                          enabled={checked}
                          label={`${checked ? 'Remove' : 'Allow'} ${tool.id}`}
                          onToggle={() => onToggleTool(tool.id)}
                        />
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
