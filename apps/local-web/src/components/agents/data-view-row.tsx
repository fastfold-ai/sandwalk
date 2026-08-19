import type {
  DatasetInstallResult,
  DatasetSummary
} from '@sandwalk/agent-ui-core'
import { Download, Loader, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'

export function DataViewRow({
  dataset,
  busy,
  canInstall,
  canRemove,
  installing,
  removing,
  onInstall,
  onRemove
}: {
  dataset: DatasetSummary
  busy: boolean
  canInstall: boolean
  canRemove: boolean
  installing: boolean
  removing: boolean
  onInstall: () => void
  onRemove: () => void
}) {
  return (
    <div className="flex gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-medium">{dataset.id}</span>
          {dataset.autoDownload ? (
            <span className="text-muted-foreground text-xs">auto-download</span>
          ) : (
            <span className="text-muted-foreground text-xs">manual</span>
          )}
        </div>
        <p className="text-muted-foreground mt-1 text-sm">{dataset.description}</p>
        <div className="text-muted-foreground mt-1 text-xs">
          <span className="font-mono">{dataset.path}</span>
        </div>
        {dataset.note ? (
          <p className="text-muted-foreground mt-1 text-xs italic">
            {dataset.note}
          </p>
        ) : null}
        {!dataset.autoDownload && dataset.source ? (
          <a
            href={dataset.source}
            target="_blank"
            rel="noreferrer"
            className="text-foreground mt-1 inline-block text-xs underline underline-offset-2"
          >
            Download source
          </a>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        {canInstall ? (
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={onInstall}
          >
            {installing ? (
              <Loader className="animate-spin" />
            ) : (
              <Download className="size-3.5" />
            )}
            {dataset.status === 'partial' ? 'Resume' : 'Install'}
          </Button>
        ) : null}
        {canRemove ? (
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-destructive size-8"
            disabled={busy}
            onClick={onRemove}
            aria-label={`Remove ${dataset.id}`}
            title="Remove"
          >
            {removing ? (
              <Loader className="size-3.5 animate-spin" />
            ) : (
              <Trash2 className="size-3.5" />
            )}
          </Button>
        ) : null}
        <div className="text-muted-foreground text-right text-xs">
          {dataset.filesExpected > 0 ? (
            <div>
              Files: {dataset.filesFound}/{dataset.filesExpected}
            </div>
          ) : null}
          <div>Size: {dataset.sizeDisplay}</div>
        </div>
      </div>
    </div>
  )
}

export function canInstallDataset(dataset: DatasetSummary) {
  return dataset.autoDownload && dataset.status !== 'complete'
}

export function canRemoveDataset(
  dataset: DatasetSummary,
  onRemoveDataset?: (
    datasetId: string,
    signal?: AbortSignal
  ) => Promise<DatasetInstallResult>
) {
  return (
    Boolean(onRemoveDataset) &&
    (dataset.status === 'complete' || dataset.status === 'partial')
  )
}
