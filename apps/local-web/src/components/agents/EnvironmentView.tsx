import type {
  EnvironmentPackage,
  EnvironmentPackageGroup,
  EnvironmentPackageMutationResult,
  EnvironmentReport,
} from '@fastfold/agent-ui-core'
import { ChevronDown, Lock, Package, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

function formatBytes(bytes: number): string {
  const value = Math.max(0, bytes)
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB'] as const
  let n = value / 1024
  for (let i = 0; i < units.length; i += 1) {
    if (n < 1024 || i === units.length - 1) {
      return `${n.toFixed(1)} ${units[i]}`
    }
    n /= 1024
  }
  return `${value} B`
}

function normalizeName(name: string): string {
  return name.trim().toLowerCase().replace(/_/g, '-')
}

function mutationErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) return String(err)
  const match = err.message.match(/FastFold Agent API \d+:\s*(.*)$/s)
  if (!match?.[1]) return err.message
  try {
    const parsed = JSON.parse(match[1]) as { detail?: string }
    if (typeof parsed.detail === 'string') return parsed.detail
  } catch {
    // keep raw
  }
  return match[1]
}

type ConfirmState = {
  action: 'install' | 'uninstall'
  name: string
  allowUnlisted: boolean
  unlisted: boolean
}

export function EnvironmentView({
  onLoad,
  onInstall,
  onUninstall,
}: {
  onLoad: (signal?: AbortSignal) => Promise<EnvironmentReport>
  onInstall: (
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal },
  ) => Promise<EnvironmentPackageMutationResult>
  onUninstall: (
    name: string,
    signal?: AbortSignal,
  ) => Promise<EnvironmentPackageMutationResult>
}) {
  const [report, setReport] = useState<EnvironmentReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({})
  const [coreOpen, setCoreOpen] = useState(false)
  const [packageName, setPackageName] = useState('')
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)

  const catalogNames = useMemo(() => {
    const set = new Set<string>()
    for (const group of report?.groups || []) {
      for (const pkg of group.packages) {
        set.add(normalizeName(pkg.name))
      }
    }
    return set
  }, [report])

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onLoad(signal)
        if (signal?.aborted) return
        setReport(next)
        setGroupOpen(current => {
          const nextOpen = { ...current }
          for (const group of next.groups) {
            if (nextOpen[group.id] === undefined) nextOpen[group.id] = true
          }
          return nextOpen
        })
      } catch (err) {
        if (signal?.aborted) return
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onLoad],
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const requestInstall = (
    name: string,
    options: { fromCatalog: boolean },
  ) => {
    const trimmed = name.trim()
    if (!trimmed) return
    const unlisted = !catalogNames.has(normalizeName(trimmed))
    setConfirm({
      action: 'install',
      name: trimmed,
      allowUnlisted: options.fromCatalog ? false : true,
      unlisted: options.fromCatalog ? false : unlisted,
    })
  }

  const requestUninstall = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    setConfirm({
      action: 'uninstall',
      name: trimmed,
      allowUnlisted: false,
      unlisted: false,
    })
  }

  const runConfirmed = async () => {
    if (!confirm) return
    const { action, name, allowUnlisted } = confirm
    setConfirm(null)
    setPending(name)
    try {
      const result =
        action === 'install'
          ? await onInstall(name, { allowUnlisted })
          : await onUninstall(name)
      toast.success(result.message || `${action} ${name}`, {
        description:
          action === 'install'
            ? 'No server restart needed — new imports work in the next tool run.'
            : undefined,
      })
      if (action === 'install') setPackageName('')
      await load()
    } catch (err) {
      toast.error(mutationErrorMessage(err))
    } finally {
      setPending(null)
    }
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-8 py-10">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">Environment</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Manage optional Python packages used by skills and tools. Core
              FastFold dependencies stay locked. Installs apply immediately —
              you usually do not need to restart the agent server.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || pending !== null}
            onClick={() => void load()}
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        {loading && !report ? (
          <SettingsBlockSkeleton />
        ) : report ? (
          <>
            <section className="space-y-3 border-b pb-8">
              <h3 className="text-base font-semibold">Sandbox Python</h3>
              <div className="space-y-1">
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
              </div>
            </section>

            <section className="space-y-3 border-b pb-8">
              <h3 className="text-base font-semibold">Install by name</h3>
              <p className="text-muted-foreground text-sm">
                Type a PyPI package name. Catalog packages install normally;
                other packages need an extra confirmation.
              </p>
              <form
                className="flex flex-col gap-2 sm:flex-row"
                onSubmit={event => {
                  event.preventDefault()
                  requestInstall(packageName, { fromCatalog: false })
                }}
              >
                <Input
                  value={packageName}
                  onChange={event => setPackageName(event.target.value)}
                  placeholder="e.g. torch, rdkit, gseapy"
                  className="font-mono"
                  disabled={pending !== null}
                  autoComplete="off"
                />
                <Button
                  type="submit"
                  disabled={pending !== null || !packageName.trim()}
                >
                  {pending &&
                  normalizeName(pending) === normalizeName(packageName)
                    ? 'Installing…'
                    : 'Install'}
                </Button>
              </form>
            </section>

            <section className="space-y-3">
              <h3 className="text-base font-semibold">Skill & tool packages</h3>
              <p className="text-muted-foreground text-sm">
                Install or remove packages that power chemistry, single-cell,
                ML, and other research tools. Large packages (e.g. torch) can
                take several minutes.
              </p>
              <div className="space-y-2">
                {report.groups.map(group => (
                  <GroupCard
                    key={group.id}
                    group={group}
                    open={Boolean(groupOpen[group.id])}
                    pending={pending}
                    onToggle={() =>
                      setGroupOpen(current => ({
                        ...current,
                        [group.id]: !current[group.id],
                      }))
                    }
                    onInstall={pkg =>
                      requestInstall(pkg.name, { fromCatalog: true })
                    }
                    onUninstall={pkg => requestUninstall(pkg.name)}
                  />
                ))}
              </div>
            </section>

            <section className="space-y-2 border-t pt-6">
              <button
                type="button"
                className="hover:bg-muted/50 flex w-full items-center gap-2 rounded-md px-2 py-2 text-left"
                onClick={() => setCoreOpen(open => !open)}
              >
                <Lock className="text-muted-foreground size-3.5 shrink-0" />
                <span className="flex-1 text-sm font-semibold">
                  Core (locked)
                </span>
                <span className="text-muted-foreground text-xs">
                  {report.core.length} packages
                </span>
                <ChevronDown
                  className={cn(
                    'text-muted-foreground size-3.5 transition-transform',
                    coreOpen && 'rotate-180',
                  )}
                />
              </button>
              {coreOpen ? (
                <ScrollArea className="h-64 rounded-md border">
                  <div className="space-y-0.5 p-2">
                    {report.core.map(pkg => (
                      <div
                        key={pkg.name}
                        className="text-muted-foreground flex items-center gap-3 px-2 py-1.5 text-sm"
                      >
                        <span className="min-w-0 flex-1 truncate font-mono text-xs">
                          {pkg.name}
                        </span>
                        <span className="shrink-0 font-mono text-xs">
                          {pkg.version}
                        </span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              ) : null}
            </section>
          </>
        ) : null}
      </div>

      <AlertDialog
        open={confirm !== null}
        onOpenChange={open => {
          if (!open) setConfirm(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm?.action === 'uninstall'
                ? `Remove ${confirm.name}?`
                : `Install ${confirm?.name}?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm?.action === 'uninstall' ? (
                <>
                  This uninstalls <code className="font-mono">{confirm.name}</code>{' '}
                  from the sandbox Python environment.
                </>
              ) : confirm?.unlisted ? (
                <>
                  <code className="font-mono">{confirm.name}</code> is not in the
                  skill/tool catalog. It will still be installed into the agent
                  sandbox. Core FastFold packages cannot be changed.
                </>
              ) : (
                <>
                  Install <code className="font-mono">{confirm?.name}</code> into
                  the sandbox Python environment. No server restart is required
                  afterward in most cases.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending !== null}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={pending !== null}
              onClick={event => {
                event.preventDefault()
                void runConfirmed()
              }}
            >
              {confirm?.action === 'uninstall' ? 'Remove' : 'Install'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ScrollArea>
  )
}

function GroupCard({
  group,
  open,
  pending,
  onToggle,
  onInstall,
  onUninstall,
}: {
  group: EnvironmentPackageGroup
  open: boolean
  pending: string | null
  onToggle: () => void
  onInstall: (pkg: EnvironmentPackage) => void
  onUninstall: (pkg: EnvironmentPackage) => void
}) {
  const installedCount = group.packages.filter(pkg => pkg.installed).length
  return (
    <div className="rounded-lg border">
      <button
        type="button"
        className="hover:bg-muted/40 flex w-full items-center gap-3 px-3 py-2.5 text-left"
        onClick={onToggle}
      >
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{group.label}</div>
          <div className="text-muted-foreground truncate text-xs">
            {group.description}
          </div>
        </div>
        <span className="text-muted-foreground shrink-0 text-xs">
          {installedCount}/{group.packages.length} installed
        </span>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-3.5 shrink-0 transition-transform',
            open && 'rotate-180',
          )}
        />
      </button>
      {open ? (
        <div className="space-y-1 border-t px-2 py-2">
          {group.packages.map(pkg => {
            const busy = pending === pkg.name
            return (
              <div
                key={pkg.name}
                className="flex items-center gap-3 rounded-md px-2 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate font-mono text-sm">{pkg.name}</div>
                  <div className="text-muted-foreground text-xs">
                    {pkg.installed
                      ? pkg.version || 'Installed'
                      : 'Not installed'}
                  </div>
                </div>
                {pkg.installed ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="gap-1.5"
                    disabled={busy || pending !== null}
                    onClick={() => onUninstall(pkg)}
                  >
                    <Trash2 className="size-3.5" />
                    {busy ? 'Removing…' : 'Remove'}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="gap-1.5"
                    disabled={busy || pending !== null}
                    onClick={() => onInstall(pkg)}
                  >
                    <Plus className="size-3.5" />
                    {busy ? 'Installing…' : 'Install'}
                  </Button>
                )}
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
