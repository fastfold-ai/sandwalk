import type { EnvironmentReport } from '@sandwalk/agent-ui-core'
import { ChevronDown, Lock, Package } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  EnvironmentGroupCard,
  formatBytes,
  normalizeName
} from './environment-view-shared'

export function EnvironmentPythonSection({ report }: { report: EnvironmentReport }) {
  return (
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
  )
}

export function EnvironmentInstallForm({
  packageName,
  pending,
  onPackageNameChange,
  onSubmit
}: {
  packageName: string
  pending: string | null
  onPackageNameChange: (value: string) => void
  onSubmit: () => void
}) {
  return (
    <section className="space-y-3 border-b pb-8">
      <h3 className="text-base font-semibold">Install by name</h3>
      <p className="text-muted-foreground text-sm">
        Type a PyPI package name. Catalog packages install normally; other
        packages need an extra confirmation.
      </p>
      <form
        className="flex flex-col gap-2 sm:flex-row"
        onSubmit={event => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <Input
          value={packageName}
          onChange={event => onPackageNameChange(event.target.value)}
          placeholder="e.g. torch, rdkit, gseapy"
          className="font-mono"
          disabled={pending !== null}
          autoComplete="off"
        />
        <Button
          type="submit"
          disabled={pending !== null || !packageName.trim()}
        >
          {pending && normalizeName(pending) === normalizeName(packageName)
            ? 'Installing…'
            : 'Install'}
        </Button>
      </form>
    </section>
  )
}

export function EnvironmentGroupsSection({
  report,
  groupOpen,
  pending,
  onToggleGroup,
  onInstall,
  onUninstall
}: {
  report: EnvironmentReport
  groupOpen: Record<string, boolean>
  pending: string | null
  onToggleGroup: (groupId: string) => void
  onInstall: (name: string) => void
  onUninstall: (name: string) => void
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Skill & tool packages</h3>
      <p className="text-muted-foreground text-sm">
        Install or remove packages that power chemistry, single-cell, ML, and
        other research tools. Large packages (e.g. torch) can take several
        minutes.
      </p>
      <div className="space-y-2">
        {report.groups.map(group => (
          <EnvironmentGroupCard
            key={group.id}
            group={group}
            open={Boolean(groupOpen[group.id])}
            pending={pending}
            onToggle={() => onToggleGroup(group.id)}
            onInstall={pkg => onInstall(pkg.name)}
            onUninstall={pkg => onUninstall(pkg.name)}
          />
        ))}
      </div>
    </section>
  )
}

export function EnvironmentCoreSection({
  core,
  coreOpen,
  onToggle
}: {
  core: EnvironmentReport['core']
  coreOpen: boolean
  onToggle: () => void
}) {
  return (
    <section className="space-y-2 border-t pt-6">
      <button
        type="button"
        className="hover:bg-muted/50 flex w-full items-center gap-2 rounded-md px-2 py-2 text-left"
        onClick={onToggle}
      >
        <Lock className="text-muted-foreground size-3.5 shrink-0" />
        <span className="flex-1 text-sm font-semibold">Core (locked)</span>
        <span className="text-muted-foreground text-xs">
          {core.length} packages
        </span>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-3.5 transition-transform',
            coreOpen && 'rotate-180'
          )}
        />
      </button>
      {coreOpen ? (
        <ScrollArea className="h-64 rounded-md border">
          <div className="space-y-0.5 p-2">
            {core.map(pkg => (
              <div
                key={pkg.name}
                className="text-muted-foreground flex items-center gap-3 px-2 py-1.5 text-sm"
              >
                <span className="min-w-0 flex-1 truncate font-mono text-xs">
                  {pkg.name}
                </span>
                <span className="shrink-0 font-mono text-xs">{pkg.version}</span>
              </div>
            ))}
          </div>
        </ScrollArea>
      ) : null}
    </section>
  )
}
