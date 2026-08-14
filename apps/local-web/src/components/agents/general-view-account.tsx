import type { AccountSummary } from '@sandwalk/agent-ui-core'
import { ExternalLink, Loader, LogOut, WandSparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { openInSystemBrowser } from '@/lib/desktop'

const FASTFOLD_CLOUD_URL = 'https://cloud.fastfold.ai/'

function SettingsRow({
  label,
  description,
  children
}: {
  label: string
  description?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{label}</p>
        {description ? (
          <div className="text-muted-foreground mt-0.5 text-xs leading-snug">
            {description}
          </div>
        ) : null}
      </div>
      {children ? <div className="shrink-0">{children}</div> : null}
    </div>
  )
}

export function GeneralViewAccountSection({
  loading,
  account,
  signingOut,
  onSignOutClick,
  onOpenSetupWizard
}: {
  loading: boolean
  account: AccountSummary | null
  signingOut: boolean
  onSignOutClick: () => void
  onOpenSetupWizard?: () => void
}) {
  const navigate = useNavigate()
  const showCloudAccount = Boolean(account?.configured)
  const email = account?.user?.email?.trim() || null
  const planLabel = account?.user?.planLabel?.trim() || null
  const orgName = account?.organization?.name?.trim() || null
  const orgId = account?.organization?.id?.trim() || null

  if (loading && !account) {
    return (
      <section className="space-y-3">
        <h3 className="text-base font-semibold">Account</h3>
        <SettingsBlockSkeleton />
      </section>
    )
  }

  if (showCloudAccount) {
    return (
      <section className="space-y-3">
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
            <span>Fastfold Cloud</span>
          </p>
        </div>

        <div className="divide-border/60 border-border/60 divide-y border-y">
          <SettingsRow
            label={email || account?.user?.username || 'Fastfold account'}
            description={
              <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
                <span>{planLabel || 'Plan unknown'}</span>
                <span aria-hidden>·</span>
                <button
                  type="button"
                  className="text-blue-600 inline-flex items-center gap-1 hover:underline dark:text-blue-400"
                  onClick={() => void openInSystemBrowser(FASTFOLD_CLOUD_URL)}
                >
                  Fastfold AI Cloud
                  <ExternalLink className="size-3" />
                </button>
              </span>
            }
          >
            <Button
              variant="outline"
              size="sm"
              className="min-w-[8.5rem]"
              disabled={signingOut}
              onClick={onSignOutClick}
            >
              {signingOut ? (
                <Loader className="animate-spin" />
              ) : (
                <LogOut />
              )}
              Sign out
            </Button>
          </SettingsRow>

          {(orgName || orgId) && (
            <SettingsRow
              label={orgName || 'Organization'}
              description={
                orgId ? (
                  <code className="font-mono text-[11px]">{orgId}</code>
                ) : undefined
              }
            />
          )}

          {onOpenSetupWizard ? (
            <SettingsRow
              label="Setup wizard"
              description="Re-run onboarding for models, keys, and skills."
            >
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-w-[8.5rem]"
                onClick={onOpenSetupWizard}
              >
                <WandSparkles />
                Run wizard
              </Button>
            </SettingsRow>
          ) : null}
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Account</h3>
      <div className="divide-border/60 border-border/60 divide-y border-y">
        <SettingsRow
          label="Fastfold Cloud"
          description="Connect an API key to show your account, plan, and organization."
        >
          <Button
            variant="outline"
            size="sm"
            className="min-w-[8.5rem] gap-1.5"
            onClick={() => navigate('/dashboard/integrations/fastfold-cloud')}
          >
            <img
              src="/ff_simbol_color.svg"
              alt=""
              aria-hidden="true"
              className="size-3.5"
            />
            Link account
          </Button>
        </SettingsRow>
        {onOpenSetupWizard ? (
          <SettingsRow
            label="Setup wizard"
            description="Re-run onboarding for models, keys, and skills."
          >
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="min-w-[8.5rem]"
              onClick={onOpenSetupWizard}
            >
              <WandSparkles />
              Run wizard
            </Button>
          </SettingsRow>
        ) : null}
      </div>
    </section>
  )
}
