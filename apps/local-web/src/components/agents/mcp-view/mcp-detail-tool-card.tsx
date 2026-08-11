import type { McpToolDetail } from '@sandwalk/agent-ui-core'
import { ChevronDown, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'

import { cn } from '@/lib/utils'

import { firstParagraph, schemaPropertyEntries } from './mcp-detail-utils'

export function McpDetailToolCard({ tool }: { tool: McpToolDetail }) {
  const [open, setOpen] = useState(false)
  const properties = useMemo(
    () => schemaPropertyEntries(tool.inputSchema),
    [tool.inputSchema]
  )
  const hasSchema =
    properties.length > 0 ||
    (tool.inputSchema != null && Object.keys(tool.inputSchema).length > 0)
  const summary = tool.description
    ? firstParagraph(tool.description)
    : tool.title?.trim() || null
  const showFullDescription =
    open && Boolean(tool.description && tool.description !== summary)

  return (
    <div className="overflow-hidden rounded-lg border border-border/70">
      <button
        type="button"
        className="hover:bg-muted/40 flex w-full items-start gap-3 px-3 py-3 text-left transition-colors"
        onClick={() => setOpen(current => !current)}
        aria-expanded={open}
      >
        <span className="bg-muted text-muted-foreground mt-0.5 grid size-7 shrink-0 place-items-center rounded">
          <Wrench className="size-3.5" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <code className="truncate text-sm font-medium">{tool.name}</code>
            {tool.title && tool.title !== tool.name ? (
              <span className="text-muted-foreground truncate text-xs">
                {tool.title}
              </span>
            ) : null}
            {hasSchema || tool.description ? (
              <ChevronDown
                className={cn(
                  'text-muted-foreground ml-auto size-4 shrink-0 transition-transform',
                  open && 'rotate-180'
                )}
              />
            ) : null}
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            {summary || 'No description provided.'}
          </p>
        </div>
      </button>
      {open && (showFullDescription || hasSchema) ? (
        <div className="border-t border-border/60 bg-muted/20 space-y-3 px-3 py-3">
          {showFullDescription ? (
            <p className="text-muted-foreground whitespace-pre-wrap text-xs leading-relaxed">
              {tool.description}
            </p>
          ) : null}
          {hasSchema ? (
            properties.length > 0 ? (
              <div className="space-y-2.5">
                <p className="text-muted-foreground text-[11px] font-medium tracking-wide uppercase">
                  Parameters
                </p>
                {properties.map(prop => (
                  <div key={prop.key} className="space-y-0.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <code className="text-foreground font-medium">{prop.key}</code>
                      <span className="text-muted-foreground">{prop.type}</span>
                      {prop.required ? (
                        <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300">
                          required
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-[10px]">
                          optional
                        </span>
                      )}
                    </div>
                    {prop.description ? (
                      <p className="text-muted-foreground text-xs leading-relaxed">
                        {prop.description}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <pre className="text-muted-foreground overflow-x-auto font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                {JSON.stringify(tool.inputSchema, null, 2)}
              </pre>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
