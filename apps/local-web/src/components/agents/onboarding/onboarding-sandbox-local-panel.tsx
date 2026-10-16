import type { EnvironmentReport } from '@sandwalk/agent-ui-core'
import { Check, ChevronDown, Loader, Package, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { formatBytes } from './onboarding-sandbox-utils'

export function OnboardingSandboxLocalPanel({
  envError,
  envLoading,
  report,
  groupOpen,
  pendingPackage = null,
  onToggleGroup,
  onInstallPackage,
  onUninstallPackage
}: {
  envError: string | null
  envLoading: boolean
  report: EnvironmentReport | null
  groupOpen: Record<string, boolean>
  pendingPackage?: string | null
  onToggleGroup: (groupId: string) => void
  onInstallPackage?: (name: string) => void
  onUninstallPackage?: (name: string) => void
}) {
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
      {envError ? (
        <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
          {envError}
        </div>
      ) : null}

      {envLoading && !report ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader className="size-4 animate-spin" />
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
                        onClick={() => onToggleGroup(group.id)}
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
                          {group.packages.map(pkg => {
                            const busy = pendingPackage === pkg.name
                            const disabled = busy || pendingPackage !== null
                            return (
                              <li
                                key={pkg.name}
                                className="flex items-center gap-2 py-1 text-sm"
                              >
                                <button
                                  type="button"
                                  disabled={disabled}
                                  title={
                                    pkg.installed
                                      ? `Remove ${pkg.name}`
                                      : `Install ${pkg.name}`
                                  }
                                  onClick={() => {
                                    if (pkg.installed) {
                                      onUninstallPackage?.(pkg.name)
                                    } else {
                                      onInstallPackage?.(pkg.name)
                                    }
                                  }}
                                  className="inline-flex size-4 shrink-0 items-center justify-center rounded-full disabled:opacity-50"
                                >
                                  {busy ? (
                                    <Loader className="text-muted-foreground size-3.5 animate-spin" />
                                  ) : pkg.installed ? (
                                    <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                                  ) : (
                                    <span className="bg-muted hover:bg-foreground/30 size-3.5 rounded-full transition-colors" />
                                  )}
                                </button>
                                <code className="min-w-0 flex-1 truncate font-mono text-xs">
                                  {pkg.name}
                                </code>
                                <span className="text-muted-foreground shrink-0 font-mono text-xs">
                                  {busy
                                    ? pkg.installed
                                      ? 'removing…'
                                      : 'installing…'
                                    : pkg.installed
                                      ? pkg.version || 'installed'
                                      : 'not installed'}
                                </span>
                                {pkg.installed ? (
                                  onUninstallPackage ? (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="ghost"
                                      className="h-6 gap-1 px-2 text-xs"
                                      disabled={disabled}
                                      onClick={() =>
                                        onUninstallPackage(pkg.name)
                                      }
                                    >
                                      <Trash2 className="size-3" />
                                      Remove
                                    </Button>
                                  ) : null
                                ) : onInstallPackage ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    className="h-6 gap-1 px-2 text-xs"
                                    disabled={disabled}
                                    onClick={() => onInstallPackage(pkg.name)}
                                  >
                                    <Plus className="size-3" />
                                    Install
                                  </Button>
                                ) : null}
                              </li>
                            )
                          })}
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
  )
}
