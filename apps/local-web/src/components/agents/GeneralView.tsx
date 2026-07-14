import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { Check, ExternalLink, Loader2, LogOut, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

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
  applyPalette,
  getStoredPalette,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  THEME_PALETTES,
  type ThemePaletteId
} from '@/lib/theme'
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

export function GeneralView({
  backendUrl,
  backendVersion,
  connected,
  onLoadAccount,
  onLogoutAccount,
  onOpenSetupWizard
}: {
  backendUrl: string
  backendVersion: string | null
  connected: boolean
  onLoadAccount: (options?: {
    checkUpdates?: boolean
    signal?: AbortSignal
  }) => Promise<AccountSummary>
  onLogoutAccount: (signal?: AbortSignal) => Promise<AccountSummary>
  onOpenSetupWizard?: () => void
}) {
  const navigate = useNavigate()
  const [account, setAccount] = useState<AccountSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [checkingUpdates, setCheckingUpdates] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [palette, setPalette] = useState<ThemePaletteId>(() => getStoredPalette())

  useEffect(() => {
    const onChange = (event: Event) => {
      setPalette((event as CustomEvent<ThemePaletteId>).detail)
    }
    window.addEventListener(PALETTE_CHANGE_EVENT, onChange)
    return () => window.removeEventListener(PALETTE_CHANGE_EVENT, onChange)
  }, [])

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

  const signOut = async () => {
    setConfirmSignOut(false)
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
            Account, themes, local server, and app details.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <SandwalkServerCard
          version={backendVersion}
          running={connected}
          subtitle={listenSubtitle({
            running: connected,
            backendUrl
          })}
        />

        {loading && !account ? (
          <section className="space-y-4">
            <h3 className="text-base font-semibold">Account</h3>
            <SettingsBlockSkeleton />
          </section>
        ) : showCloudAccount ? (
          <>
            <section className="space-y-4">
              <div>
                <h3 className="text-base font-semibold">Account</h3>
                <p className="text-muted-foreground mt-1 inline-flex flex-wrap items-center gap-1.5 text-sm">
                  <span>Linked</span>
                  <img
                    src="/ff_simbol_color.svg"
                    alt=""
                    aria-hidden="true"
                    className="size-3.5"
                  />
                  <span>Fastfold Cloud Account</span>
                </p>
              </div>
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 space-y-1">
                  <div className="break-all text-sm font-medium">
                    {email || account?.user?.username || 'Fastfold account'}
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
                  onClick={() => setConfirmSignOut(true)}
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
              <section className="space-y-4">
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
          <section className="space-y-3">
            <h3 className="text-base font-semibold">Account</h3>
            <p className="text-muted-foreground text-sm">
              Connect a Fastfold Cloud API key in Integrations to show your
              account, plan, and organization here.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => navigate('/dashboard/integrations/fastfold-cloud')}
            >
              <span>Link</span>
              <img
                src="/ff_simbol_color.svg"
                alt=""
                aria-hidden="true"
                className="size-3.5"
              />
              <span>Fastfold Account</span>
            </Button>
          </section>
        )}

        <section className="space-y-4">
          <div>
            <h3 className="text-base font-semibold">Themes</h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Color palettes for light and dark mode. Mode and palette also live
              in the user menu under Theme.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {THEME_PALETTES.map(item => {
              const selected = palette === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => applyPalette(item.id)}
                  onPointerEnter={() => previewPalette(item.id)}
                  onPointerLeave={() => previewPalette(getStoredPalette())}
                  onFocus={() => previewPalette(item.id)}
                  onBlur={() => previewPalette(getStoredPalette())}
                  className={cn(
                    'bg-card hover:bg-muted/40 relative flex flex-col gap-3 rounded-xl border p-4 text-left transition-colors',
                    selected
                      ? 'border-primary ring-primary/20 ring-2'
                      : 'border-border'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold">{item.name}</div>
                      <p className="text-muted-foreground mt-1 text-xs leading-relaxed">
                        {item.description}
                      </p>
                    </div>
                    {selected ? (
                      <span className="bg-primary text-primary-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full">
                        <Check className="size-3.5" />
                      </span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {item.swatches.map(color => (
                      <span
                        key={color}
                        className="border-border size-7 rounded-md border shadow-sm"
                        style={{ backgroundColor: color }}
                        title={color}
                      />
                    ))}
                  </div>
                </button>
              )
            })}
          </div>
        </section>

        {onOpenSetupWizard ? (
          <section className="space-y-3">
            <div>
              <h3 className="text-base font-semibold">Setup wizard</h3>
              <p className="text-muted-foreground mt-1 text-sm">
                Short guided setup — model, keys, tools, sandbox.
              </p>
            </div>
            <Button type="button" variant="ghost" onClick={onOpenSetupWizard}>
              Run setup wizard
            </Button>
          </section>
        ) : null}

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

      <AlertDialog
        open={confirmSignOut}
        onOpenChange={open => {
          if (!open && !signingOut) setConfirmSignOut(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out of Fastfold Cloud?</AlertDialogTitle>
            <AlertDialogDescription>
              Removes the FastFold Cloud API key from this local agent. You can
              link an account again anytime from Integrations.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={signingOut}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={signingOut}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void signOut()
              }}
            >
              {signingOut ? 'Signing out…' : 'Sign out'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}
