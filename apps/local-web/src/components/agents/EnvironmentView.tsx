import type {
  EnvironmentPackageMutationResult,
  EnvironmentReport
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { SettingsBlockSkeleton } from '@/components/agents/PageSkeletons'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

import {
  EnvironmentConfirmDialog,
  useEnvironmentViewActions
} from './environment-view/environment-view-actions'
import {
  EnvironmentCoreSection,
  EnvironmentGroupsSection,
  EnvironmentInstallForm,
  EnvironmentPythonSection
} from './environment-view/environment-view-body'
import {
  type EnvironmentConfirmState,
  normalizeName} from './environment-view/environment-view-shared'

export function EnvironmentView({
  onLoad,
  onInstall,
  onUninstall,
  title = 'Environment',
  description = 'Manage optional Python packages used by skills and tools. Core FastFold dependencies stay locked. Installs apply immediately — you usually do not need to restart the agent server.',
  onBack,
  backLabel = 'Sandbox'
}: {
  onLoad: (signal?: AbortSignal) => Promise<EnvironmentReport>
  onInstall: (
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal }
  ) => Promise<EnvironmentPackageMutationResult>
  onUninstall: (
    name: string,
    signal?: AbortSignal
  ) => Promise<EnvironmentPackageMutationResult>
  title?: string
  description?: string
  onBack?: () => void
  backLabel?: string
}) {
  const [report, setReport] = useState<EnvironmentReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({})
  const [coreOpen, setCoreOpen] = useState(false)
  const [packageName, setPackageName] = useState('')
  const [confirm, setConfirm] = useState<EnvironmentConfirmState | null>(null)

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
    [onLoad]
  )

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const { requestInstall, requestUninstall, runConfirmed } =
    useEnvironmentViewActions({
      onLoad: load,
      onInstall,
      onUninstall,
      catalogNames,
      setConfirm,
      setPending,
      setPackageName,
      setError
    })

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 p-4 md:p-6">
        {onBack ? (
          <div className="flex items-center gap-2 text-sm">
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
              {backLabel}
            </button>
          </div>
        ) : null}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold">{title}</h2>
            <p className="text-muted-foreground mt-2 text-sm">{description}</p>
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
            <EnvironmentPythonSection report={report} />
            <EnvironmentInstallForm
              packageName={packageName}
              pending={pending}
              onPackageNameChange={setPackageName}
              onSubmit={() =>
                requestInstall(packageName, { fromCatalog: false })
              }
            />
            <EnvironmentGroupsSection
              report={report}
              groupOpen={groupOpen}
              pending={pending}
              onToggleGroup={groupId =>
                setGroupOpen(current => ({
                  ...current,
                  [groupId]: !current[groupId]
                }))
              }
              onInstall={name => requestInstall(name, { fromCatalog: true })}
              onUninstall={requestUninstall}
            />
            <EnvironmentCoreSection
              core={report.core}
              coreOpen={coreOpen}
              onToggle={() => setCoreOpen(open => !open)}
            />
          </>
        ) : null}
      </div>

      <EnvironmentConfirmDialog
        confirm={confirm}
        pending={pending}
        onConfirmChange={open => {
          if (!open) setConfirm(null)
        }}
        onRunConfirmed={() => runConfirmed(confirm)}
      />
    </ScrollArea>
  )
}
