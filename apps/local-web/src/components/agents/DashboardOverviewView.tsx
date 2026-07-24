import type { AgentSession } from '@sandwalk/agent-ui-core'
import type { ReactNode } from 'react'

import { SessionActivityHeatmap } from '@/components/agents/SessionActivityHeatmap'
import { ScrollArea } from '@/components/ui/scroll-area'

/** Overview layout: activity heatmap + Featured sections, shared column width. */
export function DashboardOverviewView({
  sessions,
  children
}: {
  sessions: AgentSession[]
  children: ReactNode
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-10 p-4 md:p-6">
        <SessionActivityHeatmap sessions={sessions} />
        <div className="space-y-10">{children}</div>
      </div>
    </ScrollArea>
  )
}
