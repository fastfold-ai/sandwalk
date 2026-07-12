import type { DoctorCheckResult, DoctorReport } from '@fastfold/agent-ui-core'
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
  RefreshCw,
  XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

const CATEGORY_ORDER = [
  'runtime',
  'tooling',
  'llm',
  'environment',
  'skills',
  'tools',
  'paths',
  'data',
  'network',
  'config',
  'policy',
  'mcp',
  'general',
]

const SCAN_PHASES = [
  'Checking runtime & tooling…',
  'Validating LLM and API keys…',
  'Scanning skills and tools…',
  'Probing MCP servers…',
  'Finishing diagnostics…',
]

function statusIcon(status: DoctorCheckResult['status']) {
  if (status === 'ok') return CheckCircle2
  if (status === 'warn') return AlertTriangle
  return XCircle
}

function collectUiDiagnostics(report: DoctorReport | null) {
  return {
    generatedAt: new Date().toISOString(),
    href: window.location.href,
    userAgent: navigator.userAgent,
    language: navigator.language,
    online: navigator.onLine,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      devicePixelRatio: window.devicePixelRatio,
    },
    localStorageKeys: Object.keys(window.localStorage || {}),
    doctorSummary: report?.summary ?? null,
    doctorOk: report?.ok ?? null,
  }
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function DoctorScanProgress({ active }: { active: boolean }) {
  const [progress, setProgress] = useState(8)
  const [phaseIndex, setPhaseIndex] = useState(0)

  useEffect(() => {
    if (!active) {
      setProgress(100)
      return
    }
    setProgress(8)
    setPhaseIndex(0)
    const progressTimer = window.setInterval(() => {
      setProgress(prev => {
        if (prev >= 92) return prev
        const step = prev < 40 ? 6 : prev < 70 ? 3 : 1.5
        return Math.min(92, prev + step)
      })
    }, 400)
    const phaseTimer = window.setInterval(() => {
      setPhaseIndex(prev => (prev + 1) % SCAN_PHASES.length)
    }, 1800)
    return () => {
      window.clearInterval(progressTimer)
      window.clearInterval(phaseTimer)
    }
  }, [active])

  return (
    <div
      className="border-border/60 bg-muted/20 rounded-lg border px-4 py-5"
      aria-busy={active}
      aria-live="polite"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {active ? 'Doctor scan running' : 'Doctor scan complete'}
          </p>
          <p className="text-muted-foreground mt-1 text-sm">
            {active ? SCAN_PHASES[phaseIndex] : 'Results are ready below.'}
          </p>
        </div>
        <span className="text-muted-foreground shrink-0 text-xs tabular-nums">
          {Math.round(progress)}%
        </span>
      </div>
      <div className="bg-muted mt-4 h-2 overflow-hidden rounded-full">
        <div
          className={cn(
            'bg-foreground/80 h-full rounded-full transition-[width] duration-300 ease-out',
            active && 'animate-pulse',
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

export function DoctorView({
  onRun,
  onDownloadDiagnostics,
}: {
  onRun: (signal?: AbortSignal) => Promise<DoctorReport>
  onDownloadDiagnostics: (
    uiDiagnostics: Record<string, unknown>,
    signal?: AbortSignal,
  ) => Promise<{ blob: Blob; filename: string }>
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
          err instanceof Error ? err.message : 'Unable to run doctor checks.',
        )
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [onRun],
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
          : 'Unable to download diagnostics bundle.',
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

  const grouped = useMemo(() => {
    const checks = report?.checks || []
    const map = new Map<string, DoctorCheckResult[]>()
    for (const check of checks) {
      const key = check.category || 'general'
      const list = map.get(key) || []
      list.push(check)
      map.set(key, list)
    }
    return [...map.entries()].sort((a, b) => {
      const ai = CATEGORY_ORDER.indexOf(a[0])
      const bi = CATEGORY_ORDER.indexOf(b[0])
      const av = ai === -1 ? CATEGORY_ORDER.length : ai
      const bv = bi === -1 ? CATEGORY_ORDER.length : bi
      if (av !== bv) return av - bv
      return a[0].localeCompare(b[0])
    })
  }, [report])

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 md:p-8">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Doctor</h1>
            <p className="text-muted-foreground mt-1 max-w-2xl text-sm">
              Same checks as <code className="text-xs">fastfold doctor</code> and
              interactive <code className="text-xs">/doctor</code>: runtime
              tooling, skills inventory, environment keys, LLM config, and more.
            </p>
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
          <div className="grid gap-3 sm:grid-cols-4">
            {[
              {
                label: 'Status',
                value: report.ok ? 'Healthy' : 'Issues found',
                tone: report.ok ? 'ok' : 'error',
              },
              { label: 'OK', value: String(report.summary.ok), tone: 'ok' },
              {
                label: 'Warnings',
                value: String(report.summary.warn),
                tone: 'warn',
              },
              {
                label: 'Errors',
                value: String(report.summary.error),
                tone: 'error',
              },
            ].map(card => {
              const Icon = statusIcon(card.tone as DoctorCheckResult['status'])
              return (
                <div key={card.label} className="px-1 py-1">
                  <Icon
                    className={cn(
                      'mb-2 size-4',
                      card.tone === 'ok' && 'text-emerald-600',
                      card.tone === 'warn' && 'text-amber-600',
                      card.tone === 'error' && 'text-red-600',
                    )}
                  />
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    {card.label}
                  </p>
                  <p className="mt-1 text-lg font-semibold">{card.value}</p>
                </div>
              )
            })}
          </div>
        ) : null}

        {!loading && report ? (
          <p className="text-muted-foreground text-xs">
            Checked at {new Date(report.checkedAt).toLocaleString()} ·{' '}
            {report.summary.total} checks
          </p>
        ) : null}

        <section className="border-t pt-5">
          <h2 className="text-sm font-semibold">Diagnostics</h2>
          <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 max-w-xl">
              <p className="text-sm font-medium">Download logs</p>
              <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                Bundles system logs for sharing with support. File paths and host
                names are redacted. Conversations and credentials aren&apos;t
                included. Review the bundle before sharing.
              </p>
              {exportMessage ? (
                <p className="text-muted-foreground mt-2 text-xs">
                  {exportMessage}
                </p>
              ) : null}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={exporting || loading}
              onClick={() => void downloadLogs()}
            >
              {exporting ? (
                <Loader2 className="mr-1.5 size-3.5 animate-spin" />
              ) : (
                <Download className="mr-1.5 size-3.5" />
              )}
              {exporting ? 'Preparing…' : 'Download logs'}
            </Button>
          </div>
        </section>

        {!loading && report ? (
          <div className="space-y-5">
            {grouped.map(([category, checks]) => (
              <section key={category} className="space-y-2">
                <h2 className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">
                  {category}
                </h2>
                <div className="divide-y overflow-hidden">
                  {checks.map(check => {
                    const Icon = statusIcon(check.status)
                    return (
                      <div
                        key={`${category}:${check.name}`}
                        className="flex items-start gap-3 px-4 py-3"
                      >
                        <Icon
                          className={cn(
                            'mt-0.5 size-4 shrink-0',
                            check.status === 'ok' && 'text-emerald-600',
                            check.status === 'warn' && 'text-amber-600',
                            check.status === 'error' && 'text-red-600',
                          )}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">{check.name}</p>
                          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                            {check.detail}
                          </p>
                          {check.fix ? (
                            <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                              Fix: {check.fix}
                            </p>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
