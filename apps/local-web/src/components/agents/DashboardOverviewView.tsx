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
      <div className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <SessionActivityHeatmap sessions={sessions} />
        <div className="space-y-10">{children}</div>
      </div>
    </ScrollArea>
  )
}
