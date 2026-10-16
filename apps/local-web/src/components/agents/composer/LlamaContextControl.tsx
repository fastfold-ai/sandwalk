import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { cn } from '@/lib/utils'

const TIERS = [4096, 8192, 16384, 32768, 65536, 131072] as const

function label(ctx: number): string {
  return `${ctx / 1024}k`
}

export function LlamaContextControl({
  client,
  modelId
}: {
  client: LocalAgentClient
  modelId: string
}) {
  const [current, setCurrent] = useState<number>(4096)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    void client
      .llamaRuntimeCatalog()
      .then(catalog => {
        if (cancelled) return
        const row = catalog.installed.find(item => item.id === modelId)
        if (row?.context) setCurrent(row.context)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [client, modelId])

  return (
    <label className="text-muted-foreground inline-flex h-7 items-center gap-1 rounded-full border border-transparent px-1 text-xs">
      <span className="sr-only">Context length</span>
      <select
        aria-label="Context length"
        title="Context length. Applies the next time this model loads."
        disabled={busy}
        value={current}
        onChange={event => {
          const next = Number(event.target.value)
          setBusy(true)
          void client
            .llamaRuntimeSetContext(modelId, next)
            .then(() => {
              setCurrent(next)
              toast.success(
                `Context set to ${label(next)}. It applies the next time this model loads.`
              )
            })
            .catch(err =>
              toast.error(err instanceof Error ? err.message : 'Could not set context')
            )
            .finally(() => setBusy(false))
        }}
        className={cn(
          'bg-transparent text-xs outline-none',
          busy && 'opacity-60'
        )}
      >
        {TIERS.map(tier => (
          <option key={tier} value={tier}>
            {label(tier)} context
          </option>
        ))}
      </select>
    </label>
  )
}
