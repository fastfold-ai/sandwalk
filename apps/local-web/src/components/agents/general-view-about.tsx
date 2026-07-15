import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { Loader2, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { formatCheckedAt } from './general-view-utils'

export function GeneralViewAboutSection({
  backendVersion,
  account,
  lastCheckedAt,
  checkingUpdates,
  loading,
  onCheckUpdates
}: {
  backendVersion: string | null
  account: AccountSummary | null
  lastCheckedAt: Date | null
  checkingUpdates: boolean
  loading: boolean
  onCheckUpdates: () => void
}) {
  const about = account?.about

  return (
    <section className="space-y-4">
      <h3 className="text-base font-semibold">About</h3>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-1">
          <div className="text-sm font-medium">sandwalk</div>
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
          onClick={onCheckUpdates}
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
  )
}
