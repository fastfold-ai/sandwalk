import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { ExternalLink, Loader2, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { openInSystemBrowser } from '@/lib/desktop'

const FASTFOLD_CLOUD_URL = 'https://cloud.fastfold.ai/'

export function GeneralViewAccountSection({
  loading,
  account,
  signingOut,
  onSignOutClick
}: {
  loading: boolean
  account: AccountSummary | null
  signingOut: boolean
  onSignOutClick: () => void
}) {
  const navigate = useNavigate()
  const showCloudAccount = Boolean(account?.configured)
  const email = account?.user?.email?.trim() || null
  const planLabel = account?.user?.planLabel?.trim() || null
  const orgName = account?.organization?.name?.trim() || null
  const orgId = account?.organization?.id?.trim() || null

  if (loading && !account) {
    return (
      <section className="space-y-4">
        <h3 className="text-base font-semibold">Account</h3>
        <SettingsBlockSkeleton />
      </section>
    )
  }

  if (showCloudAccount) {
    return (
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
                <span aria-hidden>·</span>
                <button
                  type="button"
                  className="text-blue-600 inline-flex items-center gap-1 hover:underline dark:text-blue-400"
                  onClick={() => void openInSystemBrowser(FASTFOLD_CLOUD_URL)}
                >
                  Fastfold AI Cloud
                  <ExternalLink className="size-3.5" />
                </button>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={signingOut}
              onClick={onSignOutClick}
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
    )
  }

  return (
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
  )
}
