import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import {
  ArrowLeft,
  ArrowRight,
  CircleCheck,
  Loader2,
  Search
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import {
  CardGridSkeleton,
  ListRowsSkeleton
} from '@/components/agents/PageSkeletons'
import { TerminalPanel } from '@/components/agents/TerminalPanel'
import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { isFeaturedIntegration } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

export function IntegrationsView({
  terminalClient,
  integrations,
  loading = false,
  selectedKey,
  values,
  featuredOnly = false,
  onShowAll,
  onSelect,
  onValueChange,
  onSave,
  onValidate,
  onAutofill,
  onSetup,
  onOpenVercelTerminal,
  onRemove,
  embedded = false
}: {
  terminalClient: LocalAgentClient
  integrations: IntegrationSummary[]
  loading?: boolean
  selectedKey: string | null
  values: Record<string, string>
  /** Overview: only Featured integration cards (same as Integrations page). */
  featuredOnly?: boolean
  onShowAll?: () => void
  onSelect: (key: string | null) => void
  onValueChange: (envName: string, value: string) => void
  onSave: () => Promise<void>
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
  onSetup: (key: string) => Promise<IntegrationSetupResult>
  onOpenVercelTerminal: () => Promise<string>
  onRemove: (key: string) => Promise<void>
  embedded?: boolean
}) {
  const selected = integrations.find(item => item.key === selectedKey)
  const [integrationSearch, setIntegrationSearch] = useState('')
  const [integrationCategory, setIntegrationCategory] = useState('all')
  const [integrationStatus, setIntegrationStatus] = useState<
    'all' | 'configured' | 'not_configured'
  >('all')
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
  const vercelSetupRunCommand =
    'vercel login && vercel link && vercel env pull .env.local --environment=development'
  useEffect(() => {
    setSetupResult(null)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
    setValidationMessage(null)
    setValidationBusy(false)
    setOverlay(null)
  }, [selectedKey])

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
    if (!autoFetchPending || selected?.key !== 'skills-sh') return
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
  }, [autoFetchPending, onAutofill, selected?.key])
  const categories = Array.from(
    new Set(integrations.map(item => item.category))
  ).sort()
  const configuredCount = integrations.filter(item => item.configured).length
  const notConfiguredCount = integrations.length - configuredCount
  const featuredCount = integrations.filter(item =>
    isFeaturedIntegration(item)
  ).length
  const categoryCounts = integrations.reduce<Record<string, number>>(
    (counts, item) => {
      counts[item.category] = (counts[item.category] || 0) + 1
      return counts
    },
    {}
  )
  const visibleIntegrations = integrations.filter(item => {
    const query = integrationSearch.trim().toLowerCase()
    const matchesQuery =
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.description.toLowerCase().includes(query) ||
      item.key.toLowerCase().includes(query)
    const matchesStatus =
      integrationStatus === 'all' ||
      (integrationStatus === 'configured' ? item.configured : !item.configured)
    const matchesCategory =
      integrationCategory === 'all'
        ? true
        : integrationCategory === 'featured'
        ? isFeaturedIntegration(item)
        : item.category === integrationCategory
    return (
      matchesStatus &&
      matchesQuery &&
      matchesCategory
    )
  })
  const orderedVisibleIntegrations = [...visibleIntegrations].sort((a, b) => {
    const featuredDelta =
      Number(isFeaturedIntegration(b)) - Number(isFeaturedIntegration(a))
    if (featuredDelta !== 0) return featuredDelta
    return a.name.localeCompare(b.name)
  })
  const featuredVisible = orderedVisibleIntegrations.filter(item =>
    isFeaturedIntegration(item)
  )
  const nonFeaturedVisible = orderedVisibleIntegrations.filter(
    item => !isFeaturedIntegration(item)
  )
  const vercelIntegrationDir = '~/.sandwalk/vercel-integration'
  const vercelSetupCommands = [
    `cd "${vercelIntegrationDir}"`,
    'vercel login',
    'vercel link',
    'vercel env pull .env.local --environment=development'
  ]
  const renderConfiguredToggle = (configured: boolean, name: string) => (
    <span
      role="switch"
      aria-checked={configured}
      aria-label={`${name} ${configured ? 'configured' : 'not configured'}`}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        configured ? 'bg-black/75 dark:bg-zinc-300/50' : 'bg-zinc-200 dark:bg-zinc-700'
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
  const renderIntegrationCard = (item: IntegrationSummary) => (
    <div
      key={item.key}
      className="bg-background/60 hover:bg-muted/40 flex items-start justify-between gap-3 rounded-lg p-3 transition-colors"
    >
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={() => onSelect(item.key)}
      >
        <div className="flex items-center gap-2">
          <IntegrationIcon integration={item} />
          <span className="truncate text-sm font-medium">{item.name}</span>
          <span className="text-muted-foreground text-xs">{item.category}</span>
        </div>
        <p className="text-muted-foreground mt-1 line-clamp-2 text-sm">
          {item.description}
        </p>
      </button>
      <div className="flex items-center pt-0.5">
        {renderConfiguredToggle(item.configured, item.name)}
      </div>
    </div>
  )
  const goBackToIntegrations = () => {
    onSelect(null)
    setValidationMessage(null)
    setSetupResult(null)
    setTerminalOpen(false)
  }

  if (selected) {
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
              onClick={goBackToIntegrations}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">/</span>
            <button
              type="button"
              onClick={goBackToIntegrations}
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
                      <code>{vercelSetupCommands.join('\n')}</code>
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
                <>
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
                </>
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
                  startupCommand={vercelSetupRunCommand}
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
                  <strong className="block truncate text-sm">
                    {field.envVar}
                  </strong>
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
            <p className="text-muted-foreground mt-3 text-sm">
              {validationMessage}
            </p>
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

  if (featuredOnly) {
    const featuredAll = integrations.filter(item => isFeaturedIntegration(item))
    const featured = featuredAll.slice(0, 2)
    return (
      <section className="space-y-3">
        <div className="flex items-end justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold tracking-tight">
              Integrations
            </h3>
            <p className="text-muted-foreground text-xs font-medium">
              Featured ({featuredAll.length})
            </p>
          </div>
          {onShowAll ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs font-medium transition-colors"
              onClick={onShowAll}
            >
              Show all
              <ArrowRight className="size-3.5" />
            </button>
          ) : null}
        </div>
        {loading && featuredAll.length === 0 ? (
          <CardGridSkeleton cards={2} columns={2} />
        ) : featured.length === 0 ? (
          <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
            No featured integrations yet.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {featured.map(item => renderIntegrationCard(item))}
          </div>
        )}
      </section>
    )
  }

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      <div
        className={
          embedded
            ? 'mx-auto flex w-full max-w-5xl flex-col gap-6 p-1 xl:flex-row'
            : 'mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6 xl:flex-row'
        }
      >
        <div className="min-w-0 flex-1">
          {!embedded ? (
            <div className="mb-4">
              <h2 className="text-2xl font-semibold">Integrations</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Connect API keys and services the agent uses for models, search,
                compute, and cloud workflows.
              </p>
            </div>
          ) : null}
          <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-20 mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2 backdrop-blur">
            <div className="relative min-w-[280px] max-w-3xl flex-1">
              <Search className="text-muted-foreground/70 pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={integrationSearch}
                onChange={event => setIntegrationSearch(event.target.value)}
                placeholder="Search integrations, descriptions..."
                className="border-border/70 bg-background/70 h-11 pl-10"
              />
            </div>
          </div>
          {loading ? (
            <div className="space-y-4 pb-4">
              <section className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <CardGridSkeleton cards={4} columns={2} />
              </section>
              <section className="space-y-2">
                <Skeleton className="h-3 w-16" />
                <div className="space-y-2">
                  <ListRowsSkeleton rows={5} />
                </div>
              </section>
            </div>
          ) : visibleIntegrations.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-sm">
              No integrations match the current search/filter.
            </div>
          ) : (
            <div className="space-y-4 pb-4">
              {featuredVisible.length > 0 ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    Featured ({featuredVisible.length})
                  </p>
                  <div className="grid gap-3 md:grid-cols-2">
                    {featuredVisible.map(item => renderIntegrationCard(item))}
                  </div>
                </section>
              ) : null}
              {integrationCategory !== 'featured' ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium">
                    All ({nonFeaturedVisible.length})
                  </p>
                  <div className="space-y-2">
                    {nonFeaturedVisible.map(item => renderIntegrationCard(item))}
                  </div>
                </section>
              ) : null}
            </div>
          )}
        </div>
        <aside className="flex w-full shrink-0 flex-col gap-4 xl:sticky xl:top-4 xl:self-start xl:w-[320px]">
          <section className="bg-background/70 rounded-lg p-2">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Status
            </div>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('all')}
            >
              All ({integrations.length})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'configured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('configured')}
            >
              Configured ({configuredCount})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationStatus === 'not_configured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationStatus('not_configured')}
            >
              Not configured ({notConfiguredCount})
            </button>
          </section>
          <section className="bg-background/70 rounded-lg p-2">
            <div className="text-muted-foreground/60 mb-1 px-2 py-1 text-xs font-semibold">
              Categories
            </div>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationCategory === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationCategory('all')}
            >
              All ({integrations.length})
            </button>
            <button
              type="button"
              className={cn(
                'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                integrationCategory === 'featured'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
              onClick={() => setIntegrationCategory('featured')}
            >
              Featured ({featuredCount})
            </button>
            {categories.map(category => (
              <button
                key={category}
                type="button"
                className={cn(
                  'block w-full rounded-md px-2 py-1 text-left text-xs transition-colors',
                  integrationCategory === category
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
                onClick={() => setIntegrationCategory(category)}
              >
                {category} ({categoryCounts[category] || 0})
              </button>
            ))}
          </section>
        </aside>
      </div>
    </ScrollArea>
  )
}
