import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function ArtifactsBrowserPathFooter({
  workspacePath,
  relativePath
}: {
  workspacePath?: string | null
  relativePath?: string | null
}) {
  const [copied, setCopied] = useState(false)
  const root = String(workspacePath || '')
    .replace(/\\/g, '/')
    .replace(/\/$/, '')
  const rel = String(relativePath || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
  const absolute = root ? (rel ? `${root}/${rel}` : root) : rel || ''

  if (!absolute) return null

  return (
    <div className="border-border/60 bg-muted/20 flex shrink-0 items-center gap-1.5 border-t px-2 py-1.5">
      <span
        className="text-muted-foreground min-w-0 flex-1 truncate font-mono text-[10px]"
        title={absolute}
      >
        {absolute}
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-6 shrink-0"
        title="Copy absolute path"
        aria-label="Copy absolute path"
        onClick={() => {
          void navigator.clipboard.writeText(absolute).then(() => {
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1500)
          })
        }}
      >
        {copied ? (
          <Check className="size-3 text-emerald-500" />
        ) : (
          <Copy className={cn('size-3')} />
        )}
      </Button>
    </div>
  )
}
