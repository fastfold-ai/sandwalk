import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { useCallback, useEffect, useState } from 'react'

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

import { GeneralViewAboutSection } from './general-view-about'
import { GeneralViewAccountSection } from './general-view-account'
import { GeneralViewNotificationsSection } from './general-view-notifications'
import { GeneralViewServerSection } from './general-view-server'

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
  const [account, setAccount] = useState<AccountSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [checkingUpdates, setCheckingUpdates] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [confirmSignOut, setConfirmSignOut] = useState(false)
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div>
          <h2 className="text-2xl font-semibold">General</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Account, agent server connection, and app details. Theme and
            sidebar appearance live under Appearance.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

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
        />

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

        <GeneralViewNotificationsSection />

        <GeneralViewAboutSection
          backendVersion={backendVersion}
          account={account}
          lastCheckedAt={lastCheckedAt}
          checkingUpdates={checkingUpdates}
          loading={loading}
          onCheckUpdates={() => void loadAccount(true)}
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
    </ScrollArea>
  )
}
