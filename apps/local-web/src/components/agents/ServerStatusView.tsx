import type { ServerCacheInfo, ServerStatusReport } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import {
  listenSubtitle,
  SandwalkServerCard
} from '@/components/agents/SandwalkServerCard'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  desktopServerRestart,
  desktopServerStart,
  desktopServerStatus,
  desktopServerStop,
  isTauri,
  type DesktopServerStatus
} from '@/lib/desktop'

import {
  ServerStatusCacheSection,
  ServerStatusSystemSection
} from './server-status-view-panels'
import { SectionLabel } from './server-status-view-shared'

export function ServerStatusView({
  onLoad,
  onClearCache
}: {
  onLoad: (signal?: AbortSignal) => Promise<ServerStatusReport>
  onClearCache: (signal?: AbortSignal) => Promise<ServerCacheInfo>
}) {
  const desktop = isTauri()
  const [report, setReport] = useState<ServerStatusReport | null>(null)
  const [desktopStatus, setDesktopStatus] = useState<DesktopServerStatus | null>(
    null
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [lifecycleBusy, setLifecycleBusy] = useState(false)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoad(signal)
        if (signal?.aborted) return
        setReport(next)
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onLoad]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  useEffect(() => {
    if (!desktop) return
    let cancelled = false
    const refresh = async () => {
      const next = await desktopServerStatus()
      if (!cancelled && next) setDesktopStatus(next)
    }
    void refresh()
    const id = window.setInterval(() => void refresh(), 4000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [desktop])

  const runLifecycle = async (action: 'start' | 'stop' | 'restart') => {
    setLifecycleBusy(true)
    setError(null)
    try {
      const next =
        action === 'start'
          ? await desktopServerStart()
          : action === 'stop'
            ? await desktopServerStop()
            : await desktopServerRestart()
      setDesktopStatus(next)
      toast.success(
        action === 'start'
          ? 'Starting services…'
          : action === 'stop'
            ? 'Stopped'
            : 'Restarted'
      )
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLifecycleBusy(false)
    }
  }

  const clearCache = async () => {
    setConfirmClear(false)
    setClearing(true)
    setError(null)
    try {
      const cache = await onClearCache()
      setReport(current => (current ? { ...current, cache } : current))
      toast.success('Runtime cache cleared')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setClearing(false)
    }
  }

  const running = report?.status === 'running'

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <h2 className="text-2xl font-semibold">Status</h2>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {desktop ? (
          <section className="space-y-3 rounded-xl border px-4 py-4">
            <div>
              <p className="text-sm font-medium">Process control</p>
              <p className="text-muted-foreground text-xs">
                {desktopStatus?.label || 'Menubar supervisor'} — closing this
                window does not stop the agent.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={lifecycleBusy}
                onClick={() => void runLifecycle('start')}
              >
                Start
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={lifecycleBusy}
                onClick={() => void runLifecycle('stop')}
              >
                Stop
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={lifecycleBusy}
                onClick={() => void runLifecycle('restart')}
              >
                Restart
              </Button>
            </div>
          </section>
        ) : (
          <DesktopOnlyCallout feature="Server process control" />
        )}

        {loading && !report ? (
          <>
            <div className="bg-muted/40 rounded-xl border px-4 py-4">
              <SettingsBlockSkeleton />
            </div>
            <section>
              <SectionLabel>System</SectionLabel>
              <div className="bg-background rounded-2xl border px-4 py-2">
                <SettingsBlockSkeleton />
              </div>
            </section>
          </>
        ) : report ? (
          <>
            <SandwalkServerCard
              version={report.version}
              running={running}
              subtitle={listenSubtitle({
                running,
                host: report.host,
                port: report.port,
                message: report.message
              })}
            />
            <ServerStatusSystemSection report={report} />
            <ServerStatusCacheSection
              report={report}
              clearing={clearing}
              onRequestClear={() => setConfirmClear(true)}
            />
          </>
        ) : null}
      </div>

      <AlertDialog
        open={confirmClear}
        onOpenChange={open => {
          if (!open) setConfirmClear(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clear runtime cache?</AlertDialogTitle>
            <AlertDialogDescription>
              Clears files under{' '}
              <code className="font-mono">~/.sandwalk/cache</code>. Datasets
              and sessions are not deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={clearing}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={clearing}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void clearCache()
              }}
            >
              Clear cache
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}
