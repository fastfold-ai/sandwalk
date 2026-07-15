import { Download, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'

export function DoctorDiagnosticsSection({
  loading,
  exporting,
  exportMessage,
  onDownloadLogs
}: {
  loading: boolean
  exporting: boolean
  exportMessage: string | null
  onDownloadLogs: () => void
}) {
  return (
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
            <p className="text-muted-foreground mt-2 text-xs">{exportMessage}</p>
          ) : null}
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={exporting || loading}
          onClick={onDownloadLogs}
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
  )
}
