import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

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
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  desktopCliPathInstall,
  desktopCliPathStatus,
  desktopMenubarAvailable,
  type DesktopCliPathStatus,
  isTauri,
  platformOS
} from '@/lib/desktop'
import {
  checkDesktopUpdate,
  desktopUpdaterAvailable,
  installDesktopUpdate
} from '@/lib/desktop-updater'

import { GeneralViewAccountSection } from './general-view-account'
import { GeneralViewNotificationsSection } from './general-view-notifications'
import { GeneralViewServerSection } from './general-view-server'
import { GeneralViewVersionSection } from './general-view-version'

export function GeneralView({
  backendUrl,
  backendVersion,
  connected,
  onLoadAccount,
  onLogoutAccount,
  onOpenSetupWizard,
  onChangeBackend,
  onDisconnectBackend
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
  onChangeBackend: (url: string, apiKey?: string) => void | Promise<void>
  onDisconnectBackend: () => void | Promise<void>
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [account, setAccount] = useState<AccountSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [checkingUpdates, setCheckingUpdates] = useState(false)
  const [installingUpdate, setInstallingUpdate] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const [hasCheckedUpdates, setHasCheckedUpdates] = useState(false)
  const [desktopUpToDate, setDesktopUpToDate] = useState<boolean | null>(null)
  const [desktopLatest, setDesktopLatest] = useState<string | null>(null)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cliPath, setCliPath] = useState<DesktopCliPathStatus | null>(null)
  const [checkingCliPath, setCheckingCliPath] = useState(false)
  const [installingCliPath, setInstallingCliPath] = useState(false)
  const [cliPathError, setCliPathError] = useState<string | null>(null)
  const [showCliPath, setShowCliPath] = useState(false)
  const useDesktopUpdater = desktopUpdaterAvailable()

  const refreshCliPath = useCallback(async () => {
    if (!isTauri() || platformOS() !== 'macos') return
    setCheckingCliPath(true)
    setCliPathError(null)
    try {
      const next = await desktopCliPathStatus()
      if (!next) {
        setCliPathError('Sandwalk Server is not running.')
        return
      }
      setCliPath(next)
    } catch (err) {
      setCliPathError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingCliPath(false)
    }
  }, [])

  const installCliPath = useCallback(async () => {
    setInstallingCliPath(true)
    setCliPathError(null)
    try {
      // Explicit Install/Reinstall may replace a curl/uv-owned sandwalk.
      const next = await desktopCliPathInstall(true)
      setCliPath(next)
      if (next.error) setCliPathError(next.error)
    } catch (err) {
      setCliPathError(err instanceof Error ? err.message : String(err))
    } finally {
      setInstallingCliPath(false)
    }
  }, [cliPath?.state])

  const loadAccount = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoadAccount({ signal })
        if (signal?.aborted) return
        setAccount(next)
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onLoadAccount]
  )

  const runUpdateCheck = useCallback(async () => {
    setCheckingUpdates(true)
    setCheckError(null)
    try {
      if (useDesktopUpdater) {
        const result = await checkDesktopUpdate()
        setHasCheckedUpdates(true)
        if (result.kind === 'available') {
          setDesktopUpToDate(false)
          setDesktopLatest(result.info.version)
        } else if (result.kind === 'current') {
          setDesktopUpToDate(true)
          setDesktopLatest(null)
        } else if (result.kind === 'error') {
          setCheckError(result.message)
        }
        return
      }

      // Browser / non-desktop: advisory PyPI compare via account API.
      const next = await onLoadAccount({ checkUpdates: true })
      setAccount(next)
      setHasCheckedUpdates(true)
      setDesktopUpToDate(next.about.upToDate)
      setDesktopLatest(next.about.latestVersion)
    } catch (err) {
      setCheckError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingUpdates(false)
    }
  }, [onLoadAccount, useDesktopUpdater])

  useEffect(() => {
    const controller = new AbortController()
    void loadAccount(controller.signal)
    return () => controller.abort()
  }, [loadAccount])

  useEffect(() => {
    if (!isTauri() || platformOS() !== 'macos') return
    let cancelled = false
    void (async () => {
      const available = await desktopMenubarAvailable()
      if (cancelled || !available) return
      setShowCliPath(true)
      await refreshCliPath()
    })()
    return () => {
      cancelled = true
    }
  }, [refreshCliPath])

  // Auto-check once on desktop a few seconds after mount (Unsloth-style).
  // Quiet on network/404 until a Release exists — manual Check still surfaces errors.
  useEffect(() => {
    if (!useDesktopUpdater) return
    const timer = window.setTimeout(() => {
      void (async () => {
        setCheckingUpdates(true)
        try {
          const result = await checkDesktopUpdate()
          setHasCheckedUpdates(true)
          if (result.kind === 'available') {
            setDesktopUpToDate(false)
            setDesktopLatest(result.info.version)
          } else if (result.kind === 'current') {
            setDesktopUpToDate(true)
            setDesktopLatest(null)
          }
        } catch {
          // ignore background failures
        } finally {
          setCheckingUpdates(false)
        }
      })()
    }, 5000)
    return () => window.clearTimeout(timer)
  }, [useDesktopUpdater])

  // Sandwalk menu → Check for Updates… lands here with ?checkUpdates=1
  useEffect(() => {
    if (searchParams.get('checkUpdates') !== '1') return
    const next = new URLSearchParams(searchParams)
    next.delete('checkUpdates')
    setSearchParams(next, { replace: true })
    void runUpdateCheck()
  }, [runUpdateCheck, searchParams, setSearchParams])

  const runInstall = async () => {
    setInstallingUpdate(true)
    setCheckError(null)
    const result = await installDesktopUpdate()
    if (!result.ok) {
      setCheckError(result.message || 'Update failed')
      setInstallingUpdate(false)
    }
    // On success the app relaunches; no need to clear installing.
  }

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
  const upToDate = useDesktopUpdater ? desktopUpToDate : (about?.upToDate ?? null)
  const latestVersion = useDesktopUpdater
    ? desktopLatest
    : (about?.latestVersion ?? null)

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pt-6 pb-10 md:px-6 md:pt-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">General</h2>
          <p className="text-muted-foreground mt-1.5 text-sm">
            Versions, agent server, account, and notifications.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <GeneralViewVersionSection
          sandwalkVersion={__UI_VERSION__}
          checkingUpdates={checkingUpdates}
          installingUpdate={installingUpdate}
          hasChecked={hasCheckedUpdates}
          upToDate={upToDate}
          latestVersion={latestVersion}
          checkError={checkError}
          onCheckUpdates={() => void runUpdateCheck()}
          onInstallUpdate={
            useDesktopUpdater ? () => void runInstall() : undefined
          }
          showCliPath={showCliPath}
          cliPath={cliPath}
          checkingCliPath={checkingCliPath}
          installingCliPath={installingCliPath}
          cliPathError={cliPathError}
          onCheckCliPath={() => void refreshCliPath()}
          onInstallCliPath={() => void installCliPath()}
        />

        <GeneralViewServerSection
          backendUrl={backendUrl}
          backendVersion={backendVersion}
          connected={connected}
          onChangeBackend={onChangeBackend}
          onDisconnectBackend={onDisconnectBackend}
        />

        <GeneralViewAccountSection
          loading={loading}
          account={account}
          signingOut={signingOut}
          onSignOutClick={() => setConfirmSignOut(true)}
          onOpenSetupWizard={onOpenSetupWizard}
        />

        <GeneralViewNotificationsSection />
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
