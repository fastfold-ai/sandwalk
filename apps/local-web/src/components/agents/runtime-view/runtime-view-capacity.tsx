import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { RunCapacity } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import { type RuntimeDraft, RuntimeNumberField } from './runtime-view-fields'

const POLL_MS = 3000

function gb(mb: number | null | undefined): string {
  if (mb == null) return '—'
  return `${(mb / 1024).toFixed(1)} GB`
}

/**
 * How many chats may run at once and how much RAM to keep free. Shows the
 * live gate state so a user who opened a 4×4 grid can see runs waiting
 * instead of wondering why some panes are quiet.
 */
export function RuntimeCapacitySection({
  draft,
  connected,
  saving,
  onDraftChange,
  client
}: {
  draft: RuntimeDraft
  connected: boolean
  saving: boolean
  onDraftChange: (updater: (current: RuntimeDraft) => RuntimeDraft) => void
  client?: LocalAgentClient
}) {
  const [capacity, setCapacity] = useState<RunCapacity | null>(null)

  useEffect(() => {
    if (!client || !connected) return
    let cancelled = false
    const tick = async () => {
      try {
        const next = await client.getRunCapacity()
        if (!cancelled) setCapacity(next)
      } catch {
        // Older servers have no capacity endpoint; the fields still work.
      }
    }
    void tick()
    const timer = window.setInterval(() => void tick(), POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [client, connected])

  const autoLimit = capacity
    ? Math.max(4, Math.min(16, capacity.cpuCount))
    : null
  const effective =
    Number(draft.maxConcurrentRuns) > 0
      ? Number(draft.maxConcurrentRuns)
      : capacity?.maxConcurrentRuns ?? autoLimit

  return (
    <section className="space-y-4" data-testid="runtime-capacity">
      <div>
        <h3 className="text-base font-semibold">Capacity</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Every chat turn is a worker in the agent server. These limits keep a
          big grid from starving the machine; runs over the limit wait in a
          queue and say so in their pane.
        </p>
      </div>
      {capacity ? (
        <div className="grid grid-cols-2 gap-3 rounded-lg border px-3 py-3 text-sm sm:grid-cols-4">
          <div>
            <div className="text-muted-foreground text-xs">Running</div>
            <div className="font-medium" data-testid="capacity-running">
              {capacity.running} / {effective ?? capacity.maxConcurrentRuns}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Queued</div>
            <div className="font-medium" data-testid="capacity-queued">
              {capacity.queued}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Memory available</div>
            <div className="font-medium">
              {gb(capacity.availableMemoryMb)}
              {capacity.totalMemoryMb ? (
                <span className="text-muted-foreground">
                  {' '}
                  of {gb(capacity.totalMemoryMb)}
                </span>
              ) : null}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">CPU cores</div>
            <div className="font-medium">{capacity.cpuCount}</div>
          </div>
        </div>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <RuntimeNumberField
          label="Max concurrent runs"
          hint={
            autoLimit
              ? `0 = automatic (${autoLimit} on this machine, from the core count).`
              : '0 = automatic, from the core count.'
          }
          value={draft.maxConcurrentRuns}
          min={0}
          max={64}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({ ...current, maxConcurrentRuns: value }))
          }
        />
        <RuntimeNumberField
          label="Keep free memory (GB)"
          hint="A new run waits while available memory is below this."
          value={draft.minFreeMemoryGb}
          min={0}
          max={256}
          step={0.5}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({ ...current, minFreeMemoryGb: value }))
          }
        />
      </div>
    </section>
  )
}
