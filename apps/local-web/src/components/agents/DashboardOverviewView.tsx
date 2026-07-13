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
      <div className="mx-auto w-full max-w-5xl space-y-10 px-6 py-8 sm:px-8 sm:py-10">
        <SessionActivityHeatmap sessions={sessions} />
        <div className="space-y-10">{children}</div>
      </div>
    </ScrollArea>
  )
}
