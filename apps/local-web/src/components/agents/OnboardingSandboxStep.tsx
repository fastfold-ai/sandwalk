import type {
  EnvironmentReport,
  IntegrationSummary,
  SandboxSettings
} from '@sandwalk/agent-ui-core'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Check, ChevronDown, Loader2, Monitor, Package } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'

import { AgentSandboxView } from '@/components/agents/AgentSandboxView'
import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

const MODAL_ICON = INTEGRATION_ICONS.modal

type SandboxTab = 'local' | 'modal'

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`
}

export function OnboardingSandboxStep({
  client
}: {
  client: LocalAgentClient
}) {
  const [tab, setTab] = useState<SandboxTab>('local')
  const [report, setReport] = useState<EnvironmentReport | null>(null)
  const [envLoading, setEnvLoading] = useState(true)
  const [envError, setEnvError] = useState<string | null>(null)
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({})

  const [sandboxSettings, setSandboxSettings] =
    useState<SandboxSettings | null>(null)
  const [modalIntegration, setModalIntegration] =
    useState<IntegrationSummary | null>(null)

  const loadEnvironment = useCallback(async () => {
    setEnvLoading(true)
    setEnvError(null)
    try {
      const next = await client.getEnvironment()
      setReport(next)
    } catch (err) {
      setEnvError(err instanceof Error ? err.message : String(err))
    } finally {
      setEnvLoading(false)
    }
  }, [client])

  const refreshModal = useCallback(async () => {
    try {
      const [settings, integrations] = await Promise.all([
        client.getSandboxSettings(),
        client.listIntegrations()
      ])
      setSandboxSettings(settings)
      setModalIntegration(
        integrations.find(item => item.key === 'modal') ?? null
      )
      return settings
    } catch {
      return null
    }
  }, [client])

  useEffect(() => {
    void loadEnvironment()
    void refreshModal()
  }, [loadEnvironment, refreshModal])

  useEffect(() => {
    if (tab === 'modal' && !sandboxSettings) void refreshModal()
  }, [tab, sandboxSettings, refreshModal])

  const loadSandboxSettings = useCallback(async () => {
    const next = await client.getSandboxSettings()
    setSandboxSettings(next)
    return next
  }, [client])

  const updateSandboxSettings = useCallback(
    async (changes: Partial<SandboxSettings>) => {
      const next = await client.updateSandboxSettings(changes)
      setSandboxSettings(next)
      return next
    },
    [client]
  )

  const saveModalIntegration = useCallback(
    async (values: Record<string, string>) => {
      const next = await client.updateIntegration('modal', values)
      setModalIntegration(next)
      return next
    },
    [client]
  )

  const removeModalIntegration = useCallback(async () => {
    await client.removeIntegration('modal')
    setModalIntegration(null)
  }, [client])

  const probeSandbox = useCallback(
    () => client.probeSandboxSettings(),
    [client]
  )

  const refreshIntegrations = useCallback(async () => {
    await refreshModal()
  }, [refreshModal])

  const installedCount =
    report?.groups.reduce(
      (sum, group) =>
        sum + group.packages.filter(pkg => pkg.installed).length,
      0
    ) ?? 0
  const catalogCount =
    report?.groups.reduce((sum, group) => sum + group.packages.length, 0) ?? 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setTab('local')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
            tab === 'local'
              ? 'border-foreground/25 bg-muted/60'
              : 'border-border/60 hover:bg-muted/40'
          )}
        >
          <Monitor className="size-3.5 shrink-0" />
          Local Sandbox
          <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[10px] font-medium">
            Default
          </span>
        </button>
        <button
          type="button"
          onClick={() => setTab('modal')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
            tab === 'modal'
              ? 'border-foreground/25 bg-muted/60'
              : 'border-border/60 hover:bg-muted/40'
          )}
        >
          {MODAL_ICON ? (
            <img
              src={MODAL_ICON.src}
              alt=""
              className="size-3.5 shrink-0 rounded object-contain"
            />
          ) : null}
          Modal Sandbox
        </button>
      </div>

      {tab === 'local' ? (
        <div className="space-y-4">
          {envError ? (
            <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
              {envError}
            </div>
          ) : null}

          {envLoading && !report ? (
            <div className="text-muted-foreground flex items-center gap-2 text-sm">
              <Loader2 className="size-4 animate-spin" />
              Loading environment…
            </div>
          ) : null}

          {report ? (
            <div className="space-y-4">
              <section className="space-y-2 rounded-lg border border-border/60 px-3 py-3">
                <div className="flex items-center gap-2">
                  <Package className="text-muted-foreground size-4 shrink-0" />
                  <code className="truncate font-mono text-sm">
                    {report.envPath || report.pythonPath}
                  </code>
                </div>
                <p className="text-muted-foreground text-sm">
                  {formatBytes(report.envBytes)} on disk · interpreter{' '}
                  <code className="font-mono text-xs">{report.pythonPath}</code>
                </p>
              </section>

              <section className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border/60 px-3 py-3">
                  <p className="text-muted-foreground text-xs">Core packages</p>
                  <p className="mt-1 text-sm font-medium">
                    {report.core.length} installed
                  </p>
                  {report.core.length > 0 ? (
                    <p className="text-muted-foreground mt-1 line-clamp-2 font-mono text-xs">
                      {report.core
                        .slice(0, 4)
                        .map(pkg => `${pkg.name}@${pkg.version}`)
                        .join(', ')}
                      {report.core.length > 4 ? '…' : ''}
                    </p>
                  ) : null}
                </div>
                <div className="rounded-lg border border-border/60 px-3 py-3">
                  <p className="text-muted-foreground text-xs">
                    Skill & tool packages
                  </p>
                  <p className="mt-1 text-sm font-medium">
                    {installedCount} / {catalogCount} installed
                  </p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {report.groups.length} catalog group
                    {report.groups.length === 1 ? '' : 's'}
                  </p>
                </div>
              </section>

              {report.groups.length > 0 ? (
                <section className="space-y-2">
                  <h4 className="text-sm font-semibold">Catalog groups</h4>
                  <ul className="space-y-2">
                    {report.groups.map(group => {
                      const installed = group.packages.filter(
                        pkg => pkg.installed
                      ).length
                      const open = Boolean(groupOpen[group.id])
                      return (
                        <li
                          key={group.id}
                          className="overflow-hidden rounded-md border border-border/50"
                        >
                          <button
                            type="button"
                            className="hover:bg-muted/40 flex w-full items-start justify-between gap-3 px-3 py-2 text-left transition-colors"
                            onClick={() =>
                              setGroupOpen(current => ({
                                ...current,
                                [group.id]: !current[group.id]
                              }))
                            }
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">
                                {group.label}
                              </p>
                              <p className="text-muted-foreground line-clamp-1 text-xs">
                                {group.description}
                              </p>
                            </div>
                            <span className="text-muted-foreground flex shrink-0 items-center gap-1.5 text-xs">
                              {installed}/{group.packages.length}
                              <ChevronDown
                                className={cn(
                                  'size-3.5 transition-transform',
                                  open && 'rotate-180'
                                )}
                              />
                            </span>
                          </button>
                          {open ? (
                            <ul className="border-border/50 space-y-0.5 border-t px-3 py-2">
                              {group.packages.map(pkg => (
                                <li
                                  key={pkg.name}
                                  className="flex items-center gap-2 py-1 text-sm"
                                >
                                  {pkg.installed ? (
                                    <Check className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                                  ) : (
                                    <span className="bg-muted size-3.5 shrink-0 rounded-full" />
                                  )}
                                  <code className="min-w-0 flex-1 truncate font-mono text-xs">
                                    {pkg.name}
                                  </code>
                                  <span className="text-muted-foreground shrink-0 font-mono text-xs">
                                    {pkg.installed
                                      ? pkg.version || 'installed'
                                      : 'not installed'}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </li>
                      )
                    })}
                  </ul>
                </section>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <AgentSandboxView
          bare
          embedded
          connected
          sandboxSettings={sandboxSettings}
          modalIntegration={modalIntegration}
          onLoadSandboxSettings={loadSandboxSettings}
          onUpdateSandboxSettings={updateSandboxSettings}
          onProbeSandbox={probeSandbox}
          onSaveModalIntegration={saveModalIntegration}
          onRemoveModalIntegration={removeModalIntegration}
          onRefreshIntegrations={refreshIntegrations}
        />
      )}
    </div>
  )
}
