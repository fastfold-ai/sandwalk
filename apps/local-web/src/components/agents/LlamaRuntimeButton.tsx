import type {
  LlamaRuntimeDebug,
  LlamaRuntimeStatus
} from '@sandwalk/agent-local-client'
import { Loader } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'

function formatDebug(debug: LlamaRuntimeDebug) {
  const lines = [
    debug.command ? `command: ${debug.command}` : '',
    debug.port ? `port: ${debug.port}` : '',
    debug.exitCode != null ? `exit: ${debug.exitCode}` : '',
    debug.binary !== undefined || debug.searched?.length
      ? `binary: ${debug.binary || '(not found)'}`
      : '',
    debug.searched?.length
      ? `searched:\n${debug.searched.map(path => `  ${path}`).join('\n')}`
      : '',
    debug.log ? `log:\n${debug.log}` : ''
  ]
  return lines.filter(Boolean).join('\n')
}

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
        detail: err instanceof Error ? err.message : String(err),
        debug: {
          command: 'GET /v1/local-runtimes/llama',
          port: 9931
        }
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
                detail: err instanceof Error ? err.message : String(err),
                debug: {
                  command: 'POST /v1/local-runtimes/llama/ensure',
                  port: 9931
                }
              })
            )
            .finally(() => setBusy(false))
        }}
      >
        {working ? <Loader className="size-3.5 animate-spin" /> : null}
        {label}
      </Button>
      {status?.phase === 'error' && status.detail ? (
        <p className="text-destructive text-xs">{status.detail}</p>
      ) : status?.detail ? (
        <p className="text-muted-foreground text-xs">{status.detail}</p>
      ) : (
        <p className="text-muted-foreground text-xs">
          Sandwalk runs the llama CLI on localhost:9931. The menu-bar app stays closed.
        </p>
      )}
      {status?.phase === 'error' && status.debug ? (
        <pre className="bg-muted/50 text-muted-foreground max-h-48 overflow-auto rounded-md p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
          {formatDebug(status.debug)}
        </pre>
      ) : null}
    </div>
  )
}
