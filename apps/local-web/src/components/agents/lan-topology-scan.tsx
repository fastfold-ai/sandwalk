import { OsPlatformIcon } from '@/components/agents/os-platform-icon'
import type { LanDesktopServer } from '@/lib/desktop'
import { cn } from '@/lib/utils'

export type LanTopologyNode = LanDesktopServer & {
  title: string
  detail: string
  hostLine: string
}

function nodePosition(index: number, total: number) {
  // Spread around the ring; keep a slight top bias so labels stay readable.
  const angle = (-90 + (360 * index) / Math.max(total, 1)) * (Math.PI / 180)
  // Keep nodes between the middle and outer rings.
  const radius = 34 + (index % 3) * 4
  return {
    left: `${50 + Math.cos(angle) * radius}%`,
    top: `${50 + Math.sin(angle) * radius}%`
  }
}

/** Concentric radar with discovered hosts as OS-icon dots + detail chips. */
export function LanTopologyScan({
  active,
  nodes,
  selectedUrl,
  onSelect,
  emptyLabel = 'No servers found on this network.'
}: {
  active: boolean
  nodes: LanTopologyNode[]
  selectedUrl?: string | null
  onSelect: (node: LanTopologyNode) => void
  emptyLabel?: string
}) {
  const label =
    active && nodes.length === 0
      ? 'Scanning local network…'
      : active
        ? `Found ${nodes.length} · still scanning…`
        : nodes.length === 0
          ? emptyLabel
          : `${nodes.length} nearby`

  return (
    <div
      className="border-border/60 bg-muted/15 relative overflow-hidden rounded-lg border px-3 py-4"
      aria-busy={active}
      aria-live="polite"
    >
      <div className="relative mx-auto aspect-square w-full max-w-[280px]">
        <div className="border-border/40 absolute inset-[6%] rounded-full border" />
        <div className="border-border/30 absolute inset-[22%] rounded-full border" />
        <div className="border-border/25 absolute inset-[38%] rounded-full border" />
        <div className="bg-foreground/70 absolute top-1/2 left-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full shadow-[0_0_0_4px_color-mix(in_oklab,var(--foreground)_12%,transparent)]" />
        <span className="text-muted-foreground absolute top-[calc(50%+10px)] left-1/2 -translate-x-1/2 text-[10px] tracking-wide uppercase">
          You
        </span>

        {active ? (
          <>
            <div
              className="pointer-events-none absolute inset-[6%] animate-[spin_2.8s_linear_infinite] rounded-full"
              style={{
                background:
                  'conic-gradient(from 0deg, transparent 0deg, transparent 255deg, color-mix(in oklab, var(--foreground) 40%, transparent) 310deg, transparent 360deg)'
              }}
            />
            <div className="border-foreground/15 pointer-events-none absolute inset-[10%] animate-ping rounded-full border opacity-30" />
          </>
        ) : null}

        {nodes.map((node, index) => {
          const pos = nodePosition(index, nodes.length)
          const selected = selectedUrl === node.url
          return (
            <button
              key={node.url}
              type="button"
              onClick={() => onSelect(node)}
              className={cn(
                'absolute z-10 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1',
                'focus-visible:ring-ring rounded-md outline-none focus-visible:ring-2'
              )}
              style={{ left: pos.left, top: pos.top }}
              title={`${node.title} — ${node.hostLine}`}
            >
              <span
                className={cn(
                  'relative rounded-full transition-transform',
                  selected && 'scale-110'
                )}
              >
                {active ? (
                  <span className="bg-foreground/20 absolute inset-[-4px] animate-ping rounded-full" />
                ) : null}
                <OsPlatformIcon
                  platform={node.platform}
                  className={cn(
                    'shadow-sm ring-1',
                    selected
                      ? 'ring-foreground/50 bg-background'
                      : 'ring-border bg-background/90'
                  )}
                />
              </span>
              <span
                className={cn(
                  'max-w-[7.5rem] rounded-md px-1.5 py-1 text-center shadow-sm backdrop-blur-sm',
                  'border bg-background/90',
                  selected ? 'border-foreground/35' : 'border-border/80'
                )}
              >
                <span className="block truncate text-[11px] leading-tight font-medium">
                  {node.title}
                </span>
                {node.detail ? (
                  <span className="text-muted-foreground mt-0.5 block truncate text-[10px] leading-tight">
                    {node.detail}
                  </span>
                ) : null}
                <span className="text-muted-foreground mt-0.5 block truncate text-[10px] leading-tight">
                  {node.hostname !== node.hostLine.split(':')[0]
                    ? `${node.hostname} · `
                    : ''}
                  {node.hostLine}
                  {node.authRequired ? ' · key' : ''}
                </span>
              </span>
            </button>
          )
        })}
      </div>

      <p
        className={cn(
          'text-muted-foreground mt-2 text-center text-xs',
          active && nodes.length === 0 && 'animate-pulse'
        )}
      >
        {label}
      </p>
    </div>
  )
}
