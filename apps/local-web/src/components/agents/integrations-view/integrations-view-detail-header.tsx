import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { openInSystemBrowser } from '@/lib/desktop'

/** Stable mount points for Add split buttons (filled via portal). */
export const SLACK_ADD_HEADER_SLOT_ID = 'sandwalk-slack-add-header-slot'
export const VERCEL_ADD_HEADER_SLOT_ID = 'sandwalk-vercel-add-header-slot'

function setupHostLabel(url: string) {
  try {
    return new URL(url).hostname
  } catch {
    return 'provider site'
  }
}

export function IntegrationsDetailNav({
  selected,
  onBack
}: {
  selected: IntegrationSummary
  onBack: () => void
}) {
  return (
    <DetailStickyNav>
      <div className="flex items-center gap-2 text-sm">
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <span className="text-muted-foreground/40">/</span>
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          Integrations
        </button>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {selected.key === 'modal' ? (
          <Link
            to="/dashboard/agent/sandbox/modal"
            className="text-muted-foreground hover:text-foreground shrink-0 text-xs underline underline-offset-4"
          >
            Modal Settings
          </Link>
        ) : null}
      </div>
    </DetailStickyNav>
  )
}

export function IntegrationsDetailHeader({
  selected
}: {
  selected: IntegrationSummary
}) {
  return (
    <div className="flex items-start gap-3">
      <IntegrationIcon integration={selected} size="lg" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">{selected.name}</h2>
          {selected.key === 'slack' ? (
            <div id={SLACK_ADD_HEADER_SLOT_ID} className="shrink-0" />
          ) : null}
          {selected.key === 'skills-sh' ? (
            <div id={VERCEL_ADD_HEADER_SLOT_ID} className="shrink-0" />
          ) : null}
        </div>
        {selected.key === 'skills-sh' ? (
          <p className="text-muted-foreground mt-1 text-sm">
            Skills.sh catalog search authentication via Vercel OIDC.
          </p>
        ) : selected.key === 'modal' ? (
          <p className="text-muted-foreground mt-1 text-sm">
            Modal tokens for sandbox chats. App defaults and images live under
            Modal Settings.
          </p>
        ) : selected.key === 'slack' ? (
          <p className="text-muted-foreground mt-1 text-sm">
            Use your agents from a Slack workspace — complete Relay Agent and
            Socket Mode support.
          </p>
        ) : (
          <p className="text-muted-foreground mt-1 text-sm">
            Preset provider env keys. Fill values and save.
          </p>
        )}
        {selected.setupUrl &&
        selected.key !== 'skills-sh' &&
        selected.key !== 'slack' ? (
          <p className="text-muted-foreground mt-1 text-xs">
            No key yet?{' '}
            <button
              type="button"
              className="underline underline-offset-2"
              onClick={() => void openInSystemBrowser(selected.setupUrl!)}
            >
              Create one at {setupHostLabel(selected.setupUrl)} ↗
            </button>
          </p>
        ) : null}
      </div>
    </div>
  )
}
