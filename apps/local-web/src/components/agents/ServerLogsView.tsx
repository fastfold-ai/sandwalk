import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { copyText } from '@/lib/clipboard'
import { type DesktopLogs,desktopTailLogs, isTauri } from '@/lib/desktop'

export function ServerLogsView() {
  const desktop = isTauri()
  const [name, setName] = useState('server.log')
  const [lines, setLines] = useState(200)
  const [log, setLog] = useState<DesktopLogs | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!desktop) return
    setLoading(true)
    setError(null)
    const next = await desktopTailLogs(name, lines)
    if (!next) {
      setError('Menubar control plane unavailable. Is Sandwalk.app running?')
      setLoading(false)
      return
    }
    setLog(next)
    setLoading(false)
  }, [desktop, name, lines])

  useEffect(() => {
    void load()
    if (!desktop) return
    const id = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(id)
  }, [desktop, load])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex max-w-5xl flex-col space-y-6 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">Logs</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Live tails of menubar process logs under Application Support.
          </p>
        </div>

        {!desktop ? (
          <DesktopOnlyCallout feature="Live server logs" />
        ) : (
          <>
            {error ? (
              <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <select
                className="bg-background rounded-md border px-3 py-2 text-sm"
                value={name}
                onChange={e => setName(e.target.value)}
              >
                <option value="server.log">server.log (API)</option>
                <option value="web.log">web.log (dashboard)</option>
              </select>
              <select
                className="bg-background rounded-md border px-3 py-2 text-sm"
                value={lines}
                onChange={e => setLines(Number(e.target.value))}
              >
                <option value={100}>Last 100</option>
                <option value={200}>Last 200</option>
                <option value={500}>Last 500</option>
                <option value={1000}>Last 1,000</option>
              </select>
              <Button
                variant="outline"
                size="sm"
                disabled={loading}
                onClick={() => void load()}
              >
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!log?.text}
                onClick={() => {
                  if (!log?.text) return
                  void copyText(log.text).then(ok => {
                    if (ok) toast.success('Copied')
                    else toast.error('Could not copy — select it manually')
                  })
                }}
              >
                Copy
              </Button>
              {log ? (
                <span className="text-muted-foreground text-xs">
                  {log.total_lines} lines · {log.path}
                </span>
              ) : null}
            </div>

            <pre className="bg-muted/30 max-h-[60vh] overflow-auto rounded-xl border p-4 font-mono text-xs whitespace-pre-wrap">
              {log?.text || (loading ? 'Loading…' : 'No log output yet.')}
            </pre>
          </>
        )}
      </div>
    </ScrollArea>
  )
}
