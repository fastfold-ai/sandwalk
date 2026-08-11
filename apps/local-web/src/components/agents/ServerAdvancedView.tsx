import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  desktopGetSettings,
  desktopPutSettings,
  desktopRebuildDashboard,
  type DesktopSettings,
  isTauri} from '@/lib/desktop'

export function ServerAdvancedView() {
  const desktop = isTauri()
  const [settings, setSettings] = useState<DesktopSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<'production' | 'development'>('production')
  const [dbAutoHeal, setDbAutoHeal] = useState(true)

  const load = useCallback(async () => {
    if (!desktop) return
    setError(null)
    const next = await desktopGetSettings()
    if (!next) {
      setError('Menubar control plane unavailable. Is Sandwalk.app running?')
      return
    }
    setSettings(next)
    setMode(
      next.dashboard_serve_mode === 'development' ? 'development' : 'production'
    )
    setDbAutoHeal(next.db_auto_heal)
  }, [desktop])

  useEffect(() => {
    void load()
  }, [load])

  const apply = async () => {
    setBusy(true)
    setError(null)
    try {
      const next = await desktopPutSettings({
        dashboard_serve_mode: mode,
        db_auto_heal: dbAutoHeal
      })
      setSettings(next)
      toast.success('Advanced settings applied')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const rebuild = async () => {
    setBusy(true)
    setError(null)
    try {
      await desktopRebuildDashboard()
      toast.success('Dashboard rebuilt')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-8 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">Advanced</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Dashboard serve mode and agent database recovery.
          </p>
        </div>

        {!desktop ? (
          <DesktopOnlyCallout feature="Advanced server settings" />
        ) : (
          <>
            {error ? (
              <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
                {error}
              </div>
            ) : null}

            <section className="space-y-4 rounded-xl border px-4 py-4">
              <div className="space-y-2 text-sm">
                <p className="font-medium">Dashboard mode</p>
                <label className="flex items-start gap-2">
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === 'production'}
                    onChange={() => setMode('production')}
                  />
                  <span>
                    <span className="font-medium">Production</span>
                    <span className="text-muted-foreground block">
                      Serve the built dashboard from the API (one process).
                    </span>
                  </span>
                </label>
                <label className="flex items-start gap-2">
                  <input
                    type="radio"
                    name="mode"
                    checked={mode === 'development'}
                    onChange={() => setMode('development')}
                  />
                  <span>
                    <span className="font-medium">Development</span>
                    <span className="text-muted-foreground block">
                      Run Vite with hot reload on the dashboard port.
                    </span>
                  </span>
                </label>
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={dbAutoHeal}
                  onChange={e => setDbAutoHeal(e.target.checked)}
                />
                Auto-heal corrupt agent database on start
              </label>

              {settings ? (
                <p className="text-muted-foreground text-xs">
                  Current mode: {settings.dashboard_serve_mode}
                </p>
              ) : null}

              <div className="flex flex-wrap justify-end gap-2">
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => void rebuild()}
                >
                  Rebuild dashboard
                </Button>
                <Button disabled={busy} onClick={() => void apply()}>
                  {busy ? 'Applying…' : 'Apply'}
                </Button>
              </div>
            </section>
          </>
        )}
      </div>
    </ScrollArea>
  )
}
