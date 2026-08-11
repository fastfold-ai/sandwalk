import { ChevronDown, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'

import { groupConsecutiveSameNameTools } from '@/components/agents/chat-transcript-timeline'
import { ToolCard, type TranscriptTool } from '@/components/agents/ToolCard'
import { TOOL_RUN_VISIBLE_COUNT } from '@/components/agents/transcript'

type LiveToolStackProps = {
  tools: TranscriptTool[]
  runActive: boolean
  onInterrupt?: () => void
}

function LiveToolGroup({
  tools,
  runActive,
  onInterrupt
}: {
  tools: TranscriptTool[]
  runActive: boolean
  onInterrupt?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const pendingCount = tools.filter(tool => tool.status === 'pending').length
  const visibleTools = expanded
    ? tools
    : tools.slice(-TOOL_RUN_VISIBLE_COUNT)
  const hiddenCount = Math.max(0, tools.length - TOOL_RUN_VISIBLE_COUNT)
  const label = tools[0]?.name || 'tool'

  return (
    <div className="space-y-1">
      {hiddenCount > 0 ? (
        <div className="mx-auto w-full max-w-[44rem] px-2">
          <button
            type="button"
            className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex h-7 items-center gap-1 rounded-md px-1.5 text-xs"
            onClick={() => setExpanded(current => !current)}
          >
            {expanded ? (
              <ChevronDown className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
            ) : (
              <ChevronRight className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
            )}
            <span>
              {expanded
                ? 'Show less'
                : `${label} × ${tools.length}${
                    pendingCount > 0 ? ` · ${pendingCount} running` : ''
                  }`}
            </span>
          </button>
        </div>
      ) : null}
      {visibleTools.map(tool => (
        <div
          key={`active-${tool.id}`}
          className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
        >
          <ToolCard tool={tool} isRunning={runActive} onStop={onInterrupt} />
        </div>
      ))}
    </div>
  )
}

/** Live tool cards under the stream, collapsed by consecutive same-name runs. */
export function LiveToolStack({
  tools,
  runActive,
  onInterrupt
}: LiveToolStackProps) {
  const groups = useMemo(
    () => groupConsecutiveSameNameTools(tools),
    [tools]
  )
  if (tools.length === 0) return null
  return (
    <div className="space-y-1">
      {groups.map(group => {
        if (Array.isArray(group)) {
          return (
            <LiveToolGroup
              key={`group-${group[0]?.id}`}
              tools={group}
              runActive={runActive}
              onInterrupt={onInterrupt}
            />
          )
        }
        return (
          <div
            key={`active-${group.id}`}
            className="fade-in slide-in-from-bottom-1 animate-in mx-auto w-full max-w-[44rem] px-2 duration-150"
          >
            <ToolCard
              tool={group}
              isRunning={runActive}
              onStop={onInterrupt}
            />
          </div>
        )
      })}
    </div>
  )
}
