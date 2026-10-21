import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  SshBootstrapStep,
  SshHost,
  SshSlurmQueueEntry
} from '@sandwalk/agent-ui-core'
import {
  Bookmark,
  ChevronDown,
  Globe,
  KeyRound,
  Loader2,
  RefreshCw,
  Terminal,
  Trash2
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { isTauri, openDesktopWindow } from '@/lib/desktop'
import { persistRememberedApiKey } from '@/lib/remembered-auth'
import {
  rememberRemoteHostname,
  rememberRemotePlatform
} from '@/lib/remote-hostname'
import { cn } from '@/lib/utils'

export function SshView({ client }: { client: LocalAgentClient }) {
  const [sshHosts, setSshHosts] = useState<SshHost[]>([])
  const [loading, setLoading] = useState(true)
  const [sshStep, setSshStep] = useState<1 | 2 | 3>(1)
  const [sshTarget, setSshTarget] = useState('')
  const [sshAlias, setSshAlias] = useState('')
  const [sshPassword, setSshPassword] = useState('')
  const [sshWorkdir, setSshWorkdir] = useState('')
  const [selectedSshHostId, setSelectedSshHostId] = useState<string | null>(
    null
  )
  const [sshBusy, setSshBusy] = useState(false)
  const [bootstrapSteps, setBootstrapSteps] = useState<SshBootstrapStep[]>([])
  const [sshConfigOpen, setSshConfigOpen] = useState(false)
  const [sshConfigPath, setSshConfigPath] = useState('~/.ssh/config')
  const [sshConfigContent, setSshConfigContent] = useState('')
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [sshExecCmd, setSshExecCmd] = useState('uptime && df -h .')
  const [sshExecOutput, setSshExecOutput] = useState<string | null>(null)
  const [slurmJobs, setSlurmJobs] = useState<SshSlurmQueueEntry[]>([])

  const refreshHosts = useCallback(async () => {
    try {
      const hostList = await client.listSshHosts(true).catch(() => [])
      setSshHosts(hostList)
      if (!selectedSshHostId && hostList.length > 0) {
        setSelectedSshHostId(hostList[0].id)
      }
    } finally {
      setLoading(false)
    }
  }, [client, selectedSshHostId])

  useEffect(() => {
    void refreshHosts()
  }, [refreshHosts])

  const activeSshHost =
    sshHosts.find(h => h.id === selectedSshHostId) || sshHosts[0] || null

  const handleConnectSsh = async (
    targetOverride?: string,
    passwordOverride?: string
  ) => {
    const target = (targetOverride ?? sshTarget).trim()
    if (!target) {
      toast.error('Type in a host like user@host or select from SSH config')
      return
    }
    setSshBusy(true)
    setSshStep(3)
    setBootstrapSteps([
      {
        step: 'probe',
        status: 'running',
        detail: `Connecting via SSH to ${target}...`
      }
    ])
    try {
      const res = await client.connectAndBootstrapSsh({
        hostIdOrTarget: target,
        alias: sshAlias.trim() || null,
        password: passwordOverride || null,
        saveToSshConfig: Boolean(sshAlias.trim()),
        autoInstall: true,
        startDaemon: true,
        openTunnel: true,
        enableWatchdog: true,
        defaultWorkdir: sshWorkdir.trim() || null
      })
      setBootstrapSteps(res.steps || [])
      await refreshHosts()
      if (res.host?.id) setSelectedSshHostId(res.host.id)

      if (res.authRequired) {
        setSshStep(2)
        if (passwordOverride) {
          toast.error(
            'Password authentication failed. Check your password and try again.'
          )
        }
        return
      }

      if (res.localUrl) {
        const remoteHostLabel =
          res.hostname ||
          res.host?.hostname ||
          res.host?.alias ||
          sshAlias.trim() ||
          target
        const remotePlatform =
          res.platform || res.host?.platform || 'Linux'
        rememberRemoteHostname(res.localUrl, remoteHostLabel)
        rememberRemotePlatform(res.localUrl, remotePlatform)
        if (res.remoteApiKey) {
          persistRememberedApiKey(res.localUrl, res.remoteApiKey)
        }
        if (isTauri()) {
          await openDesktopWindow({
            backendUrl: res.localUrl,
            apiKey: res.remoteApiKey || null,
            title: remoteHostLabel,
            hostname: remoteHostLabel,
            platform: remotePlatform,
            route: '/agents/new',
            focusExisting: true
          })
          toast.success(`Opened remote window for ${remoteHostLabel}`)
        } else {
          toast.success(
            `Connected & tunneled at ${res.localUrl} (${res.daemonPersistence || 'persistent'})`
          )
        }
        setSshStep(1)
        setSshPassword('')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'SSH connection failed')
    } finally {
      setSshBusy(false)
    }
  }

  const handleOpenSshConfig = async () => {
    try {
      const cfg = await client.getSshConfigFile()
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
      await client.updateSshConfigFile(sshConfigContent)
      toast.success('Saved ~/.ssh/config')
      setSshConfigOpen(false)
      await refreshHosts()
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not save ~/.ssh/config'
      )
    }
  }

  const handleProbeSsh = async (host: SshHost) => {
    setSshBusy(true)
    try {
      const res = await client.probeSshHost(host.id)
      if (res.reachable) {
        toast.success(
          `Connected to ${res.hostname || host.alias} (${res.platform || 'Linux'})`
        )
      } else if (res.authRequired) {
        setSshTarget(host.user ? `${host.user}@${host.host}` : host.host)
        setSshAlias(host.alias)
        setSshStep(2)
        toast.message(`Password required for ${host.alias}`)
      } else {
        toast.error(`Unreachable: ${res.detail || 'SSH connection failed'}`)
      }
      await refreshHosts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'SSH probe failed')
    } finally {
      setSshBusy(false)
    }
  }

  const handleRunSshCommand = async (host: SshHost) => {
    if (!sshExecCmd.trim()) return
    setSshBusy(true)
    try {
      const [execRes, slurmRes] = await Promise.all([
        client.execSshCommand({
          hostIdOrTarget: host.id,
          command: sshExecCmd.trim()
        }),
        client.getSshSlurmStatus(host.id).catch(() => null)
      ])
      setSshExecOutput(
        (
          execRes.stdout + (execRes.stderr ? `\n${execRes.stderr}` : '')
        ).trim() || `(exit ${execRes.exitCode})`
      )
      if (slurmRes) setSlurmJobs(slurmRes.jobs || [])
    } catch (err) {
      setSshExecOutput(
        err instanceof Error ? err.message : 'Remote command failed'
      )
    } finally {
      setSshBusy(false)
    }
  }

  const handleRemoveSshHost = async (host: SshHost) => {
    try {
      await client.deleteSshHost(host.id)
      toast.success(`Removed ${host.alias}`)
      await refreshHosts()
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Could not remove SSH host'
      )
    }
  }

  return (
    <div className="mx-auto flex h-full w-full max-w-7xl flex-col px-4 pt-6 pb-8 md:px-6 md:pt-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">SSH</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Connect to remote servers over SSH. Sandwalk installs automatically
            in user space and keeps running in the background after you
            disconnect.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 gap-1.5"
          onClick={() => void refreshHosts()}
        >
          <RefreshCw className="size-3.5" />
          Refresh
        </Button>
      </div>

      <div className="chat-scrollbar flex-1 space-y-5 overflow-y-auto pr-1 pb-10">
        {/* Clean VS Code / Cursor-style Connect via SSH Card */}
        <div className="border-border/60 bg-card/40 space-y-3 rounded-xl border p-4">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">Connect via SSH</span>
            {sshStep !== 1 ? (
              <button
                type="button"
                onClick={() => setSshStep(1)}
                className="text-muted-foreground hover:text-foreground text-xs"
              >
                Back to hosts
              </button>
            ) : null}
          </div>

          {sshConfigOpen ? (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground font-mono">
                  {sshConfigPath}
                </span>
                <button
                  type="button"
                  onClick={() => setSshConfigOpen(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  Close
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
            <>
              <form
                onSubmit={e => {
                  e.preventDefault()
                  void handleConnectSsh()
                }}
                className="flex items-center gap-2"
              >
                <Input
                  value={sshTarget}
                  onChange={e => setSshTarget(e.target.value)}
                  placeholder="SSH Hostname (e.g. user@host)"
                  className="h-9 flex-1 font-mono text-xs"
                  spellCheck={false}
                />
                <Button
                  type="submit"
                  size="sm"
                  className="h-9 px-3.5 text-xs"
                  disabled={sshBusy}
                >
                  {sshBusy ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : null}
                  Connect ↵
                </Button>
              </form>

              <div className="max-h-56 space-y-0.5 overflow-y-auto py-1">
                {loading ? (
                  <p className="text-muted-foreground px-2 py-3 text-xs">
                    Loading SSH hosts...
                  </p>
                ) : (
                  sshHosts.map(h => {
                    const targetStr = h.user ? `${h.user}@${h.host}` : h.host
                    const isSelected = activeSshHost?.id === h.id
                    return (
                      <div
                        key={h.id}
                        onClick={() => {
                          setSelectedSshHostId(h.id)
                          setSshTarget(targetStr)
                          setSshAlias(h.alias)
                          if (h.defaultWorkdir) setSshWorkdir(h.defaultWorkdir)
                        }}
                        onDoubleClick={() => void handleConnectSsh(targetStr)}
                        className={cn(
                          'hover:bg-muted/60 flex cursor-pointer items-center justify-between rounded-md px-2.5 py-2 text-xs transition-colors',
                          isSelected && 'bg-muted/50'
                        )}
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
                          {h.host !== h.alias ? (
                            <span className="text-muted-foreground font-mono text-[11px]">
                              {targetStr}
                            </span>
                          ) : null}
                        </span>
                        <span className="text-muted-foreground ml-3 flex items-center gap-2 text-[11px]">
                          <span
                            className={cn(
                              'size-1.5 rounded-full',
                              h.status === 'tunnel_active' ||
                                h.status === 'online'
                                ? 'bg-emerald-400'
                                : h.status === 'offline'
                                  ? 'bg-rose-400'
                                  : 'bg-muted-foreground/40'
                            )}
                          />
                          {h.user || 'SSH'}
                        </span>
                      </div>
                    )
                  })
                )}
              </div>

              <div className="border-border/60 flex items-center justify-between border-t pt-2.5 text-[11px]">
                <span className="text-muted-foreground">
                  Type in a host like user@host or select from SSH config
                </span>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setSshStep(2)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    Custom Hostname / Password
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleOpenSshConfig()}
                    className="text-primary hover:underline"
                  >
                    Open SSH Config
                  </button>
                </div>
              </div>
            </>
          ) : sshStep === 2 ? (
            /* Step 2: Password Prompt & Custom Hostname Setup */
            <form
              onSubmit={e => {
                e.preventDefault()
                void handleConnectSsh(sshTarget, sshPassword)
              }}
              className="space-y-3"
            >
              <div className="bg-muted/30 flex items-center gap-2.5 rounded-lg border px-3 py-2 text-xs">
                <KeyRound className="text-primary size-4 shrink-0" />
                <div>
                  <p className="text-foreground font-medium">
                    SSH Authentication & Custom Hostname
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    If the server requires a password, Sandwalk installs your
                    SSH public key on first login so future connections and
                    automations work passwordlessly.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <div>
                  <label className="text-muted-foreground mb-1 block text-[11px]">
                    SSH Host (`user@host`)
                  </label>
                  <Input
                    value={sshTarget}
                    onChange={e => setSshTarget(e.target.value)}
                    placeholder="user@remote-server"
                    className="h-8 font-mono text-xs"
                  />
                </div>
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
                    SSH Password (optional if key is already authorized)
                  </label>
                  <Input
                    type="password"
                    value={sshPassword}
                    onChange={e => setSshPassword(e.target.value)}
                    placeholder="Enter password to authorize SSH key..."
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

              <div className="flex justify-end gap-2 pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setSshStep(1)}
                >
                  Back
                </Button>
                <Button type="submit" size="sm" disabled={sshBusy}>
                  {sshBusy ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : null}
                  Save & Connect ↵
                </Button>
              </div>
            </form>
          ) : (
            /* Step 3: Auto-Install & Tunnel Progress */
            <div className="space-y-2.5">
              <div className="bg-muted/40 space-y-1.5 rounded-lg border p-3 text-xs">
                {bootstrapSteps.map(st => (
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
            </div>
          )}
        </div>

        {/* Selected Host Summary Card */}
        {activeSshHost ? (
          <div className="border-border/60 bg-card/30 space-y-3 rounded-xl border p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">{activeSshHost.alias}</h3>
                <p className="text-muted-foreground font-mono text-xs">
                  {activeSshHost.user ? `${activeSshHost.user}@` : ''}
                  {activeSshHost.host}:{activeSshHost.port}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {activeSshHost.source === 'saved' ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-destructive h-7 px-2"
                    onClick={() => void handleRemoveSshHost(activeSshHost)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={sshBusy}
                  onClick={() => void handleProbeSsh(activeSshHost)}
                >
                  Probe Host
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="h-7 text-xs"
                  disabled={sshBusy}
                  onClick={() =>
                    void handleConnectSsh(
                      activeSshHost.user
                        ? `${activeSshHost.user}@${activeSshHost.host}`
                        : activeSshHost.host
                    )
                  }
                >
                  Connect Window
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 text-xs">
              <div className="bg-muted/30 rounded-lg p-2.5">
                <span className="text-muted-foreground block text-[10px]">
                  Platform
                </span>
                <span className="font-medium">
                  {activeSshHost.platform || 'Not probed'}{' '}
                  {activeSshHost.arch || ''}
                </span>
              </div>
              <div className="bg-muted/30 rounded-lg p-2.5">
                <span className="text-muted-foreground block text-[10px]">
                  Sandwalk Server
                </span>
                <span className="font-medium">
                  {activeSshHost.sandwalkInstalled
                    ? activeSshHost.sandwalkVersion || 'Installed'
                    : 'Auto-installs on connect'}
                </span>
              </div>
              <div className="bg-muted/30 rounded-lg p-2.5">
                <span className="text-muted-foreground block text-[10px]">
                  Connection
                </span>
                <span className="font-medium">
                  {activeSshHost.status === 'tunnel_active'
                    ? 'Tunnel Active'
                    : 'SSH Ready'}
                </span>
              </div>
            </div>

            <div className="border-t pt-2">
              <button
                type="button"
                onClick={() => setConsoleOpen(v => !v)}
                className="text-muted-foreground hover:text-foreground flex w-full items-center justify-between text-xs font-medium"
              >
                <span>Run Remote Command</span>
                <ChevronDown
                  className={cn(
                    'size-3.5 transition-transform',
                    consoleOpen && 'rotate-180'
                  )}
                />
              </button>

              {consoleOpen ? (
                <div className="mt-2.5 space-y-2">
                  <div className="flex gap-2">
                    <Input
                      value={sshExecCmd}
                      onChange={e => setSshExecCmd(e.target.value)}
                      placeholder="uptime && df -h ."
                      className="h-8 flex-1 font-mono text-xs"
                    />
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="h-8 gap-1.5"
                      disabled={sshBusy}
                      onClick={() => void handleRunSshCommand(activeSshHost)}
                    >
                      <Terminal className="size-3.5" />
                      Run via SSH
                    </Button>
                  </div>
                  {sshExecOutput !== null ? (
                    <pre className="bg-muted/50 max-h-48 overflow-auto rounded-lg p-3 font-mono text-[11px] whitespace-pre-wrap">
                      {sshExecOutput}
                    </pre>
                  ) : null}
                  {slurmJobs.length > 0 ? (
                    <div className="space-y-1 pt-1">
                      <p className="text-xs font-medium">
                        Active Queue Jobs ({slurmJobs.length})
                      </p>
                      {slurmJobs.map(j => (
                        <div
                          key={j.jobId}
                          className="bg-muted/30 flex items-center justify-between rounded px-2.5 py-1.5 font-mono text-[11px]"
                        >
                          <span>
                            #{j.jobId} · {j.name} ({j.partition})
                          </span>
                          <span>
                            {j.state} · {j.timeUsed}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
