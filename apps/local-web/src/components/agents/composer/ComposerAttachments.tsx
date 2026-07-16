import { FileText, Loader2, X } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

export type ComposerAttachmentItem = {
  id: string
  name: string
  contentType: string
  /** Local object URL for image thumbnails (revoked on remove). */
  previewUrl?: string
  path?: string
  status: 'uploading' | 'ready' | 'error'
  error?: string
}

function isImageAttachment(item: ComposerAttachmentItem) {
  return (
    item.contentType.startsWith('image/') ||
    Boolean(item.previewUrl?.startsWith('blob:') || item.previewUrl?.startsWith('data:image'))
  )
}

function AttachmentThumb({ item }: { item: ComposerAttachmentItem }) {
  const [loaded, setLoaded] = useState(false)
  const image = isImageAttachment(item)

  if (image && item.previewUrl) {
    return (
      <div className="bg-muted relative size-14 overflow-hidden rounded-xl">
        <img
          src={item.previewUrl}
          alt={item.name}
          className={cn(
            'size-full object-cover transition-opacity',
            loaded ? 'opacity-100' : 'opacity-0'
          )}
          onLoad={() => setLoaded(true)}
        />
      </div>
    )
  }

  return (
    <div className="bg-background flex size-14 items-center justify-center rounded-xl border">
      <FileText className="text-muted-foreground size-6" strokeWidth={1.5} />
    </div>
  )
}

export function ComposerAttachments({
  attachments,
  onRemove
}: {
  attachments: ComposerAttachmentItem[]
  onRemove: (id: string) => void
}) {
  if (attachments.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2 px-1 pb-2 pt-0.5">
      {attachments.map(item => (
        <div
          key={item.id}
          className="group relative"
          title={item.error || item.name}
        >
          <AttachmentThumb item={item} />
          {item.status === 'uploading' ? (
            <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/35">
              <Loader2 className="size-4 animate-spin text-white" />
            </div>
          ) : null}
          {item.status === 'error' ? (
            <div className="absolute inset-0 rounded-xl ring-2 ring-red-500/70" />
          ) : null}
          <button
            type="button"
            className="bg-foreground text-background absolute -top-1.5 -right-1.5 inline-flex size-5 items-center justify-center rounded-full shadow-sm opacity-100 transition-opacity"
            onClick={() => onRemove(item.id)}
            aria-label={`Remove ${item.name}`}
          >
            <X className="size-3" strokeWidth={2.5} />
          </button>
        </div>
      ))}
    </div>
  )
}
