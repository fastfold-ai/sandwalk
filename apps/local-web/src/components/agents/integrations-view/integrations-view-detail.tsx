import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, CircleCheck, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  VERCEL_SETUP_COMMANDS,
  VERCEL_SETUP_RUN_COMMAND
} from './integrations-view-shared'

export function IntegrationsDetailView({
  terminalClient,
  selected,
  values,
  onBack,
  onValueChange,
  onSave,
  onValidate,
  onAutofill,
  onSetup,
  onOpenVercelTerminal,
  onRemove
}: {
  terminalClient: LocalAgentClient
  selected: IntegrationSummary
  values: Record<string, string>
  onBack: () => void
  onValueChange: (envName: string, value: string) => void
  onSave: () => Promise<void>
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
  onSetup: (key: string) => Promise<IntegrationSetupResult>
  onOpenVercelTerminal: () => Promise<string>
  onRemove: (key: string) => Promise<void>
}) {
  const [validationMessage, setValidationMessage] = useState<string | null>(
    null
  )
  const [validationBusy, setValidationBusy] = useState(false)
  const [overlay, setOverlay] = useState<{
    phase: 'working' | 'done'
    message: string
    description?: string
  } | null>(null)
  const [setupResult, setSetupResult] = useState<IntegrationSetupResult | null>(
    null
  )
  const [setupRunning, setSetupRunning] = useState(false)
  const [autoFetchPending, setAutoFetchPending] = useState(false)
  const autoFetchAttemptsRef = useRef(0)
  const [terminalSessionId, setTerminalSessionId] = useState<string | null>(null)
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [openingTerminal, setOpeningTerminal] = useState(false)
  const [terminalStartupNonce, setTerminalStartupNonce] = useState(0)

  useEffect(() => {
    setSetupResult(null)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
    setValidationMessage(null)
    setValidationBusy(false)
    setOverlay(null)
    setTerminalOpen(false)
  }, [selected.key])

  async function showDoneOverlay(message: string, description?: string) {
    setOverlay({ phase: 'done', message, description })
    await new Promise(resolve => setTimeout(resolve, 900))
    setOverlay(null)
  }

  async function runValidate(key: string) {
    const isModalProbe = key === 'modal'
    setValidationBusy(true)
    setValidationMessage(null)
    if (isModalProbe) {
      setOverlay({
        phase: 'working',
        message: 'Probing Modal…',
        description:
          'Creating a sandbox, syncing files, and running a health check.'
      })
    }
    try {
      const result = await onValidate(key)
      setValidationMessage(result.message)
      if (isModalProbe) {
        if (result.ok) {
          await showDoneOverlay(
            'Probe healthy',
            'Modal sandbox is ready to use.'
          )
        } else {
          setOverlay(null)
        }
      }
    } catch (error) {
      setOverlay(null)
      setValidationMessage(
        error instanceof Error
          ? error.message
          : 'Unable to test integration.'
      )
    } finally {
      setValidationBusy(false)
    }
  }

  useEffect(() => {
    if (!autoFetchPending || selected.key !== 'skills-sh') return
    let cancelled = false
    let timer: number | null = null
    const attemptImport = async () => {
      if (cancelled) return
      try {
        await onAutofill(selected.key)
        if (cancelled) return
        setAutoFetchPending(false)
        setValidationMessage(
          'Imported Vercel OIDC token into /keys config. Skills.sh search is now enabled.'
        )
      } catch {
        if (cancelled) return
        autoFetchAttemptsRef.current += 1
        if (autoFetchAttemptsRef.current >= 40) {
          setAutoFetchPending(false)
          setValidationMessage(
            'Still waiting for Vercel token. Finish terminal prompts, then click Re-link Project again.'
          )
          return
        }
        timer = window.setTimeout(() => {
          void attemptImport()
        }, 3000)
      }
    }
    timer = window.setTimeout(() => {
      void attemptImport()
    }, 2500)
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [autoFetchPending, onAutofill, selected.key])

  return (
    <ScrollArea className="flex-1">
      <BusyConfirmOverlay
        open={Boolean(overlay)}
        phase={overlay?.phase || 'working'}
        message={overlay?.message || ''}
        description={overlay?.description}
      />
      <div className="mx-auto max-w-6xl px-8 py-8">
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
                        {selected.configured
                          ? 'Re-link Project'
                          : 'Link Project'}
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
                onClick={() => {
                  setOpeningTerminal(true)
                  setAutoFetchPending(false)
                  autoFetchAttemptsRef.current = 0
                  void onOpenVercelTerminal()
                    .then(id => {
                      setTerminalSessionId(id)
                      setTerminalOpen(true)
                      setTerminalStartupNonce(current => current + 1)
                      setSetupRunning(true)
                      return onSetup(selected.key)
                    })
                    .then(result => {
                      setSetupResult(result)
                      setValidationMessage(
                        `${result.summary} Use the terminal below to run the listed commands.`
                      )
                      setAutoFetchPending(true)
                    })
                    .catch(error => {
                      setSetupResult(null)
                      setAutoFetchPending(false)
                      setValidationMessage(
                        error instanceof Error
                          ? error.message
                          : 'Unable to open Vercel setup.'
                      )
                    })
                    .finally(() => {
                      setSetupRunning(false)
                      setOpeningTerminal(false)
                    })
                }}
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
        {selected.key === 'skills-sh' && setupResult ? (
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
        {selected.key === 'skills-sh' && terminalOpen && terminalSessionId ? (
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
                onClose={() => setTerminalOpen(false)}
              />
            </div>
          </div>
        ) : null}
        <div className="mt-5 overflow-hidden rounded-md border">
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
                onChange={event =>
                  onValueChange(field.envVar, event.target.value)
                }
                placeholder={`Enter ${field.envVar}`}
              />
              <span className="text-muted-foreground min-w-0 truncate text-xs">
                {field.configured
                  ? `Configured · ${field.maskedPreview || field.source}`
                  : 'Not configured'}
              </span>
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
                <span className="text-muted-foreground justify-self-end px-1">
                  -
                </span>
              )}
            </div>
          ))}
        </div>
        {validationMessage ? (
          <p className="text-muted-foreground mt-3 text-sm">{validationMessage}</p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            disabled={validationBusy}
            onClick={() => void runValidate(selected.key)}
          >
            {validationBusy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <CircleCheck className="size-4" />
            )}
            Test API Key
          </Button>
          <Button
            disabled={!Object.values(values).some(value => value.trim())}
            onClick={() => void onSave()}
          >
            Save Overrides
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
