import type { DoctorCheckResult } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

import { statusIcon } from './doctor-view-utils'

export function DoctorCheckGroups({
  grouped
}: {
  grouped: Array<[string, DoctorCheckResult[]]>
}) {
  return (
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
                      check.status === 'error' && 'text-red-600'
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
  )
}

export function DoctorSummaryCards({
  report
}: {
  report: { ok: boolean; summary: { ok: number; warn: number; error: number } }
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-4">
      {[
        {
          label: 'Status',
          value: report.ok ? 'Healthy' : 'Issues found',
          tone: report.ok ? 'ok' : 'error'
        },
        { label: 'OK', value: String(report.summary.ok), tone: 'ok' },
        {
          label: 'Warnings',
          value: String(report.summary.warn),
          tone: 'warn'
        },
        {
          label: 'Errors',
          value: String(report.summary.error),
          tone: 'error'
        }
      ].map(card => {
        const Icon = statusIcon(card.tone as DoctorCheckResult['status'])
        return (
          <div key={card.label} className="px-1 py-1">
            <Icon
              className={cn(
                'mb-2 size-4',
                card.tone === 'ok' && 'text-emerald-600',
                card.tone === 'warn' && 'text-amber-600',
                card.tone === 'error' && 'text-red-600'
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
  )
}
