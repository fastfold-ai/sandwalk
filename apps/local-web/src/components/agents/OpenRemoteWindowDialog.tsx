import { Check, Copy, Loader2, Lock, Network, RefreshCw, Terminal } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { DEFAULT_BACKEND_URL, normalizeBackendUrl } from '@/lib/backend-url'
import { copyText } from '@/lib/clipboard'
import {
  isTauri,
  openDesktopWindow,
  scanLanDesktopServers,
  type LanDesktopServer
} from '@/lib/desktop'
import { persistRememberedApiKey, readRememberedApiKey } from '@/lib/remembered-auth'
import { cn } from '@/lib/utils'

const CLI_REMOTE_SNIPPET = [
  '# Security — API key',
  'sandwalk auth generate',
  'sandwalk auth enable',
  'sandwalk auth show',
  '',
  '# Network — Allow Remote Connections',
  'sandwalk serve --host 0.0.0.0 --port 8787'
].join('\n')

export function OpenRemoteWindowDialog({
  open,
  onOpenChange,
  initialUrl
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialUrl?: string | null
}) {
  const [draftUrl, setDraftUrl] = useState(DEFAULT_BACKEND_URL)
  const [draftKey, setDraftKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [hits, setHits] = useState<LanDesktopServer[]>([])
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null)
  const [showCli, setShowCli] = useState(false)
  const [copied, setCopied] = useState(false)

  const runScan = useCallback(async () => {
    if (!isTauri()) return
    setScanning(true)
    setScanError(null)
    try {
      const rows = await scanLanDesktopServers()
      setHits(rows)
    } catch (err) {
      setHits([])
      setScanError(
        err instanceof Error ? err.message : 'Could not scan the local network'
      )
    } finally {
      setScanning(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const url = normalizeBackendUrl(initialUrl || DEFAULT_BACKEND_URL)
    setDraftUrl(url)
    setDraftKey(readRememberedApiKey(url) || '')
    setError(null)
    setBusy(false)
    setSelectedUrl(null)
    setHits([])
    setScanError(null)
    setShowCli(false)
    setCopied(false)
    void runScan()
  }, [initialUrl, open, runScan])

  const pickHit = (hit: LanDesktopServer) => {
    const url = normalizeBackendUrl(hit.url)
    setDraftUrl(url)
    setSelectedUrl(url)
    const remembered = readRememberedApiKey(url)
    if (remembered) setDraftKey(remembered)
    setError(
      hit.authRequired && !remembered
        ? 'This server requires an API key'
        : null
    )
  }

  const copyCli = async () => {
    const ok = await copyText(CLI_REMOTE_SNIPPET)
    if (!ok) return
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const submit = async () => {
    const url = normalizeBackendUrl(draftUrl)
    if (!url) {
      setError('Enter a server URL')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const key = draftKey.trim()
      if (key) persistRememberedApiKey(url, key)
      await openDesktopWindow({
        backendUrl: url,
        apiKey: key || null,
        // Explicit Remote always opens a window; Open Recent uses focusExisting.
        focusExisting: false
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open window')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Window (Remote)</DialogTitle>
          <DialogDescription asChild>
            <div className="text-muted-foreground space-y-2 text-sm">
              <p>
                On the other machine: Server Settings →{' '}
                <span className="text-foreground/90 inline-flex items-center gap-1">
                  <Network className="size-3.5 shrink-0" aria-hidden />
                  Network
                </span>{' '}
                → Allow Remote Connections;{' '}
                <span className="text-foreground/90 inline-flex items-center gap-1">
                  <Lock className="size-3.5 shrink-0" aria-hidden />
                  Security
                </span>{' '}
                for the API key.
              </p>
              <div>
                <button
                  type="button"
                  className="text-foreground/90 inline-flex items-center gap-1.5 text-sm hover:underline"
                  onClick={() => setShowCli(v => !v)}
                  aria-expanded={showCli}
                >
                  <Terminal className="size-3.5 shrink-0" aria-hidden />
                  CLI equivalent
                </button>
                {showCli ? (
                  <div className="border-border bg-muted/40 mt-2 overflow-hidden rounded-md border">
                    <div className="flex items-center justify-end border-b px-2 py-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1 px-2"
                        onClick={() => void copyCli()}
                      >
                        {copied ? (
                          <Check className="size-3.5" />
                        ) : (
                          <Copy className="size-3.5" />
                        )}
                        {copied ? 'Copied' : 'Copy'}
                      </Button>
                    </div>
                    <pre className="overflow-x-auto p-3 font-mono text-[11px] leading-relaxed whitespace-pre">
                      {CLI_REMOTE_SNIPPET}
                    </pre>
                  </div>
                ) : null}
              </div>
            </div>
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-3"
          onSubmit={event => {
            event.preventDefault()
            void submit()
          }}
        >
          {isTauri() ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                  Nearby servers
                </p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2"
                  disabled={scanning}
                  onClick={() => void runScan()}
                >
                  {scanning ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  Rescan
                </Button>
              </div>
              {scanning && hits.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  Scanning local network…
                </p>
              ) : null}
              {scanError ? (
                <p className="text-destructive text-sm" role="alert">
                  {scanError}
                </p>
              ) : null}
              {!scanning && !scanError && hits.length === 0 ? (
                <p className="text-muted-foreground text-sm">
                  No servers found on this network.
                </p>
              ) : null}
              {hits.length > 0 ? (
                <ul className="max-h-40 space-y-1 overflow-y-auto">
                  {hits.map(hit => {
                    const url = normalizeBackendUrl(hit.url)
                    const active = selectedUrl === url || draftUrl === url
                    return (
                      <li key={hit.url}>
                        <button
                          type="button"
                          onClick={() => pickHit(hit)}
                          className={cn(
                            'w-full rounded-md border px-3 py-2 text-left transition-colors',
                            active
                              ? 'border-foreground/30 bg-muted'
                              : 'border-border hover:bg-muted/60'
                          )}
                        >
                          <div className="text-sm font-medium">
                            {hit.deviceLabel}
                          </div>
                          <div className="text-muted-foreground truncate text-xs">
                            {hit.hostname}
                            {hit.authRequired ? ' · API key required' : ''}
                            {' · '}
                            {url.replace(/^https?:\/\//, '')}
                          </div>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              ) : null}
            </div>
          ) : null}
          <Input
            value={draftUrl}
            onChange={event => {
              const next = event.target.value
              setDraftUrl(next)
              setSelectedUrl(null)
              const normalized = normalizeBackendUrl(next)
              const remembered = readRememberedApiKey(normalized)
              if (remembered && !draftKey) setDraftKey(remembered)
            }}
            placeholder="http://192.168.1.10:8787"
            autoFocus
            autoComplete="url"
            spellCheck={false}
          />
          <Input
            type="password"
            value={draftKey}
            onChange={event => setDraftKey(event.target.value)}
            placeholder="API key (if the server requires auth)"
            autoComplete="off"
          />
          {error ? (
            <p className="text-destructive text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" /> : null}
              Open window
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
