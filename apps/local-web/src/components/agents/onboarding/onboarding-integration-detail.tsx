import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { Check, CircleCheck, Eye, EyeOff, Loader2 } from 'lucide-react'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import {
  VERCEL_INTEGRATION_DIR,
  VERCEL_SETUP_COMMANDS,
  VERCEL_SETUP_RUN_COMMAND
} from './onboarding-integrations-shared'

export function OnboardingIntegrationDetail({
  client,
  selected,
  isVercel,
  values,
  showSecrets,
  busy,
  setupResult,
  setupRunning,
  openingTerminal,
  terminalOpen,
  terminalSessionId,
  terminalStartupNonce,
  onRunVercelSetup,
  onCloseTerminal,
  onValueChange,
  onToggleSecret,
  onTestKey,
  onSave
}: {
  client: LocalAgentClient
  selected: IntegrationSummary
  isVercel: boolean
  values: Record<string, string>
  showSecrets: Record<string, boolean>
  busy: boolean
  setupResult: IntegrationSetupResult | null
  setupRunning: boolean
  openingTerminal: boolean
  terminalOpen: boolean
  terminalSessionId: string | null
  terminalStartupNonce: number
  onRunVercelSetup: () => void
  onCloseTerminal: () => void
  onValueChange: (envVar: string, value: string) => void
  onToggleSecret: (envVar: string) => void
  onTestKey: () => void
  onSave: () => void
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <IntegrationIcon integration={selected} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">{selected.name}</p>
            {isVercel ? (
              <div className="text-muted-foreground mt-1 space-y-1 text-xs leading-relaxed">
                <p>Use this for Skills.sh catalog search authentication.</p>
                <ol className="list-inside list-decimal space-y-0.5">
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
                    , open the project, then enable OIDC Federation under
                    Settings → Security.
                  </li>
                  <li>
                    Click{' '}
                    <strong>
                      {selected.configured ? 'Re-link Project' : 'Link Project'}
                    </strong>{' '}
                    to open the setup terminal and run the commands.
                  </li>
                  <li>Follow the terminal prompts, then click Test.</li>
                </ol>
                <pre className="bg-muted/40 mt-2 overflow-x-auto rounded border p-2 font-mono text-[11px]">
                  <code>{VERCEL_SETUP_COMMANDS.join('\n')}</code>
                </pre>
              </div>
            ) : (
              <>
                <p className="text-muted-foreground mt-1 text-xs">
                  Fill values and save.
                </p>
                {selected.setupUrl ? (
                  <a
                    href={selected.setupUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-muted-foreground mt-1 inline-block text-xs underline"
                  >
                    Get a {selected.name} key
                  </a>
                ) : null}
              </>
            )}
          </div>
        </div>
        {isVercel ? (
          <Button
            type="button"
            variant="secondary"
            disabled={setupRunning || openingTerminal}
            onClick={() => onRunVercelSetup()}
            className="shrink-0"
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

      {isVercel && setupResult ? (
        <div className="bg-muted/20 rounded-md border p-3">
          <p className="text-sm font-medium">{setupResult.summary}</p>
          <ul className="mt-2 space-y-1">
            {setupResult.steps.map(step => (
              <li
                key={step.id}
                className="text-muted-foreground flex items-start gap-2 text-xs"
              >
                <span
                  className={cn(
                    'mt-0.5 inline-block h-2 w-2 rounded-full',
                    step.ok ? 'bg-emerald-500' : 'bg-amber-500'
                  )}
                />
                <span>
                  <strong className="text-foreground mr-1">{step.label}:</strong>
                  {step.detail}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isVercel && terminalOpen && terminalSessionId ? (
        <div className="bg-background overflow-hidden rounded-md border">
          <div className="text-muted-foreground border-b px-3 py-2 text-xs">
            Setup terminal in `{VERCEL_INTEGRATION_DIR}`. Run: `vercel login`,
            `vercel link`, then `vercel env pull`.
          </div>
          <div className="h-[260px]">
            <TerminalPanel
              client={client}
              sessionId={terminalSessionId}
              visible={terminalOpen}
              autoCreateOnEmpty
              startupCommand={VERCEL_SETUP_RUN_COMMAND}
              startupNonce={terminalStartupNonce}
              onClose={onCloseTerminal}
            />
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        {selected.fields.map(field => {
          const show = Boolean(showSecrets[field.envVar])
          return (
            <div key={field.envVar} className="space-y-1">
              <label className="text-muted-foreground text-xs">
                {field.label}
                <span className="ml-1 font-mono text-[10px]">
                  {field.envVar}
                </span>
              </label>
              <div className="relative">
                <Input
                  type={field.isSecret && !show ? 'password' : 'text'}
                  value={values[field.envVar] || ''}
                  onChange={event =>
                    onValueChange(field.envVar, event.target.value)
                  }
                  placeholder={
                    field.configured
                      ? field.maskedPreview || 'Configured'
                      : `Enter ${field.envVar}`
                  }
                  className="pr-10"
                />
                {field.isSecret ? (
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2"
                    onClick={() => onToggleSecret(field.envVar)}
                    aria-label={show ? 'Hide value' : 'Show value'}
                  >
                    {show ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                ) : null}
              </div>
              {field.configured ? (
                <p className="text-muted-foreground text-[11px]">
                  Configured · {field.maskedPreview || field.source}
                </p>
              ) : null}
            </div>
          )
        })}
      </div>

      <div className="flex justify-end gap-2">
        {isVercel ? (
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => onTestKey()}
          >
            <CircleCheck className="size-4" />
            Test
          </Button>
        ) : null}
        <Button
          type="button"
          disabled={busy || !Object.values(values).some(value => value.trim())}
          onClick={() => onSave()}
          className="inline-flex h-9 items-center gap-2"
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Check className="size-4" />
          )}
          Save & use
        </Button>
      </div>
    </section>
  )
}
