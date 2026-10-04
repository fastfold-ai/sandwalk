import { cn } from '@/lib/utils'

/** Shared pane marks. The filled half is the side the new pane lands on. */
function PaneIcon({
  className,
  panes
}: {
  className?: string
  panes: { x: number; y: number; w: number; h: number; filled?: boolean }[]
}) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden
      className={cn('size-3.5 text-muted-foreground', className)}
    >
      {panes.map(pane => (
        <rect
          key={`${pane.x}-${pane.y}`}
          x={pane.x}
          y={pane.y}
          width={pane.w}
          height={pane.h}
          rx="1"
          fill={pane.filled ? 'currentColor' : 'none'}
          fillOpacity={pane.filled ? 0.18 : undefined}
          stroke="currentColor"
          strokeWidth="1.3"
        />
      ))}
    </svg>
  )
}

export function SplitRightIcon({ className }: { className?: string }) {
  return (
    <PaneIcon
      className={className}
      panes={[
        { x: 1.75, y: 2.25, w: 5.25, h: 11.5 },
        { x: 9, y: 2.25, w: 5.25, h: 11.5, filled: true }
      ]}
    />
  )
}

export function SplitDownIcon({ className }: { className?: string }) {
  return (
    <PaneIcon
      className={className}
      panes={[
        { x: 2.25, y: 1.75, w: 11.5, h: 5.25 },
        { x: 2.25, y: 9, w: 11.5, h: 5.25, filled: true }
      ]}
    />
  )
}
