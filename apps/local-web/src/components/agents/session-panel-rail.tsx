import { File, Globe2, SquareTerminal } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/**
 * Right-edge panel switcher. Lives inside the chat column, so it never
 * slides under the files panel the way the old floating header buttons did.
 * Each icon toggles its own panel, so there is no separate close or plus.
 */
export function SessionPanelRail({
  filesOpen,
  previewOpen,
  onToggleFiles,
  onTogglePreview,
  onOpenTerminal
}: {
  filesOpen: boolean
  previewOpen: boolean
  onToggleFiles: () => void
  onTogglePreview: () => void
  onOpenTerminal?: () => void
}) {
  return (
    <div className="sandwalk-glass-menu pointer-events-auto absolute right-2 top-2 z-20 flex flex-col items-center gap-px rounded-lg border border-border/70 bg-background/80 p-0.5 shadow-sm">
      <RailButton
        label={previewOpen ? 'Hide browser' : 'Browser'}
        pressed={previewOpen}
        onClick={onTogglePreview}
      >
        <Globe2 className="size-3.5" />
      </RailButton>
      {onOpenTerminal ? (
        <RailButton label="Split with terminal" onClick={onOpenTerminal}>
          <SquareTerminal className="size-3.5" />
        </RailButton>
      ) : null}
      <RailButton
        label={filesOpen ? 'Hide files' : 'Files'}
        pressed={filesOpen}
        onClick={onToggleFiles}
      >
        <File className="size-3.5" />
      </RailButton>
    </div>
  )
}

function RailButton({
  label,
  pressed,
  onClick,
  children
}: {
  label: string
  pressed?: boolean
  onClick?: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={cn(
        'text-muted-foreground hover:bg-muted hover:text-foreground inline-flex size-6 items-center justify-center rounded-md',
        pressed && 'bg-muted text-foreground'
      )}
      onClick={onClick}
    >
      {children}
    </button>
  )
}
