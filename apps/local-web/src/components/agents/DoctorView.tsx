import type { DoctorReport } from '@sandwalk/agent-ui-core'
import { Loader2, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import { DoctorScanProgress } from './doctor-scan-progress'
import {
  DoctorCheckGroups,
  DoctorSummaryCards
} from './doctor-view-checks'
import { DoctorDiagnosticsSection } from './doctor-view-diagnostics'
import {
  collectUiDiagnostics,
  groupDoctorChecks,
  triggerBlobDownload
} from './doctor-view-utils'

export function DoctorView({
  onRun,
  onDownloadDiagnostics,
  embedded = false
}: {
  onRun: (signal?: AbortSignal) => Promise<DoctorReport>
  onDownloadDiagnostics: (
    uiDiagnostics: Record<string, unknown>,
    signal?: AbortSignal
  ) => Promise<{ blob: Blob; filename: string }>
  embedded?: boolean
}) {
  const [report, setReport] = useState<DoctorReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exportMessage, setExportMessage] = useState<string | null>(null)

  const runDoctor = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      setError(null)
      try {
        const next = await onRun(signal)
        if (!signal?.aborted) setReport(next)
      } catch (err) {
        if (signal?.aborted) return
        setError(
          err instanceof Error ? err.message : 'Unable to run doctor checks.'
        )
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onRun]
  )

  const downloadLogs = useCallback(async () => {
    setExporting(true)
    setExportMessage(null)
    setError(null)
    try {
      const result = await onDownloadDiagnostics(collectUiDiagnostics(report))
      triggerBlobDownload(result.blob, result.filename)
      setExportMessage(`Downloaded ${result.filename}`)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to download diagnostics bundle.'
      )
    } finally {
      setExporting(false)
    }
  }, [onDownloadDiagnostics, report])

  useEffect(() => {
    const controller = new AbortController()
    void runDoctor(controller.signal)
    return () => controller.abort()
  }, [runDoctor])

  const grouped = useMemo(() => groupDoctorChecks(report), [report])

  return (
    <ScrollArea className={embedded ? 'h-[min(28rem,55vh)]' : 'flex-1'}>
      <div
        className={
          embedded
            ? 'mx-auto flex w-full max-w-7xl flex-col gap-6 px-1 py-2'
            : 'mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8'
        }
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            {!embedded ? (
              <>
                <h1 className="text-2xl font-semibold tracking-tight">Doctor</h1>
                <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
                  Same checks as <code className="text-xs">sandwalk doctor</code>{' '}
                  and interactive <code className="text-xs">/doctor</code>: runtime
                  tooling, skills inventory, environment keys, LLM config, and more.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                Run the same checks as <code className="text-xs">sandwalk doctor</code>.
              </p>
            )}
          </div>
          <Button
            type="button"
            size="sm"
            disabled={loading}
            onClick={() => void runDoctor()}
          >
            {loading ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-1.5 size-3.5" />
            )}
            {loading ? 'Running…' : 'Run doctor'}
          </Button>
        </div>

        {error ? (
          <div
            role="alert"
            className="border-destructive/30 bg-destructive/5 text-destructive rounded-lg border px-3 py-2 text-sm"
          >
            {error}
          </div>
        ) : null}

        {loading ? <DoctorScanProgress active /> : null}

        {!loading && report ? (
          <>
            <DoctorSummaryCards report={report} />
            <p className="text-muted-foreground text-xs">
              Checked at {new Date(report.checkedAt).toLocaleString()} ·{' '}
              {report.summary.total} checks
            </p>
          </>
        ) : null}

        <DoctorDiagnosticsSection
          loading={loading}
          exporting={exporting}
          exportMessage={exportMessage}
          onDownloadLogs={() => void downloadLogs()}
        />

        {!loading && report ? <DoctorCheckGroups grouped={grouped} /> : null}
      </div>
    </ScrollArea>
  )
}
