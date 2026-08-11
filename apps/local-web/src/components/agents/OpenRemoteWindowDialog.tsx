import {
  Check,
  Copy,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Network,
  RefreshCw,
  Terminal
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { LanTopologyScan } from '@/components/agents/lan-topology-scan'
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
import { normalizeBackendUrl } from '@/lib/backend-url'
import { copyText } from '@/lib/clipboard'
import {
  isTauri,
  type LanDesktopServer,
  openDesktopWindow,
  scanLanDesktopServers
} from '@/lib/desktop'
import { persistRememberedApiKey, readRememberedApiKey } from '@/lib/remembered-auth'
import { rememberRemoteHostname } from '@/lib/remote-hostname'

const CLI_REMOTE_SNIPPET = [
  '# Security — API key',
  'sandwalk auth generate',
  'sandwalk auth enable',
  'sandwalk auth show',
  '',
  '# Network — Allow Remote Connections',
  'sandwalk serve --host 0.0.0.0 --port 8787'
].join('\n')

function splitDeviceLabel(label: string, hostname: string) {
  const parts = label
    .split('·')
    .map(part => part.trim())
    .filter(Boolean)
  if (parts.length === 0) {
    return { title: hostname || 'Sandwalk', detail: '' }
  }
  return {
    title: parts[0],
    detail: parts.slice(1).join(' · ')
  }
}

export function OpenRemoteWindowDialog({
  open,
  onOpenChange,
  initialUrl
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialUrl?: string | null
}) {
  const [draftUrl, setDraftUrl] = useState('')
  const [draftKey, setDraftKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [hits, setHits] = useState<LanDesktopServer[]>([])
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null)
  const [showCli, setShowCli] = useState(false)
  const [copied, setCopied] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const scanGen = useRef(0)

  const runScan = useCallback(async () => {
    if (!isTauri()) return
    const gen = ++scanGen.current
    setScanning(true)
    setScanError(null)
    try {
      const rows = await scanLanDesktopServers()
      if (gen !== scanGen.current) return
      setHits(rows)
    } catch (err) {
      if (gen !== scanGen.current) return
      setHits([])
      setScanError(
        err instanceof Error ? err.message : 'Could not scan the local network'
      )
    } finally {
      if (gen === scanGen.current) setScanning(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    const url = initialUrl?.trim()
      ? normalizeBackendUrl(initialUrl)
      : ''
    setDraftUrl(url)
    setDraftKey(url ? readRememberedApiKey(url) || '' : '')
    setError(null)
    setBusy(false)
    setSelectedUrl(null)
    setHits([])
    setScanError(null)
    setShowCli(false)
    setCopied(false)
    setShowKey(false)
    // Paint the dialog first; discover runs in the background (async Tauri cmd).
    setScanning(isTauri())
    const timer = window.setTimeout(() => {
      void runScan()
    }, 0)
    return () => {
      window.clearTimeout(timer)
      scanGen.current += 1
    }
  }, [initialUrl, open, runScan])

  const pickHit = (hit: LanDesktopServer) => {
    // Prefer LAN IP in the URL field (hit.url) — more reliable than .local mDNS.
    const url = normalizeBackendUrl(hit.url)
    setDraftUrl(url)
    setSelectedUrl(url)
    setError(null)
    const remembered = readRememberedApiKey(url)
    if (remembered) setDraftKey(remembered)
  }

  const topologyNodes = useMemo(
    () =>
      hits.map(hit => {
        const url = normalizeBackendUrl(hit.url)
        const { title, detail } = splitDeviceLabel(hit.deviceLabel, hit.hostname)
        return {
          ...hit,
          url,
          title,
          detail,
          hostLine: url.replace(/^https?:\/\//, '')
        }
      }),
    [hits]
  )

  const copyCli = async () => {
    const ok = await copyText(CLI_REMOTE_SNIPPET)
    if (!ok) return
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  const submit = async () => {
    if (!draftUrl.trim()) {
      setError('Enter a server URL')
      return
    }
    const url = normalizeBackendUrl(draftUrl)
    const key = draftKey.trim()
    const selected = hits.find(hit => normalizeBackendUrl(hit.url) === url)
    if (selected?.authRequired && !key) {
      setError('This server requires an API key')
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (key) persistRememberedApiKey(url, key)
      const hostname = selected?.hostname?.trim() || null
      if (hostname) rememberRemoteHostname(url, hostname)
      await openDesktopWindow({
        backendUrl: url,
        apiKey: key || null,
        hostname,
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
                  onClick={() => {
                    setHits([])
                    void runScan()
                  }}
                >
                  {scanning ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  Rescan
                </Button>
              </div>

              {scanError ? (
                <p className="text-destructive text-sm" role="alert">
                  {scanError}
                </p>
              ) : null}

              {!scanError ? (
                <LanTopologyScan
                  active={scanning}
                  nodes={topologyNodes}
                  selectedUrl={selectedUrl || draftUrl}
                  onSelect={node => pickHit(node)}
                />
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
            placeholder="http://<Local or remote>"
            autoFocus
            autoComplete="url"
            spellCheck={false}
          />
          <div className="relative">
            <Input
              type={showKey ? 'text' : 'password'}
              value={draftKey}
              onChange={event => {
                setDraftKey(event.target.value)
                if (error) setError(null)
              }}
              placeholder="API key (if the server requires auth)"
              autoComplete="off"
              className="pr-10"
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="text-muted-foreground absolute top-1/2 right-1 size-8 -translate-y-1/2"
              onClick={() => setShowKey(v => !v)}
              aria-label={showKey ? 'Hide API key' : 'Show API key'}
            >
              {showKey ? (
                <EyeOff className="size-4" />
              ) : (
                <Eye className="size-4" />
              )}
            </Button>
          </div>
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
