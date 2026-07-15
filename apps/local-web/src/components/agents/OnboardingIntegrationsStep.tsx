import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { Check, CircleCheck, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { DataView } from '@/components/agents/DataView'
import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { isFeaturedIntegration } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

const FEATURED_ORDER = [
  'skills-sh',
  'boltz',
  'fastfold-cloud',
  'slack'
] as const

const VERCEL_INTEGRATION_DIR = '~/.sandwalk/vercel-integration'
const VERCEL_SETUP_RUN_COMMAND =
  'vercel login && vercel link && vercel env pull .env.local --environment=development'
const VERCEL_SETUP_COMMANDS = [
  `cd "${VERCEL_INTEGRATION_DIR}"`,
  'vercel login',
  'vercel link',
  'vercel env pull .env.local --environment=development'
]

function ConfiguredToggle({
  configured,
  name
}: {
  configured: boolean
  name: string
}) {
  return (
    <span
      role="switch"
      aria-checked={configured}
      aria-label={`${name} ${configured ? 'configured' : 'not configured'}`}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        configured
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700'
      )}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          configured ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </span>
  )
}

export function OnboardingIntegrationsStep({
  client
}: {
  client: LocalAgentClient
}) {
  const [integrations, setIntegrations] = useState<IntegrationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [values, setValues] = useState<Record<string, string>>({})
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [setupResult, setSetupResult] = useState<IntegrationSetupResult | null>(
    null
  )
  const [setupRunning, setSetupRunning] = useState(false)
  const [openingTerminal, setOpeningTerminal] = useState(false)
  const [terminalSessionId, setTerminalSessionId] = useState<string | null>(
    null
  )
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [terminalStartupNonce, setTerminalStartupNonce] = useState(0)
  const [autoFetchPending, setAutoFetchPending] = useState(false)
  const autoFetchAttemptsRef = useRef(0)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const next = await client.listIntegrations()
      setIntegrations(next)
    } catch {
      // Keep step usable.
    } finally {
      setLoading(false)
    }
  }, [client])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    setSetupResult(null)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
  }, [selectedKey])

  useEffect(() => {
    if (!autoFetchPending || selectedKey !== 'skills-sh') return
    let cancelled = false
    let timer: number | null = null
    const attemptImport = async () => {
      if (cancelled) return
      try {
        await client.autofillIntegration('skills-sh')
        if (cancelled) return
        setAutoFetchPending(false)
        setNotice(
          'Imported Vercel OIDC token. Skills.sh search is now enabled.'
        )
        await refresh()
      } catch {
        if (cancelled) return
        autoFetchAttemptsRef.current += 1
        if (autoFetchAttemptsRef.current >= 40) {
          setAutoFetchPending(false)
          setNotice(
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
      if (timer != null) window.clearTimeout(timer)
    }
  }, [autoFetchPending, client, refresh, selectedKey])

  const featured = useMemo(() => {
    const byKey = new Map(integrations.map(item => [item.key, item]))
    const ordered = FEATURED_ORDER.map(key => byKey.get(key)).filter(
      (item): item is IntegrationSummary => Boolean(item)
    )
    const extras = integrations.filter(
      item =>
        isFeaturedIntegration(item) &&
        !FEATURED_ORDER.includes(item.key as (typeof FEATURED_ORDER)[number])
    )
    return [...ordered, ...extras]
  }, [integrations])

  const selected = featured.find(item => item.key === selectedKey) || null
  const isVercel = selected?.key === 'skills-sh'

  const pick = (item: IntegrationSummary) => {
    setSelectedKey(item.key)
    setValues({})
    setShowSecrets({})
    setError(null)
    setNotice(null)
    if (item.key !== 'skills-sh') {
      setTerminalOpen(false)
    }
  }

  const openVercelTerminal = async () => {
    const sessions = await client.listSessions()
    const existing = sessions.find(item =>
      String(item.workspacePath || '')
        .trim()
        .endsWith('/.sandwalk/vercel-integration')
    )
    if (existing) return existing.id
    const created = await client.createSession({
      title: 'Vercel integration setup',
      workspacePath: VERCEL_INTEGRATION_DIR
    })
    return created.id
  }

  const runVercelSetup = async () => {
    setOpeningTerminal(true)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
    setError(null)
    setNotice(null)
    try {
      const id = await openVercelTerminal()
      setTerminalSessionId(id)
      setTerminalOpen(true)
      setTerminalStartupNonce(current => current + 1)
      setSetupRunning(true)
      const result = await client.setupIntegration('skills-sh')
      setSetupResult(result)
      setNotice(
        `${result.summary} Use the terminal below to finish login and link.`
      )
      setAutoFetchPending(true)
      await refresh()
    } catch (err) {
      setSetupResult(null)
      setAutoFetchPending(false)
      setError(
        err instanceof Error ? err.message : 'Unable to open Vercel setup.'
      )
    } finally {
      setSetupRunning(false)
      setOpeningTerminal(false)
    }
  }

  const save = async () => {
    if (!selected) return
    const payload = Object.fromEntries(
      Object.entries(values)
        .map(([envVar, value]) => [envVar, value.trim()])
        .filter(([, value]) => Boolean(value))
    )
    if (!Object.keys(payload).length) {
      setError('Enter at least one value to save.')
      return
    }
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await client.updateIntegration(selected.key, payload)
      setValues({})
      setNotice(`${selected.name} connected.`)
      await refresh()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not save integration.'
      )
    } finally {
      setBusy(false)
    }
  }

  const testKey = async () => {
    if (!selected) return
    setBusy(true)
    setError(null)
    try {
      const result = await client.validateIntegration(selected.key)
      setNotice(result.message)
      await refresh()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Could not validate integration.'
      )
    } finally {
      setBusy(false)
    }
  }

  if (loading && featured.length === 0) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading integrations…
      </p>
    )
  }

  return (
    <div className="space-y-5 pb-2">
      <section className="space-y-3">
        <p className="text-muted-foreground text-sm">Featured</p>
        {featured.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No featured integrations yet.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {featured.map(item => {
              const active = selectedKey === item.key
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => pick(item)}
                  className={cn(
                    'bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg border p-3 text-left transition-colors',
                    active
                      ? 'border-foreground bg-muted/40'
                      : 'border-transparent'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <IntegrationIcon integration={item} />
                      <span className="truncate text-sm font-medium">
                        {item.name}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {item.category}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
                      {item.description}
                    </p>
                  </div>
                  <div className="flex items-center pt-0.5">
                    <ConfiguredToggle
                      configured={item.configured}
                      name={item.name}
                    />
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </section>

      {selected ? (
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
                          {selected.configured
                            ? 'Re-link Project'
                            : 'Link Project'}
                        </strong>{' '}
                        to open the setup terminal and run the commands.
                      </li>
                      <li>
                        Follow the terminal prompts, then click Test API Key.
                      </li>
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
                onClick={() => void runVercelSetup()}
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
                      <strong className="text-foreground mr-1">
                        {step.label}:
                      </strong>
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
                Setup terminal in `{VERCEL_INTEGRATION_DIR}`. Run:{' '}
                `vercel login`, `vercel link`, then `vercel env pull`.
              </div>
              <div className="h-[260px]">
                <TerminalPanel
                  client={client}
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
                        setValues(prev => ({
                          ...prev,
                          [field.envVar]: event.target.value
                        }))
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
                        onClick={() =>
                          setShowSecrets(prev => ({
                            ...prev,
                            [field.envVar]: !prev[field.envVar]
                          }))
                        }
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
                onClick={() => void testKey()}
              >
                <CircleCheck className="size-4" />
                Test API Key
              </Button>
            ) : null}
            <Button
              type="button"
              disabled={
                busy || !Object.values(values).some(value => value.trim())
              }
              onClick={() => void save()}
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
      ) : null}

      {error ? <p className="text-destructive text-sm">{error}</p> : null}
      {notice ? <p className="text-muted-foreground text-sm">{notice}</p> : null}

      <div className="border-t border-border/60 pt-5">
        <DataView
          bare
          title="Datasets"
          description="Install open-access datasets your tools use. Others need a manual download."
          onListDatasets={signal => client.listDatasets(signal)}
          onInstallDataset={(datasetId, signal) =>
            client.installDataset(datasetId, signal)
          }
          onRemoveDataset={(datasetId, signal) =>
            client.removeDataset(datasetId, signal)
          }
        />
        <p className="text-muted-foreground mt-3 text-xs">
          Later you can manage datasets in your dashboard.
        </p>
      </div>
    </div>
  )
}
