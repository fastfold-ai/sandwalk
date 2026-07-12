import type { AccountSummary } from '@sandwalk/agent-ui-core'
import {
  ExternalLink,
  Loader2,
  LogOut,
  RefreshCw
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

function formatCheckedAt(date: Date | null) {
  if (!date) return 'never'
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 8) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  return date.toLocaleTimeString()
}

function normalizeBackendUrl(value: string) {
  return value.trim().replace(/\/+$/, '')
}

export function GeneralView({
  backendUrl,
  backendVersion,
  connected,
  onCheckBackend,
  onUpdateBackendUrl,
  onLoadAccount,
  onLogoutAccount
}: {
  backendUrl: string
  backendVersion: string | null
  connected: boolean
  onCheckBackend: () => Promise<boolean>
  onUpdateBackendUrl: (url: string) => Promise<boolean>
  onLoadAccount: (options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }) => Promise<AccountSummary>
  onLogoutAccount: (signal?: AbortSignal) => Promise<AccountSummary>
}) {
  const navigate = useNavigate()
  const [account, setAccount] = useState<AccountSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [checkingUpdates, setCheckingUpdates] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [backendOk, setBackendOk] = useState(connected)
  const [checkingBackend, setCheckingBackend] = useState(false)
  const [draftBackendUrl, setDraftBackendUrl] = useState(backendUrl)
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

  const backendDirty =
    normalizeBackendUrl(draftBackendUrl) !== normalizeBackendUrl(backendUrl)

  useEffect(() => {
    setDraftBackendUrl(backendUrl)
  }, [backendUrl])

  const loadAccount = useCallback(
    async (checkUpdates = false, signal?: AbortSignal) => {
      if (checkUpdates) setCheckingUpdates(true)
      else setLoading(true)
      setError(null)
      try {
        const next = await onLoadAccount({
          checkUpdates,
          signal
        })
        if (signal?.aborted) return
        setAccount(next)
        if (checkUpdates) setLastCheckedAt(new Date())
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) {
          setLoading(false)
          setCheckingUpdates(false)
        }
      }
    },
    [onLoadAccount]
  )

  useEffect(() => {
    const controller = new AbortController()
    void loadAccount(false, controller.signal)
    return () => controller.abort()
  }, [loadAccount])

  useEffect(() => {
    setBackendOk(connected)
  }, [connected])

  const refreshBackend = async () => {
    setCheckingBackend(true)
    setError(null)
    try {
      if (backendDirty) {
        const nextUrl = normalizeBackendUrl(draftBackendUrl)
        if (!nextUrl) {
          setError('Backend URL is required.')
          setBackendOk(false)
          return
        }
        setBackendOk(await onUpdateBackendUrl(nextUrl))
        return
      }
      setBackendOk(await onCheckBackend())
    } catch (err) {
      setBackendOk(false)
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingBackend(false)
    }
  }

  const signOut = async () => {
    if (
      !window.confirm(
        'Remove the FastFold Cloud API key from this local agent?'
      )
    ) {
      return
    }
    setSigningOut(true)
    setError(null)
    try {
      setAccount(await onLogoutAccount())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSigningOut(false)
    }
  }

  const about = account?.about
  const email = account?.user?.email?.trim() || null
  const planLabel = account?.user?.planLabel?.trim() || null
  const orgName = account?.organization?.name?.trim() || null
  const orgId = account?.organization?.id?.trim() || null
  const showCloudAccount = Boolean(account?.configured)

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">General</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Account, local backend connection, and app details.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {loading && !account ? (
          <section className="space-y-4 border-b pb-8">
            <h3 className="text-base font-semibold">Account</h3>
            <SettingsBlockSkeleton />
          </section>
        ) : showCloudAccount ? (
          <>
            <section className="space-y-4 border-b pb-8">
              <h3 className="text-base font-semibold">Account</h3>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 space-y-1">
                  <div className="truncate text-sm font-medium">
                    {email || account?.user?.username || 'FastFold account'}
                  </div>
                  <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                    <span>{planLabel || 'Plan unknown'}</span>
                    {account?.billingUrl ? (
                      <>
                        <span aria-hidden>·</span>
                        <a
                          href={account.billingUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 inline-flex items-center gap-1 hover:underline dark:text-blue-400"
                        >
                          Manage billing
                          <ExternalLink className="size-3.5" />
                        </a>
                      </>
                    ) : null}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={signingOut}
                  onClick={() => void signOut()}
                >
                  {signingOut ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    <LogOut />
                  )}
                  Sign out
                </Button>
              </div>
            </section>

            {(orgName || orgId) && (
              <section className="space-y-4 border-b pb-8">
                <h3 className="text-base font-semibold">Organization</h3>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-muted-foreground min-w-0 truncate text-sm">
                    {orgName || 'Organization'}
                  </div>
                  {orgId ? (
                    <code className="bg-muted text-muted-foreground rounded-full px-2.5 py-1 font-mono text-xs">
                      {orgId}
                    </code>
                  ) : null}
                </div>
              </section>
            )}
          </>
        ) : (
          <section className="space-y-3 border-b pb-8">
            <h3 className="text-base font-semibold">Account</h3>
            <p className="text-muted-foreground text-sm">
              Connect a FastFold Cloud API key in Integrations to show your
              account, plan, and organization here.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/dashboard/integrations/fastfold-cloud')}
            >
              Open FastFold Cloud
            </Button>
          </section>
        )}

        <section className="space-y-4 border-b pb-8">
          <h3 className="text-base font-semibold">Connection</h3>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <label className="min-w-0 flex-1 space-y-1.5">
              <span className="text-muted-foreground text-xs">Backend URL</span>
              <Input
                value={draftBackendUrl}
                onChange={event => setDraftBackendUrl(event.target.value)}
                placeholder="http://127.0.0.1:8787"
                className="font-mono text-sm"
                spellCheck={false}
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void refreshBackend()
                  }
                }}
              />
            </label>
            <div className="flex shrink-0 items-center gap-2">
              <span
                className={cn(
                  'inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium',
                  checkingBackend
                    ? 'border-border text-muted-foreground'
                    : backendOk
                      ? 'border-emerald-500/30 text-emerald-700 dark:text-emerald-400'
                      : 'border-destructive/40 text-destructive'
                )}
              >
                {checkingBackend ? (
                  <Loader2 className="size-3 animate-spin" />
                ) : (
                  <span
                    className={cn(
                      'size-2 rounded-full',
                      backendOk ? 'bg-emerald-500' : 'bg-destructive'
                    )}
                  />
                )}
                {checkingBackend
                  ? 'Checking…'
                  : backendOk
                    ? 'Connected'
                    : 'Failed'}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={checkingBackend || !normalizeBackendUrl(draftBackendUrl)}
                onClick={() => void refreshBackend()}
              >
                {checkingBackend ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <RefreshCw />
                )}
                {backendDirty ? 'Save & connect' : 'Recheck'}
              </Button>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-base font-semibold">About</h3>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-1">
              <div className="text-sm font-medium">Sandwalk</div>
              <div className="text-muted-foreground space-y-0.5 text-sm">
                <div>
                  Backend runtime:{' '}
                  <span className="text-foreground font-medium">
                    {backendVersion || about?.version || '—'}
                  </span>
                </div>
                <div>
                  UI:{' '}
                  <span className="text-foreground font-medium">
                    {__UI_VERSION__}
                  </span>
                </div>
              </div>
              <div className="text-muted-foreground text-sm">
                Channel: {about?.channel || 'default'} · Last checked{' '}
                {formatCheckedAt(lastCheckedAt)}
              </div>
              <div className="text-sm">
                {checkingUpdates ? (
                  <span className="text-muted-foreground">
                    Checking for updates…
                  </span>
                ) : about?.upToDate === false && about.latestVersion ? (
                  `Update available: ${about.latestVersion}`
                ) : lastCheckedAt ? (
                  "You're up to date."
                ) : (
                  <span className="text-muted-foreground">
                    Updates not checked yet.
                  </span>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={checkingUpdates || loading}
              onClick={() => void loadAccount(true)}
            >
              {checkingUpdates ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw />
              )}
              Check for updates
            </Button>
          </div>
        </section>
      </div>
    </ScrollArea>
  )
}
