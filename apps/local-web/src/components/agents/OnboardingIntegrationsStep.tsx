import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { Loader2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { DataView } from '@/components/agents/DataView'
import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { isFeaturedIntegration } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import { OnboardingIntegrationDetail } from './onboarding/onboarding-integration-detail'
import {
  ONBOARDING_FEATURED_INTEGRATION_ORDER,
  OnboardingConfiguredToggle,
  VERCEL_INTEGRATION_DIR
} from './onboarding/onboarding-integrations-shared'

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
    const ordered = ONBOARDING_FEATURED_INTEGRATION_ORDER.map(key =>
      byKey.get(key)
    ).filter((item): item is IntegrationSummary => Boolean(item))
    const extras = integrations.filter(
      item =>
        isFeaturedIntegration(item) &&
        !ONBOARDING_FEATURED_INTEGRATION_ORDER.includes(
          item.key as (typeof ONBOARDING_FEATURED_INTEGRATION_ORDER)[number]
        )
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
                    <OnboardingConfiguredToggle
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
        <OnboardingIntegrationDetail
          client={client}
          selected={selected}
          isVercel={isVercel}
          values={values}
          showSecrets={showSecrets}
          busy={busy}
          setupResult={setupResult}
          setupRunning={setupRunning}
          openingTerminal={openingTerminal}
          terminalOpen={terminalOpen}
          terminalSessionId={terminalSessionId}
          terminalStartupNonce={terminalStartupNonce}
          onRunVercelSetup={() => void runVercelSetup()}
          onCloseTerminal={() => setTerminalOpen(false)}
          onValueChange={(envVar, value) =>
            setValues(prev => ({ ...prev, [envVar]: value }))
          }
          onToggleSecret={envVar =>
            setShowSecrets(prev => ({ ...prev, [envVar]: !prev[envVar] }))
          }
          onTestKey={() => void testKey()}
          onSave={() => void save()}
        />
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
