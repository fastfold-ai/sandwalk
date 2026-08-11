import type { AgentSkill, McpServer } from '@sandwalk/agent-ui-core'
import { CornerDownLeft } from 'lucide-react'

import { cleanSkillDescription } from '@/components/agents/composer/composer-mention-utils'
import { ScrollArea } from '@/components/ui/scroll-area'

export function ComposerSlashPreview({
  selectedMcp,
  selectedSkill,
  previewLoading,
  previewOverview,
  selectedExamples,
  onPickMcp,
  onPickExample
}: {
  selectedMcp: McpServer | null
  selectedSkill: AgentSkill | null
  previewLoading: boolean
  previewOverview: string | null
  selectedExamples: { title: string; prompt: string }[]
  onPickMcp: (server: McpServer) => void
  onPickExample: (skillName: string, prompt: string) => void
}) {
  return (
    <ScrollArea className="h-72">
      <div className="px-1 py-1">
        {selectedMcp ? (
          <div className="space-y-3 px-2 py-1">
            <div className="flex items-start justify-between gap-2">
              <span className="truncate text-sm font-semibold">
                {selectedMcp.name}
              </span>
              <a
                href={
                  selectedMcp.catalogId
                    ? `/dashboard/mcp/catalog/${encodeURIComponent(
                        selectedMcp.catalogId
                      )}`
                    : `/dashboard/mcp/server/${encodeURIComponent(
                        selectedMcp.id
                      )}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                onMouseDown={event => event.preventDefault()}
              >
                Read more
              </a>
            </div>
            <p className="text-muted-foreground line-clamp-5 text-[11px] leading-relaxed">
              {previewOverview ||
                `Mention mcp:${selectedMcp.name} so the agent prefers tools from this MCP server.`}
            </p>
            <div className="border-border/60 border-t pt-2">
              <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                Insert
              </p>
              <button
                type="button"
                tabIndex={-1}
                onMouseDown={event => event.preventDefault()}
                onClick={() => onPickMcp(selectedMcp)}
                className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="block truncate text-[11px] font-medium">
                    Mention this MCP
                  </span>
                  <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                    Insert
                    <CornerDownLeft className="h-3 w-3" />
                  </span>
                </span>
                <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                  Adds mcp:{selectedMcp.name} so the agent can prioritize its
                  tools.
                </span>
              </button>
            </div>
          </div>
        ) : selectedSkill ? (
          <div className="space-y-3 px-2 py-1">
            <div className="flex items-start justify-between gap-2">
              <span className="truncate text-sm font-semibold">
                {selectedSkill.name}
              </span>
              <a
                href={`/dashboard/skills/${encodeURIComponent(
                  selectedSkill.name
                )}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary shrink-0 text-[11px] font-medium hover:underline"
                onMouseDown={event => event.preventDefault()}
              >
                Read more
              </a>
            </div>
            <p className="text-muted-foreground line-clamp-3 text-[11px] leading-relaxed">
              {previewLoading
                ? 'Loading preview…'
                : previewOverview ||
                  cleanSkillDescription(selectedSkill.description) ||
                  `Use /${selectedSkill.name} to run this skill.`}
            </p>
            <div className="border-border/60 border-t pt-2">
              <p className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                Examples
              </p>
              <div className="space-y-1">
                {selectedExamples.map(example => (
                  <button
                    key={`${selectedSkill.name}-${example.title}`}
                    type="button"
                    tabIndex={-1}
                    onMouseDown={event => event.preventDefault()}
                    onClick={() =>
                      onPickExample(selectedSkill.name, example.prompt)
                    }
                    className="hover:bg-muted/50 border-border/60 bg-background w-full rounded-md border px-2 py-1.5 text-left"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="block truncate text-[11px] font-medium">
                        {example.title}
                      </span>
                      <span className="border-primary/30 text-primary inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium">
                        Try
                        <CornerDownLeft className="h-3 w-3" />
                      </span>
                    </span>
                    <span className="text-muted-foreground mt-0.5 line-clamp-2 block text-[10px]">
                      {example.prompt}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-muted-foreground p-3 text-xs">
            Select a skill or MCP to preview.
          </div>
        )}
      </div>
    </ScrollArea>
  )
}
