import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { DoctorCheckResult, DoctorReport } from '@sandwalk/agent-ui-core'
import {
  AlertTriangle,
  CheckCircle2,
  XCircle
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { cn } from '@/lib/utils'

function statusIcon(status: DoctorCheckResult['status']) {
  if (status === 'ok') return CheckCircle2
  if (status === 'warn') return AlertTriangle
  return XCircle
}

function statusClass(status: DoctorCheckResult['status']) {
  if (status === 'ok') return 'text-emerald-600 dark:text-emerald-400'
  if (status === 'warn') return 'text-amber-600 dark:text-amber-400'
  return 'text-destructive'
}

const CORE_CHECKS = [
  'config_file',
  'llm',
  'python_runtime',
  'sandbox_backend'
] as const

const CHECK_LABELS: Record<string, string> = {
  config_file: 'Config',
  llm: 'Configured LLM',
  python_runtime: 'Python runtime',
  sandbox_backend: 'Sandbox'
}

function coreChecks(report: DoctorReport | null): DoctorCheckResult[] {
  if (!report) return []
  const byName = new Map(report.checks.map(check => [check.name, check]))
  const ordered = CORE_CHECKS.map(name => byName.get(name)).filter(
    (check): check is DoctorCheckResult => Boolean(check)
  )
  // Fallback if an older server ignored ?scope=core and used different names.
  if (ordered.length > 0) return ordered
  return report.checks.filter(check =>
    (CORE_CHECKS as readonly string[]).includes(check.name)
  )
}

export function OnboardingDoneStep({
  client,
  onLoadingChange
}: {
  client: LocalAgentClient
  onLoadingChange?: (loading: boolean) => void
}) {
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState<DoctorReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [auraTick, setAuraTick] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    onLoadingChange?.(true)
    setError(null)
    void client
      .runDoctor({ scope: 'core' })
      .then(next => {
        if (!cancelled) setReport(next)
      })
      .catch(err => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
          onLoadingChange?.(false)
        }
      })
    return () => {
      cancelled = true
      onLoadingChange?.(false)
    }
  }, [client, onLoadingChange])

  useEffect(() => {
    if (!loading) return
    setAuraTick(tick => tick + 1)
    const timer = window.setInterval(() => {
      setAuraTick(tick => tick + 1)
    }, 900)
    return () => window.clearInterval(timer)
  }, [loading])

  const checks = useMemo(() => coreChecks(report), [report])
  const complete = !loading && !error && report !== null
  const coreOk =
    checks.length > 0 && checks.every(check => check.status !== 'error')

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 text-center">
        <AuraIconPulse
          animateTick={auraTick}
          className="text-foreground h-12 w-12"
        />
        <p className="text-muted-foreground max-w-xs text-sm">
          Checking core services and configured LLM…
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-md space-y-5">
      {complete ? (
        <div className="flex flex-col items-center gap-2 pb-1 text-center">
          <span
            className="onboarding-tada text-5xl leading-none"
            role="img"
            aria-label="Ta-da"
          >
            🎉
          </span>
          <p className="text-base font-medium tracking-tight">
            You&apos;re ready
          </p>
          {coreOk ? (
            <p className="text-muted-foreground max-w-sm text-sm">
              All checks passed
            </p>
          ) : (
            <p className="text-muted-foreground max-w-sm text-sm">
              Setup finished with some issues — you can still chat, or fix them
              in Dashboard → Doctor.
            </p>
          )}
        </div>
      ) : null}

      {error ? (
        <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
          {error}
        </div>
      ) : null}

      {checks.length > 0 ? (
        <ul className="space-y-2">
          {checks.map(check => {
            const Icon = statusIcon(check.status)
            return (
              <li
                key={check.name}
                className="flex items-start gap-2.5 rounded-md px-3 py-2"
              >
                <Icon
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    statusClass(check.status)
                  )}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {CHECK_LABELS[check.name] || check.name}
                  </p>
                  <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
                    {check.detail}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
