import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'

import { VERCEL_SETUP_COMMANDS } from './integrations-view-shared'

export function IntegrationsDetailHeader({
  selected,
  setupRunning,
  openingTerminal,
  onBack,
  onLinkProject
}: {
  selected: IntegrationSummary
  setupRunning: boolean
  openingTerminal: boolean
  onBack: () => void
  onLinkProject: () => void
}) {
  return (
    <>
      <div className="mb-8 flex items-center gap-2 text-sm">
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
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <IntegrationIcon integration={selected} size="lg" />
          <div>
            <h2 className="text-xl font-semibold">{selected.name}</h2>
            {selected.key === 'skills-sh' ? (
              <div className="text-muted-foreground mt-1 space-y-1 text-sm">
                <p>Use this for Skills.sh catalog search authentication.</p>
                <ol className="list-inside list-decimal space-y-0.5 text-xs">
                  <li>
                    In{' '}
                    {selected.setupUrl ? (
                      <a
                        href={selected.setupUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="underline"
                      >
                        Vercel Dashboard
                      </a>
                    ) : (
                      'Vercel Dashboard'
                    )}
                    , open the target project, then go to `Settings {'->'}{' '}
                    Security {'->'} OIDC Federation` and enable it.
                  </li>
                  <li>
                    Click{' '}
                    <strong>
                      {selected.configured ? 'Re-link Project' : 'Link Project'}
                    </strong>{' '}
                    - it opens the setup terminal and runs these commands for
                    you.
                  </li>
                  <li>Follow the terminal prompts, then click Test API Key.</li>
                </ol>
                <pre className="bg-muted/40 mt-2 rounded border p-2 font-mono text-[11px]">
                  <code>{VERCEL_SETUP_COMMANDS.join('\n')}</code>
                </pre>
              </div>
            ) : selected.key === 'modal' ? (
              <p className="text-muted-foreground mt-1 text-sm">
                Modal tokens for sandbox chats. App defaults and images live
                under Modal Settings.
              </p>
            ) : (
              <p className="text-muted-foreground mt-1 text-sm">
                Preset provider env keys. Fill values and save.
              </p>
            )}
            {selected.setupUrl && selected.key !== 'skills-sh' ? (
              <p className="text-muted-foreground mt-1 text-xs">
                Get API keys at{' '}
                <a
                  href={selected.setupUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="underline"
                >
                  {selected.setupUrl}
                </a>
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selected.key === 'modal' ? (
            <Link
              to="/dashboard/agent/sandbox/modal"
              className="text-muted-foreground hover:text-foreground shrink-0 text-xs underline underline-offset-4"
            >
              Modal Settings
            </Link>
          ) : null}
          {selected.key === 'skills-sh' ? (
            <Button
              variant="secondary"
              disabled={setupRunning || openingTerminal}
              onClick={onLinkProject}
            >
              {setupRunning || openingTerminal ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <img
                  src="/integrations/vercel.png"
                  alt=""
                  className="size-4 rounded object-contain dark:invert"
                />
              )}
              {selected.configured ? 'Re-link Project' : 'Link Project'}
            </Button>
          ) : null}
        </div>
      </div>
    </>
  )
}
