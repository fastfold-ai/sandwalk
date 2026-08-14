import type {
  AgentSkillDepsInstallResult,
  AgentSkillDepsStatus
} from '@sandwalk/agent-ui-core'
import { CheckCircle2, Download, Loader, RotateCcw, Stethoscope } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type SkillDepsHandlers = {
  getDeps: (
    name: string,
    signal?: AbortSignal
  ) => Promise<AgentSkillDepsStatus>
  doctorDeps: (
    name: string,
    signal?: AbortSignal
  ) => Promise<AgentSkillDepsStatus>
  installDeps: (
    name: string,
    options?: { force?: boolean },
    signal?: AbortSignal
  ) => Promise<AgentSkillDepsInstallResult>
}

function statusTone(status: string) {
  if (status === 'ok') return 'text-emerald-700 dark:text-emerald-300'
  if (status === 'error') return 'text-red-700 dark:text-red-300'
  return 'text-amber-700 dark:text-amber-300'
}

function statusLabel(status: string) {
  if (status === 'ok') return 'Healthy'
  if (status === 'error') return 'Error'
  return 'Needs install'
}

export function SkillsDetailDepsPanel({
  skillName,
  handlers
}: {
  skillName: string
  handlers: SkillDepsHandlers
}) {
  const [status, setStatus] = useState<AgentSkillDepsStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'install' | 'reinstall' | 'doctor' | null>(
    null
  )
  const [unavailable, setUnavailable] = useState(false)

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      try {
        const next = await handlers.getDeps(skillName, signal)
        if (signal?.aborted) return
        setStatus(next)
        setUnavailable(false)
      } catch {
        if (signal?.aborted) return
        setUnavailable(true)
        setStatus(null)
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [handlers, skillName]
  )

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  if (unavailable) return null

  const runInstall = async (force: boolean) => {
    setBusy(force ? 'reinstall' : 'install')
    try {
      const result = await handlers.installDeps(skillName, { force })
      if (result.status) setStatus(result.status)
      else await refresh()
      toast.success(result.summary || (force ? 'Reinstalled' : 'Installed'), {
        description: skillName
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err), {
        description: skillName
      })
      await refresh()
    } finally {
      setBusy(null)
    }
  }

  const runDoctor = async () => {
    setBusy('doctor')
    try {
      const next = await handlers.doctorDeps(skillName)
      setStatus(next)
      toast.success(next.summary || 'Health check complete', {
        description: skillName
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err), {
        description: skillName
      })
    } finally {
      setBusy(null)
    }
  }

  const healthy = status?.status === 'ok'

  return (
    <div className="mb-5 space-y-3 rounded-lg border border-border/70 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium">Runtime dependencies</p>
          <p className="text-muted-foreground text-xs">
            Extra libraries this skill needs beyond SKILL.md install.
          </p>
        </div>
        {loading && !status ? (
          <span className="text-muted-foreground inline-flex items-center gap-1 text-xs">
            <Loader className="size-3.5 animate-spin" />
            Checking…
          </span>
        ) : status ? (
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs font-medium',
              statusTone(status.status)
            )}
          >
            {healthy ? (
              <CheckCircle2 className="size-3.5" />
            ) : (
              <Stethoscope className="size-3.5" />
            )}
            {statusLabel(status.status)}
          </span>
        ) : null}
      </div>

      {status?.summary ? (
        <p className="text-muted-foreground text-xs">{status.summary}</p>
      ) : null}

      {status?.setupSteps?.length ? (
        <ol className="space-y-2">
          {status.setupSteps.map((step, index) => (
            <li key={step.title} className="text-xs">
              <span className="text-foreground/90 font-medium">
                {index + 1}. {step.title}
              </span>
              <p className="text-muted-foreground mt-0.5 whitespace-pre-wrap">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      ) : null}

      {status?.checks?.length ? (
        <ul className="space-y-1 border-t border-border/50 pt-2">
          {status.checks.map(check => (
            <li
              key={check.name}
              className="flex items-start gap-2 text-xs"
            >
              <span
                className={cn(
                  'mt-0.5 shrink-0 font-medium uppercase',
                  statusTone(check.status)
                )}
              >
                {check.status}
              </span>
              <span className="text-muted-foreground min-w-0">
                <span className="text-foreground/80 font-medium">
                  {check.name}
                </span>
                {' — '}
                {check.detail}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {!healthy ? (
          <Button
            type="button"
            size="sm"
            className="h-7 gap-1.5 text-xs"
            disabled={busy != null || loading}
            onClick={() => void runInstall(false)}
          >
            {busy === 'install' ? (
              <Loader className="size-3.5 animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            Install dependencies
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 gap-1.5 text-xs"
            disabled={busy != null || loading}
            onClick={() => void runInstall(true)}
          >
            {busy === 'reinstall' ? (
              <Loader className="size-3.5 animate-spin" />
            ) : (
              <RotateCcw className="size-3.5" />
            )}
            Reinstall
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 gap-1.5 text-xs"
          disabled={busy != null || loading}
          onClick={() => void runDoctor()}
        >
          {busy === 'doctor' ? (
            <Loader className="size-3.5 animate-spin" />
          ) : (
            <Stethoscope className="size-3.5" />
          )}
          Run health check
        </Button>
      </div>

      {status?.command ? (
        <p className="text-muted-foreground font-mono text-[11px] break-all">
          Preferred command: {status.command}
        </p>
      ) : null}
    </div>
  )
}
