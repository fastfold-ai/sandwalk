import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  desktopGetSettings,
  desktopPutSettings,
  type DesktopSettings,
  isTauri} from '@/lib/desktop'

export function ServerNetworkView() {
  const desktop = isTauri()
  const [settings, setSettings] = useState<DesktopSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState({
    bind_host: '127.0.0.1',
    port: 8787,
    dashboard_host: '127.0.0.1',
    dashboard_port: 8969
  })

  const load = useCallback(async () => {
    if (!desktop) return
    setError(null)
    const next = await desktopGetSettings()
    if (!next) {
      setError('Menubar control plane unavailable. Is Sandwalk.app running?')
      return
    }
    setSettings(next)
    setDraft({
      bind_host: next.bind_host,
      port: next.port,
      dashboard_host: next.dashboard_host,
      dashboard_port: next.dashboard_port
    })
  }, [desktop])

  useEffect(() => {
    void load()
  }, [load])

  const apply = async () => {
    setBusy(true)
    setError(null)
    try {
      const next = await desktopPutSettings({
        bind_host: draft.bind_host,
        port: draft.port,
        dashboard_host: draft.dashboard_host,
        dashboard_port: draft.dashboard_port
      })
      setSettings(next)
      toast.success('Network settings applied (services restarted if running)')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const remote =
    draft.bind_host === '0.0.0.0' || draft.dashboard_host === '0.0.0.0'

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-8 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">Network</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            API and dashboard bind addresses. Apply restarts supervised services.
          </p>
        </div>

        {!desktop ? (
          <DesktopOnlyCallout feature="Network settings" />
        ) : (
          <>
            {error ? (
              <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
                {error}
              </div>
            ) : null}

            <section className="space-y-4 rounded-xl border px-4 py-4">
              <label className="block space-y-1 text-sm">
                <span className="font-medium">API host</span>
                <input
                  className="bg-background w-full rounded-md border px-3 py-2 font-mono text-sm"
                  value={draft.bind_host}
                  onChange={e =>
                    setDraft(d => ({ ...d, bind_host: e.target.value }))
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-medium">API port</span>
                <input
                  type="number"
                  className="bg-background w-full rounded-md border px-3 py-2 font-mono text-sm"
                  value={draft.port}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      port: Number(e.target.value) || 8787
                    }))
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Dashboard host</span>
                <input
                  className="bg-background w-full rounded-md border px-3 py-2 font-mono text-sm"
                  value={draft.dashboard_host}
                  onChange={e =>
                    setDraft(d => ({ ...d, dashboard_host: e.target.value }))
                  }
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Dashboard port</span>
                <input
                  type="number"
                  className="bg-background w-full rounded-md border px-3 py-2 font-mono text-sm"
                  value={draft.dashboard_port}
                  onChange={e =>
                    setDraft(d => ({
                      ...d,
                      dashboard_port: Number(e.target.value) || 8969
                    }))
                  }
                />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={remote}
                  onChange={e => {
                    const host = e.target.checked ? '0.0.0.0' : '127.0.0.1'
                    setDraft(d => ({
                      ...d,
                      bind_host: host,
                      dashboard_host: host
                    }))
                  }}
                />
                Allow remote connections (bind 0.0.0.0)
              </label>
              {settings ? (
                <p className="text-muted-foreground text-xs">
                  Mode: {settings.dashboard_serve_mode} · auto-start:{' '}
                  {settings.auto_start ? 'on' : 'off'}
                </p>
              ) : null}
              <div className="flex justify-end">
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
