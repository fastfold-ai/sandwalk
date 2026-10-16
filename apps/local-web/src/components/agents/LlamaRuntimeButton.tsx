import type { LlamaRuntimeStatus } from '@sandwalk/agent-local-client'
import { Loader } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'

export function LlamaRuntimeButton({
  load,
  ensure
}: {
  load: () => Promise<LlamaRuntimeStatus>
  ensure: () => Promise<LlamaRuntimeStatus>
}) {
  const [status, setStatus] = useState<LlamaRuntimeStatus | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setStatus(await load())
    } catch (err) {
      setStatus({
        baseUrl: 'http://127.0.0.1:9931/v1',
        installed: false,
        running: false,
        version: null,
        models: [],
        phase: 'error',
        detail: err instanceof Error ? err.message : String(err)
      })
    }
  }, [load])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (status?.phase !== 'installing' && status?.phase !== 'opening') return
    const timer = window.setInterval(() => {
      void refresh()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [refresh, status?.phase])

  const working =
    busy || status?.phase === 'installing' || status?.phase === 'opening'
  const label = status?.running
    ? `Llama is running · ${status.models.length} model${status.models.length === 1 ? '' : 's'}`
    : status?.phase === 'installing'
      ? 'Installing Llama…'
      : status?.phase === 'opening'
        ? 'Opening Llama…'
        : status?.installed
          ? 'Start llama'
          : 'Install llama'

  return (
    <div className="space-y-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={working || Boolean(status?.running)}
        onClick={() => {
          setBusy(true)
          void ensure()
            .then(setStatus)
            .catch(err =>
              setStatus({
                baseUrl: 'http://127.0.0.1:9931/v1',
                installed: false,
                running: false,
                version: null,
                models: [],
                phase: 'error',
                detail: err instanceof Error ? err.message : String(err)
              })
            )
            .finally(() => setBusy(false))
        }}
      >
        {working ? <Loader className="size-3.5 animate-spin" /> : null}
        {label}
      </Button>
      {status?.detail ? (
        <p className="text-muted-foreground text-xs">{status.detail}</p>
      ) : (
        <p className="text-muted-foreground text-xs">
          Sandwalk runs the llama CLI on localhost:9931. The menu-bar app stays closed.
        </p>
      )}
    </div>
  )
}
