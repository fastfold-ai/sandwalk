import { Folder, FolderPlus, X } from 'lucide-react'
import { useState } from 'react'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { isTauri, pickDirectory } from '@/lib/desktop'
import { cn } from '@/lib/utils'

function folderName(path: string) {
  const trimmed = path.replace(/[/\\]+$/, '')
  const parts = trimmed.split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] || trimmed || path
}

export function ProjectFolderField({
  value,
  onChange,
  disabled
}: {
  value: string
  onChange: (next: string) => void
  disabled?: boolean
}) {
  const desktop = isTauri()
  const [draftPath, setDraftPath] = useState('')
  const [adding, setAdding] = useState(false)

  const choose = async () => {
    if (disabled) return
    if (desktop) {
      const picked = await pickDirectory()
      if (picked) onChange(picked)
      return
    }
    setAdding(true)
  }

  const commitDraft = () => {
    const next = draftPath.trim()
    if (!next) return
    onChange(next)
    setDraftPath('')
    setAdding(false)
  }

  return (
    <div className="space-y-2">
      <div className="text-muted-foreground text-sm">Project folder</div>
      <div className="border-border overflow-hidden rounded-xl border">
        {value ? (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2.5 px-3 py-2.5">
                  <Folder className="text-muted-foreground size-4 shrink-0" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {folderName(value)}
                  </span>
                  <button
                    type="button"
                    disabled={disabled}
                    aria-label="Remove folder"
                    className="text-muted-foreground hover:text-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-md disabled:opacity-50"
                    onClick={() => onChange('')}
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-sm font-mono text-xs">
                {value}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}

        {adding && !desktop ? (
          <div
            className={cn(
              'flex items-center gap-2 px-3 py-2.5',
              value && 'border-border border-t'
            )}
          >
            <input
              value={draftPath}
              onChange={event => setDraftPath(event.target.value)}
              disabled={disabled}
              autoFocus
              placeholder="/path/to/folder"
              spellCheck={false}
              className="placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent font-mono text-xs outline-none"
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  commitDraft()
                }
                if (event.key === 'Escape') {
                  setAdding(false)
                  setDraftPath('')
                }
              }}
              onBlur={() => {
                if (draftPath.trim()) commitDraft()
                else {
                  setAdding(false)
                  setDraftPath('')
                }
              }}
            />
          </div>
        ) : null}

        {!value && !adding ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => void choose()}
            className="hover:bg-muted/30 flex w-full flex-col items-center justify-center gap-2 px-4 py-8 text-center disabled:opacity-50"
          >
            <FolderPlus className="text-muted-foreground size-5" />
            <span className="text-muted-foreground text-sm">
              Add a folder Sandwalk can read and edit
            </span>
          </button>
        ) : null}
      </div>
    </div>
  )
}
