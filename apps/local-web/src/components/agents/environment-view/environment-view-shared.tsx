import type {
  EnvironmentPackage,
  EnvironmentPackageGroup,
} from '@sandwalk/agent-ui-core'
import { ChevronDown, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function formatBytes(bytes: number): string {
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

export function normalizeName(name: string): string {
  return name.trim().toLowerCase().replace(/_/g, '-')
}

export function mutationErrorMessage(err: unknown): string {
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

export type EnvironmentConfirmState = {
  action: 'install' | 'uninstall'
  name: string
  allowUnlisted: boolean
  unlisted: boolean
}

export function EnvironmentGroupCard({
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
