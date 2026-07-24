import type { TranscriptTool } from '@/components/agents/ToolCard'
import {
  agentStatusKey,
  resolveAgentStatus
} from '@/lib/agent-status-words'
import { cn } from '@/lib/utils'

export function AgentStatusText({
  tools,
  className
}: {
  /** Tools for the active run (or any pending tools while running). */
  tools?: TranscriptTool[] | null
  className?: string
}) {
  const label = resolveAgentStatus(tools)
  const key = agentStatusKey(tools)

  return (
    <span
      key={key}
      className={cn('animate-text-shimmer font-light', className)}
    >
      {label}
    </span>
  )
}
