import { Check, Copy, Terminal } from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'

import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

export function CommandRow({
  command,
  copied,
  onCopy
}: {
  command: string
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="bg-muted/60 border-border flex items-center gap-2 rounded-lg border p-2.5">
      <Terminal className="text-muted-foreground size-4 shrink-0" />
      <code className="text-foreground min-w-0 flex-1 truncate font-mono text-[13px]">
        {command}
      </code>
      <button
        type="button"
        className="text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-7 shrink-0 items-center justify-center rounded-md transition-colors"
        onClick={onCopy}
        aria-label={`Copy ${command}`}
        title="Copy command"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  )
}

export function MacAppIcon({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'flex size-11 shrink-0 items-center justify-center rounded-[11px] bg-white p-2 shadow-[0_1px_2px_rgba(0,0,0,0.12)] ring-1 ring-black/5',
        className
      )}
      aria-hidden
    >
      <img src="/sandwalk-mark.svg" alt="" className="size-full" />
    </div>
  )
}

export function copyCommand(
  id: string,
  command: string,
  setCopiedId: Dispatch<SetStateAction<string | null>>
) {
  void copyText(command)
  setCopiedId(id)
  window.setTimeout(() => {
    setCopiedId(current => (current === id ? null : current))
  }, 2000)
}
