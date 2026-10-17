import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useRef, useState } from 'react'
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
import { useDesktopUpdate } from '@/hooks/useDesktopUpdate'
import {
  desktopCliPathInstall,
  type DesktopCliPathStatus,
  desktopCliPathStatus,
  desktopMenubarAvailable,
  isTauri,
  platformOS
} from '@/lib/desktop'

import { CapyShortcutSetting } from './capy/CapyShortcutSetting'
import { GeneralViewAccountSection } from './general-view-account'
import { GeneralViewNotificationsSection } from './general-view-notifications'
import { GeneralViewResetSection, clearLocalAppPreferences } from './general-view-reset'
import { GeneralViewServerSection } from './general-view-server'
import { GeneralViewVersionSection } from './general-view-version'

export function GeneralView({
  backendUrl,
  backendVersion,
  connected,
  onLoadAccount,
  onLogoutAccount,
  onOpenSetupWizard,
  onResetSettings,
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
  onResetSettings: () => Promise<void>
  onChangeBackend: (url: string, apiKey?: string) => void | Promise<void>
  onDisconnectBackend: () => void | Promise<void>
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [account, setAccount] = useState<AccountSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [signingOut, setSigningOut] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [hasCheckedUpdates, setHasCheckedUpdates] = useState(false)
  const [advisoryUpToDate, setAdvisoryUpToDate] = useState<boolean | null>(null)
  const [advisoryLatest, setAdvisoryLatest] = useState<string | null>(null)
  const [advisoryError, setAdvisoryError] = useState<string | null>(null)
  const [checkingAdvisory, setCheckingAdvisory] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cliPath, setCliPath] = useState<DesktopCliPathStatus | null>(null)
  const [checkingCliPath, setCheckingCliPath] = useState(false)
  const [installingCliPath, setInstallingCliPath] = useState(false)
  const [cliPathError, setCliPathError] = useState<string | null>(null)
  const [showCliPath, setShowCliPath] = useState(false)
  const desktopUpdate = useDesktopUpdate()
  const useDesktopUpdater = isTauri()

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
    if (useDesktopUpdater) {
      await desktopUpdate.checkForUpdate()
      return
    }

    setCheckingAdvisory(true)
    setAdvisoryError(null)
    try {
      const next = await onLoadAccount({ checkUpdates: true })
      setAccount(next)
      setHasCheckedUpdates(true)
      setAdvisoryUpToDate(next.about.upToDate)
      setAdvisoryLatest(next.about.latestVersion)
    } catch (err) {
      setAdvisoryError(err instanceof Error ? err.message : String(err))
    } finally {
      setCheckingAdvisory(false)
    }
  }, [desktopUpdate, onLoadAccount, useDesktopUpdater])

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

  // Older menu links landed here with ?checkUpdates=1. Handle that once.
  // Depending on searchParams and calling setSearchParams in the same effect
  // retriggered replaceState until the webview aborted.
  const checkUpdatesOnce = useRef(false)
  useEffect(() => {
    if (checkUpdatesOnce.current) return
    if (searchParams.get('checkUpdates') !== '1') return
    checkUpdatesOnce.current = true
    const next = new URLSearchParams(searchParams)
    next.delete('checkUpdates')
    setSearchParams(next, { replace: true })
    void runUpdateCheck()
  }, [runUpdateCheck, searchParams, setSearchParams])

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

  const resetApp = async () => {
    setResetting(true)
    setError(null)
    try {
      await onResetSettings()
      clearLocalAppPreferences()
      window.location.assign('/onboarding/welcome')
    } catch (err) {
      setResetting(false)
      setConfirmReset(false)
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const about = account?.about
  const upToDate = useDesktopUpdater
    ? desktopUpdate.upToDate
    : (advisoryUpToDate ?? about?.upToDate ?? null)
  const latestVersion = useDesktopUpdater
    ? desktopUpdate.latestVersion
    : (advisoryLatest ?? about?.latestVersion ?? null)
  const checkingUpdates = useDesktopUpdater
    ? desktopUpdate.checking
    : checkingAdvisory
  const checkError = useDesktopUpdater ? desktopUpdate.error : advisoryError
  const hasChecked = useDesktopUpdater
    ? desktopUpdate.hasChecked
    : hasCheckedUpdates

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
          installingUpdate={desktopUpdate.installing}
          hasChecked={hasChecked}
          upToDate={upToDate}
          latestVersion={latestVersion}
          checkError={checkError}
          onCheckUpdates={() => void runUpdateCheck()}
          onInstallUpdate={
            useDesktopUpdater ? () => void desktopUpdate.installUpdate() : undefined
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

        <CapyShortcutSetting />

        <GeneralViewNotificationsSection />

        <GeneralViewResetSection
          resetting={resetting}
          onReset={() => setConfirmReset(true)}
        />
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

      <AlertDialog
        open={confirmReset}
        onOpenChange={open => {
          if (!open && !resetting) setConfirmReset(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset Sandwalk?</AlertDialogTitle>
            <AlertDialogDescription>
              Models, API keys, and app settings go back to a fresh install.
              Onboarding opens next. Chats on this machine stay.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={resetting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={resetting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={event => {
                event.preventDefault()
                void resetApp()
              }}
            >
              {resetting ? 'Resetting…' : 'Reset'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}
