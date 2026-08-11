import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { DesktopOnlyCallout } from '@/components/agents/DesktopOnlyCallout'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { copyText } from '@/lib/clipboard'
import {
  type DesktopAuth,
  desktopGetAuth,
  desktopPutAuth,
  isTauri} from '@/lib/desktop'

export function ServerSecurityView() {
  const desktop = isTauri()
  const [auth, setAuth] = useState<DesktopAuth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showKey, setShowKey] = useState(false)

  const load = useCallback(async () => {
    if (!desktop) return
    setError(null)
    const next = await desktopGetAuth()
    if (!next) {
      setError('Menubar control plane unavailable. Is Sandwalk.app running?')
      return
    }
    setAuth(next)
  }, [desktop])

  useEffect(() => {
    void load()
  }, [load])

  const save = async (patch: Record<string, unknown>) => {
    setBusy(true)
    setError(null)
    try {
      const next = await desktopPutAuth(patch)
      setAuth(next)
      toast.success('Security settings saved')
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
          <h2 className="text-2xl font-semibold">Security</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Local API key authentication (same settings.json as{' '}
            <code className="font-mono">sandwalk auth</code>).
          </p>
        </div>

        {!desktop ? (
          <DesktopOnlyCallout feature="Security settings" />
        ) : (
          <>
            {error ? (
              <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
                {error}
              </div>
            ) : null}

            <section className="space-y-4 rounded-xl border px-4 py-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(auth?.auth_enabled)}
                  disabled={!auth || busy}
                  onChange={e =>
                    void save({ auth_enabled: e.target.checked })
                  }
                />
                Require API key authentication
              </label>

              <div className="space-y-2 text-sm">
                <p className="font-medium">API key</p>
                <div className="bg-muted/40 rounded-md border px-3 py-2 font-mono text-xs break-all">
                  {auth?.api_key
                    ? showKey
                      ? auth.api_key
                      : '••••••••••••••••••••••••'
                    : 'Not configured'}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!auth?.api_key}
                    onClick={() => setShowKey(v => !v)}
                  >
                    {showKey ? 'Hide' : 'Show'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!auth?.api_key}
                    onClick={() => {
                      if (!auth?.api_key) return
                      void copyText(auth.api_key).then(ok => {
                        if (ok) toast.success('API key copied')
                        else toast.error('Could not copy — select it manually')
                      })
                    }}
                  >
                    Copy
                  </Button>
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() => void save({ generate: true })}
                  >
                    Generate new key
                  </Button>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </ScrollArea>
  )
}
