import type { ServerStatusReport } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import { formatBytes } from '@/components/agents/server-status-view-shared'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { isLocalBackendUrl, normalizeBackendUrl } from '@/lib/backend-url'
import {
  readCachedRemoteHostname,
  remoteDockSuffix,
  resolveRemoteHostname
} from '@/lib/remote-hostname'
import { cn } from '@/lib/utils'

function hostPortLabel(backendUrl: string): string {
  try {
    const parsed = new URL(normalizeBackendUrl(backendUrl))
    return parsed.port
      ? `${parsed.hostname}:${parsed.port}`
      : parsed.hostname
  } catch {
    return backendUrl
  }
}

function formatLoad(load: number[] | null | undefined): string | null {
  if (!load?.length) return null
  return load
    .slice(0, 3)
    .map(n => (Number.isFinite(n) ? n.toFixed(2) : '—'))
    .join(' · ')
}

function DetailRow({
  label,
  value
}: {
  label: string
  value: string
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="min-w-0 text-right font-medium break-all tabular-nums">
        {value}
      </span>
    </div>
  )
}

/**
 * Bottom-right connection chip — Local / remote hostname, with hover details.
 */
export function ConnectionStatusLabel({
  backendUrl,
  loadServerStatus
}: {
  backendUrl: string
  loadServerStatus?: (signal?: AbortSignal) => Promise<ServerStatusReport>
}) {
  const [hostname, setHostname] = useState<string | null>(() =>
    readCachedRemoteHostname(backendUrl)
  )
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<ServerStatusReport | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isLocalBackendUrl(backendUrl)) {
      setHostname(null)
      return
    }
    let cancelled = false
    setHostname(readCachedRemoteHostname(backendUrl))
    void resolveRemoteHostname(backendUrl).then(name => {
      if (!cancelled && name) setHostname(name)
    })
    return () => {
      cancelled = true
    }
  }, [backendUrl])

  useEffect(() => {
    if (!open || !loadServerStatus) return
    const controller = new AbortController()
    setLoading(true)
    void loadServerStatus(controller.signal)
      .then(report => {
        if (!controller.signal.aborted) setStatus(report)
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus(null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [loadServerStatus, open])

  const local = isLocalBackendUrl(backendUrl)
  const label = local
    ? 'Local'
    : remoteDockSuffix(backendUrl, hostname) || 'Remote'
  const ip =
    status?.host && status.port != null
      ? `${status.host}:${status.port}`
      : hostPortLabel(backendUrl)
  const statusLabel = status?.status
    ? status.status === 'running'
      ? 'Running'
      : 'Degraded'
    : loading
      ? '…'
      : 'Connected'
  const chip =
    status?.system.chipName?.trim() ||
    status?.system.label?.trim() ||
    null
  const ram =
    status && status.system.ramTotalBytes > 0
      ? `${formatBytes(status.system.ramUsedBytes)} / ${formatBytes(status.system.ramTotalBytes)}`
      : null
  const load = formatLoad(status?.system.loadAverage)

  return (
    <div className="absolute bottom-1.5 right-2 z-10">
      <TooltipProvider delayDuration={200}>
        <Tooltip open={open} onOpenChange={setOpen}>
          <TooltipTrigger asChild>
            <button
              type="button"
              className={cn(
                'text-muted-foreground/55 hover:text-foreground hover:bg-muted/50 inline-flex max-w-[12rem] items-center rounded-md px-1.5 py-0.5 text-[11px] tracking-wide transition-colors',
                open && 'text-foreground bg-muted/50'
              )}
              aria-label={`Connection: ${label}`}
            >
              <span className="truncate">{label}</span>
            </button>
          </TooltipTrigger>
          <TooltipContent
            side="top"
            align="end"
            sideOffset={8}
            className="w-auto min-w-48 max-w-64 px-3 py-2"
          >
            <div className="grid gap-1.5 text-xs">
              <DetailRow label="Host" value={label} />
              <DetailRow label="IP" value={ip} />
              <DetailRow label="Status" value={statusLabel} />
              {chip ? <DetailRow label="CPU" value={chip} /> : null}
              {ram ? <DetailRow label="RAM" value={ram} /> : null}
              {load ? <DetailRow label="Load" value={load} /> : null}
              {status?.version ? (
                <DetailRow label="Sandwalk" value={status.version} />
              ) : null}
              {loading && !status ? (
                <div className="text-muted-foreground/80 text-[10px]">
                  Loading system info…
                </div>
              ) : null}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  )
}
