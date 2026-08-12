import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession, WidgetLayout } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import {
  createDefaultOverviewLayout,
  normalizeOverviewLayout,
  WidgetBoard
} from '@/components/agents/widget-board'
import { ScrollArea } from '@/components/ui/scroll-area'

/** Overview layout: customizable usage widgets. */
export function DashboardOverviewView({
  sessions: _sessions,
  client
}: {
  sessions: AgentSession[]
  client?: LocalAgentClient
}) {
  const [layout, setLayout] = useState<WidgetLayout>(() =>
    createDefaultOverviewLayout()
  )
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!client?.getDashboardLayout) {
      setReady(true)
      return
    }
    let cancelled = false
    void client
      .getDashboardLayout()
      .then(next => {
        if (cancelled) return
        const normalized = normalizeOverviewLayout(next)
        setLayout(normalized)
        // Persist reseeded defaults when the stored seed is older.
        if (
          client.updateDashboardLayout &&
          (next?.version || 1) < normalized.version
        ) {
          void client.updateDashboardLayout(normalized)
        }
      })
      .catch(() => {
        if (!cancelled) setLayout(createDefaultOverviewLayout())
      })
      .finally(() => {
        if (!cancelled) setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [client])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        {client && ready ? (
          <WidgetBoard
            client={client}
            surface="overview"
            layout={layout}
            onLayoutChange={async next => {
              setLayout(next)
              if (client.updateDashboardLayout) {
                await client.updateDashboardLayout(next)
              }
            }}
          />
        ) : null}
      </div>
    </ScrollArea>
  )
}
