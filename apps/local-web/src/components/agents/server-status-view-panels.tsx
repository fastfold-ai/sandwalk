import type { ServerStatusReport } from '@sandwalk/agent-ui-core'
import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import {
  formatBytes,
  formatGpuLabel,
  formatUptime,
  MemoryBar,
  MetaRow,
  SectionLabel
} from './server-status-view-shared'

export function ServerStatusSystemSection({ report }: { report: ServerStatusReport }) {
  const gpuLabel = formatGpuLabel(
    report.system.chipName,
    report.system.gpuCores
  )

  return (
    <section>
      <SectionLabel subtitle={report.system.label}>System</SectionLabel>
      <div className="bg-background rounded-2xl border px-4">
        {gpuLabel ? (
          <MetaRow label="GPU">
            <span>{gpuLabel}</span>
          </MetaRow>
        ) : null}
        <MetaRow label="System RAM" stretch>
          <MemoryBar
            used={report.system.ramUsedBytes}
            total={report.system.ramTotalBytes}
          />
        </MetaRow>
        <MetaRow label="Load average" hint="1 · 5 · 15 minute averages">
          <span className="tabular-nums">
            {report.system.loadAverage?.length
              ? report.system.loadAverage.join(' · ')
              : '—'}
          </span>
        </MetaRow>
        <MetaRow label="Thermal state">
          {report.system.thermalState ? (
            <span className="inline-flex items-center justify-end gap-2">
              <span
                className={cn(
                  'size-2 rounded-full',
                  report.system.thermalState === 'Nominal'
                    ? 'bg-emerald-500'
                    : 'bg-amber-500'
                )}
              />
              <span className="text-foreground">
                {report.system.thermalState}
              </span>
            </span>
          ) : (
            '—'
          )}
        </MetaRow>
        <MetaRow label="Server uptime">
          <span className="tabular-nums">
            {formatUptime(report.uptimeSeconds)}
          </span>
        </MetaRow>
        <MetaRow label="Process">
          <span className="tabular-nums">
            pid {report.pid}
            {report.host && report.port != null
              ? ` · ${report.host}:${report.port}`
              : ''}
          </span>
        </MetaRow>
        <MetaRow label="Agent version">
          <span className="tabular-nums">
            {report.version} · Python {report.system.pythonVersion}
          </span>
        </MetaRow>
      </div>
    </section>
  )
}

export function ServerStatusCacheSection({
  report,
  clearing,
  onRequestClear
}: {
  report: ServerStatusReport
  clearing: boolean
  onRequestClear: () => void
}) {
  return (
    <section>
      <SectionLabel>Runtime cache</SectionLabel>
      <div className="bg-background rounded-2xl border px-4">
        <MetaRow label="Cache files">
          <span className="tabular-nums">
            {report.cache.fileCount}{' '}
            {report.cache.fileCount === 1 ? 'file' : 'files'}
          </span>
        </MetaRow>
        <MetaRow label="Total size">
          <span className="tabular-nums">
            {formatBytes(report.cache.totalBytes)}
          </span>
        </MetaRow>
        <MetaRow label="Location">
          <code className="block truncate font-mono text-xs">
            {report.cache.path}
          </code>
        </MetaRow>
        <div className="flex justify-end py-3.5">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={clearing}
            onClick={onRequestClear}
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            {clearing ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Clear cache
          </Button>
        </div>
      </div>
    </section>
  )
}
