import type { AgentSession, UsageOverview } from '@sandwalk/agent-ui-core'
import type { ReactNode } from 'react'

import { UsageOverviewSection } from '@/components/agents/UsageOverviewSection'
import { ScrollArea } from '@/components/ui/scroll-area'

/** Overview layout: usage + Featured sections. */
export function DashboardOverviewView({
  sessions: _sessions,
  client,
  children
}: {
  sessions: AgentSession[]
  client?: {
    getUsageOverview?: (signal?: AbortSignal) => Promise<UsageOverview>
  }
  children: ReactNode
}) {
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        {client ? <UsageOverviewSection client={client} /> : null}
        <div className="space-y-10">{children}</div>
      </div>
    </ScrollArea>
  )
}
