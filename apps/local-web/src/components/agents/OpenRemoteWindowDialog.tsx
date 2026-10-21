import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { SshBootstrapStep, SshHost } from '@sandwalk/agent-ui-core'
import {
  Bookmark,
  Check,
  Copy,
  Globe,
  KeyRound,
  Loader,
  Network,
  RefreshCw,
  Terminal
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import { LanTopologyScan } from '@/components/agents/lan-topology-scan'
import { SandwalkMark } from '@/components/SandwalkMark'
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
import { normalizeBackendUrl, readStoredBackendUrl } from '@/lib/backend-url'
import { copyText } from '@/lib/clipboard'
import {
  hideDesktopWindow,
  isTauri,
  type LanDesktopServer,
  openDesktopWindow,
  scanLanDesktopServers
} from '@/lib/desktop'
import {
  rememberRemoteHostname,
  rememberRemotePlatform
} from '@/lib/remote-hostname'
import { resolveBackendApiKey } from '@/lib/resolve-backend-api-key'
import { cn } from '@/lib/utils'

const CLI_REMOTE_SNIPPET = 'sandwalk serve --host 0.0.0.0 --port 8787'

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
  initialUrl,
  hideLauncherAfterOpen = false
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialUrl?: string | null
  /** When true (Welcome Home), hide this window after a remote opens. */
  hideLauncherAfterOpen?: boolean
}) {
  const [connectMode, setConnectMode] = useState<'ssh' | 'url'>('ssh')
  const [draftUrl, setDraftUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [hits, setHits] = useState<LanDesktopServer[]>([])
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null)
  const [showCli, setShowCli] = useState(true)
  const [copied, setCopied] = useState(false)
  const scanGen = useRef(0)

  // SSH 3-Step Flow State (Step 1: Host -> Step 2: Password/Alias -> Step 3: Bootstrap & Open)
  const [sshStep, setSshStep] = useState<1 | 2 | 3>(1)
  const [sshHosts, setSshHosts] = useState<SshHost[]>([])
  const [sshTarget, setSshTarget] = useState('')
  const [sshAlias, setSshAlias] = useState('')
  const [sshPassword, setSshPassword] = useState('')
  const [sshWorkdir, setSshWorkdir] = useState('')
  const [sshSteps, setSshSteps] = useState<SshBootstrapStep[]>([])
  const [sshConfigOpen, setSshConfigOpen] = useState(false)
  const [sshConfigContent, setSshConfigContent] = useState('')
  const [sshConfigPath, setSshConfigPath] = useState('~/.ssh/config')

  const getLocalClient = useCallback(async () => {
    const baseUrl = readStoredBackendUrl()
    const key = (await resolveBackendApiKey(baseUrl)) || undefined
    return new LocalAgentClient({ baseUrl, apiKey: key })
  }, [])

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

  const loadSshHosts = useCallback(async () => {
    try {
      const localClient = await getLocalClient()
      const rows = await localClient.listSshHosts(true)
      setSshHosts(rows)
    } catch {
      setSshHosts([])
    }
  }, [getLocalClient])

  useEffect(() => {
    if (!open) return
    const url = initialUrl?.trim() ? normalizeBackendUrl(initialUrl) : ''
    setDraftUrl(url)
    setConnectMode(url ? 'url' : 'ssh')
    setSshStep(1)
    setSshPassword('')
    setSshAlias('')
    setSshConfigOpen(false)
    setError(null)
    setBusy(false)
    setSelectedUrl(null)
    setHits([])
    setScanError(null)
    setShowCli(true)
    setCopied(false)
    setSshSteps([])
    void loadSshHosts()
    setScanning(isTauri())
    const timer = window.setTimeout(() => {
      void runScan()
    }, 0)
    return () => {
      window.clearTimeout(timer)
      scanGen.current += 1
    }
  }, [initialUrl, open, runScan, loadSshHosts])

  const pickHit = (hit: LanDesktopServer) => {
    const url = normalizeBackendUrl(hit.url)
    setDraftUrl(url)
    setSelectedUrl(url)
    setError(null)
  }

  const topologyNodes = useMemo(
    () =>
      hits.map(hit => {
        const url = normalizeBackendUrl(hit.url)
        const { title, detail } = splitDeviceLabel(
          hit.deviceLabel,
          hit.hostname
        )
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

  const submitUrl = async () => {
    if (!draftUrl.trim()) {
      setError('Enter a server URL')
      return
    }
    const url = normalizeBackendUrl(draftUrl)
    const selected = hits.find(hit => normalizeBackendUrl(hit.url) === url)
    setBusy(true)
    setError(null)
    try {
      const key = (await resolveBackendApiKey(url)) || null
      const hostname = selected?.hostname?.trim() || null
      const platform = selected?.platform?.trim() || null
      if (hostname) rememberRemoteHostname(url, hostname)
      if (platform) rememberRemotePlatform(url, platform)
      await openDesktopWindow({
        backendUrl: url,
        apiKey: key,
        hostname,
        platform,
        focusExisting: true
      })
      onOpenChange(false)
      if (hideLauncherAfterOpen && isTauri()) {
        void hideDesktopWindow().catch(() => {})
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not open window')
    } finally {
      setBusy(false)
    }
  }

  const runSshConnect = async (targetOverride?: string, password?: string) => {
    const target = (targetOverride ?? sshTarget).trim()
    if (!target) {
      setError('Type in a host like user@host or select from SSH config')
      return
    }
    setBusy(true)
    setError(null)
    setSshStep(3)
    setSshSteps([
      {
        step: 'probe',
        status: 'running',
        detail: `Connecting via SSH to ${target}...`
      }
    ])
    try {
      const localClient = await getLocalClient()
      const res = await localClient.connectAndBootstrapSsh({
        hostIdOrTarget: target,
        alias: sshAlias.trim() || null,
        password: password || null,
        saveToSshConfig: Boolean(sshAlias.trim()),
        autoInstall: true,
        startDaemon: true,
        openTunnel: true,
        enableWatchdog: true,
        defaultWorkdir: sshWorkdir.trim() || null
      })
      setSshSteps(res.steps || [])

      // If SSH key auth wasn't set up yet (`Permission denied`), step 2 prompts for password + custom alias!
      if (res.authRequired) {
        setSshStep(2)
        setError(
          password
            ? 'Password authentication failed. Check your password and try again.'
            : null
        )
        return
      }

      if (!res.localUrl) {
        const failedStep = (res.steps || []).find(s => s.status === 'failed')
        throw new Error(
          failedStep?.detail || 'Could not establish SSH tunnel to remote server'
        )
      }
      if (res.hostname) rememberRemoteHostname(res.localUrl, res.hostname)
      if (res.platform) rememberRemotePlatform(res.localUrl, res.platform)
      await openDesktopWindow({
        backendUrl: res.localUrl,
        apiKey: res.remoteApiKey || null,
        hostname: res.hostname || sshAlias.trim() || target,
        platform: res.platform || null,
        focusExisting: true
      })
      onOpenChange(false)
      if (hideLauncherAfterOpen && isTauri()) {
        void hideDesktopWindow().catch(() => {})
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not connect over SSH'
      )
    } finally {
      setBusy(false)
    }
  }

  const handleOpenSshConfig = async () => {
    try {
      const localClient = await getLocalClient()
      const cfg = await localClient.getSshConfigFile()
      setSshConfigPath(cfg.path)
      setSshConfigContent(cfg.content)
      setSshConfigOpen(true)
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not read ~/.ssh/config'
      )
    }
  }

  const handleSaveSshConfig = async () => {
    try {
      const localClient = await getLocalClient()
      await localClient.updateSshConfigFile(sshConfigContent)
      toast.success('Saved ~/.ssh/config')
      setSshConfigOpen(false)
      await loadSshHosts()
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not save ~/.ssh/config'
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="flex items-center justify-between pr-6">
            <DialogTitle className="flex items-center gap-2 text-sm font-medium">
              <span>
                {connectMode === 'ssh'
                  ? 'Connect via SSH'
                  : 'Connect via Direct URL / LAN'}
              </span>
            </DialogTitle>
            <button
              type="button"
              onClick={() => {
                setConnectMode(m => (m === 'ssh' ? 'url' : 'ssh'))
                setError(null)
              }}
              className="text-muted-foreground hover:text-foreground text-xs underline-offset-4 hover:underline"
            >
              {connectMode === 'ssh'
                ? 'Switch to Direct URL / LAN'
                : 'Switch to Connect via SSH'}
            </button>
          </div>
          <DialogDescription className="sr-only">
            Connect to a remote server over SSH or Direct URL
          </DialogDescription>
        </DialogHeader>

        {connectMode === 'ssh' ? (
          sshConfigOpen ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-mono">
                  {sshConfigPath}
                </span>
                <button
                  type="button"
                  onClick={() => setSshConfigOpen(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  Back
                </button>
              </div>
              <textarea
                value={sshConfigContent}
                onChange={e => setSshConfigContent(e.target.value)}
                rows={10}
                className="border-border bg-muted/40 w-full rounded-lg border p-3 font-mono text-xs leading-relaxed outline-none"
              />
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSshConfigOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void handleSaveSshConfig()}
                >
                  Save SSH Config
                </Button>
              </div>
            </div>
          ) : sshStep === 1 ? (
            /* STEP 1 OF 3: Clean VS Code / Cursor-style SSH Host Picker */
            <div className="space-y-3">
              <form
                onSubmit={e => {
                  e.preventDefault()
                  void runSshConnect()
                }}
                className="flex items-center gap-2"
              >
                <Input
                  value={sshTarget}
                  onChange={e => {
                    setSshTarget(e.target.value)
                    if (error) setError(null)
                  }}
                  placeholder="SSH Hostname (e.g. user@host)"
                  className="h-9 flex-1 font-mono text-xs"
                  autoFocus
                  spellCheck={false}
                />
                <Button
                  type="submit"
                  size="sm"
                  className="h-9 px-3.5 text-xs"
                  disabled={busy}
                >
                  {busy ? <Loader className="size-3.5 animate-spin" /> : null}
                  Connect ↵
                </Button>
              </form>

              {sshHosts.length > 0 ? (
                <div className="max-h-52 space-y-0.5 overflow-y-auto py-1">
                  {sshHosts.map(h => {
                    const targetStr = h.user ? `${h.user}@${h.host}` : h.host
                    return (
                      <button
                        key={h.id}
                        type="button"
                        onClick={() => {
                          setSshTarget(targetStr)
                          setSshAlias(h.alias)
                          if (h.defaultWorkdir) setSshWorkdir(h.defaultWorkdir)
                          void runSshConnect(targetStr)
                        }}
                        className="hover:bg-muted/60 flex w-full items-center justify-between rounded-md px-2.5 py-2 text-left text-xs transition-colors"
                      >
                        <span className="flex items-center gap-2.5 truncate">
                          {h.source === 'ssh_config' ? (
                            <Bookmark className="text-muted-foreground size-3.5 shrink-0" />
                          ) : (
                            <Globe className="text-muted-foreground size-3.5 shrink-0" />
                          )}
                          <span className="text-foreground truncate font-medium">
                            {h.alias}
                          </span>
                        </span>
                        <span className="text-muted-foreground ml-3 shrink-0 text-[11px]">
                          {h.user || 'SSH'}
                        </span>
                      </button>
                    )
                  })}
                </div>
              ) : null}

              {error ? (
                <p className="text-destructive text-xs" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="border-border/60 flex items-center justify-between border-t pt-2.5 text-[11px]">
                <span className="text-muted-foreground">
                  Type in a host like user@host or select from SSH config
                </span>
                <button
                  type="button"
                  onClick={() => void handleOpenSshConfig()}
                  className="text-primary hover:underline"
                >
                  Open SSH Config
                </button>
              </div>
            </div>
          ) : sshStep === 2 ? (
            /* STEP 2 OF 3: Password Prompt & Custom Hostname Setup */
            <form
              onSubmit={e => {
                e.preventDefault()
                void runSshConnect(sshTarget, sshPassword)
              }}
              className="space-y-3"
            >
              <div className="bg-muted/30 flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs">
                <KeyRound className="text-primary size-4 shrink-0" />
                <div>
                  <p className="text-foreground font-medium">
                    Authenticate with {sshTarget}
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Sandwalk will install your SSH public key so future
                    connections and automations work without a password.
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <div>
                  <label className="text-muted-foreground mb-1 block text-[11px]">
                    SSH Password for {sshTarget}
                  </label>
                  <Input
                    type="password"
                    value={sshPassword}
                    onChange={e => setSshPassword(e.target.value)}
                    placeholder="Enter SSH password..."
                    className="h-9 text-xs"
                    autoFocus
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-muted-foreground mb-1 block text-[11px]">
                      Custom Hostname / Alias (saved to SSH config)
                    </label>
                    <Input
                      value={sshAlias}
                      onChange={e => setSshAlias(e.target.value)}
                      placeholder="e.g. ubuntu-server"
                      className="h-8 text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-muted-foreground mb-1 block text-[11px]">
                      Default Remote Folder (optional)
                    </label>
                    <Input
                      value={sshWorkdir}
                      onChange={e => setSshWorkdir(e.target.value)}
                      placeholder="~/workspace"
                      className="h-8 font-mono text-xs"
                    />
                  </div>
                </div>
              </div>

              {error ? (
                <p className="text-destructive text-xs" role="alert">
                  {error}
                </p>
              ) : null}

              <div className="flex items-center justify-between pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSshStep(1)
                    setError(null)
                  }}
                >
                  Back
                </Button>
                <Button type="submit" size="sm" disabled={busy}>
                  {busy ? <Loader className="size-3.5 animate-spin" /> : null}
                  Authenticate & Connect ↵
                </Button>
              </div>
            </form>
          ) : (
            /* STEP 3 OF 3: Auto-Install & Tunnel Progress */
            <div className="space-y-3">
              <div className="bg-muted/40 space-y-1.5 rounded-lg border p-3 text-xs">
                {sshSteps.map(st => (
                  <div key={st.step} className="flex items-center gap-2">
                    <span
                      className={cn(
                        'size-2 rounded-full',
                        st.status === 'completed'
                          ? 'bg-emerald-400'
                          : st.status === 'failed'
                            ? 'bg-rose-400'
                            : 'bg-amber-400'
                      )}
                    />
                    <span className="font-medium capitalize">{st.step}:</span>
                    <span className="text-muted-foreground truncate">
                      {st.detail}
                    </span>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Input
                  value={sshAlias}
                  onChange={e => setSshAlias(e.target.value)}
                  placeholder="Custom Hostname / Alias"
                  className="h-8 text-xs"
                />
                <Input
                  value={sshWorkdir}
                  onChange={e => setSshWorkdir(e.target.value)}
                  placeholder="Remote folder (e.g. ~/workspace)"
                  className="h-8 font-mono text-xs"
                />
              </div>

              {error ? (
                <div className="space-y-2">
                  <p className="text-destructive text-xs" role="alert">
                    {error}
                  </p>
                  <div className="flex justify-between">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setSshStep(2)}
                    >
                      Enter Password / Alias
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => void runSshConnect()}
                    >
                      Retry
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          )
        ) : (
          /* Direct URL / LAN Mode */
          <form
            className="space-y-3"
            onSubmit={event => {
              event.preventDefault()
              void submitUrl()
            }}
          >
            <div className="text-muted-foreground space-y-2 text-xs">
              <p>
                On the other machine:{' '}
                <span className="text-foreground/90 inline-flex items-center gap-1">
                  <SandwalkMark className="size-3.5 shrink-0" />
                  Server Settings
                </span>{' '}
                →{' '}
                <span className="text-foreground/90 inline-flex items-center gap-1">
                  <Network className="size-3.5 shrink-0" aria-hidden />
                  Network
                </span>{' '}
                → Allow Remote Connections.
              </p>
              <div>
                <button
                  type="button"
                  className="text-foreground/90 inline-flex items-center gap-1.5 text-xs hover:underline"
                  onClick={() => setShowCli(v => !v)}
                  aria-expanded={showCli}
                >
                  <Terminal className="size-3.5 shrink-0" aria-hidden />
                  CLI equivalent
                </button>
                {showCli ? (
                  <div className="border-border bg-muted/40 mt-2 overflow-hidden rounded-md border">
                    <div className="flex items-center justify-between gap-2 border-b px-2 py-1">
                      <span className="text-muted-foreground truncate px-1 text-[11px] font-medium">
                        Network — Allow Remote Connections
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 shrink-0 gap-1 px-2"
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
                      <Loader className="size-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="size-3.5" />
                    )}
                    Rescan
                  </Button>
                </div>

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
                setDraftUrl(event.target.value)
                setSelectedUrl(null)
                if (error) setError(null)
              }}
              placeholder="http://<Local or remote>:8787"
              autoFocus
              autoComplete="url"
              spellCheck={false}
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
                {busy ? <Loader className="size-4 animate-spin" /> : null}
                Open window
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
