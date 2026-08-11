import { useEffect, useState } from 'react'

import type { TranscriptTool } from '@/components/agents/ToolCard'
import {
  agentStatusKey,
  resolveAgentStatus
} from '@/lib/agent-status-words'
import { cn } from '@/lib/utils'

export function AgentStatusText({
  tools,
  liveDelta,
  className
}: {
  /** Tools for the active run (or any pending tools while running). */
  tools?: TranscriptTool[] | null
  /** Growing assistant stream — resets the quiet timer when it advances. */
  liveDelta?: string
  className?: string
}) {
  const [quietMs, setQuietMs] = useState(0)
  const activityKey = `${agentStatusKey(tools)}:${(liveDelta || '').length}`

  useEffect(() => {
    setQuietMs(0)
    const started = Date.now()
    const id = window.setInterval(() => {
      setQuietMs(Date.now() - started)
    }, 1000)
    return () => window.clearInterval(id)
  }, [activityKey])

  const label = resolveAgentStatus(tools, { quietMs })
  const key = agentStatusKey(tools, { quietMs })

  return (
    <span
      key={key}
      className={cn('animate-text-shimmer font-light', className)}
    >
      {label}
    </span>
  )
}
