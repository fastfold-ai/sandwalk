import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { IntegrationSetupResult, IntegrationSummary } from '@sandwalk/agent-ui-core'

import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import { VERCEL_SETUP_RUN_COMMAND } from './integrations-view-shared'

function formatUpdatedAt(value: string | null) {
  if (!value) return 'Unknown'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

export function IntegrationsDetailVercelPanel({
  terminalClient,
  setupResult,
  terminalOpen,
  terminalSessionId,
  terminalStartupNonce,
  onCloseTerminal
}: {
  terminalClient: LocalAgentClient
  setupResult: IntegrationSetupResult | null
  terminalOpen: boolean
  terminalSessionId: string | null
  terminalStartupNonce: number
  onCloseTerminal: () => void
}) {
  return (
    <>
      {setupResult ? (
        <div className="bg-muted/20 mt-4 rounded-md border p-3">
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
      {terminalOpen && terminalSessionId ? (
        <div className="bg-background mt-4 overflow-hidden rounded-md border">
          <div className="text-muted-foreground border-b px-3 py-2 text-xs">
            Setup terminal in `~/.sandwalk/vercel-integration`. Run:
            `vercel login`, `vercel link`, then `vercel env pull`.
          </div>
          <div className="h-[320px]">
            <TerminalPanel
              client={terminalClient}
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
    </>
  )
}

export function IntegrationsDetailFieldsTable({
  selected,
  values,
  onValueChange,
  onRemove
}: {
  selected: IntegrationSummary
  values: Record<string, string>
  onValueChange: (envName: string, value: string) => void
  onRemove: (key: string) => Promise<void>
}) {
  return (
    <section className="mt-5 space-y-2">
      <h3 className="text-sm font-medium">Keys</h3>
      <div className="overflow-hidden rounded-md border">
      <div className="bg-muted/20 text-muted-foreground grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-2 text-xs">
        <span>Key</span>
        <span>Value</span>
        <span>Status</span>
        <span className="text-right">Action</span>
      </div>
      {selected.fields.map(field => (
        <div
          key={field.envVar}
          className="grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-3 last:border-b-0"
        >
          <div className="min-w-0">
            <strong className="block truncate text-sm">{field.envVar}</strong>
            <span className="text-muted-foreground block truncate text-xs">
              {field.label}
            </span>
          </div>
          <Input
            type={field.isSecret ? 'password' : 'text'}
            value={values[field.envVar] || ''}
            className="min-w-0 w-full"
            onChange={event => onValueChange(field.envVar, event.target.value)}
            placeholder={`Enter ${field.envVar}`}
          />
          <div className="text-muted-foreground min-w-0 text-xs">
            <span className="block truncate">
              {field.configured
                ? `Configured · ${field.maskedPreview || field.source}`
                : 'Not configured'}
            </span>
            {field.configured ? (
              <span className="mt-0.5 block truncate">
                Last updated {formatUpdatedAt(field.updatedAt)}
              </span>
            ) : null}
          </div>
          {field.configured ? (
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive justify-self-end"
              onClick={() => void onRemove(selected.key)}
            >
              Remove
            </Button>
          ) : (
            <span className="text-muted-foreground justify-self-end px-1">-</span>
          )}
        </div>
      ))}
      </div>
    </section>
  )
}
